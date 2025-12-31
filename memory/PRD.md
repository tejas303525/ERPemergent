# Manufacturing ERP System - PRD

## Completed Fixes (December 31, 2025)

### P0 - Critical Bugs ✅
1. **Quotation Total with VAT** - Fixed: Total now includes 5% VAT (subtotal + VAT)
2. **Quotation Validity Dropdown** - Added: 7/14/30/45/60/90 days options
3. **Settings Page CRUD** - Fixed: All tabs now support Add/Edit/Delete
   - Vendors/Suppliers, Companies, Payment Terms, Document Templates, Container Types, Packaging Types
4. **Stock Management Page** - Working: Route added, showing products and raw materials
5. **RAW Materials in BOM** - Fixed: Now loads raw_material category products for BOM dropdown

### P1 - Workflow Fixes ✅
6. **Job Order - Show ALL Products from SPA** - Fixed: Table view instead of dropdown
7. **Procurement Cleanup** - Fixed: Items with POs created are filtered out (pending_shortage = 0)
8. **Production Schedule Status Dropdown** - Added: in_production, production_completed, rescheduled
9. **Reschedule Modal** - Added: Select new date and shift when status is "rescheduled"

### Backend Endpoints Added
- `PUT /api/suppliers/{id}` - Update supplier
- `DELETE /api/suppliers/{id}` - Delete supplier
- `GET/POST/PUT/DELETE /api/settings/companies/{id}` - Company CRUD
- `GET/POST/PUT/DELETE /api/settings/payment-terms/{id}` - Payment Terms CRUD
- `GET/POST/PUT/DELETE /api/settings/document-templates/{id}` - Document Templates CRUD
- `GET/POST/PUT/DELETE /api/settings/container-types/{id}` - Container Types CRUD
- `PUT /api/job-orders/{id}/reschedule` - Reschedule job order

### Valid Job Order Statuses
- pending
- approved
- in_production
- production_completed
- procurement
- ready_for_dispatch
- dispatched
- rescheduled

## Remaining Tasks

### P2 - GRN & Status Updates
- [ ] GRN page - Production tab showing materials with status=='production_completed'
- [ ] Auto-update to READY_TO_DISPATCH when stock is ready
- [ ] Procurement column says "Material Ready"
- [ ] GRN quantity display showing how much qty added to stock

### P3 - Dispatch & Document Flow
- [ ] READY TO DISPATCH routing by incoterm:
  - EXW → Transport Window (Local Dispatch)
  - DDP → Security (Outward) → QC → DO
- [ ] Document generation:
  - Local: DO, Invoice, COA
  - Export: DO, Packing List, COO, BL draft
- [ ] Email integration for documents
- [ ] Notify Receivables

### P4 - QC Enhancements
- [ ] QC checklist fields: Supplier, Items, qty, inspection status, Sampling size
- [ ] QC Report viewer with full details

### Technical Notes
- Shortages are calculated dynamically from BOMs vs available stock
- PO quantities are subtracted from shortages (pending_shortage field)
- Auto-reschedule EOD not yet implemented (requires scheduled task)

## Test Credentials
- Admin: admin@erp.com / admin123
- Finance: finance@erp.com / finance123
- Security: security@erp.com / security123
