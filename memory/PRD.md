# Manufacturing ERP System - PRD

## Original Problem Statement
Build a comprehensive ERP system for a manufacturing plant with complete procurement-to-production-to-dispatch workflow.

## User Personas (11 Roles)
- Admin, Sales, Finance, Production, Procurement, Inventory, Security, QC, Shipping, Transport, Documentation

---

## PHASE 1 IMPLEMENTATION - PRODUCTION SCHEDULING FOCUS (December 29, 2025)

### ✅ Quotation Calculation (FIXED)
- **Formula**: For packaged items: `(net_weight_kg × qty) / 1000 = MT × unit_price`
- **Formula**: For Bulk: `quantity × unit_price` (quantity assumed in MT)
- Added `weight_mt` field to quotation items
- Example: 100 drums × 200kg = 20 MT × $1500/MT = $30,000

### ✅ Material Availability Check on Quotation Approval
- When quotation is approved, system checks:
  1. Raw material availability from product BOM
  2. Packaging material availability from packaging BOM
- Creates `material_shortages` records for procurement
- Notifies procurement team of shortages

### ✅ Unified Production Schedule (Merged Drum + Production)
- **Capacity**: 600 drums/day constraint
- **Spillover**: Jobs exceeding daily capacity move to next day
- **Material Status**: Shows `material_ready` and `shortage_items` per job
- **Date Range**: Configurable 7/14/21/30 day view
- **Utilization**: Shows % capacity used per day

### ✅ Incoterm-Based PO Routing
After PO is approved by Finance:
- **EXW** → Transportation Window (Inward)
- **DDP** → Security & QC Module
- **FOB** → Shipping Module
- **CFR/CIF** → Import Window

### ✅ Transport Window (4 Tables)
1. **Inward (EXW/Import)** - Incoming materials from suppliers
2. **Outward - Local** - Local deliveries
3. **Outward - Container** - Container shipping
4. **Dispatch Summary** - Overview of all dispatches

### ✅ Import Window
- **Status Flow**: PENDING_DOCS → IN_TRANSIT → AT_PORT → CLEARED → COMPLETED
- **Document Checklist** (8 types):
  - Required: Commercial Invoice, Packing List, Bill of Lading, COO, COA
  - Optional: Insurance Certificate, Phytosanitary Certificate, MSDS
- Auto-creates Transport Inward when completed

### ✅ BOM Management
- Product BOMs: Raw materials per KG of finished product
- Packaging BOMs: Materials per drum
- Version control with active flag

### ✅ Quotation Net Weight
- Added `net_weight_kg` field for packaged items
- Conditional display (only for non-Bulk packaging)
- Correct calculation in both frontend and backend

---

## PENDING FEATURES (PHASE 2+)

### P0 - Critical
1. Security cargo flow completion (inward checklist → QC)
2. Document generation (Invoice, DO, COA, Packing List)
3. Transport PO generation and finance approval

### P1 - High Priority
1. Production calendar integration with delivery dates
2. Auto-scheduling based on material arrival
3. Shipping window export table (Job Order chronology)

### P2 - Future
1. Auto-reminder emails
2. BL draft generation
3. COO generation

---

## Database Collections
- `quotations`, `sales_orders`, `job_orders`
- `products`, `customers`, `suppliers`
- `inventory_items`, `inventory_balances`
- `product_boms`, `product_bom_items`
- `packaging_boms`, `packaging_bom_items`
- `purchase_orders`, `rfq`
- `transport_inward`, `transport_outward`
- `imports`, `material_shortages`
- `security_checklists`, `qc_inspections`
- `payables_bills`, `receivables_invoices`
- `notifications`

---

## Test Credentials
- **Admin**: admin@erp.com / admin123
- **Sales**: sales@erp.com / sales123
- **Finance**: finance@erp.com / finance123
- **Production**: production@erp.com / production123

---

## KEY DATA FLOWS

### Procurement → Finance → Logistics
```
Shortages (from BOMs) → RFQ → Quote → PO (DRAFT)
    → Finance Approve → Send to Vendor
    → Based on Incoterm:
        LOCAL (EXW/DDP) → Transport Inward
        IMPORT (FOB/CFR) → Shipping/Import Window
```

### Inward Cargo Flow
```
PO Received → Security Checklist → Weight
    → QC Inspection → GRN → Payables Review
    → AP Posting
```

### Outward Cargo Flow
```
Job Complete → Delivery Order → Security Checklist
    → QC Checklist → Documents → Receivables
```

---

## TEST CREDENTIALS
- Admin: admin@erp.com / admin123
- Finance: finance@erp.com / finance123
- Production: production@erp.com / production123

---

## NOTES
- SMTP not configured (emails remain QUEUED)
- Material shortages derived from BOMs only
- 600 drums/day capacity is hard limit
