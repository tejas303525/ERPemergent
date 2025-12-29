import React, { useState, useEffect } from 'react';
import { rfqAPI, procurementReqAPI, purchaseOrderAPI, inventoryItemAPI } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { FileText, Plus, Send, Check, X, Package, Truck, ShoppingCart, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

const ProcurementPage = () => {
  const [activeTab, setActiveTab] = useState('rfq');
  const [rfqs, setRfqs] = useState([]);
  const [procurementReqs, setProcurementReqs] = useState([]);
  const [inventoryItems, setInventoryItems] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreateRFQ, setShowCreateRFQ] = useState(false);
  const [selectedRfq, setSelectedRfq] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [rfqRes, prRes, itemsRes] = await Promise.all([
        rfqAPI.getAll(),
        procurementReqAPI.getAll('DRAFT'),
        inventoryItemAPI.getAll()
      ]);
      setRfqs(rfqRes.data);
      setProcurementReqs(prRes.data);
      setInventoryItems(itemsRes.data);

      // Load suppliers
      const suppRes = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/suppliers`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('erp_token')}` }
      });
      if (suppRes.ok) {
        setSuppliers(await suppRes.json());
      }
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleSendRfq = async (rfqId) => {
    try {
      await rfqAPI.send(rfqId);
      toast.success('RFQ sent to supplier');
      loadData();
    } catch (error) {
      toast.error('Failed to send RFQ');
    }
  };

  const handleConvertToPO = async (rfqId) => {
    try {
      const res = await rfqAPI.convertToPO(rfqId);
      toast.success(res.data.message);
      loadData();
    } catch (error) {
      toast.error('Failed to convert to PO: ' + (error.response?.data?.detail || error.message));
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      DRAFT: 'bg-gray-500/20 text-gray-400',
      SENT: 'bg-blue-500/20 text-blue-400',
      QUOTED: 'bg-green-500/20 text-green-400',
      CONVERTED: 'bg-emerald-500/20 text-emerald-400',
      CANCELLED: 'bg-red-500/20 text-red-400'
    };
    return colors[status] || colors.DRAFT;
  };

  return (
    <div className="p-6 max-w-[1600px] mx-auto" data-testid="procurement-page">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <ShoppingCart className="w-8 h-8 text-amber-500" />
          Procurement Management
        </h1>
        <p className="text-muted-foreground mt-1">RFQ, Purchase Orders & Requisitions</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'rfq', label: 'RFQ / Quotes', icon: FileText },
          { id: 'requisitions', label: 'Requisitions', icon: AlertTriangle },
        ].map((tab) => (
          <Button
            key={tab.id}
            variant={activeTab === tab.id ? 'default' : 'outline'}
            onClick={() => setActiveTab(tab.id)}
            data-testid={`tab-${tab.id}`}
          >
            <tab.icon className="w-4 h-4 mr-2" />
            {tab.label}
          </Button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Loading...</div>
        </div>
      ) : (
        <>
          {/* RFQ Tab */}
          {activeTab === 'rfq' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h2 className="text-xl font-semibold">Request for Quotations</h2>
                <Button onClick={() => setShowCreateRFQ(true)} className="bg-amber-500 hover:bg-amber-600" data-testid="create-rfq-btn">
                  <Plus className="w-4 h-4 mr-2" />
                  Create RFQ
                </Button>
              </div>

              {rfqs.length === 0 ? (
                <div className="glass p-8 rounded-lg border border-border text-center">
                  <FileText className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-50" />
                  <p className="text-muted-foreground">No RFQs created yet</p>
                </div>
              ) : (
                <div className="grid gap-4">
                  {rfqs.map((rfq) => (
                    <div key={rfq.id} className="glass p-4 rounded-lg border border-border" data-testid={`rfq-${rfq.id}`}>
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-3 mb-2">
                            <span className="font-bold text-lg">{rfq.rfq_number}</span>
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(rfq.status)}`}>
                              {rfq.status}
                            </span>
                          </div>
                          <p className="text-muted-foreground text-sm">Supplier: {rfq.supplier_name}</p>
                          <p className="text-muted-foreground text-sm">Items: {rfq.lines?.length || 0}</p>
                          {rfq.total_amount > 0 && (
                            <p className="text-amber-400 font-medium mt-1">
                              Total: {rfq.currency} {rfq.total_amount.toFixed(2)}
                            </p>
                          )}
                        </div>
                        <div className="flex gap-2">
                          {rfq.status === 'DRAFT' && (
                            <Button size="sm" onClick={() => handleSendRfq(rfq.id)} className="bg-blue-500 hover:bg-blue-600" data-testid={`send-rfq-${rfq.id}`}>
                              <Send className="w-4 h-4 mr-1" />
                              Send
                            </Button>
                          )}
                          {rfq.status === 'QUOTED' && (
                            <Button size="sm" onClick={() => handleConvertToPO(rfq.id)} className="bg-green-500 hover:bg-green-600" data-testid={`convert-po-${rfq.id}`}>
                              <Check className="w-4 h-4 mr-1" />
                              Convert to PO
                            </Button>
                          )}
                          <Button size="sm" variant="outline" onClick={() => setSelectedRfq(rfq)}>
                            View Details
                          </Button>
                        </div>
                      </div>

                      {/* Lines Preview */}
                      {rfq.lines && rfq.lines.length > 0 && (
                        <div className="mt-4 border-t border-border pt-3">
                          <div className="grid grid-cols-4 gap-2 text-xs text-muted-foreground mb-2">
                            <span>Item</span>
                            <span>Qty</span>
                            <span>Unit Price</span>
                            <span>Total</span>
                          </div>
                          {rfq.lines.slice(0, 3).map((line, idx) => (
                            <div key={idx} className="grid grid-cols-4 gap-2 text-sm py-1">
                              <span className="truncate">{line.item_name}</span>
                              <span>{line.qty} {line.uom}</span>
                              <span>{line.unit_price > 0 ? line.unit_price.toFixed(2) : '-'}</span>
                              <span>{line.total > 0 ? line.total.toFixed(2) : '-'}</span>
                            </div>
                          ))}
                          {rfq.lines.length > 3 && (
                            <p className="text-xs text-muted-foreground">+{rfq.lines.length - 3} more items</p>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Requisitions Tab */}
          {activeTab === 'requisitions' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h2 className="text-xl font-semibold">Procurement Requisitions (Auto-Generated)</h2>
              </div>

              {procurementReqs.length === 0 ? (
                <div className="glass p-8 rounded-lg border border-border text-center">
                  <Package className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-50" />
                  <p className="text-muted-foreground">No pending requisitions</p>
                  <p className="text-sm text-muted-foreground mt-2">
                    Requisitions are auto-generated from production schedule shortages
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {procurementReqs.map((pr) => (
                    <div key={pr.id} className="glass p-4 rounded-lg border border-amber-500/30 bg-amber-500/5" data-testid={`pr-${pr.id}`}>
                      <div className="flex items-center justify-between mb-4">
                        <div>
                          <span className="font-semibold">Requisition</span>
                          <span className="text-amber-400 ml-2">{pr.status}</span>
                        </div>
                        <Button size="sm" className="bg-amber-500 hover:bg-amber-600" data-testid="create-rfq-from-pr">
                          <Plus className="w-4 h-4 mr-1" />
                          Create RFQ
                        </Button>
                      </div>

                      {pr.lines && pr.lines.length > 0 && (
                        <div className="space-y-2">
                          {pr.lines.map((line, idx) => (
                            <div key={idx} className="flex items-center justify-between p-2 rounded bg-muted/10 text-sm">
                              <div>
                                <span className="font-medium">{line.item?.name || 'Unknown'}</span>
                                <span className="text-muted-foreground ml-2">({line.item_type})</span>
                              </div>
                              <div className="text-right">
                                <div className="font-medium">{line.qty?.toFixed(2)} {line.uom}</div>
                                <div className="text-xs text-muted-foreground">
                                  Needed by: {line.required_by?.split('T')[0]}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Create RFQ Modal */}
      {showCreateRFQ && (
        <CreateRFQModal
          suppliers={suppliers}
          inventoryItems={inventoryItems}
          onClose={() => setShowCreateRFQ(false)}
          onCreated={() => {
            setShowCreateRFQ(false);
            loadData();
          }}
        />
      )}

      {/* RFQ Detail Modal */}
      {selectedRfq && (
        <RFQDetailModal
          rfq={selectedRfq}
          onClose={() => setSelectedRfq(null)}
          onUpdated={() => {
            setSelectedRfq(null);
            loadData();
          }}
        />
      )}
    </div>
  );
};

// Create RFQ Modal
const CreateRFQModal = ({ suppliers, inventoryItems, onClose, onCreated }) => {
  const [selectedSupplier, setSelectedSupplier] = useState('');
  const [lines, setLines] = useState([{ item_id: '', qty: 0, required_by: '' }]);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleAddLine = () => {
    setLines([...lines, { item_id: '', qty: 0, required_by: '' }]);
  };

  const handleRemoveLine = (index) => {
    setLines(lines.filter((_, i) => i !== index));
  };

  const handleLineChange = (index, field, value) => {
    const newLines = [...lines];
    newLines[index][field] = value;
    setLines(newLines);
  };

  const handleSubmit = async () => {
    if (!selectedSupplier || lines.length === 0) {
      toast.error('Please select a supplier and add at least one item');
      return;
    }

    setSubmitting(true);
    try {
      await rfqAPI.create({
        supplier_id: selectedSupplier,
        lines: lines.filter(l => l.item_id && l.qty > 0),
        notes
      });
      toast.success('RFQ created successfully');
      onCreated();
    } catch (error) {
      toast.error('Failed to create RFQ: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background border border-border rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto" data-testid="create-rfq-modal">
        <h2 className="text-xl font-bold mb-4">Create RFQ</h2>

        {/* Supplier Selection */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1">Supplier</label>
          <select
            value={selectedSupplier}
            onChange={(e) => setSelectedSupplier(e.target.value)}
            className="w-full bg-background border border-border rounded px-3 py-2"
            data-testid="supplier-select"
          >
            <option value="">Select Supplier</option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        {/* Lines */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">Items</label>
          {lines.map((line, idx) => (
            <div key={idx} className="grid grid-cols-4 gap-2 mb-2">
              <select
                value={line.item_id}
                onChange={(e) => handleLineChange(idx, 'item_id', e.target.value)}
                className="col-span-2 bg-background border border-border rounded px-2 py-1.5 text-sm"
              >
                <option value="">Select Item</option>
                {inventoryItems.map((item) => (
                  <option key={item.id} value={item.id}>{item.name} ({item.item_type})</option>
                ))}
              </select>
              <Input
                type="number"
                placeholder="Qty"
                value={line.qty}
                onChange={(e) => handleLineChange(idx, 'qty', parseFloat(e.target.value) || 0)}
                className="text-sm"
              />
              <div className="flex gap-1">
                <Input
                  type="date"
                  value={line.required_by}
                  onChange={(e) => handleLineChange(idx, 'required_by', e.target.value)}
                  className="text-sm flex-1"
                />
                {lines.length > 1 && (
                  <Button size="sm" variant="ghost" onClick={() => handleRemoveLine(idx)}>
                    <X className="w-4 h-4" />
                  </Button>
                )}
              </div>
            </div>
          ))}
          <Button size="sm" variant="outline" onClick={handleAddLine} className="mt-2">
            <Plus className="w-4 h-4 mr-1" />
            Add Line
          </Button>
        </div>

        {/* Notes */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1">Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full bg-background border border-border rounded px-3 py-2 text-sm"
            rows={2}
          />
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={submitting} className="bg-amber-500 hover:bg-amber-600" data-testid="submit-rfq-btn">
            {submitting ? 'Creating...' : 'Create RFQ'}
          </Button>
        </div>
      </div>
    </div>
  );
};

// RFQ Detail Modal (for updating quotes)
const RFQDetailModal = ({ rfq, onClose, onUpdated }) => {
  const [lines, setLines] = useState(rfq.lines || []);
  const [submitting, setSubmitting] = useState(false);

  const handlePriceChange = (index, price) => {
    const newLines = [...lines];
    newLines[index].unit_price = parseFloat(price) || 0;
    newLines[index].total = newLines[index].qty * newLines[index].unit_price;
    setLines(newLines);
  };

  const handleSaveQuote = async () => {
    setSubmitting(true);
    try {
      await rfqAPI.updateQuote(rfq.id, {
        lines: lines.map(l => ({
          item_id: l.item_id,
          unit_price: l.unit_price || 0,
          lead_time_days: l.lead_time_days
        }))
      });
      toast.success('Quote updated');
      onUpdated();
    } catch (error) {
      toast.error('Failed to update quote');
    } finally {
      setSubmitting(false);
    }
  };

  const totalAmount = lines.reduce((sum, l) => sum + (l.qty * (l.unit_price || 0)), 0);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background border border-border rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto" data-testid="rfq-detail-modal">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-xl font-bold">{rfq.rfq_number}</h2>
            <p className="text-muted-foreground">{rfq.supplier_name}</p>
          </div>
          <Button variant="ghost" onClick={onClose}><X className="w-4 h-4" /></Button>
        </div>

        {/* Lines with Editable Prices */}
        <div className="space-y-2 mb-4">
          <div className="grid grid-cols-5 gap-2 text-xs text-muted-foreground font-medium p-2">
            <span className="col-span-2">Item</span>
            <span>Qty</span>
            <span>Unit Price</span>
            <span>Total</span>
          </div>
          {lines.map((line, idx) => (
            <div key={idx} className="grid grid-cols-5 gap-2 p-2 rounded bg-muted/10 items-center">
              <span className="col-span-2 text-sm truncate">{line.item_name}</span>
              <span className="text-sm">{line.qty} {line.uom}</span>
              <Input
                type="number"
                step="0.01"
                value={line.unit_price || ''}
                onChange={(e) => handlePriceChange(idx, e.target.value)}
                className="text-sm h-8"
                placeholder="0.00"
              />
              <span className="text-sm font-medium">
                {(line.qty * (line.unit_price || 0)).toFixed(2)}
              </span>
            </div>
          ))}
        </div>

        {/* Total */}
        <div className="flex justify-between items-center p-3 rounded bg-amber-500/10 border border-amber-500/30 mb-4">
          <span className="font-semibold">Total Amount</span>
          <span className="text-xl font-bold text-amber-400">{rfq.currency} {totalAmount.toFixed(2)}</span>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Close</Button>
          {rfq.status === 'SENT' && (
            <Button onClick={handleSaveQuote} disabled={submitting} className="bg-green-500 hover:bg-green-600" data-testid="save-quote-btn">
              {submitting ? 'Saving...' : 'Save Quote'}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProcurementPage;
