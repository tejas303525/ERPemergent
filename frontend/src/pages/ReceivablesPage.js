import React, { useState, useEffect } from 'react';
import { receivablesAPI } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Receipt, Check, Clock, AlertTriangle, FileText, Plus } from 'lucide-react';
import { toast } from 'sonner';

const ReceivablesPage = () => {
  const [invoices, setInvoices] = useState([]);
  const [aging, setAging] = useState({ current: 0, '30_days': 0, '60_days': 0, '90_plus': 0 });
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [showPaymentModal, setShowPaymentModal] = useState(null);
  const [paymentAmount, setPaymentAmount] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await receivablesAPI.getInvoices();
      setInvoices(res.data.invoices || []);
      setAging(res.data.aging || {});
    } catch (error) {
      toast.error('Failed to load receivables data');
    } finally {
      setLoading(false);
    }
  };

  const handleRecordPayment = async () => {
    if (!paymentAmount || parseFloat(paymentAmount) <= 0) {
      toast.error('Enter a valid payment amount');
      return;
    }
    try {
      await receivablesAPI.recordPayment(showPaymentModal.id, parseFloat(paymentAmount));
      toast.success('Payment recorded');
      setShowPaymentModal(null);
      setPaymentAmount('');
      loadData();
    } catch (error) {
      toast.error('Failed to record payment');
    }
  };

  const totalOutstanding = Object.values(aging).reduce((a, b) => a + b, 0);

  const filteredInvoices = activeTab === 'all' ? invoices : 
    activeTab === 'local' ? invoices.filter(i => i.invoice_type === 'LOCAL') :
    activeTab === 'export' ? invoices.filter(i => i.invoice_type === 'EXPORT') :
    invoices.filter(i => i.status === 'OVERDUE' || (aging['90_plus'] > 0));

  return (
    <div className="p-6 max-w-[1600px] mx-auto" data-testid="receivables-page">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Receipt className="w-8 h-8 text-green-500" />
          Accounts Receivable
        </h1>
        <p className="text-muted-foreground mt-1">Invoices, Collections & Customer Payments</p>
      </div>

      {/* Aging Summary */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <div className="glass p-4 rounded-lg border border-border">
          <p className="text-sm text-muted-foreground">Total Outstanding</p>
          <p className="text-2xl font-bold text-green-400">${totalOutstanding.toLocaleString()}</p>
        </div>
        <div className="glass p-4 rounded-lg border border-green-500/30">
          <p className="text-sm text-muted-foreground">Current</p>
          <p className="text-xl font-bold text-green-400">${aging.current?.toLocaleString() || 0}</p>
        </div>
        <div className="glass p-4 rounded-lg border border-yellow-500/30">
          <p className="text-sm text-muted-foreground">30 Days</p>
          <p className="text-xl font-bold text-yellow-400">${aging['30_days']?.toLocaleString() || 0}</p>
        </div>
        <div className="glass p-4 rounded-lg border border-orange-500/30">
          <p className="text-sm text-muted-foreground">60 Days</p>
          <p className="text-xl font-bold text-orange-400">${aging['60_days']?.toLocaleString() || 0}</p>
        </div>
        <div className="glass p-4 rounded-lg border border-red-500/30">
          <p className="text-sm text-muted-foreground">90+ Days</p>
          <p className="text-xl font-bold text-red-400">${aging['90_plus']?.toLocaleString() || 0}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'all', label: 'All Invoices', count: invoices.length },
          { id: 'local', label: 'Local', count: invoices.filter(i => i.invoice_type === 'LOCAL').length },
          { id: 'export', label: 'Export', count: invoices.filter(i => i.invoice_type === 'EXPORT').length },
        ].map((tab) => (
          <Button
            key={tab.id}
            variant={activeTab === tab.id ? 'default' : 'outline'}
            onClick={() => setActiveTab(tab.id)}
            data-testid={`tab-${tab.id}`}
          >
            {tab.label}
            {tab.count > 0 && (
              <span className="ml-2 px-1.5 py-0.5 text-xs rounded bg-white/20">{tab.count}</span>
            )}
          </Button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Loading...</div>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredInvoices.length === 0 ? (
            <div className="glass p-8 rounded-lg border border-border text-center">
              <FileText className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-50" />
              <p className="text-muted-foreground">No invoices</p>
            </div>
          ) : (
            <div className="grid gap-4">
              {filteredInvoices.map((inv) => (
                <div key={inv.id} className="glass p-4 rounded-lg border border-border" data-testid={`invoice-${inv.id}`}>
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-bold">{inv.invoice_number}</span>
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          inv.invoice_type === 'EXPORT' ? 'bg-blue-500/20 text-blue-400' : 'bg-gray-500/20 text-gray-400'
                        }`}>
                          {inv.invoice_type}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          inv.status === 'PAID' ? 'bg-green-500/20 text-green-400' :
                          inv.status === 'PARTIAL' ? 'bg-amber-500/20 text-amber-400' :
                          inv.status === 'OVERDUE' ? 'bg-red-500/20 text-red-400' :
                          'bg-gray-500/20 text-gray-400'
                        }`}>
                          {inv.status}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground">Customer ID: {inv.customer_id}</p>
                      <div className="flex gap-4 mt-2">
                        <div>
                          <p className="text-xs text-muted-foreground">Amount</p>
                          <p className="font-bold text-green-400">{inv.currency} {inv.amount?.toLocaleString()}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Paid</p>
                          <p className="font-bold">{inv.currency} {inv.amount_paid?.toLocaleString() || 0}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Balance</p>
                          <p className="font-bold text-amber-400">{inv.currency} {((inv.amount || 0) - (inv.amount_paid || 0)).toLocaleString()}</p>
                        </div>
                      </div>
                    </div>
                    <div>
                      {inv.status !== 'PAID' && (
                        <Button size="sm" onClick={() => setShowPaymentModal(inv)} className="bg-green-500 hover:bg-green-600">
                          <Plus className="w-4 h-4 mr-1" /> Record Payment
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Payment Modal */}
      {showPaymentModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-background border border-border rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-bold mb-4">Record Payment - {showPaymentModal.invoice_number}</h3>
            <div className="mb-4">
              <p className="text-sm text-muted-foreground mb-2">
                Outstanding: {showPaymentModal.currency} {((showPaymentModal.amount || 0) - (showPaymentModal.amount_paid || 0)).toLocaleString()}
              </p>
              <Input
                type="number"
                placeholder="Payment amount"
                value={paymentAmount}
                onChange={(e) => setPaymentAmount(e.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowPaymentModal(null)}>Cancel</Button>
              <Button onClick={handleRecordPayment} className="bg-green-500 hover:bg-green-600">
                Record Payment
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReceivablesPage;
