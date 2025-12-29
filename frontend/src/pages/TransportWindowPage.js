import React, { useState, useEffect } from 'react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { 
  Truck, ArrowDownToLine, ArrowUpFromLine, Package, Check, Clock, 
  AlertTriangle, FileText, Plus, Calendar, MapPin, Search
} from 'lucide-react';
import { toast } from 'sonner';
import api from '../lib/api';

const TransportWindowPage = () => {
  const [activeTab, setActiveTab] = useState('inward');
  const [inwardTransports, setInwardTransports] = useState([]);
  const [outwardTransports, setOutwardTransports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [inwardRes, outwardRes] = await Promise.all([
        api.get('/transport/inward'),
        api.get('/transport/outward')
      ]);
      setInwardTransports(inwardRes.data || []);
      setOutwardTransports(outwardRes.data || []);
    } catch (error) {
      // If endpoints don't exist yet, show empty
      setInwardTransports([]);
      setOutwardTransports([]);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusUpdate = async (id, status, type) => {
    try {
      await api.put(`/transport/${type}/${id}/status`, { status });
      toast.success(`Transport ${status.toLowerCase()}`);
      loadData();
    } catch (error) {
      toast.error('Failed to update status');
    }
  };

  // Stats
  const inwardPending = inwardTransports.filter(t => t.status === 'PENDING').length;
  const inwardInTransit = inwardTransports.filter(t => t.status === 'IN_TRANSIT').length;
  const outwardPending = outwardTransports.filter(t => t.status === 'PENDING').length;

  return (
    <div className="p-6 max-w-[1800px] mx-auto" data-testid="transport-window-page">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Truck className="w-8 h-8 text-blue-500" />
          Transport Window
        </h1>
        <p className="text-muted-foreground mt-1">Manage inward and outward transport schedules</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="glass p-4 rounded-lg border border-blue-500/30">
          <p className="text-sm text-muted-foreground">Inward Pending</p>
          <p className="text-2xl font-bold text-blue-400">{inwardPending}</p>
        </div>
        <div className="glass p-4 rounded-lg border border-cyan-500/30">
          <p className="text-sm text-muted-foreground">In Transit</p>
          <p className="text-2xl font-bold text-cyan-400">{inwardInTransit}</p>
        </div>
        <div className="glass p-4 rounded-lg border border-amber-500/30">
          <p className="text-sm text-muted-foreground">Outward Pending</p>
          <p className="text-2xl font-bold text-amber-400">{outwardPending}</p>
        </div>
        <div className="glass p-4 rounded-lg border border-green-500/30">
          <p className="text-sm text-muted-foreground">Total Active</p>
          <p className="text-2xl font-bold text-green-400">{inwardTransports.length + outwardTransports.length}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <Button
          variant={activeTab === 'inward' ? 'default' : 'outline'}
          onClick={() => setActiveTab('inward')}
          data-testid="tab-inward"
        >
          <ArrowDownToLine className="w-4 h-4 mr-2" />
          Inward Transport
          {inwardPending > 0 && (
            <span className="ml-2 px-1.5 py-0.5 text-xs rounded bg-blue-500/20 text-blue-400">{inwardPending}</span>
          )}
        </Button>
        <Button
          variant={activeTab === 'outward' ? 'default' : 'outline'}
          onClick={() => setActiveTab('outward')}
          data-testid="tab-outward"
        >
          <ArrowUpFromLine className="w-4 h-4 mr-2" />
          Outward Transport
          {outwardPending > 0 && (
            <span className="ml-2 px-1.5 py-0.5 text-xs rounded bg-amber-500/20 text-amber-400">{outwardPending}</span>
          )}
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Loading...</div>
        </div>
      ) : (
        <>
          {/* Inward Transport Tab */}
          {activeTab === 'inward' && (
            <InwardTransportTab 
              transports={inwardTransports}
              onStatusUpdate={(id, status) => handleStatusUpdate(id, status, 'inward')}
              onRefresh={loadData}
            />
          )}

          {/* Outward Transport Tab */}
          {activeTab === 'outward' && (
            <OutwardTransportTab 
              transports={outwardTransports}
              onStatusUpdate={(id, status) => handleStatusUpdate(id, status, 'outward')}
              onRefresh={loadData}
            />
          )}
        </>
      )}
    </div>
  );
};

