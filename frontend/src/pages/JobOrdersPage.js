import React, { useState, useEffect } from 'react';
import { jobOrderAPI, salesOrderAPI, productAPI } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import { formatDate, getStatusColor, getPriorityColor } from '../lib/utils';
import { Plus, Factory, Eye, Play, CheckCircle, Trash2 } from 'lucide-react';

const PRIORITIES = ['low', 'normal', 'high', 'urgent'];
const STATUSES = ['pending', 'in_production', 'procurement', 'ready_for_dispatch'];

export default function JobOrdersPage() {
  const { user } = useAuth();
  const [jobs, setJobs] = useState([]);
  const [salesOrders, setSalesOrders] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [viewOpen, setViewOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');

  const [form, setForm] = useState({
    sales_order_id: '',
    product_id: '',
    product_name: '',
    quantity: 0,
    priority: 'normal',
    notes: '',
    bom: [],
  });

  const [newBomItem, setNewBomItem] = useState({
    product_id: '',
    product_name: '',
    sku: '',
    required_qty: 0,
    unit: 'KG',
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [jobsRes, ordersRes, productsRes] = await Promise.all([
        jobOrderAPI.getAll(),
        salesOrderAPI.getAll('active'),
        productAPI.getAll(),
      ]);
      setJobs(jobsRes.data);
      setSalesOrders(ordersRes.data);
      setProducts(productsRes.data);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const finishedProducts = products.filter(p => p.category === 'finished_product');
  const rawMaterials = products.filter(p => p.category !== 'finished_product');

  const handleProductSelect = (productId) => {
    const product = finishedProducts.find(p => p.id === productId);
    if (product) {
      setForm({
        ...form,
        product_id: productId,
        product_name: product.name,
      });
    }
  };

  const handleBomProductSelect = (productId) => {
    const product = rawMaterials.find(p => p.id === productId);
    if (product) {
      setNewBomItem({
        ...newBomItem,
        product_id: productId,
        product_name: product.name,
        sku: product.sku,
        unit: product.unit,
      });
    }
  };

  const addBomItem = () => {
    if (!newBomItem.product_id || newBomItem.required_qty <= 0) {
      toast.error('Please select material and enter required quantity');
      return;
    }
    setForm({
      ...form,
      bom: [...form.bom, { ...newBomItem }],
    });
    setNewBomItem({ product_id: '', product_name: '', sku: '', required_qty: 0, unit: 'KG' });
  };

  const removeBomItem = (index) => {
    setForm({
      ...form,
      bom: form.bom.filter((_, i) => i !== index),
    });
  };

  const handleCreate = async () => {
    if (!form.sales_order_id || !form.product_id || form.quantity <= 0) {
      toast.error('Please fill in all required fields');
      return;
    }
    try {
      await jobOrderAPI.create(form);
      toast.success('Job order created successfully');
      setCreateOpen(false);
      setForm({ sales_order_id: '', product_id: '', product_name: '', quantity: 0, priority: 'normal', notes: '', bom: [] });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create job order');
    }
  };

  const handleStatusUpdate = async (jobId, newStatus) => {
    try {
      await jobOrderAPI.updateStatus(jobId, newStatus);
      toast.success(`Status updated to ${newStatus.replace(/_/g, ' ')}`);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update status');
    }
  };

  const filteredJobs = statusFilter === 'all' ? jobs : jobs.filter(j => j.status === statusFilter);

  const canManageJobs = ['admin', 'production', 'procurement'].includes(user?.role);

  return (
    <div className="page-container" data-testid="job-orders-page">
      <div className="module-header">
        <div>
          <h1 className="module-title">Job Orders</h1>
          <p className="text-muted-foreground text-sm">Manage production and manufacturing jobs</p>
        </div>
        <div className="module-actions">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-40" data-testid="status-filter">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              {STATUSES.map(s => (
                <SelectItem key={s} value={s}>{s.replace(/_/g, ' ').toUpperCase()}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {canManageJobs && (
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger asChild>
                <Button data-testid="create-job-btn" className="rounded-sm">
                  <Plus className="w-4 h-4 mr-2" /> New Job Order
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Create Job Order</DialogTitle>
                </DialogHeader>
                <div className="space-y-6 py-4">
                  <div className="form-grid">
                    <div className="form-field">
                      <Label>Sales Order</Label>
                      <Select value={form.sales_order_id} onValueChange={(v) => setForm({...form, sales_order_id: v})}>
                        <SelectTrigger data-testid="sales-order-select">
                          <SelectValue placeholder="Select sales order" />
                        </SelectTrigger>
                        <SelectContent>
                          {salesOrders.map(o => (
                            <SelectItem key={o.id} value={o.id}>
                              {o.spa_number} - {o.customer_name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="form-field">
                      <Label>Product to Manufacture</Label>
                      <Select value={form.product_id} onValueChange={handleProductSelect}>
                        <SelectTrigger data-testid="product-select">
                          <SelectValue placeholder="Select product" />
                        </SelectTrigger>
                        <SelectContent>
                          {finishedProducts.map(p => (
                            <SelectItem key={p.id} value={p.id}>{p.name} ({p.sku})</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="form-field">
                      <Label>Quantity</Label>
                      <Input
                        type="number"
                        value={form.quantity || ''}
                        onChange={(e) => setForm({...form, quantity: parseFloat(e.target.value)})}
                        placeholder="Enter quantity"
                        data-testid="quantity-input"
                      />
                    </div>
                    <div className="form-field">
                      <Label>Priority</Label>
                      <Select value={form.priority} onValueChange={(v) => setForm({...form, priority: v})}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {PRIORITIES.map(p => (
                            <SelectItem key={p} value={p}>{p.toUpperCase()}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {/* BOM Section */}
                  <div className="border-t border-border pt-4">
                    <h3 className="font-semibold mb-4">Bill of Materials (BOM)</h3>
                    <div className="grid grid-cols-4 gap-2 mb-3">
                      <div className="col-span-2">
                        <Select value={newBomItem.product_id} onValueChange={handleBomProductSelect}>
                          <SelectTrigger data-testid="bom-product-select">
                            <SelectValue placeholder="Select material" />
                          </SelectTrigger>
                          <SelectContent>
                            {rawMaterials.map(p => (
                              <SelectItem key={p.id} value={p.id}>{p.name} ({p.sku})</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <Input
                        type="number"
                        placeholder="Required Qty"
                        value={newBomItem.required_qty || ''}
                        onChange={(e) => setNewBomItem({...newBomItem, required_qty: parseFloat(e.target.value)})}
                      />
                      <Button type="button" variant="secondary" onClick={addBomItem} data-testid="add-bom-btn">
                        <Plus className="w-4 h-4" />
                      </Button>
                    </div>

                    {form.bom.length > 0 && (
                      <div className="data-grid">
                        <table className="erp-table w-full">
                          <thead>
                            <tr>
                              <th>Material</th>
                              <th>SKU</th>
                              <th>Required Qty</th>
                              <th>Unit</th>
                              <th></th>
                            </tr>
                          </thead>
                          <tbody>
                            {form.bom.map((item, idx) => (
                              <tr key={idx}>
                                <td>{item.product_name}</td>
                                <td>{item.sku}</td>
                                <td>{item.required_qty}</td>
                                <td>{item.unit}</td>
                                <td>
                                  <Button variant="ghost" size="icon" onClick={() => removeBomItem(idx)}>
                                    <Trash2 className="w-4 h-4 text-destructive" />
                                  </Button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
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
                    <Button onClick={handleCreate} data-testid="submit-job-btn">Create Job Order</Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {/* Jobs List */}
      <div className="data-grid">
        <div className="data-grid-header">
          <h3 className="font-medium">Job Orders ({filteredJobs.length})</h3>
        </div>
        {loading ? (
          <div className="p-8 text-center text-muted-foreground">Loading...</div>
        ) : filteredJobs.length === 0 ? (
          <div className="empty-state">
            <Factory className="empty-state-icon" />
            <p className="empty-state-title">No job orders found</p>
            <p className="empty-state-description">Create a new job order from a sales order</p>
          </div>
        ) : (
          <table className="erp-table w-full">
            <thead>
              <tr>
                <th>Job Number</th>
                <th>SPA Number</th>
                <th>Product</th>
                <th>Quantity</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Procurement</th>
                <th>Batch #</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredJobs.map((job) => (
                <tr key={job.id} data-testid={`job-row-${job.job_number}`}>
                  <td className="font-medium">{job.job_number}</td>
                  <td>{job.spa_number}</td>
                  <td>{job.product_name}</td>
                  <td className="font-mono">{job.quantity}</td>
                  <td><span className={getPriorityColor(job.priority)}>{job.priority?.toUpperCase()}</span></td>
                  <td><Badge className={getStatusColor(job.status)}>{job.status?.replace(/_/g, ' ')}</Badge></td>
                  <td><Badge className={getStatusColor(job.procurement_status === 'complete' ? 'approved' : job.procurement_status)}>{job.procurement_status?.replace(/_/g, ' ')}</Badge></td>
                  <td>{job.batch_number || '-'}</td>
                  <td>{formatDate(job.created_at)}</td>
                  <td>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => { setSelectedJob(job); setViewOpen(true); }}
                        data-testid={`view-job-${job.job_number}`}
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                      {canManageJobs && job.status === 'pending' && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleStatusUpdate(job.id, 'in_production')}
                          className="text-sky-500 hover:text-sky-400"
                          title="Start Production"
                          data-testid={`start-job-${job.job_number}`}
                        >
                          <Play className="w-4 h-4" />
                        </Button>
                      )}
                      {canManageJobs && job.status === 'in_production' && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleStatusUpdate(job.id, 'ready_for_dispatch')}
                          className="text-emerald-500 hover:text-emerald-400"
                          title="Mark Ready for Dispatch"
                          data-testid={`complete-job-${job.job_number}`}
                        >
                          <CheckCircle className="w-4 h-4" />
                        </Button>
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
            <DialogTitle>Job Order {selectedJob?.job_number}</DialogTitle>
          </DialogHeader>
          {selectedJob && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="text-muted-foreground">SPA Number:</span> {selectedJob.spa_number}</div>
                <div><span className="text-muted-foreground">Product:</span> {selectedJob.product_name}</div>
                <div><span className="text-muted-foreground">Quantity:</span> <span className="font-mono">{selectedJob.quantity}</span></div>
                <div><span className="text-muted-foreground">Priority:</span> <span className={getPriorityColor(selectedJob.priority)}>{selectedJob.priority?.toUpperCase()}</span></div>
                <div><span className="text-muted-foreground">Status:</span> <Badge className={getStatusColor(selectedJob.status)}>{selectedJob.status?.replace(/_/g, ' ')}</Badge></div>
                <div><span className="text-muted-foreground">Batch:</span> {selectedJob.batch_number || '-'}</div>
                {selectedJob.production_start && <div><span className="text-muted-foreground">Production Start:</span> {formatDate(selectedJob.production_start)}</div>}
                {selectedJob.production_end && <div><span className="text-muted-foreground">Production End:</span> {formatDate(selectedJob.production_end)}</div>}
              </div>

              {selectedJob.bom?.length > 0 && (
                <div className="data-grid">
                  <div className="data-grid-header">
                    <h4 className="font-medium">Bill of Materials</h4>
                  </div>
                  <table className="erp-table w-full">
                    <thead>
                      <tr>
                        <th>Material</th>
                        <th>SKU</th>
                        <th>Required</th>
                        <th>Available</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedJob.bom.map((item, idx) => (
                        <tr key={idx}>
                          <td>{item.product_name}</td>
                          <td>{item.sku}</td>
                          <td className="font-mono">{item.required_qty} {item.unit}</td>
                          <td className="font-mono">{item.available_qty} {item.unit}</td>
                          <td>
                            {item.available_qty >= item.required_qty ? (
                              <Badge className="status-approved">Available</Badge>
                            ) : (
                              <Badge className="status-warning">Shortage</Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {selectedJob.notes && (
                <div>
                  <p className="text-sm text-muted-foreground">Notes:</p>
                  <p className="text-sm">{selectedJob.notes}</p>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
