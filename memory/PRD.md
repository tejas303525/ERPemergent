# Manufacturing ERP System - PRD

## Original Problem Statement
Build a comprehensive ERP system for a manufacturing plant with complete procurement-to-production-to-dispatch workflow.

## User Personas (11 Roles)
- Admin, Sales, Finance, Production, Procurement, Inventory, Security, QC, Shipping, Transport, Documentation

---

## IMPLEMENTED FEATURES (December 29, 2025)

### Core Modules ✅
- Quotations with net_weight_kg for packaging, Sales Orders, Job Orders
- Products, Customers, Suppliers
- Users with role-based access

### BOM Management ✅ (NEW)
- **Product BOMs**: Define raw materials per KG of finished product
- **Packaging BOMs**: Define packaging materials per drum
- BOM versioning with active flag
- Activation endpoints for both product and packaging BOMs

### Production ✅
- Drum Schedule with 600/day capacity
- Material requirements from BOMs (product_boms + packaging_boms)
- Blend reports

### Inventory ✅ (ENHANCED)
- **Finished Products Tab**: Traditional inventory with low stock alerts
- **Raw Materials Tab**: Status display (IN_STOCK, INBOUND, OUT_OF_STOCK)
- **Packaging Materials Tab**: Separate view for packaging inventory
- Correct status calculation: INBOUND for 0 on_hand with open POs

### Procurement ✅ (Redesigned)
- **RFQ for Products**: Job-based view showing material shortages
- **RFQ for Packaging**: Separate packaging material procurement
- Vendor selection with address auto-fill
- Billing/Shipping company selection
- Delivery date, Payment terms, **Incoterms (EXW, DDP, FOB, CFR, CIF)**
- Auto-Generate PR from BOM shortages (520 error FIXED)

### Finance ✅
- PO Approval workflow
- Email outbox (QUEUED when SMTP not configured)
- GRN payables review gate

### Payables (AP) ✅ (ENHANCED)
- **Supplier Ledger Tab**: Balance by supplier with totals
- **GRN Approvals Tab**: Pending GRNs for payables review
- **Bills by Type Tabs**: PO/RFQ, Transport, Shipping, Import
- Aging buckets: Current, 30 days, 60 days, 90+ days
- Approve/Pay workflow

### Receivables (AR) ✅ (ENHANCED)
- **Sales Contracts (SPA) Tab**: Outstanding balances with payment tracking
- **Local Invoices Tab**: Domestic invoices with aging
- **Export Invoices Tab**: International invoices with aging
- **Aging Report Tab**: Cross-type aging analysis
- Record payments functionality

### Logistics ✅
- Incoterm-based routing (EXW, DDP, FOB, CFR, CIF)
- PO routing to appropriate windows

### Security/QC ✅
- Inward checklists with weight
- QC inspections (PASS/FAIL/HOLD)

### Notifications ✅
- Bell icon with unread count
- Strict event triggers only:
  - RFQ_QUOTE_RECEIVED
  - PO_PENDING_APPROVAL
  - PRODUCTION_BLOCKED
  - GRN_PAYABLES_REVIEW

---

## PENDING FEATURES (Based on User Requirements)

### P0 - Critical
1. Transportation window inward/outward tables
2. Import window with document management
3. Security cargo flow completion

### P1 - High Priority
1. Document generation (Invoice, DO, COA, Packing List)
2. Production calendar integration with delivery dates

### P2 - Medium Priority
1. Auto-reminder emails
2. BL draft generation
3. COO generation

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