// Inward Transport Tab
const InwardTransportTab = ({ transports, onStatusUpdate, onRefresh }) => {
  const [filter, setFilter] = useState('all');
  
  const filtered = filter === 'all' 
    ? transports 
    : transports.filter(t => t.status === filter);

  const statusColors = {
    PENDING: 'bg-gray-500/20 text-gray-400',
    SCHEDULED: 'bg-blue-500/20 text-blue-400',
    IN_TRANSIT: 'bg-cyan-500/20 text-cyan-400',
    ARRIVED: 'bg-green-500/20 text-green-400',
    COMPLETED: 'bg-emerald-500/20 text-emerald-400'
  };

  return (
    <div className="space-y-4">
      {/* Filter */}
      <div className="flex gap-2 flex-wrap">
        {['all', 'PENDING', 'SCHEDULED', 'IN_TRANSIT', 'ARRIVED'].map(status => (
          <Button
            key={status}
            size="sm"
            variant={filter === status ? 'default' : 'outline'}
            onClick={() => setFilter(status)}
          >
            {status === 'all' ? 'All' : status.replace(/_/g, ' ')}
          </Button>
        ))}
      </div>

      {/* Table */}
      <div className="glass rounded-lg border border-border overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted/30">
            <tr>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Transport #</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">PO Reference</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Supplier</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Vehicle</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Driver</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">ETA</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Status</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="p-8 text-center text-muted-foreground">
                  <Truck className="w-12 h-12 mx-auto mb-4 opacity-30" />
                  <p>No inward transports</p>
                </td>
              </tr>
            ) : (
              filtered.map(transport => (
                <tr key={transport.id} className="border-t border-border/50 hover:bg-muted/10">
                  <td className="p-3 font-medium font-mono">{transport.transport_number}</td>
                  <td className="p-3 text-blue-400">{transport.po_number}</td>
                  <td className="p-3">{transport.supplier_name}</td>
                  <td className="p-3">{transport.vehicle_number || '-'}</td>
                  <td className="p-3">{transport.driver_name || '-'}</td>
                  <td className="p-3">
                    {transport.eta ? new Date(transport.eta).toLocaleDateString() : '-'}
                  </td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${statusColors[transport.status] || statusColors.PENDING}`}>
                      {transport.status}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="flex gap-1">
                      {transport.status === 'PENDING' && (
                        <Button size="sm" onClick={() => onStatusUpdate(transport.id, 'SCHEDULED')}>
                          Schedule
                        </Button>
                      )}
                      {transport.status === 'SCHEDULED' && (
                        <Button size="sm" onClick={() => onStatusUpdate(transport.id, 'IN_TRANSIT')}>
                          Dispatch
                        </Button>
                      )}
                      {transport.status === 'IN_TRANSIT' && (
                        <Button size="sm" onClick={() => onStatusUpdate(transport.id, 'ARRIVED')} className="bg-green-500 hover:bg-green-600">
                          Mark Arrived
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// Outward Transport Tab
const OutwardTransportTab = ({ transports, onStatusUpdate, onRefresh }) => {
  const [filter, setFilter] = useState('all');
  
  const filtered = filter === 'all' 
    ? transports 
    : transports.filter(t => t.status === filter);

  const statusColors = {
    PENDING: 'bg-gray-500/20 text-gray-400',
    LOADING: 'bg-amber-500/20 text-amber-400',
    DISPATCHED: 'bg-blue-500/20 text-blue-400',
    DELIVERED: 'bg-green-500/20 text-green-400'
  };

  return (
    <div className="space-y-4">
      {/* Filter */}
      <div className="flex gap-2 flex-wrap">
        {['all', 'PENDING', 'LOADING', 'DISPATCHED', 'DELIVERED'].map(status => (
          <Button
            key={status}
            size="sm"
            variant={filter === status ? 'default' : 'outline'}
            onClick={() => setFilter(status)}
          >
            {status === 'all' ? 'All' : status}
          </Button>
        ))}
      </div>

      {/* Table */}
      <div className="glass rounded-lg border border-border overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted/30">
            <tr>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Transport #</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">DO Reference</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Customer</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Vehicle</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Destination</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Dispatch Date</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Status</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="p-8 text-center text-muted-foreground">
                  <Truck className="w-12 h-12 mx-auto mb-4 opacity-30" />
                  <p>No outward transports</p>
                </td>
              </tr>
            ) : (
              filtered.map(transport => (
                <tr key={transport.id} className="border-t border-border/50 hover:bg-muted/10">
                  <td className="p-3 font-medium font-mono">{transport.transport_number}</td>
                  <td className="p-3 text-amber-400">{transport.do_number}</td>
                  <td className="p-3">{transport.customer_name}</td>
                  <td className="p-3">{transport.vehicle_number || '-'}</td>
                  <td className="p-3 text-sm">{transport.destination || '-'}</td>
                  <td className="p-3">
                    {transport.dispatch_date ? new Date(transport.dispatch_date).toLocaleDateString() : '-'}
                  </td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${statusColors[transport.status] || statusColors.PENDING}`}>
                      {transport.status}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="flex gap-1">
                      {transport.status === 'PENDING' && (
                        <Button size="sm" onClick={() => onStatusUpdate(transport.id, 'LOADING')}>
                          Start Loading
                        </Button>
                      )}
                      {transport.status === 'LOADING' && (
                        <Button size="sm" onClick={() => onStatusUpdate(transport.id, 'DISPATCHED')} className="bg-blue-500 hover:bg-blue-600">
                          Dispatch
                        </Button>
                      )}
                      {transport.status === 'DISPATCHED' && (
                        <Button size="sm" onClick={() => onStatusUpdate(transport.id, 'DELIVERED')} className="bg-green-500 hover:bg-green-600">
                          Confirm Delivered
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TransportWindowPage;
