# Manufacturing ERP System - PRD

## Original Problem Statement
Build a comprehensive ERP system for a production plant manufacturing unit with:
- Sales, quotation generation, quotation approval
- Quotation to Sales Order (SPA) conversion
- Payment tracking from SPA
- Job orders for manufacturing
- Production, procurement, and dispatch workflows
- Shipping (container booking), Transport (logistics), Documentation (export docs)
- Finance and accounts
- Inventory management with auto-add/deduct
- **DRUMS-ONLY Production Scheduling** with capacity enforcement (600 drums/day)

## User Personas (11 Roles)
1. **Admin** - Full system access
2. **Sales** - Quotations, customers, products
3. **Finance** - Quotation approval, PO approval, payment tracking, payables/receivables
4. **Production** - Job orders, scheduling, BOM, drum schedule
5. **Procurement** - Pending materials, supplier management, RFQ
6. **Inventory** - Stock tracking, movements
7. **Security** - GRN (goods receipt), Delivery Orders, gate checklists
8. **QC** - Quality control, batch numbers, specifications
9. **Shipping** - Container bookings, CRO management
10. **Transport** - Container pickup scheduling
11. **Documentation** - Export documents (invoices, packing lists, B/L)

---

## Implementation Status (All 9 Phases Complete)

### Phase 1: Inventory Status Discrepancy Fix ✅
- `GET /api/inventory-items` returns items with calculated `status`
- Status: IN_STOCK (available > 0), INBOUND (only incoming POs), OUT_OF_STOCK
- `GET /api/inventory-items/:id/availability` for detailed breakdown

### Phase 2: Quantity & Packaging Rules ✅
- Optional fields for UOM and weight supported in models
- DRUM = COUNT, BULK = KG/MT/L

### Phase 3: SMTP Email Queue ✅
- `email_outbox` collection for queuing
- Emails remain QUEUED when SMTP not configured
- SMTP via env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS

### Phase 4: Procurement Auto-Generation from BOMs ✅
- `GET /api/procurement/shortages` - derives from product_boms + packaging_boms
- `POST /api/procurement/auto-generate` - creates PR from shortages
- **NEVER** reads from job_orders.bom

### Phase 5: RFQ → PO Flow ✅
- Create, send, quote, convert workflow
- Email queued on send

### Phase 6: Finance Approval ✅
- PO approval/rejection workflow
- Send to supplier queues email
- Notification on pending approval

### Phase 7: Drum Scheduling (600/day) ✅
- Weekly view with capacity enforcement
- Campaign grouping by product + packaging
- Material availability from BOMs
- BLOCKED status triggers procurement notification

### Phase 8: Incoterm-Based Logistics Routing ✅
- LOCAL: EXW, DDP, DAP → Transportation/Security inward
- IMPORT: FOB, CFR, CIF, FCA → Shipping booking/Import checklist

### Phase 9: Security, QC, Payables, Receivables ✅
- GRN payables review gate (PENDING_PAYABLES → APPROVED/HOLD/REJECTED)
- Payables: bills with aging buckets (Current, 30, 60, 90+ days)
- Receivables: invoices (LOCAL/EXPORT) with aging
- Security: inward checklists with weight in/out
- QC: inspections with PASS/FAIL/HOLD

### Notifications (Event-Based) ✅
- Strict triggers only: RFQ_QUOTE_RECEIVED, PO_PENDING_APPROVAL, PRODUCTION_BLOCKED, GRN_PAYABLES_REVIEW
- Bell icon in header with unread count
- Role-filtered notifications

---

## Technical Architecture

### Backend (Python/FastAPI + MongoDB)
- `/app/backend/server.py` - All API endpoints
- `/app/backend/production_scheduling.py` - Drum scheduling models

### Frontend (React + Tailwind + Shadcn)
- `/app/frontend/src/pages/` - Page components
- `/app/frontend/src/lib/api.js` - API client
- `/app/frontend/src/components/layout/NotificationBell.js` - Bell component

### Key Collections
- `job_orders`, `sales_orders`, `quotations`, `products`
- `product_boms`, `product_bom_items` (RAW materials - SOURCE OF TRUTH)
- `packaging_boms`, `packaging_bom_items` (PACK materials - SOURCE OF TRUTH)
- `inventory_items`, `inventory_balances`, `inventory_reservations`
- `purchase_orders`, `rfq`, `procurement_requisitions`
- `grn`, `delivery_orders`, `shipping_bookings`
- `email_outbox`, `notifications`
- `payable_bills`, `receivable_invoices`
- `security_checklists`, `qc_inspections`
- `logistics_routing`, `import_checklists`

---

## Testing Status

### Test Results (December 29, 2025)
- **Backend**: 26/26 tests passed (100%)
- **Frontend**: All pages load successfully
- **Test Report**: `/app/test_reports/iteration_2.json`

### Test Files
- `/app/backend/tests/test_erp_backend.py` - Core tests
- `/app/backend/tests/test_erp_phases_8_9.py` - Phase 8-9 tests

---

## Prioritized Backlog

### P0 (Critical) - COMPLETED ✅
All 9 phases implemented and tested.

### P1 (High Priority) - Future Enhancements
- Dashboard analytics charts
- PDF export improvements for blend reports
- Import checklist document upload
- Multi-currency support

### P2 (Medium Priority)
- Customer portal for order tracking
- Mobile-responsive enhancements
- Audit trail improvements
- Barcode scanner integration

---

## Test Credentials
- Admin: `admin@erp.com` / `admin123`
- Sales: `sales@erp.com` / `sales123`
- Finance: `finance@erp.com` / `finance123`
- Production: `production@erp.com` / `production123`

---

## Documentation
- `/app/USER_MANUAL.md` - Complete user guide
- `/app/CHANGELOG.md` - Version history

---

## Notes
- SMTP intentionally NOT configured; emails remain QUEUED
- Material shortages derived from BOMs, never from job_orders.bom
- 600 drums/day capacity is a hard limit
- GRN must be approved by payables before AP posting
