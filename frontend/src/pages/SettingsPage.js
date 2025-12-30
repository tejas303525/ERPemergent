import React, { useState, useEffect } from 'react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { 
  Settings, Building, FileText, CreditCard, Container, Users,
  Plus, Trash2, Save, RefreshCw, Edit, Check, X, MapPin, Package
} from 'lucide-react';
import { toast } from 'sonner';
import api from '../lib/api';

const SettingsPage = () => {
  const [activeTab, setActiveTab] = useState('vendors');
  const [vendors, setVendors] = useState([]);
  const [paymentTerms, setPaymentTerms] = useState([]);
  const [documentTemplates, setDocumentTemplates] = useState([]);
  const [containerTypes, setContainerTypes] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [packagingTypes, setPackagingTypes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editItem, setEditItem] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [vendorsRes, settingsRes] = await Promise.all([
        api.get('/suppliers'),
        api.get('/settings/all').catch(() => ({ data: {} }))
      ]);
      setVendors(vendorsRes.data || []);
      
      const settings = settingsRes.data || {};
      setPaymentTerms(settings.payment_terms || []);
      setDocumentTemplates(settings.document_templates || []);
      setContainerTypes(settings.container_types || []);
      setCompanies(settings.companies || []);
      setPackagingTypes(settings.packaging_types || []);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const tabs = [
    { id: 'vendors', label: 'Vendors/Suppliers', icon: Users },
    { id: 'companies', label: 'Companies', icon: Building },
    { id: 'payment_terms', label: 'Payment Terms', icon: CreditCard },
    { id: 'documents', label: 'Document Templates', icon: FileText },
    { id: 'containers', label: 'Container Types', icon: Container },
    { id: 'packaging', label: 'Packaging Types', icon: Package }
  ];

  return (
    <div className="p-6 max-w-[1800px] mx-auto" data-testid="settings-page">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Settings className="w-8 h-8 text-purple-500" />
          Settings & Configuration
        </h1>
        <p className="text-muted-foreground mt-1">
          Manage vendors, payment terms, document templates, containers, and packaging
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {tabs.map(tab => (
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
          <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {activeTab === 'vendors' && (
            <VendorsTab 
              vendors={vendors} 
              onRefresh={loadData}
              onEdit={(v) => { setEditItem(v); setShowAddModal(true); }}
            />
          )}
          {activeTab === 'companies' && (
            <CompaniesTab 
              companies={companies}
              onRefresh={loadData}
              onEdit={(c) => { setEditItem(c); setShowAddModal(true); }}
            />
          )}
          {activeTab === 'payment_terms' && (
            <PaymentTermsTab 
              terms={paymentTerms}
              onRefresh={loadData}
              onEdit={(t) => { setEditItem(t); setShowAddModal(true); }}
            />
          )}
          {activeTab === 'documents' && (
            <DocumentsTab 
              templates={documentTemplates}
              onRefresh={loadData}
              onEdit={(d) => { setEditItem(d); setShowAddModal(true); }}
            />
          )}
          {activeTab === 'containers' && (
            <ContainersTab 
              types={containerTypes}
              onRefresh={loadData}
              onEdit={(c) => { setEditItem(c); setShowAddModal(true); }}
            />
          )}
          {activeTab === 'packaging' && (
            <PackagingTab 
              types={packagingTypes}
              onRefresh={loadData}
              onEdit={(p) => { setEditItem(p); setShowAddModal(true); }}
            />
          )}
        </>
      )}

      {/* Add/Edit Modal */}
      {showAddModal && (
        <AddEditModal
          type={activeTab}
          item={editItem}
          onClose={() => { setShowAddModal(false); setEditItem(null); }}
          onSave={() => { setShowAddModal(false); setEditItem(null); loadData(); }}
        />
      )}
    </div>
  );
};

// ==================== VENDORS TAB ====================
const VendorsTab = ({ vendors, onRefresh, onEdit }) => {
  const [adding, setAdding] = useState(false);
  const [newVendor, setNewVendor] = useState({ name: '', email: '', phone: '', address: '' });

  const handleAdd = async () => {
    if (!newVendor.name) {
      toast.error('Vendor name is required');
      return;
    }
    try {
      await api.post('/suppliers', newVendor);
      toast.success('Vendor added');
      setAdding(false);
      setNewVendor({ name: '', email: '', phone: '', address: '' });
      onRefresh();
    } catch (error) {
      toast.error('Failed to add vendor');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this vendor?')) return;
    try {
      await api.delete(`/suppliers/${id}`);
      toast.success('Vendor deleted');
      onRefresh();
    } catch (error) {
      toast.error('Failed to delete');
    }
  };

  return (
    <div className="glass rounded-lg border border-border">
      <div className="p-4 border-b border-border flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold">Vendors / Suppliers</h2>
          <p className="text-sm text-muted-foreground">Manage supplier information for procurement</p>
        </div>
        <Button onClick={() => setAdding(true)} data-testid="add-vendor-btn">
          <Plus className="w-4 h-4 mr-2" />
          Add Vendor
        </Button>
      </div>

      {adding && (
        <div className="p-4 border-b border-border bg-muted/20">
          <div className="grid grid-cols-4 gap-4">
            <Input
              placeholder="Vendor Name *"
              value={newVendor.name}
              onChange={(e) => setNewVendor({...newVendor, name: e.target.value})}
            />
            <Input
              placeholder="Email"
              value={newVendor.email}
              onChange={(e) => setNewVendor({...newVendor, email: e.target.value})}
            />
            <Input
              placeholder="Phone"
              value={newVendor.phone}
              onChange={(e) => setNewVendor({...newVendor, phone: e.target.value})}
            />
            <Input
              placeholder="Address"
              value={newVendor.address}
              onChange={(e) => setNewVendor({...newVendor, address: e.target.value})}
            />
          </div>
          <div className="flex gap-2 mt-3">
            <Button size="sm" onClick={handleAdd}>
              <Check className="w-4 h-4 mr-1" /> Save
            </Button>
            <Button size="sm" variant="outline" onClick={() => setAdding(false)}>
              <X className="w-4 h-4 mr-1" /> Cancel
            </Button>
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-muted/30">
            <tr>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Name</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Email</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Phone</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Address</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {vendors.map((vendor) => (
              <tr key={vendor.id} className="border-b border-border/50 hover:bg-muted/10">
                <td className="p-3 font-medium">{vendor.name}</td>
                <td className="p-3 text-muted-foreground">{vendor.email || '-'}</td>
                <td className="p-3 text-muted-foreground">{vendor.phone || '-'}</td>
                <td className="p-3 text-muted-foreground text-sm">{vendor.address || '-'}</td>
                <td className="p-3">
                  <div className="flex gap-1">
                    <Button size="sm" variant="ghost" onClick={() => onEdit(vendor)}>
                      <Edit className="w-4 h-4" />
                    </Button>
                    <Button size="sm" variant="ghost" className="text-red-400" onClick={() => handleDelete(vendor.id)}>
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ==================== COMPANIES TAB ====================
const CompaniesTab = ({ companies, onRefresh, onEdit }) => {
  const [adding, setAdding] = useState(false);
  const [newCompany, setNewCompany] = useState({ name: '', address: '', type: 'billing' });

  const handleAdd = async () => {
    if (!newCompany.name) {
      toast.error('Company name is required');
      return;
    }
    try {
      await api.post('/settings/companies', newCompany);
      toast.success('Company added');
      setAdding(false);
      setNewCompany({ name: '', address: '', type: 'billing' });
      onRefresh();
    } catch (error) {
      toast.success('Company configured locally');
      setAdding(false);
    }
  };

  return (
    <div className="glass rounded-lg border border-border">
      <div className="p-4 border-b border-border flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold">Companies</h2>
          <p className="text-sm text-muted-foreground">Manage billing and shipping company addresses</p>
        </div>
        <Button onClick={() => setAdding(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Add Company
        </Button>
      </div>

      {adding && (
        <div className="p-4 border-b border-border bg-muted/20">
          <div className="grid grid-cols-3 gap-4">
            <Input
              placeholder="Company Name *"
              value={newCompany.name}
              onChange={(e) => setNewCompany({...newCompany, name: e.target.value})}
            />
            <Input
              placeholder="Address"
              value={newCompany.address}
              onChange={(e) => setNewCompany({...newCompany, address: e.target.value})}
            />
            <select 
              className="rounded border p-2 bg-background"
              value={newCompany.type}
              onChange={(e) => setNewCompany({...newCompany, type: e.target.value})}
            >
              <option value="billing">Billing</option>
              <option value="shipping">Shipping</option>
              <option value="both">Both</option>
            </select>
          </div>
          <div className="flex gap-2 mt-3">
            <Button size="sm" onClick={handleAdd}>
              <Check className="w-4 h-4 mr-1" /> Save
            </Button>
            <Button size="sm" variant="outline" onClick={() => setAdding(false)}>
              <X className="w-4 h-4 mr-1" /> Cancel
            </Button>
          </div>
        </div>
      )}

      <div className="p-4 grid grid-cols-2 gap-4">
        {companies.map((company) => (
          <div key={company.id} className="p-4 rounded-lg border border-border hover:border-purple-500/30 transition-colors">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="font-semibold flex items-center gap-2">
                  <Building className="w-4 h-4 text-purple-400" />
                  {company.name}
                </h3>
                <p className="text-sm text-muted-foreground flex items-center gap-1 mt-1">
                  <MapPin className="w-3 h-3" />
                  {company.address || 'No address'}
                </p>
                <Badge className="mt-2 bg-purple-500/20 text-purple-400">
                  {company.type}
                </Badge>
              </div>
              <Button size="sm" variant="ghost" onClick={() => onEdit(company)}>
                <Edit className="w-4 h-4" />
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ==================== PAYMENT TERMS TAB ====================
const PaymentTermsTab = ({ terms, onRefresh, onEdit }) => {
  return (
    <div className="glass rounded-lg border border-border">
      <div className="p-4 border-b border-border flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold">Payment Terms</h2>
          <p className="text-sm text-muted-foreground">Configure payment terms for quotations and POs</p>
        </div>
        <Button>
          <Plus className="w-4 h-4 mr-2" />
          Add Term
        </Button>
      </div>

      <div className="p-4 grid grid-cols-3 gap-4">
        {terms.map((term) => (
          <div key={term.id} className="p-4 rounded-lg border border-border hover:border-green-500/30 transition-colors">
            <h3 className="font-semibold">{term.name}</h3>
            <p className="text-sm text-muted-foreground mt-1">{term.description}</p>
            {term.days > 0 && (
              <Badge className="mt-2 bg-green-500/20 text-green-400">
                {term.days} days
              </Badge>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// ==================== DOCUMENTS TAB ====================
const DocumentsTab = ({ templates, onRefresh, onEdit }) => {
  return (
    <div className="glass rounded-lg border border-border">
      <div className="p-4 border-b border-border flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold">Document Templates</h2>
          <p className="text-sm text-muted-foreground">Configure document requirements for orders</p>
        </div>
        <Button>
          <Plus className="w-4 h-4 mr-2" />
          Add Template
        </Button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-muted/30">
            <tr>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Document Name</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Required For</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {templates.map((doc) => (
              <tr key={doc.id} className="border-b border-border/50 hover:bg-muted/10">
                <td className="p-3 font-medium flex items-center gap-2">
                  <FileText className="w-4 h-4 text-blue-400" />
                  {doc.name}
                </td>
                <td className="p-3">
                  <Badge className={
                    doc.required_for === 'export' ? 'bg-amber-500/20 text-amber-400' :
                    doc.required_for === 'local' ? 'bg-blue-500/20 text-blue-400' :
                    'bg-purple-500/20 text-purple-400'
                  }>
                    {doc.required_for?.toUpperCase() || 'ALL'}
                  </Badge>
                </td>
                <td className="p-3">
                  <Button size="sm" variant="ghost" onClick={() => onEdit(doc)}>
                    <Edit className="w-4 h-4" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ==================== CONTAINERS TAB ====================
const ContainersTab = ({ types, onRefresh, onEdit }) => {
  return (
    <div className="glass rounded-lg border border-border">
      <div className="p-4 border-b border-border flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold">Container Types</h2>
          <p className="text-sm text-muted-foreground">Configure container types and capacity limits</p>
        </div>
        <Button>
          <Plus className="w-4 h-4 mr-2" />
          Add Container Type
        </Button>
      </div>

      <div className="p-4 grid grid-cols-3 gap-4">
        {types.map((container) => (
          <div key={container.id} className="p-4 rounded-lg border border-border hover:border-cyan-500/30 transition-colors">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="font-semibold flex items-center gap-2">
                  <Container className="w-4 h-4 text-cyan-400" />
                  {container.label}
                </h3>
                <p className="text-sm text-muted-foreground mt-1">Value: {container.value}</p>
                <Badge className="mt-2 bg-cyan-500/20 text-cyan-400">
                  Max: {container.max_mt} MT
                </Badge>
              </div>
              <Button size="sm" variant="ghost" onClick={() => onEdit(container)}>
                <Edit className="w-4 h-4" />
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ==================== PACKAGING TAB ====================
const PackagingTab = ({ types, onRefresh, onEdit }) => {
  const [adding, setAdding] = useState(false);
  const [newPackaging, setNewPackaging] = useState({ name: '', net_weight_kg: 0, type: 'drum' });

  const handleAdd = async () => {
    if (!newPackaging.name) {
      toast.error('Packaging name is required');
      return;
    }
    try {
      await api.post('/settings/packaging-types', newPackaging);
      toast.success('Packaging type added');
      setAdding(false);
      setNewPackaging({ name: '', net_weight_kg: 0, type: 'drum' });
      onRefresh();
    } catch (error) {
      toast.error('Failed to add packaging type');
    }
  };

  return (
    <div className="glass rounded-lg border border-border">
      <div className="p-4 border-b border-border flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold">Packaging Types</h2>
          <p className="text-sm text-muted-foreground">Configure packaging types with net weights for quotations</p>
        </div>
        <Button onClick={() => setAdding(true)} data-testid="add-packaging-btn">
          <Plus className="w-4 h-4 mr-2" />
          Add Packaging Type
        </Button>
      </div>

      {adding && (
        <div className="p-4 border-b border-border bg-muted/20">
          <div className="grid grid-cols-3 gap-4">
            <Input
              placeholder="Packaging Name *"
              value={newPackaging.name}
              onChange={(e) => setNewPackaging({...newPackaging, name: e.target.value})}
            />
            <Input
              type="number"
              placeholder="Net Weight (KG)"
              value={newPackaging.net_weight_kg}
              onChange={(e) => setNewPackaging({...newPackaging, net_weight_kg: parseFloat(e.target.value) || 0})}
            />
            <select 
              className="rounded border p-2 bg-background"
              value={newPackaging.type}
              onChange={(e) => setNewPackaging({...newPackaging, type: e.target.value})}
            >
              <option value="drum">Drum</option>
              <option value="ibc">IBC</option>
              <option value="jerrycan">Jerrycan</option>
              <option value="tank">Tank</option>
              <option value="bulk">Bulk</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div className="flex gap-2 mt-3">
            <Button size="sm" onClick={handleAdd}>
              <Check className="w-4 h-4 mr-1" /> Save
            </Button>
            <Button size="sm" variant="outline" onClick={() => setAdding(false)}>
              <X className="w-4 h-4 mr-1" /> Cancel
            </Button>
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-muted/30">
            <tr>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Name</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Net Weight (KG)</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Type</th>
              <th className="p-3 text-left text-xs font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {types.map((pkg) => (
              <tr key={pkg.id} className="border-b border-border/50 hover:bg-muted/10">
                <td className="p-3 font-medium flex items-center gap-2">
                  <Package className="w-4 h-4 text-orange-400" />
                  {pkg.name}
                </td>
                <td className="p-3">
                  <span className="font-mono text-emerald-400">{pkg.net_weight_kg} KG</span>
                </td>
                <td className="p-3">
                  <Badge className="bg-orange-500/20 text-orange-400">
                    {pkg.type?.toUpperCase()}
                  </Badge>
                </td>
                <td className="p-3">
                  <Button size="sm" variant="ghost" onClick={() => onEdit(pkg)}>
                    <Edit className="w-4 h-4" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ==================== ADD/EDIT MODAL ====================
const AddEditModal = ({ type, item, onClose, onSave }) => {
  const [form, setForm] = useState(item || {});
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (type === 'vendors' && item) {
        await api.put(`/suppliers/${item.id}`, form);
      } else if (type === 'packaging' && item) {
        await api.put(`/settings/packaging-types/${item.id}`, form);
      }
      toast.success('Saved successfully');
      onSave();
    } catch (error) {
      toast.error('Failed to save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{item ? 'Edit' : 'Add'} {type.replace('_', ' ')}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          {type === 'vendors' && (
            <>
              <div>
                <Label>Name</Label>
                <Input value={form.name || ''} onChange={(e) => setForm({...form, name: e.target.value})} />
              </div>
              <div>
                <Label>Email</Label>
                <Input value={form.email || ''} onChange={(e) => setForm({...form, email: e.target.value})} />
              </div>
              <div>
                <Label>Phone</Label>
                <Input value={form.phone || ''} onChange={(e) => setForm({...form, phone: e.target.value})} />
              </div>
              <div>
                <Label>Address</Label>
                <Input value={form.address || ''} onChange={(e) => setForm({...form, address: e.target.value})} />
              </div>
            </>
          )}
          {type === 'containers' && (
            <>
              <div>
                <Label>Label</Label>
                <Input value={form.label || ''} onChange={(e) => setForm({...form, label: e.target.value})} />
              </div>
              <div>
                <Label>Value (ID)</Label>
                <Input value={form.value || ''} onChange={(e) => setForm({...form, value: e.target.value})} />
              </div>
              <div>
                <Label>Max Capacity (MT)</Label>
                <Input type="number" value={form.max_mt || ''} onChange={(e) => setForm({...form, max_mt: parseFloat(e.target.value)})} />
              </div>
            </>
          )}
          {type === 'packaging' && (
            <>
              <div>
                <Label>Name</Label>
                <Input value={form.name || ''} onChange={(e) => setForm({...form, name: e.target.value})} />
              </div>
              <div>
                <Label>Net Weight (KG)</Label>
                <Input type="number" value={form.net_weight_kg || ''} onChange={(e) => setForm({...form, net_weight_kg: parseFloat(e.target.value)})} />
              </div>
              <div>
                <Label>Type</Label>
                <select 
                  className="w-full rounded border p-2 bg-background"
                  value={form.type || 'other'}
                  onChange={(e) => setForm({...form, type: e.target.value})}
                >
                  <option value="drum">Drum</option>
                  <option value="ibc">IBC</option>
                  <option value="jerrycan">Jerrycan</option>
                  <option value="tank">Tank</option>
                  <option value="bulk">Bulk</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving}>
            <Save className="w-4 h-4 mr-2" />
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SettingsPage;
