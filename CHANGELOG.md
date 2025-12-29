# CHANGELOG - ERP Enhancement Implementation

## Phase 1: Inventory Status Fix
### Backend Changes
- `inventory_service.py` (NEW) - Centralized inventory availability logic
- Updated `/api/inventory-items` endpoint to use `inventory_balances.on_hand - reserved`
- Fixed status calculation: `IN_STOCK`, `INBOUND`, `OUT_OF_STOCK`

### Database Changes
- No new collections
- No schema changes (existing fields used correctly)

## Phase 2: Quantity & Packaging Rules
### Database Changes - New Optional Fields
- `job_orders.quantity_uom` (optional: 'COUNT' | 'KG' | 'MT' | 'L')
- `job_orders.net_weight_kg_per_unit` (optional: number)
- `products.quantity_uom` (optional)
- `packaging.quantity_uom` (optional, default: 'COUNT' for DRUM)

### Business Rules Added
- DRUM packaging → quantity_uom = 'COUNT'
- BULK packaging → quantity_uom = 'KG' | 'MT' | 'L' (mandatory)
- Conversion logic enhanced for unit handling

## Phase 3: SMTP Email Queue
### New Files
- `email_service.py` (NEW) - Nodemailer-based SMTP service
- `email_worker.py` (NEW) - Background worker for email queue processing

### Database Changes
- `email_outbox` collection (ENHANCED with new fields):
  - `attempts` (number, default: 0)
  - `lastError` (string, optional)
  - `cc` (array of emails, optional)
  - `html` (string, email body)

### Configuration Added
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD env variables
- Retry logic with exponential backoff (3 attempts)

### Removed
- Resend API integration removed
- All `send_email_notification()` now use email_outbox queue

## Phase 4: Procurement Auto-Demand
### New Files
- `procurement_auto_demand_service.py` (NEW)

### Logic Added
- Auto-creates `procurement_requisition_lines` when:
  - `production_day_requirements.shortageQty > 0`
  - `inventory_balances.on_hand - reserved <= 0`
- Links to `campaignId`, `scheduleDayId`, `job_order_id`
- Sets `requiredBy` = `production_schedule_days.scheduleDate`

### API Endpoints Added
- `POST /api/procurement/auto-generate` - Trigger auto-demand generation
- `GET /api/procurement/shortages` - View all shortages requiring procurement

## Phase 5: RFQ & PO Flow
### New Collections
- `rfq_requests` - Request for Quotation headers
- `rfq_lines` - RFQ line items (links to job_orders, shows shortages)

### New Files
- `rfq_service.py` (NEW)
- Frontend: `RFQPage.js` (NEW)
- Frontend: `RFQCreatePage.js` (NEW)

### API Endpoints Added
- `POST /api/rfq` - Create RFQ
- `GET /api/rfq` - List RFQs
- `GET /api/rfq/:id` - Get RFQ details
- `POST /api/rfq/:id/convert-to-po` - Convert RFQ to PO
- `GET /api/rfq/packaging-demand` - Get packaging requirements from packaging_bom_items
- `GET /api/rfq/raw-material-demand` - Get RAW material requirements

### Features
- Auto-fill vendor/billing/shipping addresses
- Shows job_number, product_name, packaging_type, net_weight, qty_needed
- Converts to PO with FINANCE_REVIEW status

## Phase 6: Finance Approval & PO Send
### New Files
- Frontend: `FinancePOApprovalPage.js` (NEW)

### API Endpoints Added
- `GET /api/finance/pos-pending-approval` - POs awaiting finance review
- `POST /api/finance/approve-po/:id` - Approve PO (enables send)
- `POST /api/finance/reject-po/:id` - Reject PO
- `POST /api/purchase-orders/:id/send-to-vendor` - Send PO via email

### Logic Added
- PO approval changes status: FINANCE_REVIEW → APPROVED
- Send to Vendor creates `email_outbox` entry with:
  - PO PDF attachment
  - Delivery date
  - Incoterms
  - Payment terms
- Email status tracked: QUEUED → SENT/FAILED

## Phase 7: Production Scheduling Enhancement
### Files Modified (ADDITIVE ONLY)
- `production_scheduling.py` (ENHANCED, no breaking changes)

### Logic Enhanced
1. **Demand Source**: job_orders with status=pending, packaging_type=DRUM
2. **Consolidation**: By product_id + packaging_id + active BOM version
3. **Priority**: Material availability date (GRN/PO ETA), then delivery_date
4. **Hard Constraint**: Total planned drums per day ≤ 600
5. **Conversion Logic** (order of resolution):
   - product_packaging_specs.net_weight_kg
   - packaging.net_weight_kg_default
   - packaging.capacity_liters × products.density_kg_per_l
   - If missing → BLOCKED (CONVERSION_MISSING)
6. **Requirements**: RAW from product_bom_items, PACK from packaging_bom_items
7. **Availability**: on_hand - reserved + inbound_by_eta
8. **Shortage Handling**: Auto-create procurement_requisition_lines
9. **Approval System**: Creates inventory_reservations, supports reassignment

### API Endpoints Enhanced
- `POST /api/production/drum-schedule/approve` (ENHANCED) - Now creates reservations
- `POST /api/production/drum-schedule/reassign` (NEW) - Reassign drums between campaigns
- `GET /api/production/drum-schedule/unreserved` (NEW) - View unreserved schedules

## Phase 8: Incoterm-Based Routing
### New Files
- `incoterm_router_service.py` (NEW)

### Logic Added
- **LOCAL EXWORKS** → routes to `transport_schedules` (INWARD)
- **LOCAL DDP** → routes to security + QC flow
- **IMPORT FOB** → routes to `shipping_bookings`
- **IMPORT CFR** → routes to import/logistics inward window

