# Manufacturing ERP System - Product Requirements Document

## Original Problem Statement
Build a full Manufacturing ERP system based on a detailed mermaid chart with comprehensive modules for:
- Sales and Quotation Management
- Production and Job Order Management  
- Inventory and Procurement
- Shipping and Logistics
- Quality Control and Security
- Finance (Payables/Receivables)

## Core Requirements

### Phase 1 (COMPLETED ✅)
1. **Unified Production Scheduling** - 600 drums/day capacity with allocation logic
2. **Transport Window** - 4 tabs (Inward/Outward Raw, Inward/Outward Container)
3. **Import Window** - Document checklist and tracking
4. **Incoterm-based PO Routing** - Auto-route based on EXW/DDP/FOB/CFR
5. **BOM Management** - Product and Packaging BOMs
6. **Material Availability Check** - Auto-check on quotation approval

### Phase 2 (COMPLETED ✅ - December 30, 2025)

#### Bug Fixes Implemented
1. **Quotation Page Enhancements** ✅
   - Container types, container count, capacity validation
   - "Max cargo exceeded" error with solution
   - Documents renamed to "Documents that need to be submitted"

2. **Quotation Approval UI Bug** ✅ - Fixed state update

3. **Job Order Automation** ✅
   - Auto-fill from SPA
   - Label confirmation & Schedule timing fields
   - Shift selection (Morning/Evening/Night)
   - Sales role access added

4. **Shipping/Transport Integration** ✅
   - CRO fields (freight_charges, pull_out_date, si_cutoff, gate_in_date)
   - Auto-creates transport_outward

5. **Procurement Flow Rework** ✅ - Generate PO model

#### New Modules Implemented
1. **Security Gate Module** (`/security`) ✅
2. **QC Inspection Module** (`/qc-inspection`) ✅
3. **Settings Module** (`/settings`) ✅
4. **Transportation Operation Module** (`/transport-operation`) ✅
5. **Transportation Planner Module** (`/transport-planner`) ✅

### Phase 2.1 - Bug Fixes (COMPLETED ✅ - December 30, 2025)

#### Critical Bug Fixes (P0)
1. **Settings Page 404 Error** ✅ FIXED
   - `/api/settings/all` endpoint verified working
   - Returns payment_terms, document_templates, container_types, companies, packaging_types

2. **Quotation Approval 520 Error** ✅ FIXED
   - ObjectId serialization issue resolved
   - Used `{**dict}` spread before `insert_one` to prevent _id mutation

3. **Security Checklist 520 Error** ✅ FIXED
   - ObjectId serialization issue resolved
   - Returns clean checklist without MongoDB _id

4. **EXW Incoterm Routing** ✅ FIXED
   - EXW POs now correctly route to Transport Window (TRANSPORTATION_INWARD)
   - Transport Window shows EXW records with proper badges

5. **Production Schedule Missing Jobs** ✅ FIXED
   - Added `in_production` and `approved` to schedule query
   - Unified schedule now shows all relevant job statuses

6. **Job Order Status Update** ✅ FIXED
   - PUT /api/job-orders/{id}/status?status=approved works correctly

## Workflow by Incoterm

### EXW (Ex Works) - Inward
```
Finance Approves PO → Transport Window (Inward EXW) → Security Gate → QC → GRN → Stock → Payables
```

### DDP (Delivered Duty Paid) - Inward
```
Finance Approves PO → Security Gate → QC → GRN → Stock → Payables
```

### FOB/CFR/CIF - Import
```
Finance Approves PO → Import Window → Customs → Transport → Security → QC → GRN → Stock
```

### Local Dispatch
```
Job Approved → Production → Ready → Transport Planner → Security → QC → DO → Tax Invoice → Receivables
```

### Export Container
```
Job Approved → Production → Shipping → Transport → Security → QC → DO + Packing List + COO + BL + COA → Invoice → Receivables
```

## Technical Architecture

### Backend: FastAPI (Python) + MongoDB
### Frontend: React + TailwindCSS + Shadcn/UI
### Auth: JWT

## Test Credentials
- Admin: admin@erp.com / admin123
- Finance: finance@erp.com / finance123
- Security: security@erp.com / security123

## Current State (December 30, 2025)
- Backend: Running ✅
- Frontend: Running ✅
- All P0 Bug Fixes: Verified ✅ (19/19 tests passed)

## Test Reports
- `/app/test_reports/iteration_6.json` - Latest test results (100% pass rate)
- `/app/tests/test_phase2_bugfixes.py` - Test file

## Remaining Tasks (Backlog)

### P1 - High Priority
1. **Duplicate Job Orders** - System creating duplicate job orders for same item
   - Need to investigate job order creation logic
2. **QC Report for Payables** - Enhance QC module for detailed reports
3. **Transportation PO Generation** - Generate PO after transport booking with email
4. **Stock Management Page** - Full implementation needed

### P2 - Medium Priority
1. **Job Order SPA Selection** - Show all SPAs for a product, not one-by-one
2. **Import Window "Move to Transport"** - Action to move to Inward (Import/Logistics) tab
3. **Quotation Enhancements** - Container count validation
4. **Job Order Enhancements** - Label confirmation, schedule timing, sales access

### P3 - Low Priority
1. **Full System Documentation** - Complete DOCUMENTATION.md
2. **Production Schedule Automation** - Auto-deduct materials, trigger GRN
3. **PDF generation** with custom fields
4. **Email integration** for sending POs
5. **Mobile responsive** enhancements
6. **Dashboard analytics**
7. **Bulk operations**

### Technical Debt
1. **server.py Refactoring** - 6500+ lines, needs to be split into routers
   - `/app/backend/routers/quotations.py`
   - `/app/backend/routers/procurement.py`
   - `/app/backend/routers/qc.py`
   - etc.

## Documentation
- Full documentation available at `/app/DOCUMENTATION.md`
