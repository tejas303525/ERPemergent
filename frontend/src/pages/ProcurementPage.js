import React, { useState, useEffect } from 'react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { 
  ShoppingCart, Package, FileText, Plus, Send, Check, X, 
  RefreshCw, Building, MapPin, Calendar, Truck, AlertTriangle 
} from 'lucide-react';
import { toast } from 'sonner';
import api from '../lib/api';

const ProcurementPage = () => {
  const [activeTab, setActiveTab] = useState('products');
  const [shortages, setShortages] = useState({ raw_shortages: [], pack_shortages: [] });
  const [rfqs, setRfqs] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreateRFQ, setShowCreateRFQ] = useState(false);
  const [rfqType, setRfqType] = useState('PRODUCT'); // PRODUCT or PACKAGING

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [shortagesRes, rfqRes, suppRes] = await Promise.all([
        api.get('/procurement/shortages'),
        api.get('/rfq'),
        api.get('/suppliers')
      ]);
      setShortages(shortagesRes.data);
      setRfqs(rfqRes.data || []);
      setSuppliers(suppRes.data || []);
      
      // Load companies for billing/shipping
      try {
        const compRes = await api.get('/companies');
        setCompanies(compRes.data || []);
      } catch (e) {
        // Companies endpoint may not exist yet
        setCompanies([
          { id: '1', name: 'Main Factory', address: '123 Industrial Area, City' },
          { id: '2', name: 'Warehouse A', address: '456 Storage Zone, City' }
        ]);
      }
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleAutoGenerate = async () => {
    try {
      const res = await api.post('/procurement/auto-generate');
      toast.success(res.data.message);
      loadData();
    } catch (error) {
      toast.error('Failed: ' + (error.response?.data?.detail || error.message));
    }
  };

  const productRFQs = rfqs.filter(r => r.rfq_type === 'PRODUCT' || !r.rfq_type);
  const packagingRFQs = rfqs.filter(r => r.rfq_type === 'PACKAGING');

  return (
    <div className="p-6 max-w-[1800px] mx-auto" data-testid="procurement-page">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <ShoppingCart className="w-8 h-8 text-amber-500" />
          Procurement Management
        </h1>
        <p className="text-muted-foreground mt-1">RFQ for Products & Packaging Materials</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="glass p-4 rounded-lg border border-red-500/30">
          <p className="text-sm text-muted-foreground">RAW Material Shortages</p>
          <p className="text-2xl font-bold text-red-400">{shortages.raw_shortages?.length || 0}</p>
        </div>
        <div className="glass p-4 rounded-lg border border-amber-500/30">
          <p className="text-sm text-muted-foreground">Packaging Shortages</p>
          <p className="text-2xl font-bold text-amber-400">{shortages.pack_shortages?.length || 0}</p>
        </div>
        <div className="glass p-4 rounded-lg border border-blue-500/30">
          <p className="text-sm text-muted-foreground">Open RFQs (Products)</p>
          <p className="text-2xl font-bold text-blue-400">{productRFQs.filter(r => r.status !== 'CONVERTED').length}</p>
        </div>
        <div className="glass p-4 rounded-lg border border-cyan-500/30">
          <p className="text-sm text-muted-foreground">Open RFQs (Packaging)</p>
          <p className="text-2xl font-bold text-cyan-400">{packagingRFQs.filter(r => r.status !== 'CONVERTED').length}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        <Button
          variant={activeTab === 'products' ? 'default' : 'outline'}
          onClick={() => setActiveTab('products')}
          className={shortages.raw_shortages?.length > 0 ? 'border-red-500/50' : ''}
        >
          <Package className="w-4 h-4 mr-2" />
          RFQ for Products
          {shortages.raw_shortages?.length > 0 && (
            <span className="ml-2 px-1.5 py-0.5 text-xs rounded bg-red-500/20 text-red-400">
              {shortages.raw_shortages.length}
            </span>
          )}
        </Button>
        <Button
          variant={activeTab === 'packaging' ? 'default' : 'outline'}
          onClick={() => setActiveTab('packaging')}
        >
          <FileText className="w-4 h-4 mr-2" />
          RFQ for Packaging
          {shortages.pack_shortages?.length > 0 && (
            <span className="ml-2 px-1.5 py-0.5 text-xs rounded bg-amber-500/20 text-amber-400">
              {shortages.pack_shortages.length}
            </span>
          )}
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {/* RFQ for Products Tab */}
          {activeTab === 'products' && (
            <ProductRFQTab
              shortages={shortages.raw_shortages || []}
              rfqs={productRFQs}
              suppliers={suppliers}
              companies={companies}
              onRefresh={loadData}
              onAutoGenerate={handleAutoGenerate}
            />
          )}

          {/* RFQ for Packaging Tab */}
          {activeTab === 'packaging' && (
            <PackagingRFQTab
              shortages={shortages.pack_shortages || []}
              rfqs={packagingRFQs}
              suppliers={suppliers}
              companies={companies}
              onRefresh={loadData}
            />
          )}
        </>
      )}
    </div>
  );
};

