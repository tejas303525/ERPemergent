import React, { useState, useEffect } from 'react';
import { quotationAPI, customerAPI, productAPI, pdfAPI } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import { formatCurrency, formatDate, getStatusColor, cn } from '../lib/utils';
import { Plus, FileText, Check, X, Eye, Trash2, Download } from 'lucide-react';

const CURRENCIES = ['USD', 'AED', 'EUR'];
const ORDER_TYPES = ['local', 'export'];
const PAYMENT_TERMS = ['Cash', 'LC', 'CAD', 'TT'];
const INCOTERMS = ['FOB', 'CFR', 'CIF', 'EXW', 'DDP'];
const PACKAGING = ['Bulk', 'Drums', 'IBC', 'Bags', 'Cartons'];

export default function QuotationsPage() {
  const { user } = useAuth();
  const [quotations, setQuotations] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [viewOpen, setViewOpen] = useState(false);
  const [selectedQuotation, setSelectedQuotation] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');

  const [form, setForm] = useState({
    customer_id: '',
    customer_name: '',
    currency: 'USD',
    order_type: 'local',
    incoterm: '',
    port_of_loading: '',
    delivery_place: '',
    payment_terms: 'Cash',
    validity_days: 30,
    notes: '',
    items: [],
  });

  const [newItem, setNewItem] = useState({
    product_id: '',
    product_name: '',
    sku: '',
    quantity: 0,
    unit_price: 0,
    packaging: 'Bulk',
    net_weight_kg: null,
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [quotationsRes, customersRes, productsRes] = await Promise.all([
        quotationAPI.getAll(),
        customerAPI.getAll(),
        productAPI.getAll(),
      ]);
      setQuotations(quotationsRes.data);
      setCustomers(customersRes.data);
      setProducts(productsRes.data.filter(p => p.category === 'finished_product'));
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleCustomerChange = (customerId) => {
    const customer = customers.find(c => c.id === customerId);
    setForm({
      ...form,
      customer_id: customerId,
      customer_name: customer?.name || '',
    });
  };

  const handleProductSelect = (productId) => {
    const product = products.find(p => p.id === productId);
    if (product) {
      const price = form.currency === 'USD' ? product.price_usd :
                    form.currency === 'AED' ? product.price_aed : product.price_eur;
      setNewItem({
        ...newItem,
        product_id: productId,
        product_name: product.name,
        sku: product.sku,
        unit_price: price,
      });
    }
  };

  const addItem = () => {
    if (!newItem.product_id || newItem.quantity <= 0) {
      toast.error('Please select a product and enter quantity');
      return;
    }
    // Require net_weight_kg for non-Bulk packaging
    if (newItem.packaging !== 'Bulk' && !newItem.net_weight_kg) {
      toast.error('Please enter net weight (kg) for packaged items');
      return;
    }
    setForm({
      ...form,
      items: [...form.items, { ...newItem, total: newItem.quantity * newItem.unit_price }],
    });
    setNewItem({ product_id: '', product_name: '', sku: '', quantity: 0, unit_price: 0, packaging: 'Bulk', net_weight_kg: null });
  };

  const removeItem = (index) => {
    setForm({
      ...form,
      items: form.items.filter((_, i) => i !== index),
    });
  };

  const handleCreate = async () => {
    if (!form.customer_id || form.items.length === 0) {
      toast.error('Please select customer and add items');
      return;
    }
    try {
      await quotationAPI.create(form);
      toast.success('Quotation created successfully');
      setCreateOpen(false);
      resetForm();
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create quotation');
    }
  };

  const handleApprove = async (id) => {
    try {
      await quotationAPI.approve(id);
      toast.success('Quotation approved');
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to approve');
    }
  };

  const handleReject = async (id) => {
    try {
      await quotationAPI.reject(id);
      toast.success('Quotation rejected');
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to reject');
    }
  };

  const handleDownloadPDF = async (quotationId, pfiNumber) => {
    try {
      const token = localStorage.getItem('erp_token');
      const url = pdfAPI.getQuotationUrl(quotationId);
      
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to download PDF');
      }
      
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `PFI_${pfiNumber}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
      toast.success('PDF downloaded successfully');
    } catch (error) {
      toast.error('Failed to download PDF');
    }
  };

  const resetForm = () => {
    setForm({
      customer_id: '',
      customer_name: '',
      currency: 'USD',
      order_type: 'local',
      incoterm: '',
      port_of_loading: '',
      delivery_place: '',
      payment_terms: 'Cash',
      validity_days: 30,
      notes: '',
      items: [],
    });
  };

  const filteredQuotations = statusFilter === 'all' 
    ? quotations 
    : quotations.filter(q => q.status === statusFilter);

  const canApprove = user?.role === 'admin' || user?.role === 'finance';

  return (
    <div className="page-container" data-testid="quotations-page">
      <div className="module-header">
        <div>
          <h1 className="module-title">Quotations / PFI</h1>
          <p className="text-muted-foreground text-sm">Manage proforma invoices and quotations</p>
        </div>
        <div className="module-actions">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-40" data-testid="status-filter">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="approved">Approved</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
              <SelectItem value="converted">Converted</SelectItem>
            </SelectContent>
          </Select>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button data-testid="create-quotation-btn" className="rounded-sm">
                <Plus className="w-4 h-4 mr-2" /> New Quotation
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Create New Quotation</DialogTitle>
              </DialogHeader>
              <div className="space-y-6 py-4">
                {/* Customer & Basic Info */}
                <div className="form-grid">
                  <div className="form-field">
                    <Label>Customer</Label>
                    <Select value={form.customer_id} onValueChange={handleCustomerChange}>
                      <SelectTrigger data-testid="customer-select">
                        <SelectValue placeholder="Select customer" />
                      </SelectTrigger>
                      <SelectContent>
                        {customers.map(c => (
                          <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="form-field">
                    <Label>Currency</Label>
                    <Select value={form.currency} onValueChange={(v) => setForm({...form, currency: v})}>
                      <SelectTrigger data-testid="currency-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {CURRENCIES.map(c => (
                          <SelectItem key={c} value={c}>{c}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="form-field">
                    <Label>Order Type</Label>
                    <Select value={form.order_type} onValueChange={(v) => setForm({...form, order_type: v})}>
                      <SelectTrigger data-testid="order-type-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ORDER_TYPES.map(t => (
                          <SelectItem key={t} value={t}>{t.toUpperCase()}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {form.order_type === 'export' && (
                  <div className="form-grid">
                    <div className="form-field">
                      <Label>Incoterm</Label>
                      <Select value={form.incoterm} onValueChange={(v) => setForm({...form, incoterm: v})}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select incoterm" />
                        </SelectTrigger>
                        <SelectContent>
                          {INCOTERMS.map(i => (
                            <SelectItem key={i} value={i}>{i}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="form-field">
                      <Label>Port of Loading</Label>
                      <Input
                        value={form.port_of_loading}
                        onChange={(e) => setForm({...form, port_of_loading: e.target.value})}
                        placeholder="e.g., Jebel Ali"
                      />
                    </div>
                    <div className="form-field">
                      <Label>Delivery Place</Label>
                      <Input
                        value={form.delivery_place}
                        onChange={(e) => setForm({...form, delivery_place: e.target.value})}
                        placeholder="Destination port/city"
                      />
                    </div>
                  </div>
                )}

                <div className="form-grid">
                  <div className="form-field">
                    <Label>Payment Terms</Label>
                    <Select value={form.payment_terms} onValueChange={(v) => setForm({...form, payment_terms: v})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {PAYMENT_TERMS.map(p => (
                          <SelectItem key={p} value={p}>{p}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="form-field">
                    <Label>Validity (Days)</Label>
                    <Input
                      type="number"
                      value={form.validity_days}
                      onChange={(e) => setForm({...form, validity_days: parseInt(e.target.value)})}
                    />
                  </div>
                </div>

                {/* Items Section */}
                <div className="border-t border-border pt-4">
                  <h3 className="font-semibold mb-4">Items</h3>
                  <div className="grid grid-cols-6 gap-2 mb-3">
                    <div className="col-span-2">
                      <Select value={newItem.product_id} onValueChange={handleProductSelect}>
                        <SelectTrigger data-testid="product-select">
                          <SelectValue placeholder="Select product" />
                        </SelectTrigger>
                        <SelectContent>
                          {products.map(p => (
                            <SelectItem key={p.id} value={p.id}>{p.name} ({p.sku})</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <Input
                      type="number"
                      placeholder="Qty"
                      value={newItem.quantity || ''}
                      onChange={(e) => setNewItem({...newItem, quantity: parseFloat(e.target.value)})}
                    />
                    <Input
                      type="number"
                      placeholder="Price"
                      value={newItem.unit_price || ''}
                      onChange={(e) => setNewItem({...newItem, unit_price: parseFloat(e.target.value)})}
                    />
                    <Select value={newItem.packaging} onValueChange={(v) => setNewItem({...newItem, packaging: v})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {PACKAGING.map(p => (
                          <SelectItem key={p} value={p}>{p}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button type="button" variant="secondary" onClick={addItem} data-testid="add-item-btn">
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>

                  {form.items.length > 0 && (
                    <div className="data-grid">
                      <table className="erp-table w-full">
                        <thead>
                          <tr>
                            <th>Product</th>
                            <th>SKU</th>
                            <th>Qty</th>
                            <th>Price</th>
                            <th>Packaging</th>
                            <th>Total</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {form.items.map((item, idx) => (
                            <tr key={idx}>
                              <td>{item.product_name}</td>
                              <td>{item.sku}</td>
                              <td>{item.quantity}</td>
                              <td>{formatCurrency(item.unit_price, form.currency)}</td>
                              <td>{item.packaging}</td>
                              <td>{formatCurrency(item.quantity * item.unit_price, form.currency)}</td>
                              <td>
                                <Button variant="ghost" size="icon" onClick={() => removeItem(idx)}>
                                  <Trash2 className="w-4 h-4 text-destructive" />
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <div className="p-4 border-t border-border flex justify-end">
                        <div className="text-right">
                          <p className="text-sm text-muted-foreground">Total</p>
                          <p className="text-xl font-bold font-mono">
                            {formatCurrency(form.items.reduce((sum, i) => sum + i.quantity * i.unit_price, 0), form.currency)}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                <div className="form-field">
                  <Label>Notes</Label>
                  <Textarea
                    value={form.notes}
                    onChange={(e) => setForm({...form, notes: e.target.value})}
                    placeholder="Additional notes..."
                  />
                </div>

                <div className="flex justify-end gap-3">
                  <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
                  <Button onClick={handleCreate} data-testid="submit-quotation-btn">Create Quotation</Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Quotations List */}
      <div className="data-grid">
        <div className="data-grid-header">
          <h3 className="font-medium">Quotations ({filteredQuotations.length})</h3>
        </div>
        {loading ? (
          <div className="p-8 text-center text-muted-foreground">Loading...</div>
        ) : filteredQuotations.length === 0 ? (
          <div className="empty-state">
            <FileText className="empty-state-icon" />
            <p className="empty-state-title">No quotations found</p>
            <p className="empty-state-description">Create a new quotation to get started</p>
          </div>
        ) : (
          <table className="erp-table w-full">
            <thead>
              <tr>
                <th>PFI Number</th>
                <th>Customer</th>
                <th>Type</th>
                <th>Items</th>
                <th>Total</th>
                <th>Status</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredQuotations.map((q) => (
                <tr key={q.id} data-testid={`quotation-row-${q.pfi_number}`}>
                  <td className="font-medium">{q.pfi_number}</td>
                  <td>{q.customer_name}</td>
                  <td>
                    <Badge variant="outline" className="uppercase text-xs">{q.order_type}</Badge>
                  </td>
                  <td>{q.items?.length || 0}</td>
                  <td className="font-mono">{formatCurrency(q.total, q.currency)}</td>
                  <td><Badge className={getStatusColor(q.status)}>{q.status}</Badge></td>
                  <td>{formatDate(q.created_at)}</td>
                  <td>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => { setSelectedQuotation(q); setViewOpen(true); }}
                        data-testid={`view-quotation-${q.pfi_number}`}
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDownloadPDF(q.id, q.pfi_number)}
                        title="Download PDF"
                        data-testid={`download-quotation-${q.pfi_number}`}
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                      {canApprove && q.status === 'pending' && (
                        <>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleApprove(q.id)}
                            className="text-emerald-500 hover:text-emerald-400"
                            data-testid={`approve-quotation-${q.pfi_number}`}
                          >
                            <Check className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleReject(q.id)}
                            className="text-destructive hover:text-destructive/80"
                            data-testid={`reject-quotation-${q.pfi_number}`}
                          >
                            <X className="w-4 h-4" />
                          </Button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* View Dialog */}
      <Dialog open={viewOpen} onOpenChange={setViewOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Quotation {selectedQuotation?.pfi_number}</DialogTitle>
          </DialogHeader>
          {selectedQuotation && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="text-muted-foreground">Customer:</span> {selectedQuotation.customer_name}</div>
                <div><span className="text-muted-foreground">Currency:</span> {selectedQuotation.currency}</div>
                <div><span className="text-muted-foreground">Order Type:</span> {selectedQuotation.order_type?.toUpperCase()}</div>
                <div><span className="text-muted-foreground">Payment Terms:</span> {selectedQuotation.payment_terms}</div>
                {selectedQuotation.incoterm && <div><span className="text-muted-foreground">Incoterm:</span> {selectedQuotation.incoterm}</div>}
                {selectedQuotation.port_of_loading && <div><span className="text-muted-foreground">Port of Loading:</span> {selectedQuotation.port_of_loading}</div>}
              </div>
              <div className="data-grid">
                <table className="erp-table w-full">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>SKU</th>
                      <th>Qty</th>
                      <th>Price</th>
                      <th>Packaging</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedQuotation.items?.map((item, idx) => (
                      <tr key={idx}>
                        <td>{item.product_name}</td>
                        <td>{item.sku}</td>
                        <td>{item.quantity}</td>
                        <td>{formatCurrency(item.unit_price, selectedQuotation.currency)}</td>
                        <td>{item.packaging}</td>
                        <td>{formatCurrency(item.total, selectedQuotation.currency)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex justify-between items-center pt-4 border-t">
                <Badge className={getStatusColor(selectedQuotation.status)}>{selectedQuotation.status}</Badge>
                <div className="text-right">
                  <p className="text-sm text-muted-foreground">Total Amount</p>
                  <p className="text-2xl font-bold font-mono">{formatCurrency(selectedQuotation.total, selectedQuotation.currency)}</p>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
