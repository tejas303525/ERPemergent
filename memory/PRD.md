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
3. **Finance** - Quotation approval, PO approval, payment tracking
4. **Production** - Job orders, scheduling, BOM, drum schedule
5. **Procurement** - Pending materials, supplier management, RFQ
6. **Inventory** - Stock tracking, movements
7. **Security** - GRN (goods receipt), Delivery Orders
8. **QC** - Quality control, batch numbers, specifications
9. **Shipping** - Container bookings, CRO management
10. **Transport** - Container pickup scheduling
11. **Documentation** - Export documents (invoices, packing lists, B/L)

## What's Been Implemented

### Phase 1: Inventory Status Discrepancy Fix ✅ (Dec 29, 2025)
- `GET /api/inventory-items` now returns items with `status` field
- Status calculated as: IN_STOCK (available > 0), INBOUND (only incoming POs), OUT_OF_STOCK
- `GET /api/inventory-items/:id/availability` returns detailed breakdown:
  - on_hand, reserved, available, inbound, inbound_details, reservations

### Phase 3: SMTP Email Queue ✅ (Dec 29, 2025)
- `POST /api/email/queue` - Queue emails for sending
- `GET /api/email/outbox` - View email queue with SMTP status
- `POST /api/email/process-queue` - Process queued emails (admin only)
- Emails remain QUEUED when SMTP not configured (no mocking)
- SMTP configuration via env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM

### Phase 4: Auto Procurement from Shortages ✅ (Dec 29, 2025)
- `POST /api/procurement/auto-generate` - Creates procurement requisition lines from schedule shortages
- Automatically links to blocked schedule days
- Creates PR with DRAFT status for procurement team review

### Phase 5: RFQ Flow ✅ (Dec 29, 2025)
- `POST /api/rfq` - Create RFQ for supplier
- `GET /api/rfq` - List all RFQs
- `PUT /api/rfq/:id/send` - Mark as SENT, queue email to supplier
- `PUT /api/rfq/:id/quote` - Update with supplier prices
- `POST /api/rfq/:id/convert-to-po` - Convert QUOTED RFQ to PO

### Phase 6: Finance Approval ✅ (Dec 29, 2025)
- `GET /api/purchase-orders/pending-approval` - POs awaiting finance approval
- `PUT /api/purchase-orders/:id/finance-approve` - Finance approves PO
- `PUT /api/purchase-orders/:id/finance-reject` - Finance rejects with reason
- `PUT /api/purchase-orders/:id/send` - Send approved PO to supplier, queue email

### Phase 7: Drum Scheduling (600/day) ✅ (Dec 28-29, 2025)
- Weekly production schedule with 7-day view
- 600 drums/day capacity enforcement
- Campaign-based scheduling (groups same product/packaging)
- Material availability checking (RAW + PACK)
- Automatic blocking for material shortages
- Integration with product_boms and packaging_boms

### Frontend Pages Added (Dec 29, 2025)
- `/procurement` - Procurement Management (RFQ, Requisitions)
- `/finance-approval` - Finance PO Approval (pending, approved, email outbox)

## Technical Architecture

### Backend (FastAPI + MongoDB)
- `/app/backend/server.py` - Main API endpoints
- `/app/backend/production_scheduling.py` - Drum scheduling models and logic

### Frontend (React + Tailwind + Shadcn)
- `/app/frontend/src/pages/` - All page components
- `/app/frontend/src/lib/api.js` - API client
- `/app/frontend/src/components/ui/` - Shadcn components

### Key Collections
- `users`, `customers`, `products`
- `quotations`, `sales_orders`, `payments`
- `job_orders`, `job_order_items`
- `inventory_items`, `inventory_balances`, `inventory_reservations`
- `purchase_orders`, `purchase_order_lines`
- `rfq`, `procurement_requisitions`, `procurement_requisition_lines`
- `production_campaigns`, `production_schedule_days`
- `email_outbox`

## Prioritized Backlog

### P0 (Critical) - COMPLETED ✅
- All core ERP workflows
- Phases 1-7 of drum scheduling enhancement

### P1 (High Priority) - Next
- **Phase 2**: Quantity & Packaging Rules (UOM, weight fields)
- **Phase 8**: Incoterm-Based Logistics Routing
- Blend report PDF generation improvements
- Dashboard analytics charts

### P2 (Medium Priority) - Future
- **Phase 9**: Security, QC, Payables, Receivables modules
- Customer portal for order tracking
- Mobile-responsive enhancements
- Audit trail improvements
- Barcode scanner integration

## Test Credentials
- Admin: `admin@erp.com` / `admin123`
- Sales: `sales@erp.com` / `sales123`
- Finance: `finance@erp.com` / `finance123`
- Production: `production@erp.com` / `production123`

## Notes
- SMTP is intentionally NOT configured; emails remain QUEUED until SMTP env vars are set
- All tests passing (15/15 backend, all frontend pages load correctly)
- Test report: `/app/test_reports/iteration_1.json`