// ==================== RFQ FOR PRODUCTS TAB ====================
const ProductRFQTab = ({ shortages, rfqs, suppliers, companies, onRefresh, onAutoGenerate }) => {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedItems, setSelectedItems] = useState([]);

  const toggleSelectItem = (shortage) => {
    if (selectedItems.find(s => s.item_id === shortage.item_id)) {
      setSelectedItems(selectedItems.filter(s => s.item_id !== shortage.item_id));
    } else {
      setSelectedItems([...selectedItems, shortage]);
    }
  };

  return (
    <div className="space-y-6">
      {/* Shortages Table - Job Order Based */}
      <div className="glass rounded-lg border border-border">
        <div className="p-4 border-b border-border flex justify-between items-center">
          <div>
            <h2 className="text-lg font-semibold">Material Requirements (from Job Orders)</h2>
            <p className="text-sm text-muted-foreground">Select items to create RFQ</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onAutoGenerate}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh from BOMs
            </Button>
            <Button 
              onClick={() => setShowCreateModal(true)}
              disabled={selectedItems.length === 0}
              className="bg-amber-500 hover:bg-amber-600"
            >
              <Plus className="w-4 h-4 mr-2" />
              Create RFQ ({selectedItems.length})
            </Button>
          </div>
        </div>

        {shortages.length === 0 ? (
          <div className="p-8 text-center">
            <Check className="w-12 h-12 text-green-500 mx-auto mb-4" />
            <p className="text-green-400 font-medium">All materials available</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/30">
                <tr>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Select</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Job Order</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Product</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Material</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Net Weight</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Qty Needed</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">On Hand</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Shortage</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Status</th>
                </tr>
              </thead>
              <tbody>
                {shortages.map((shortage) => (
                  shortage.jobs?.map((job, idx) => (
                    <tr key={`${shortage.item_id}-${idx}`} className="border-b border-border/50 hover:bg-muted/10">
                      <td className="p-3">
                        <input
                          type="checkbox"
                          checked={selectedItems.some(s => s.item_id === shortage.item_id)}
                          onChange={() => toggleSelectItem(shortage)}
                          className="w-4 h-4"
                        />
                      </td>
                      <td className="p-3 font-mono text-sm">{job.job_number}</td>
                      <td className="p-3">{job.product_name}</td>
                      <td className="p-3 font-medium">{shortage.item_name}</td>
                      <td className="p-3">{job.required_qty?.toFixed(2)} {shortage.uom}</td>
                      <td className="p-3 text-amber-400">{shortage.total_required?.toFixed(2)} {shortage.uom}</td>
                      <td className="p-3">{shortage.on_hand?.toFixed(2)} {shortage.uom}</td>
                      <td className="p-3 text-red-400 font-bold">-{shortage.total_shortage?.toFixed(2)}</td>
                      <td className="p-3">
                        <span className="px-2 py-1 rounded text-xs bg-red-500/20 text-red-400">
                          SHORTAGE
                        </span>
                      </td>
                    </tr>
                  ))
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Open RFQs */}
      <div className="glass rounded-lg border border-border">
        <div className="p-4 border-b border-border">
          <h2 className="text-lg font-semibold">Open Product RFQs</h2>
        </div>
        {rfqs.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">No open RFQs</div>
        ) : (
          <div className="p-4 space-y-3">
            {rfqs.map((rfq) => (
              <RFQCard key={rfq.id} rfq={rfq} onRefresh={onRefresh} />
            ))}
          </div>
        )}
      </div>

      {/* Create RFQ Modal */}
      {showCreateModal && (
        <CreateProductRFQModal
          selectedItems={selectedItems}
          suppliers={suppliers}
          companies={companies}
          onClose={() => setShowCreateModal(false)}
          onCreated={() => {
            setShowCreateModal(false);
            setSelectedItems([]);
            onRefresh();
          }}
        />
      )}
    </div>
  );
};

// ==================== RFQ FOR PACKAGING TAB ====================
const PackagingRFQTab = ({ shortages, rfqs, suppliers, companies, onRefresh }) => {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedItems, setSelectedItems] = useState([]);

  const toggleSelectItem = (shortage) => {
    if (selectedItems.find(s => s.item_id === shortage.item_id)) {
      setSelectedItems(selectedItems.filter(s => s.item_id !== shortage.item_id));
    } else {
      setSelectedItems([...selectedItems, shortage]);
    }
  };

  return (
    <div className="space-y-6">
      {/* Packaging Shortages */}
      <div className="glass rounded-lg border border-border">
        <div className="p-4 border-b border-border flex justify-between items-center">
          <div>
            <h2 className="text-lg font-semibold">Packaging Material Requirements</h2>
            <p className="text-sm text-muted-foreground">From packaging BOMs</p>
          </div>
          <Button 
            onClick={() => setShowCreateModal(true)}
            disabled={selectedItems.length === 0}
            className="bg-cyan-500 hover:bg-cyan-600"
          >
            <Plus className="w-4 h-4 mr-2" />
            Create Packaging RFQ ({selectedItems.length})
          </Button>
        </div>

        {shortages.length === 0 ? (
          <div className="p-8 text-center">
            <Check className="w-12 h-12 text-green-500 mx-auto mb-4" />
            <p className="text-green-400 font-medium">All packaging materials available</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/30">
                <tr>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Select</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Material</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">SKU</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Qty Needed</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">On Hand</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Shortage</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Jobs</th>
                </tr>
              </thead>
              <tbody>
                {shortages.map((shortage) => (
                  <tr key={shortage.item_id} className="border-b border-border/50 hover:bg-muted/10">
                    <td className="p-3">
                      <input
                        type="checkbox"
                        checked={selectedItems.some(s => s.item_id === shortage.item_id)}
                        onChange={() => toggleSelectItem(shortage)}
                        className="w-4 h-4"
                      />
                    </td>
                    <td className="p-3 font-medium">{shortage.item_name}</td>
                    <td className="p-3 font-mono text-sm text-muted-foreground">{shortage.item_sku}</td>
                    <td className="p-3 text-amber-400">{shortage.total_required?.toFixed(0)} {shortage.uom}</td>
                    <td className="p-3">{shortage.on_hand?.toFixed(0)}</td>
                    <td className="p-3 text-red-400 font-bold">-{shortage.total_shortage?.toFixed(0)}</td>
                    <td className="p-3 text-xs text-muted-foreground">
                      {shortage.jobs?.slice(0, 2).map(j => j.job_number).join(', ')}
                      {shortage.jobs?.length > 2 && ` +${shortage.jobs.length - 2}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Open Packaging RFQs */}
      <div className="glass rounded-lg border border-border">
        <div className="p-4 border-b border-border">
          <h2 className="text-lg font-semibold">Open Packaging RFQs</h2>
        </div>
        {rfqs.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">No open packaging RFQs</div>
        ) : (
          <div className="p-4 space-y-3">
            {rfqs.map((rfq) => (
              <RFQCard key={rfq.id} rfq={rfq} onRefresh={onRefresh} />
            ))}
          </div>
        )}
      </div>

      {/* Create Packaging RFQ Modal */}
      {showCreateModal && (
        <CreatePackagingRFQModal
          selectedItems={selectedItems}
          suppliers={suppliers}
          companies={companies}
          onClose={() => setShowCreateModal(false)}
          onCreated={() => {
            setShowCreateModal(false);
            setSelectedItems([]);
            onRefresh();
          }}
        />
      )}
    </div>
  );
};

// ==================== RFQ CARD ====================
const RFQCard = ({ rfq, onRefresh }) => {
  const handleSend = async () => {
    try {
      await api.put(`/rfq/${rfq.id}/send`);
      toast.success('RFQ sent to supplier');
      onRefresh();
    } catch (error) {
      toast.error('Failed to send');
    }
  };

  const handleConvert = async () => {
    try {
      const res = await api.post(`/rfq/${rfq.id}/convert-to-po`);
      toast.success(res.data.message);
      onRefresh();
    } catch (error) {
      toast.error('Failed: ' + (error.response?.data?.detail || error.message));
    }
  };

  const statusColor = {
    DRAFT: 'bg-gray-500/20 text-gray-400',
    SENT: 'bg-blue-500/20 text-blue-400',
    QUOTED: 'bg-green-500/20 text-green-400',
    CONVERTED: 'bg-emerald-500/20 text-emerald-400'
  };

  return (
    <div className="p-4 rounded-lg border border-border bg-muted/5">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-bold">{rfq.rfq_number}</span>
            <span className={`px-2 py-0.5 rounded text-xs ${statusColor[rfq.status] || statusColor.DRAFT}`}>
              {rfq.status}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">Supplier: {rfq.supplier_name}</p>
          <p className="text-sm">Items: {rfq.lines?.length || 0}</p>
          {rfq.total_amount > 0 && (
            <p className="text-amber-400 font-medium">{rfq.currency} {rfq.total_amount?.toFixed(2)}</p>
          )}
        </div>
        <div className="flex gap-2">
          {rfq.status === 'DRAFT' && (
            <Button size="sm" onClick={handleSend} className="bg-blue-500 hover:bg-blue-600">
              <Send className="w-4 h-4 mr-1" /> Send
            </Button>
          )}
          {rfq.status === 'QUOTED' && (
            <Button size="sm" onClick={handleConvert} className="bg-green-500 hover:bg-green-600">
              <Check className="w-4 h-4 mr-1" /> Convert to PO
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

// ==================== CREATE PRODUCT RFQ MODAL ====================
const CreateProductRFQModal = ({ selectedItems, suppliers, companies, onClose, onCreated }) => {
  const [form, setForm] = useState({
    supplier_id: '',
    billing_company_id: '',
    shipping_company_id: '',
    delivery_date: '',
    payment_terms: 'Net 30',
    incoterm: 'EXW',
    notes: ''
  });
  const [lines, setLines] = useState(
    selectedItems.map(item => ({
      item_id: item.item_id,
      item_name: item.item_name,
      qty: item.total_shortage || 0,
      uom: item.uom,
      qty_per_unit: '',
      jobs: item.jobs || []
    }))
  );
  const [submitting, setSubmitting] = useState(false);

  const selectedSupplier = suppliers.find(s => s.id === form.supplier_id);
  const billingCompany = companies.find(c => c.id === form.billing_company_id);
  const shippingCompany = companies.find(c => c.id === form.shipping_company_id);

  const handleSubmit = async () => {
    if (!form.supplier_id) {
      toast.error('Select a supplier');
      return;
    }
    setSubmitting(true);
    try {
      await api.post('/rfq', {
        supplier_id: form.supplier_id,
        rfq_type: 'PRODUCT',
        billing_company: billingCompany?.name,
        billing_address: billingCompany?.address,
        shipping_company: shippingCompany?.name,
        shipping_address: shippingCompany?.address,
        delivery_date: form.delivery_date,
        payment_terms: form.payment_terms,
        incoterm: form.incoterm,
        lines: lines.map(l => ({
          item_id: l.item_id,
          qty: l.qty,
          qty_per_unit: l.qty_per_unit,
          required_by: form.delivery_date,
          job_numbers: l.jobs.map(j => j.job_number)
        })),
        notes: form.notes
      });
      toast.success('RFQ created');
      onCreated();
    } catch (error) {
      toast.error('Failed: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-background border border-border rounded-lg p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold">Create Product RFQ</h2>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="w-4 h-4" /></Button>
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Left Column - Vendor & Companies */}
          <div className="space-y-4">
            {/* Vendor */}
            <div>
              <label className="block text-sm font-medium mb-1">Vendor *</label>
              <select
                value={form.supplier_id}
                onChange={(e) => setForm({...form, supplier_id: e.target.value})}
                className="w-full bg-background border border-border rounded px-3 py-2"
              >
                <option value="">Select Vendor</option>
                {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
              {selectedSupplier && (
                <div className="mt-2 p-2 rounded bg-muted/30 text-sm">
                  <MapPin className="w-3 h-3 inline mr-1" />
                  {selectedSupplier.address || 'No address'}
                </div>
              )}
            </div>

            {/* Billing Company */}
            <div>
              <label className="block text-sm font-medium mb-1">Billing Company</label>
              <select
                value={form.billing_company_id}
                onChange={(e) => setForm({...form, billing_company_id: e.target.value})}
                className="w-full bg-background border border-border rounded px-3 py-2"
              >
                <option value="">Select Billing Company</option>
                {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              {billingCompany && (
                <div className="mt-2 p-2 rounded bg-muted/30 text-sm">
                  <Building className="w-3 h-3 inline mr-1" />
                  {billingCompany.address}
                </div>
              )}
            </div>

            {/* Shipping Company */}
            <div>
              <label className="block text-sm font-medium mb-1">Shipping Company</label>
              <select
                value={form.shipping_company_id}
                onChange={(e) => setForm({...form, shipping_company_id: e.target.value})}
                className="w-full bg-background border border-border rounded px-3 py-2"
              >
                <option value="">Select Shipping Company</option>
                {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              {shippingCompany && (
                <div className="mt-2 p-2 rounded bg-muted/30 text-sm">
                  <Truck className="w-3 h-3 inline mr-1" />
                  {shippingCompany.address}
                </div>
              )}
            </div>
          </div>

          {/* Right Column - Terms */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Delivery Date</label>
              <Input
                type="date"
                value={form.delivery_date}
                onChange={(e) => setForm({...form, delivery_date: e.target.value})}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Terms of Payment</label>
              <select
                value={form.payment_terms}
                onChange={(e) => setForm({...form, payment_terms: e.target.value})}
                className="w-full bg-background border border-border rounded px-3 py-2"
              >
                <option value="Advance">Advance</option>
                <option value="Net 15">Net 15</option>
                <option value="Net 30">Net 30</option>
                <option value="Net 45">Net 45</option>
                <option value="Net 60">Net 60</option>
                <option value="COD">COD</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Terms of Delivery (Incoterm)</label>
              <select
                value={form.incoterm}
                onChange={(e) => setForm({...form, incoterm: e.target.value})}
                className="w-full bg-background border border-border rounded px-3 py-2"
              >
                <optgroup label="LOCAL">
                  <option value="EXW">EXW - Ex Works</option>
                  <option value="DDP">DDP - Delivered Duty Paid</option>
                  <option value="DAP">DAP - Delivered at Place</option>
                </optgroup>
                <optgroup label="IMPORT">
                  <option value="FOB">FOB - Free On Board</option>
                  <option value="CFR">CFR - Cost and Freight</option>
                  <option value="CIF">CIF - Cost Insurance Freight</option>
                  <option value="FCA">FCA - Free Carrier</option>
                </optgroup>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Notes</label>
              <textarea
                value={form.notes}
                onChange={(e) => setForm({...form, notes: e.target.value})}
                className="w-full bg-background border border-border rounded px-3 py-2"
                rows={2}
              />
            </div>
          </div>
        </div>

        {/* Lines Table */}
        <div className="mt-6">
          <h3 className="font-semibold mb-3">Items</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/30">
                <tr>
                  <th className="p-2 text-left">Job Orders</th>
                  <th className="p-2 text-left">Material</th>
                  <th className="p-2 text-left">Qty Needed</th>
                  <th className="p-2 text-left">Qty/Unit (optional)</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line, idx) => (
                  <tr key={idx} className="border-b border-border/50">
                    <td className="p-2 text-xs">
                      {line.jobs.map(j => j.job_number).join(', ')}
                    </td>
                    <td className="p-2 font-medium">{line.item_name}</td>
                    <td className="p-2">
                      <Input
                        type="number"
                        value={line.qty}
                        onChange={(e) => {
                          const newLines = [...lines];
                          newLines[idx].qty = parseFloat(e.target.value) || 0;
                          setLines(newLines);
                        }}
                        className="w-32"
                      />
                      <span className="ml-1 text-muted-foreground">{line.uom}</span>
                    </td>
                    <td className="p-2">
                      <Input
                        type="text"
                        placeholder="e.g., 25kg/bag"
                        value={line.qty_per_unit}
                        onChange={(e) => {
                          const newLines = [...lines];
                          newLines[idx].qty_per_unit = e.target.value;
                          setLines(newLines);
                        }}
                        className="w-32"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2 mt-6">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={submitting} className="bg-amber-500 hover:bg-amber-600">
            {submitting ? 'Creating...' : 'Create RFQ'}
          </Button>
        </div>
      </div>
    </div>
  );
};

// ==================== CREATE PACKAGING RFQ MODAL ====================
const CreatePackagingRFQModal = ({ selectedItems, suppliers, companies, onClose, onCreated }) => {
  const [form, setForm] = useState({
    supplier_id: '',
    delivery_date: '',
    payment_terms: 'Net 30',
    notes: ''
  });
  const [lines, setLines] = useState(
    selectedItems.map(item => ({
      item_id: item.item_id,
      item_name: item.item_name,
      qty: item.total_shortage || 0,
      uom: item.uom
    }))
  );
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!form.supplier_id) {
      toast.error('Select a supplier');
      return;
    }
    setSubmitting(true);
    try {
      await api.post('/rfq', {
        supplier_id: form.supplier_id,
        rfq_type: 'PACKAGING',
        delivery_date: form.delivery_date,
        payment_terms: form.payment_terms,
        lines: lines.map(l => ({
          item_id: l.item_id,
          qty: l.qty,
          required_by: form.delivery_date
        })),
        notes: form.notes
      });
      toast.success('Packaging RFQ created');
      onCreated();
    } catch (error) {
      toast.error('Failed: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-background border border-border rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold">Create Packaging RFQ</h2>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="w-4 h-4" /></Button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Packaging Supplier *</label>
            <select
              value={form.supplier_id}
              onChange={(e) => setForm({...form, supplier_id: e.target.value})}
              className="w-full bg-background border border-border rounded px-3 py-2"
            >
              <option value="">Select Supplier</option>
              {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Delivery Date</label>
              <Input
                type="date"
                value={form.delivery_date}
                onChange={(e) => setForm({...form, delivery_date: e.target.value})}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Payment Terms</label>
              <select
                value={form.payment_terms}
                onChange={(e) => setForm({...form, payment_terms: e.target.value})}
                className="w-full bg-background border border-border rounded px-3 py-2"
              >
                <option value="Net 30">Net 30</option>
                <option value="Net 15">Net 15</option>
                <option value="COD">COD</option>
              </select>
            </div>
          </div>

          {/* Lines */}
          <div>
            <h3 className="font-semibold mb-2">Packaging Items</h3>
            <div className="space-y-2">
              {lines.map((line, idx) => (
                <div key={idx} className="flex items-center gap-4 p-2 rounded bg-muted/20">
                  <span className="flex-1 font-medium">{line.item_name}</span>
                  <Input
                    type="number"
                    value={line.qty}
                    onChange={(e) => {
                      const newLines = [...lines];
                      newLines[idx].qty = parseFloat(e.target.value) || 0;
                      setLines(newLines);
                    }}
                    className="w-24"
                  />
                  <span className="text-muted-foreground">{line.uom}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={submitting} className="bg-cyan-500 hover:bg-cyan-600">
            {submitting ? 'Creating...' : 'Create RFQ'}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ProcurementPage;
