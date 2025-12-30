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

### Phase 2.1 (COMPLETED ✅ - December 30, 2025)

1. **Transport Window Restructured**
   - Inward (EXW) - Supplier-arranged
   - Inward (Import/Logistics) - International imports
   - Local Dispatch - Tanker/trailer
   - Export Container - Container shipments

2. **Transportation Operation Module**
   - 7-day hierarchical view
   - Status: On the Way (ETA), Scheduled (Time), Rescheduled (New transporter & date)
   - Columns: JO/PO, Qty, Product, Vehicle, Transporter, Status, ETA

3. **Transportation Planner Module**
   - Inward (EXW) planning
   - Inward (Import) planning
   - Dispatch planning
   - Transport booking

4. **Local Quotation Incoterm**
   - Added incoterm dropdown for local orders

5. **Finance Approval Auto-Routing**
   - EXW → Transport Window (Inward)
   - DDP → Security Gate directly
   - FOB/CFR/CIF → Import Window

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

## Current State
- Backend: Running ✅
- Frontend: Running ✅
- All Modules: Tested and Working ✅

## Documentation
- Full documentation available at `/app/DOCUMENTATION.md`

## Future Tasks (Backlog)

### P1
1. PDF generation with all custom fields
2. Email integration for sending POs

### P2
1. Production schedule auto-deduct materials
2. Production → GRN notification flow
3. Mobile responsive enhancements

### P3
1. Dashboard analytics
2. Bulk operations
