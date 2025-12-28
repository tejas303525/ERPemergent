import React, { useState, useEffect } from 'react';
import { transportAPI, shippingAPI } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import { formatDate, getStatusColor } from '../lib/utils';
import { Plus, Truck, Edit2 } from 'lucide-react';

const VEHICLE_TYPES = ['Truck', 'Trailer', 'Flatbed', 'Container Chassis'];
const STATUSES = ['pending', 'dispatched', 'delivered'];

export default function TransportPage() {
  const { user } = useAuth();
  const [schedules, setSchedules] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [selectedSchedule, setSelectedSchedule] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');

  const [form, setForm] = useState({
    shipping_booking_id: '',
    transporter: '',
    vehicle_type: 'Truck',
    pickup_date: '',
    pickup_location: 'Factory',
    notes: '',
  });

  const [editForm, setEditForm] = useState({
    status: '',
    vehicle_number: '',
    driver_name: '',
    driver_phone: '',
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [schedulesRes, bookingsRes] = await Promise.all([
        transportAPI.getAll(),
        shippingAPI.getAll('confirmed'),
      ]);
      setSchedules(schedulesRes.data);
      setBookings(bookingsRes.data);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!form.shipping_booking_id || !form.transporter || !form.pickup_date) {
      toast.error('Please fill in all required fields');
      return;
    }
    try {
      await transportAPI.create(form);
      toast.success('Transport schedule created');
      setCreateOpen(false);
      setForm({ shipping_booking_id: '', transporter: '', vehicle_type: 'Truck', pickup_date: '', pickup_location: 'Factory', notes: '' });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create schedule');
    }
  };

  const handleEdit = async () => {
    try {
      const updateData = {};
      if (editForm.status) updateData.status = editForm.status;
      if (editForm.vehicle_number) updateData.vehicle_number = editForm.vehicle_number;
      if (editForm.driver_name) updateData.driver_name = editForm.driver_name;
      if (editForm.driver_phone) updateData.driver_phone = editForm.driver_phone;
      
      await transportAPI.update(selectedSchedule.id, updateData);
      toast.success('Schedule updated');
      setEditOpen(false);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update');
    }
  };

  const openEdit = (schedule) => {
    setSelectedSchedule(schedule);
    setEditForm({
      status: schedule.status,
      vehicle_number: schedule.vehicle_number || '',
      driver_name: schedule.driver_name || '',
      driver_phone: schedule.driver_phone || '',
    });
    setEditOpen(true);
  };

  const filteredSchedules = statusFilter === 'all' ? schedules : schedules.filter(s => s.status === statusFilter);
  const canCreate = ['admin', 'transport'].includes(user?.role);

  return (
    <div className="page-container" data-testid="transport-page">
      <div className="module-header">
        <div>
          <h1 className="module-title">Transport</h1>
          <p className="text-muted-foreground text-sm">Manage transport schedules and container pickups</p>
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
                <Button data-testid="create-schedule-btn" className="rounded-sm">
                  <Plus className="w-4 h-4 mr-2" /> New Schedule
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create Transport Schedule</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="form-field">
                    <Label>Shipping Booking</Label>
                    <Select value={form.shipping_booking_id} onValueChange={(v) => setForm({...form, shipping_booking_id: v})}>
                      <SelectTrigger data-testid="booking-select">
                        <SelectValue placeholder="Select shipping booking" />
                      </SelectTrigger>
                      <SelectContent>
                        {bookings.map(b => (
                          <SelectItem key={b.id} value={b.id}>
                            {b.booking_number} - {b.shipping_line} (Cutoff: {formatDate(b.cutoff_date)})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="form-grid">
                    <div className="form-field">
                      <Label>Transporter</Label>
                      <Input
                        value={form.transporter}
                        onChange={(e) => setForm({...form, transporter: e.target.value})}
                        placeholder="Transport company name"
                        data-testid="transporter-input"
                      />
                    </div>
                    <div className="form-field">
                      <Label>Vehicle Type</Label>
                      <Select value={form.vehicle_type} onValueChange={(v) => setForm({...form, vehicle_type: v})}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {VEHICLE_TYPES.map(t => (
                            <SelectItem key={t} value={t}>{t}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="form-grid">
                    <div className="form-field">
                      <Label>Pickup Date</Label>
                      <Input
                        type="date"
                        value={form.pickup_date}
                        onChange={(e) => setForm({...form, pickup_date: e.target.value})}
                        data-testid="pickup-date-input"
                      />
                    </div>
                    <div className="form-field">
                      <Label>Pickup Location</Label>
                      <Input
                        value={form.pickup_location}
                        onChange={(e) => setForm({...form, pickup_location: e.target.value})}
                        placeholder="Pickup location"
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
                    <Button onClick={handleCreate} data-testid="submit-schedule-btn">Create Schedule</Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {/* Schedules List */}
      <div className="data-grid">
        <div className="data-grid-header">
          <h3 className="font-medium">Transport Schedules ({filteredSchedules.length})</h3>
        </div>
        {loading ? (
          <div className="p-8 text-center text-muted-foreground">Loading...</div>
        ) : filteredSchedules.length === 0 ? (
          <div className="empty-state">
            <Truck className="empty-state-icon" />
            <p className="empty-state-title">No schedules found</p>
            <p className="empty-state-description">Create a transport schedule for container pickups</p>
          </div>
        ) : (
          <table className="erp-table w-full">
            <thead>
              <tr>
                <th>Schedule #</th>
                <th>Booking #</th>
                <th>Transporter</th>
                <th>Vehicle Type</th>
                <th>Pickup Date</th>
                <th>Vehicle #</th>
                <th>Driver</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredSchedules.map((schedule) => (
                <tr key={schedule.id} data-testid={`schedule-row-${schedule.schedule_number}`}>
                  <td className="font-medium">{schedule.schedule_number}</td>
                  <td>{schedule.booking_number}</td>
                  <td>{schedule.transporter}</td>
                  <td>{schedule.vehicle_type}</td>
                  <td>{formatDate(schedule.pickup_date)}</td>
                  <td>{schedule.vehicle_number || '-'}</td>
                  <td>
                    {schedule.driver_name ? (
                      <div>
                        <p className="text-sm">{schedule.driver_name}</p>
                        {schedule.driver_phone && <p className="text-xs text-muted-foreground">{schedule.driver_phone}</p>}
                      </div>
                    ) : '-'}
                  </td>
                  <td><Badge className={getStatusColor(schedule.status)}>{schedule.status}</Badge></td>
                  <td>
                    {canCreate && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEdit(schedule)}
                        data-testid={`edit-schedule-${schedule.schedule_number}`}
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
            <DialogTitle>Update Schedule {selectedSchedule?.schedule_number}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
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
            <div className="form-field">
              <Label>Vehicle Number</Label>
              <Input
                value={editForm.vehicle_number}
                onChange={(e) => setEditForm({...editForm, vehicle_number: e.target.value})}
                placeholder="Vehicle plate number"
              />
            </div>
            <div className="form-grid">
              <div className="form-field">
                <Label>Driver Name</Label>
                <Input
                  value={editForm.driver_name}
                  onChange={(e) => setEditForm({...editForm, driver_name: e.target.value})}
                  placeholder="Driver name"
                />
              </div>
              <div className="form-field">
                <Label>Driver Phone</Label>
                <Input
                  value={editForm.driver_phone}
                  onChange={(e) => setEditForm({...editForm, driver_phone: e.target.value})}
                  placeholder="Phone number"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
              <Button onClick={handleEdit} data-testid="update-schedule-btn">Update</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
