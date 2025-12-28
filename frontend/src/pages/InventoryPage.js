import React, { useState, useEffect } from 'react';
import { inventoryAPI, productAPI } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { toast } from 'sonner';
import { formatDate } from '../lib/utils';
import { Boxes, AlertTriangle, TrendingUp, TrendingDown, Eye } from 'lucide-react';

const CATEGORIES = [
  { value: 'all', label: 'All Categories' },
  { value: 'raw_material', label: 'Raw Materials' },
  { value: 'packaging', label: 'Packaging' },
  { value: 'finished_product', label: 'Finished Products' },
];

export default function InventoryPage() {
  const [inventory, setInventory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [movementsOpen, setMovementsOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [movements, setMovements] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    loadData();
  }, [categoryFilter, lowStockOnly]);

  const loadData = async () => {
    try {
      const category = categoryFilter === 'all' ? null : categoryFilter;
      const res = await inventoryAPI.getAll(category, lowStockOnly || null);
      setInventory(res.data);
    } catch (error) {
      toast.error('Failed to load inventory');
    } finally {
      setLoading(false);
    }
  };

  const viewMovements = async (product) => {
    setSelectedProduct(product);
    try {
      const res = await inventoryAPI.getMovements(product.id);
      setMovements(res.data);
    } catch (error) {
      setMovements([]);
    }
    setMovementsOpen(true);
  };

  const filteredInventory = inventory.filter(p =>
    p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.sku.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const totalItems = inventory.length;
  const lowStockItems = inventory.filter(p => p.current_stock < p.min_stock).length;
  const totalValue = inventory.reduce((sum, p) => sum + (p.current_stock * p.price_usd), 0);

  return (
    <div className="page-container" data-testid="inventory-page">
      <div className="module-header">
        <div>
          <h1 className="module-title">Inventory</h1>
          <p className="text-muted-foreground text-sm">Track stock levels and movements</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-card border border-border rounded-sm p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="kpi-value">{totalItems}</p>
              <p className="kpi-label">Total Products</p>
            </div>
            <Boxes className="w-8 h-8 text-sky-400" />
          </div>
        </div>
        <div className="bg-card border border-border rounded-sm p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="kpi-value text-red-400">{lowStockItems}</p>
              <p className="kpi-label">Low Stock Items</p>
            </div>
            <AlertTriangle className="w-8 h-8 text-red-400" />
          </div>
        </div>
        <div className="bg-card border border-border rounded-sm p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="kpi-value text-emerald-400">${totalValue.toLocaleString()}</p>
              <p className="kpi-label">Total Value (USD)</p>
            </div>
            <TrendingUp className="w-8 h-8 text-emerald-400" />
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-6">
        <div className="w-64">
          <Input
            placeholder="Search by name or SKU..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            data-testid="search-input"
          />
        </div>
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-48" data-testid="category-filter">
            <SelectValue placeholder="Select category" />
          </SelectTrigger>
          <SelectContent>
            {CATEGORIES.map(c => (
              <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant={lowStockOnly ? 'default' : 'outline'}
          onClick={() => setLowStockOnly(!lowStockOnly)}
          data-testid="low-stock-filter"
        >
          <AlertTriangle className="w-4 h-4 mr-2" />
          Low Stock Only
        </Button>
      </div>

      {/* Inventory Table */}
      <div className="data-grid">
        <div className="data-grid-header">
          <h3 className="font-medium">Inventory Items ({filteredInventory.length})</h3>
        </div>
        {loading ? (
          <div className="p-8 text-center text-muted-foreground">Loading...</div>
        ) : filteredInventory.length === 0 ? (
          <div className="empty-state">
            <Boxes className="empty-state-icon" />
            <p className="empty-state-title">No inventory items found</p>
            <p className="empty-state-description">Add products to see them here</p>
          </div>
        ) : (
          <table className="erp-table w-full">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Product Name</th>
                <th>Category</th>
                <th>Current Stock</th>
                <th>Min Stock</th>
                <th>Unit</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredInventory.map((item) => {
                const isLowStock = item.current_stock < item.min_stock;
                return (
                  <tr key={item.id} data-testid={`inventory-row-${item.sku}`}>
                    <td className="font-medium">{item.sku}</td>
                    <td>{item.name}</td>
                    <td>
                      <Badge variant="outline" className="text-xs">
                        {item.category?.replace(/_/g, ' ').toUpperCase()}
                      </Badge>
                    </td>
                    <td className={`font-mono ${isLowStock ? 'text-red-400' : ''}`}>
                      {item.current_stock?.toLocaleString()}
                    </td>
                    <td className="font-mono text-muted-foreground">{item.min_stock?.toLocaleString()}</td>
                    <td>{item.unit}</td>
                    <td>
                      {isLowStock ? (
                        <Badge className="status-rejected">Low Stock</Badge>
                      ) : (
                        <Badge className="status-approved">In Stock</Badge>
                      )}
                    </td>
                    <td>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => viewMovements(item)}
                        data-testid={`view-movements-${item.sku}`}
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Movements Dialog */}
      <Dialog open={movementsOpen} onOpenChange={setMovementsOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Stock Movements - {selectedProduct?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div><span className="text-muted-foreground">SKU:</span> {selectedProduct?.sku}</div>
              <div><span className="text-muted-foreground">Current Stock:</span> <span className="font-mono">{selectedProduct?.current_stock}</span></div>
              <div><span className="text-muted-foreground">Unit:</span> {selectedProduct?.unit}</div>
            </div>

            {movements.length > 0 ? (
              <div className="data-grid max-h-96 overflow-y-auto">
                <table className="erp-table w-full">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Type</th>
                      <th>Reference</th>
                      <th>Qty</th>
                      <th>Previous</th>
                      <th>New</th>
                    </tr>
                  </thead>
                  <tbody>
                    {movements.map((m, idx) => (
                      <tr key={idx}>
                        <td>{formatDate(m.created_at)}</td>
                        <td>
                          <div className="flex items-center gap-2">
                            {m.movement_type === 'grn_add' ? (
                              <TrendingUp className="w-4 h-4 text-emerald-400" />
                            ) : (
                              <TrendingDown className="w-4 h-4 text-red-400" />
                            )}
                            <span>{m.movement_type?.replace(/_/g, ' ').toUpperCase()}</span>
                          </div>
                        </td>
                        <td>{m.reference_number}</td>
                        <td className={`font-mono ${m.movement_type === 'grn_add' ? 'text-emerald-400' : 'text-red-400'}`}>
                          {m.movement_type === 'grn_add' ? '+' : '-'}{m.quantity}
                        </td>
                        <td className="font-mono text-muted-foreground">{m.previous_stock}</td>
                        <td className="font-mono">{m.new_stock}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-center text-muted-foreground py-8">No movements recorded</p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
