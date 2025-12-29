import React, { useState, useEffect } from 'react';
import { payablesAPI, grnAPI } from '../lib/api';
import { Button } from '../components/ui/button';
import { DollarSign, Check, Clock, AlertTriangle, FileText, X } from 'lucide-react';
import { toast } from 'sonner';

const PayablesPage = () => {
  const [bills, setBills] = useState([]);
  const [aging, setAging] = useState({ current: 0, '30_days': 0, '60_days': 0, '90_plus': 0 });
  const [pendingGRNs, setPendingGRNs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('bills');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [billsRes, grnsRes] = await Promise.all([
        payablesAPI.getBills(),
        grnAPI.getPendingPayables()
      ]);
      setBills(billsRes.data.bills || []);
      setAging(billsRes.data.aging || {});
      setPendingGRNs(grnsRes.data || []);
    } catch (error) {
      toast.error('Failed to load payables data');
    } finally {
      setLoading(false);
    }
  };

  const handleApproveBill = async (billId) => {
    try {
      await payablesAPI.approveBill(billId);
      toast.success('Bill approved for payment');
      loadData();
    } catch (error) {
      toast.error('Failed to approve bill');
    }
  };

  const handlePayBill = async (billId) => {
    try {
      await payablesAPI.payBill(billId);
      toast.success('Bill marked as paid');
      loadData();
    } catch (error) {
      toast.error('Failed to mark bill as paid');
    }
  };

  const handleApproveGRN = async (grnId) => {
    try {
      await grnAPI.payablesApprove(grnId, 'Approved for AP posting');
      toast.success('GRN approved for payables');
      loadData();
    } catch (error) {
      toast.error('Failed to approve GRN');
    }
  };

  const handleHoldGRN = async (grnId) => {
    try {
      await grnAPI.payablesHold(grnId, 'On hold for review');
      toast.success('GRN put on hold');
      loadData();
    } catch (error) {
      toast.error('Failed to hold GRN');
    }
  };

  const totalOutstanding = Object.values(aging).reduce((a, b) => a + b, 0);

  return (
    <div className="p-6 max-w-[1600px] mx-auto" data-testid="payables-page">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <DollarSign className="w-8 h-8 text-red-500" />
          Accounts Payable
        </h1>
        <p className="text-muted-foreground mt-1">Bills, GRN Approvals & Supplier Payments</p>
      </div>

      {/* Aging Summary */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <div className="glass p-4 rounded-lg border border-border">
          <p className="text-sm text-muted-foreground">Total Outstanding</p>
          <p className="text-2xl font-bold text-red-400">${totalOutstanding.toLocaleString()}</p>
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
          { id: 'grn', label: 'GRN Approvals', icon: FileText, count: pendingGRNs.length },
          { id: 'bills', label: 'Payable Bills', icon: DollarSign, count: bills.filter(b => b.status === 'PENDING').length },
        ].map((tab) => (
          <Button
            key={tab.id}
            variant={activeTab === tab.id ? 'default' : 'outline'}
            onClick={() => setActiveTab(tab.id)}
            data-testid={`tab-${tab.id}`}
          >
            <tab.icon className="w-4 h-4 mr-2" />
            {tab.label}
            {tab.count > 0 && (
              <span className="ml-2 px-1.5 py-0.5 text-xs rounded bg-red-500/20 text-red-400">{tab.count}</span>
            )}
          </Button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Loading...</div>
        </div>
      ) : (
        <>
          {/* GRN Approvals Tab */}
          {activeTab === 'grn' && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">GRN Pending Payables Review</h2>
              {pendingGRNs.length === 0 ? (
                <div className="glass p-8 rounded-lg border border-green-500/30 bg-green-500/5 text-center">
                  <Check className="w-12 h-12 text-green-500 mx-auto mb-4" />
                  <p className="text-green-400">All GRNs reviewed</p>
                </div>
              ) : (
                <div className="grid gap-4">
                  {pendingGRNs.map((grn) => (
                    <div key={grn.id} className="glass p-4 rounded-lg border border-amber-500/30" data-testid={`grn-${grn.id}`}>
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-bold">{grn.grn_number}</span>
                            <span className="px-2 py-0.5 rounded text-xs bg-amber-500/20 text-amber-400">
                              PENDING REVIEW
                            </span>
                          </div>
                          <p className="text-sm text-muted-foreground">Supplier: {grn.supplier}</p>
                          <p className="text-sm text-muted-foreground">Items: {grn.items?.length || 0}</p>
                          <p className="text-xs text-muted-foreground">
                            Received: {new Date(grn.received_at).toLocaleDateString()}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" onClick={() => handleApproveGRN(grn.id)} className="bg-green-500 hover:bg-green-600">
                            <Check className="w-4 h-4 mr-1" /> Approve
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => handleHoldGRN(grn.id)} className="border-amber-500/50 text-amber-400">
                            <Clock className="w-4 h-4 mr-1" /> Hold
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Bills Tab */}
          {activeTab === 'bills' && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">Payable Bills</h2>
              {bills.length === 0 ? (
                <div className="glass p-8 rounded-lg border border-border text-center">
                  <FileText className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-50" />
                  <p className="text-muted-foreground">No bills</p>
                </div>
              ) : (
                <div className="grid gap-4">
                  {bills.map((bill) => (
                    <div key={bill.id} className="glass p-4 rounded-lg border border-border" data-testid={`bill-${bill.id}`}>
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-bold">{bill.bill_number}</span>
                            <span className={`px-2 py-0.5 rounded text-xs ${
                              bill.status === 'PAID' ? 'bg-green-500/20 text-green-400' :
                              bill.status === 'APPROVED' ? 'bg-blue-500/20 text-blue-400' :
                              'bg-amber-500/20 text-amber-400'
                            }`}>
                              {bill.status}
                            </span>
                          </div>
                          <p className="text-sm text-muted-foreground">Type: {bill.ref_type}</p>
                          <p className="text-lg font-bold text-red-400">{bill.currency} {bill.amount?.toLocaleString()}</p>
                        </div>
                        <div className="flex gap-2">
                          {bill.status === 'PENDING' && (
                            <Button size="sm" onClick={() => handleApproveBill(bill.id)} className="bg-blue-500 hover:bg-blue-600">
                              Approve
                            </Button>
                          )}
                          {bill.status === 'APPROVED' && (
                            <Button size="sm" onClick={() => handlePayBill(bill.id)} className="bg-green-500 hover:bg-green-600">
                              Mark Paid
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
        </>
      )}
    </div>
  );
};

export default PayablesPage;
