# Manufacturing ERP System - Product Requirements Document

## Original Problem Statement
Build a full Manufacturing ERP system with modules for Sales, Production, Inventory, Procurement, Shipping, QC, Security, and Finance.

## Completed Features (December 30, 2025)

### Phase 2 Bug Fixes - COMPLETED ✅
1. **Settings Page 404** - Fixed `/api/settings/all` endpoint
2. **Quotation Approval 520 Error** - Fixed ObjectId serialization
3. **Security Checklist 520 Error** - Fixed ObjectId serialization  
4. **EXW Incoterm Routing** - EXW POs now route to Transport Window
5. **Supplier 404 Error** - Added GET/PUT/DELETE `/api/suppliers/{id}` endpoints
6. **Job Order Status Update** - Working correctly

### Phase 2 Features - COMPLETED ✅
1. **Incoterm dropdown for local quotations** - Added to quotation form
2. **Packaging Types with Net Weight** - Configurable in Settings page
3. **Stock Management Page** - Full implementation with:
   - Stock Items tab with current stock, reserved, available
   - Adjustment History tab
   - Add Item functionality
   - Manual stock adjustment
4. **Import Window Updates** - Documents changed to:
   - Delivery Order
   - Bill of Lading
   - EPDA
   - SIRA
   - "Move to Transport" action button
5. **QC Reports for Payables** - New tab in Payables page showing completed QC inspections
6. **Production Schedule** - Now includes `in_production` and `approved` jobs
   - JOB-000013 is visible on 2026-01-01 (Thursday)

## Incoterm-Based Workflow
- **EXW** → Transport Window (Inward EXW)
- **DDP** → Security Gate → QC
- **FOB/CFR/CIF** → Import Window → Transport (Import/Logistics)

## Test Credentials
- Admin: `admin@erp.com` / `admin123`
- Finance: `finance@erp.com` / `finance123`
- Security: `security@erp.com` / `security123`

## Backend API Endpoints (New/Updated)
- GET/PUT/DELETE `/api/suppliers/{supplier_id}` - Single supplier operations
- GET `/api/qc/inspections/completed` - Completed QC inspections for Payables
- POST `/api/imports/{import_id}/move-to-transport` - Move cleared imports to transport
- PUT `/api/imports/{import_id}/document` - Update single import document
- PUT `/api/imports/{import_id}/status` - Update import status
- PUT `/api/settings/packaging-types/{id}` - Update packaging type
- GET/POST `/api/stock/adjustments` - Stock adjustment history

## Frontend Routes
- `/stock-management` - Stock Management page
- `/settings` - Settings with Packaging Types tab
- `/import-window` - Import Window with new documents
- `/payables` - Payables with QC Reports tab

## Remaining Tasks

### P1 - High Priority
- [ ] Duplicate Job Orders - Prevent duplicate creation for same item
- [ ] Transportation PO Generation - Generate PO after transport booking

### P2 - Medium Priority  
- [ ] Job Order SPA Selection - Show all SPAs for a product
- [ ] Full System Documentation

### Technical Debt
- [ ] Refactor server.py (6500+ lines) into smaller routers
