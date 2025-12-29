# Manufacturing ERP System - PRD

## Original Problem Statement
Build a comprehensive ERP system for a manufacturing plant with complete procurement-to-production-to-dispatch workflow.

## User Personas (11 Roles)
- Admin, Sales, Finance, Production, Procurement, Inventory, Security, QC, Shipping, Transport, Documentation

---

## IMPLEMENTED FEATURES (December 29, 2025)

### Core Modules ✅
- Quotations, Sales Orders, Job Orders
- Products, Customers, Suppliers
- Users with role-based access

### Production ✅
- Drum Schedule with 600/day capacity
- Material requirements from BOMs (product_boms + packaging_boms)
- Blend reports

### Procurement ✅ (Redesigned)
- **RFQ for Products**: Job-based view showing material shortages
- **RFQ for Packaging**: Separate packaging material procurement
- Vendor selection with address auto-fill
- Billing/Shipping company selection
- Delivery date, Payment terms, Incoterms

### Finance ✅
- PO Approval workflow
- Email outbox (QUEUED when SMTP not configured)
- GRN payables review gate

### Payables (AP) ✅
- GRN approvals (4 pending)
- Payable bills with aging buckets
- Approve/Pay workflow

### Receivables (AR) ✅
- Local/Export invoices
- Aging buckets (Current/30/60/90+)
- Record payments

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
2. Receivables split into SPA/Local/Export
3. Payables ledger view
4. Production calendar integration with delivery dates

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
