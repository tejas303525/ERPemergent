import React, { useState, useEffect } from 'react';
import { shippingAPI, jobOrderAPI } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import { formatDate, getStatusColor } from '../lib/utils';
import { Plus, Ship, Edit2 } from 'lucide-react';

const CONTAINER_TYPES = ['20ft', '40ft', '40ft_hc'];
const STATUSES = ['pending', 'confirmed', 'loaded', 'shipped'];

export default function ShippingPage() {
  const { user } = useAuth();
  const [bookings, setBookings] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [selectedBooking, setSelectedBooking] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');

  const [form, setForm] = useState({
    job_order_ids: [],
    shipping_line: '',
    container_type: '20ft',
    container_count: 1,
    port_of_loading: '',
    port_of_discharge: '',
    cutoff_date: '',
    pullout_date: '',
    notes: '',
  });

  const [editForm, setEditForm] = useState({
    cro_number: '',
    status: '',
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [bookingsRes, jobsRes] = await Promise.all([
        shippingAPI.getAll(),
        jobOrderAPI.getAll('ready_for_dispatch'),
      ]);
      setBookings(bookingsRes.data);
      setJobs(jobsRes.data);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const toggleJobSelection = (jobId) => {
    setForm(prev => ({
      ...prev,
      job_order_ids: prev.job_order_ids.includes(jobId)
        ? prev.job_order_ids.filter(id => id !== jobId)
        : [...prev.job_order_ids, jobId]
    }));
  };

  const handleCreate = async () => {
    if (form.job_order_ids.length === 0 || !form.shipping_line || !form.cutoff_date) {
      toast.error('Please fill in all required fields');
      return;
    }
    try {
      await shippingAPI.create(form);
      toast.success('Shipping booking created');
      setCreateOpen(false);
      setForm({ job_order_ids: [], shipping_line: '', container_type: '20ft', container_count: 1, port_of_loading: '', port_of_discharge: '', cutoff_date: '', pullout_date: '', notes: '' });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create booking');
    }
  };

  const handleEdit = async () => {
    try {
      const updateData = {};
      if (editForm.cro_number) updateData.cro_number = editForm.cro_number;
      if (editForm.status) updateData.status = editForm.status;
      
      await shippingAPI.update(selectedBooking.id, updateData);
      toast.success('Booking updated');
      setEditOpen(false);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update');
    }
  };

  const openEdit = (booking) => {
    setSelectedBooking(booking);
    setEditForm({ cro_number: booking.cro_number || '', status: booking.status });
    setEditOpen(true);
  };

  const filteredBookings = statusFilter === 'all' ? bookings : bookings.filter(b => b.status === statusFilter);
  const canCreate = ['admin', 'shipping'].includes(user?.role);

  return (
    <div className="page-container" data-testid="shipping-page">
      <div className="module-header">
        <div>
          <h1 className="module-title">Shipping</h1>
          <p className="text-muted-foreground text-sm">Manage container bookings and shipping</p>
        </div>
        <div className="module-actions">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-40" data-testid="status-filter">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              {STATUSES.map(s => (
                <SelectItem key={s} value={s}>{s.toUpperCase()}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {canCreate && (
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger asChild>
                <Button data-testid="create-booking-btn" className="rounded-sm">
                  <Plus className="w-4 h-4 mr-2" /> New Booking
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Create Shipping Booking</DialogTitle>
                </DialogHeader>
                <div className="space-y-6 py-4">
                  {/* Job Orders Selection */}
                  <div>
                    <Label className="mb-2 block">Select Job Orders</Label>
                    <div className="border border-border rounded-sm max-h-48 overflow-y-auto">
                      {jobs.length > 0 ? jobs.map(job => (
                        <div key={job.id} className="flex items-center gap-3 p-3 border-b border-border last:border-0 hover:bg-muted/30">
                          <Checkbox
                            checked={form.job_order_ids.includes(job.id)}
                            onCheckedChange={() => toggleJobSelection(job.id)}
                          />
                          <div className="flex-1">
                            <p className="font-mono text-sm">{job.job_number}</p>
                            <p className="text-xs text-muted-foreground">{job.product_name} - Qty: {job.quantity}</p>
                          </div>
                        </div>
                      )) : (
                        <p className="p-4 text-center text-muted-foreground text-sm">No jobs ready for dispatch</p>
                      )}
                    </div>
                  </div>

                  <div className="form-grid">
                    <div className="form-field">
                      <Label>Shipping Line</Label>
                      <Input
                        value={form.shipping_line}
                        onChange={(e) => setForm({...form, shipping_line: e.target.value})}
                        placeholder="e.g., MSC, Maersk, Hapag"
                        data-testid="shipping-line-input"
                      />
                    </div>
                    <div className="form-field">
                      <Label>Container Type</Label>
                      <Select value={form.container_type} onValueChange={(v) => setForm({...form, container_type: v})}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {CONTAINER_TYPES.map(t => (
                            <SelectItem key={t} value={t}>{t.toUpperCase()}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="form-field">
                      <Label>Container Count</Label>
                      <Input
                        type="number"
                        min="1"
                        value={form.container_count}
                        onChange={(e) => setForm({...form, container_count: parseInt(e.target.value)})}
                      />
                    </div>
                  </div>

                  <div className="form-grid">
                    <div className="form-field">
                      <Label>Port of Loading</Label>
                      <Input
                        value={form.port_of_loading}
                        onChange={(e) => setForm({...form, port_of_loading: e.target.value})}
                        placeholder="e.g., Jebel Ali"
                        data-testid="port-loading-input"
                      />
                    </div>
                    <div className="form-field">
                      <Label>Port of Discharge</Label>
                      <Input
                        value={form.port_of_discharge}
                        onChange={(e) => setForm({...form, port_of_discharge: e.target.value})}
                        placeholder="e.g., Mumbai"
                        data-testid="port-discharge-input"
                      />
                    </div>
                  </div>

                  <div className="form-grid">
                    <div className="form-field">
                      <Label>Cutoff Date</Label>
                      <Input
                        type="date"
                        value={form.cutoff_date}
                        onChange={(e) => setForm({...form, cutoff_date: e.target.value})}
                        data-testid="cutoff-date-input"
                      />
                    </div>
                    <div className="form-field">
                      <Label>Pullout Date</Label>
                      <Input
                        type="date"
                        value={form.pullout_date}
                        onChange={(e) => setForm({...form, pullout_date: e.target.value})}
                      />
                    </div>
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
                    <Button onClick={handleCreate} data-testid="submit-booking-btn">Create Booking</Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {/* Bookings List */}
      <div className="data-grid">
        <div className="data-grid-header">
          <h3 className="font-medium">Shipping Bookings ({filteredBookings.length})</h3>
        </div>
        {loading ? (
          <div className="p-8 text-center text-muted-foreground">Loading...</div>
        ) : filteredBookings.length === 0 ? (
          <div className="empty-state">
            <Ship className="empty-state-icon" />
            <p className="empty-state-title">No bookings found</p>
            <p className="empty-state-description">Create a shipping booking for export orders</p>
          </div>
        ) : (
          <table className="erp-table w-full">
            <thead>
              <tr>
                <th>Booking #</th>
                <th>Shipping Line</th>
                <th>Container</th>
                <th>Route</th>
                <th>Cutoff</th>
                <th>Pullout</th>
                <th>CRO #</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredBookings.map((booking) => (
                <tr key={booking.id} data-testid={`booking-row-${booking.booking_number}`}>
                  <td className="font-medium">{booking.booking_number}</td>
                  <td>{booking.shipping_line}</td>
                  <td>{booking.container_count}x {booking.container_type?.toUpperCase()}</td>
                  <td className="text-xs">{booking.port_of_loading} → {booking.port_of_discharge}</td>
                  <td>{formatDate(booking.cutoff_date)}</td>
                  <td>{formatDate(booking.pullout_date)}</td>
                  <td>{booking.cro_number || '-'}</td>
                  <td><Badge className={getStatusColor(booking.status)}>{booking.status}</Badge></td>
                  <td>
                    {canCreate && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEdit(booking)}
                        data-testid={`edit-booking-${booking.booking_number}`}
                      >
                        <Edit2 className="w-4 h-4" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Update Booking {selectedBooking?.booking_number}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="form-field">
              <Label>CRO Number</Label>
              <Input
                value={editForm.cro_number}
                onChange={(e) => setEditForm({...editForm, cro_number: e.target.value})}
                placeholder="Enter CRO number"
                data-testid="cro-number-input"
              />
            </div>
            <div className="form-field">
              <Label>Status</Label>
              <Select value={editForm.status} onValueChange={(v) => setEditForm({...editForm, status: v})}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUSES.map(s => (
                    <SelectItem key={s} value={s}>{s.toUpperCase()}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
              <Button onClick={handleEdit} data-testid="update-booking-btn">Update</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