### API Endpoints Added
- `POST /api/logistics/route-by-incoterm` - Auto-route based on PO incoterm
- `GET /api/logistics/inward-pending` - View inward transportation pending
- `GET /api/logistics/outward-pending` - View outward transportation pending

### Features
- Automatic routing after Finance approval
- Does NOT modify existing transportation UI
- Feeds data to existing screens

## Phase 9: Complete Flow Integration
### New Collections
- `qc_inspections` - Quality control inspection records (links to GRN/DO)
- `local_invoices` - Local sales invoices
- `export_invoices` - Export sales invoices
- `payables_ledger` - Vendor payment tracking
- `receivables_ledger` - Customer payment tracking
- `document_templates` - Document generation templates

### New Files - Security & QC
- `security_service.py` (NEW) - Security gate management
- `qc_service.py` (NEW) - QC inspection workflow
- Frontend: `SecurityInwardPage.js` (NEW)
- Frontend: `SecurityOutwardPage.js` (NEW)
- Frontend: `QCInspectionPage.js` (NEW)

### New Files - Documents
- `document_service.py` (NEW) - Auto-generate COA, COO, BL
- Frontend: `DocumentGenerationPage.js` (NEW)

### New Files - Payables
- Frontend: `PayablesPage.js` (NEW)
- Frontend: `PayablesAgingReport.js` (NEW)
- `payables_service.py` (NEW)

### New Files - Receivables
- Frontend: `ReceivablesPage.js` (NEW)
- Frontend: `ReceivablesAgingReport.js` (NEW)
- `receivables_service.py` (NEW)

### API Endpoints Added
#### Security
- `POST /api/security/inward/gate-entry` - Record inward gate entry
- `POST /api/security/outward/gate-exit` - Record outward gate exit
- `GET /api/security/today-schedule` - Today's expected arrivals/dispatches

#### QC
- `POST /api/qc/inspection` - Create QC inspection
- `PUT /api/qc/inspection/:id/approve` - Approve inspection (triggers GRN/DO)
- `PUT /api/qc/inspection/:id/reject` - Reject inspection
- `GET /api/qc/pending` - Pending inspections

#### Documents
- `POST /api/documents/generate-coa` - Generate Certificate of Analysis
- `POST /api/documents/generate-coo` - Generate Certificate of Origin
- `POST /api/documents/generate-bl-draft` - Generate Bill of Lading draft
- `GET /api/documents/by-job/:jobId` - Get all documents for job

#### Payables
- `GET /api/payables/ledger` - View payables ledger
- `GET /api/payables/aging-report` - Aging analysis
- `POST /api/payables/record-payment` - Record vendor payment
- `GET /api/payables/pending` - Pending payments

#### Receivables
- `GET /api/receivables/ledger` - View receivables ledger
- `GET /api/receivables/aging-report` - Aging analysis
- `POST /api/receivables/send-reminder` - Send payment reminder email
- `GET /api/receivables/overdue` - Overdue invoices

### Workflow Integration
#### Inward Flow
1. Security gate entry → `qc_inspections` (PENDING)
2. QC inspection → Approve/Reject
3. If approved → GRN auto-created → `inventory_balances` updated
4. GRN → Creates `payables_ledger` entry
5. Payables → Track payment status

#### Outward Flow
1. Security gate exit → `qc_inspections` (PENDING, final check)
2. QC approval → DO auto-created → `inventory` deducted
3. DO → Auto-generate documents (Invoice, COA, etc.)
4. Documents → Email to customer via `email_outbox`
5. Invoice → Creates `receivables_ledger` entry
6. Receivables → Track payment + send reminders

### Email Automation Added
- PO sent to vendor
- Documents sent to customer
- Payment reminders (receivables)
- Shortage alerts (procurement)
- All via `email_outbox` queue with SMTP

## Testing Added
### Scheduler Tests
- Test: Never exceeds 600 drums/day
- Test: BOM missing blocks schedule
- Test: Conversion missing blocks schedule
- Test: Shortages auto-create PR lines
- Test: Idempotent regeneration
- Test: Material reservation on approval

### Integration Tests
- Test: RFQ → PO → Finance Approval → Send
- Test: PO → GRN → Payables
- Test: DO → Receivables
- Test: Email queue processing with retry
- Test: Incoterm routing logic

## Configuration Changes
### Environment Variables Added
```
# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@example.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@company.com

# Feature Flags
ENABLE_AUTO_PROCUREMENT=true
ENABLE_EMAIL_WORKER=true
ENABLE_INCOTERM_ROUTING=true
```

## UI Routes Added
- `/rfq` - RFQ Management
- `/rfq/create` - Create RFQ
- `/finance/po-approval` - Finance PO Approval
- `/security/inward` - Security Inward Gate
- `/security/outward` - Security Outward Gate
- `/qc/inspections` - QC Inspections
- `/documents` - Document Generation
- `/payables` - Payables Management
- `/payables/aging` - Payables Aging Report
- `/receivables` - Receivables Management
- `/receivables/aging` - Receivables Aging Report

## Sidebar Menu Updates (ADDITIVE)
- Added "RFQ" under Procurement section
- Added "PO Approval" under Finance section
- Added "Security Inward" and "Security Outward" under Security section
- Added "QC Inspections" under Quality section
- Added "Payables" and "Receivables" under Finance section
- Added "Documents" under Documentation section

## Breaking Changes
**NONE** - All changes are additive only. Existing functionality preserved.

## Migration Notes
- No database migration required
- New collections will be created automatically
- Existing collections remain unchanged
- Optional fields default to null (safe)
- Email worker can be enabled gradually

## Rollback Strategy
- Disable feature flags in .env
- Stop email worker
- System reverts to previous behavior
- No data loss (new collections isolated)
