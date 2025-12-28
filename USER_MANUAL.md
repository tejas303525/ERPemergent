================================================================================
    MANUFACTURING ERP SYSTEM - COMPLETE USER MANUAL
    From Quotation to Dispatch - Step by Step Guide
================================================================================

TABLE OF CONTENTS
-----------------
1. Create Customer
2. Create Quotation (PFI)
3. Approve Quotation (Finance)
4. Create Sales Order (SPA)
5. Record Payment
6. Create Job Order
7. Start Production
8. Create Blend Report
9. Complete Production (Adds to Stock)
10. View Inventory
11. Create Delivery Order (Dispatch)
12. Complete Flow Summary

================================================================================
STEP 1: CREATE CUSTOMER
================================================================================

LOGIN: admin@erp.com / admin123 (or sales@erp.com / sales123)
PAGE: /customers

ACTIONS:
1. Click "Customers" in sidebar
2. Click "+ Add Customer" button
3. Fill in details:
   - Name: ABC Trading LLC
   - Company: ABC Trading Company
   - Email: abc@trading.com
   - Phone: +971501234567
   - Country: UAE
   - Customer Type: local (or export)
4. Click "Create Customer"
5. ✅ Customer created successfully

RESULT: Customer appears in customers list

================================================================================
STEP 2: CREATE QUOTATION (PFI)
================================================================================

LOGIN: sales@erp.com / sales123
PAGE: /quotations

ACTIONS:
1. Click "Quotations" in sidebar
2. Click "+ Create Quotation" button
3. Select Customer: ABC Trading LLC
4. Fill quotation details:
   - Currency: USD
   - Order Type: local
   - Payment Terms: CAD
5. Add Products:
   - Click "Add Product"
   - Select Product: Hydraulic Oil ISO 68
   - Quantity: 100 (in KG)
   - Unit Price: 5.0 (auto-filled from product)
   - Packaging: Drums
6. Can add multiple products by clicking "Add Product" again
7. Click "Create Quotation"
8. ✅ Quotation created with PFI number (e.g., PFI-000001)

RESULT: Quotation appears with status "PENDING"

================================================================================
STEP 3: APPROVE QUOTATION (Finance Role)
================================================================================

LOGIN: finance@erp.com / finance123
PAGE: /quotations

ACTIONS:
1. Click "Quotations" in sidebar
2. Find the pending quotation (PFI-000001)
3. Click "View" or click on the quotation row
4. Review quotation details:
   - Customer information
   - Products and quantities
   - Total amount
5. Click "Approve" button (green button)
6. ✅ Quotation status changes to "APPROVED"
7. Email notification sent to sales team (if configured)

RESULT: Quotation status = APPROVED, ready to convert to Sales Order

NOTE: Finance can also "Reject" if needed

================================================================================
STEP 4: CREATE SALES ORDER (SPA)
================================================================================

LOGIN: sales@erp.com / sales123 (or admin)
PAGE: /sales-orders

ACTIONS:
1. Click "Sales Orders" in sidebar
2. Click "+ Create from Quotation" button
3. Select the approved quotation (PFI-000001)
4. System auto-fills:
   - Customer details
   - Products and quantities
   - Total amount
5. Click "Create Sales Order"
6. ✅ Sales Order created with SPA number (e.g., SPA-000001)

RESULT: 
- Sales Order appears with status "UNPAID" or "PENDING"
- Quotation status changes to "CONVERTED"

================================================================================
STEP 5: RECORD PAYMENT
================================================================================

LOGIN: finance@erp.com / finance123
PAGE: /sales-orders

ACTIONS:
1. Click "Sales Orders" in sidebar
2. Find the sales order (SPA-000001)
3. Click "Record Payment" button
4. Fill payment details:
   - Amount: 500.00 (or partial payment)
   - Payment Method: Bank Transfer / LC / CAD / Cash
   - Payment Date: (auto-filled with today)
5. Click "Submit Payment"
6. ✅ Payment recorded successfully

RESULT:
- Payment status updates (PENDING → PARTIAL → PAID)
- Balance reduces by payment amount
- Can record multiple partial payments

================================================================================
STEP 6: CREATE JOB ORDER
================================================================================

LOGIN: production@erp.com / production123 (or admin)
PAGE: /job-orders

ACTIONS:
1. Click "Job Orders" in sidebar
2. Click "+ Create Job Order" button
3. Select Sales Order: SPA-000001
4. System shows products from sales order
5. For each product:
   - Confirm quantity
   - Add BOM (Bill of Materials):
     * Click "Add Material"
     * Select Raw Material (e.g., Base Oil SN150)
     * Enter Required Quantity (e.g., 85 KG for 100 KG finished)
     * System shows Available Quantity
     * Repeat for all BOM items
6. Set Priority: Normal / High / Urgent
7. Click "Create Job Order"
8. ✅ Job Order created with JOB number (e.g., JOB-000001)

RESULT: Job Order appears with status "PENDING"

IMPORTANT: BOM determines material requirements
- System checks if materials are available
- If shortage: Status = "PROCUREMENT" 
- If available: Status = "PENDING" (ready to start)

================================================================================
STEP 7: START PRODUCTION
================================================================================

LOGIN: production@erp.com / production123
PAGE: /job-orders

ACTIONS:
1. Click "Job Orders" in sidebar
2. Find job order (JOB-000001) with status "PENDING"
3. Click "Update Status" button
4. Select new status: "IN_PRODUCTION"
5. Click "Update"
6. ✅ Production started

RESULT:
- Job Order status = "IN_PRODUCTION"
- Production start timestamp recorded
- Notification sent to production team
- (Future: RAW materials automatically deducted from inventory)

VISUAL INDICATORS:
- Status badge changes color
- Shows production start time
- Can see job in "Active Production" list

================================================================================
STEP 8: CREATE BLEND REPORT (During Production)
================================================================================

LOGIN: production@erp.com / production123 (or qc@erp.com)
PAGE: /blend-reports

ACTIONS:
1. Click "Blend Reports" in sidebar
2. Click "+ Create Blend Report" button
3. Select Job Order: JOB-000001
4. Fill production details:
   - Batch Number: BATCH-001
   - Blend Date: (auto-filled)
   - Operator Name: John Doe
5. Add Materials Used:
   - Base Oil SN150: 850 KG (with batch/lot number)
   - Additive Package A: 100 KG (with batch/lot number)
   - Viscosity Modifier: 50 KG (with batch/lot number)
6. Add Process Parameters:
   - Mixing Temperature: 60°C
   - Mixing Time: 120 minutes
   - Mixing Speed: 150 RPM
7. Add Quality Checks:
   - Viscosity: 68 cSt @ 40°C
   - Flash Point: 210°C
   - Pour Point: -15°C
8. Output:
   - Output Quantity: 995 KG (some loss is normal)
   - Yield %: 99.5%
9. Click "Submit Report"
10. ✅ Blend Report created

RESULT:
- Blend Report appears with status "SUBMITTED"
- Linked to job order
- Awaiting QC approval

================================================================================
STEP 9: COMPLETE PRODUCTION & ADD TO STOCK
================================================================================

LOGIN: production@erp.com / production123
PAGE: /job-orders

OPTION A: MARK AS READY FOR DISPATCH (Current System)
------------------------------------------------------
ACTIONS:
1. Click "Job Orders" in sidebar
2. Find job order (JOB-000001) with status "IN_PRODUCTION"
3. Click "Update Status" button
4. Select new status: "READY_FOR_DISPATCH"
5. Click "Update"
6. ✅ Production completed

RESULT:
- Job Order status = "READY_FOR_DISPATCH"
- Production end timestamp recorded
- Notification sent to shipping/security

⚠️ IMPORTANT: This does NOT automatically add to finished goods inventory!
   Inventory is updated when you create a Delivery Order (Step 11)

OPTION B: CREATE GRN FOR FINISHED GOODS (Recommended for Stock Tracking)
------------------------------------------------------------------------
LOGIN: inventory@erp.com / inventory123
PAGE: /grn

ACTIONS:
1. Click "GRN" in sidebar
2. Click "+ Create GRN" button
3. Fill details:
   - Supplier: "INTERNAL PRODUCTION"
   - Reference: JOB-000001
4. Add Items:
   - Product: Hydraulic Oil ISO 68
   - Quantity: 995 KG (from blend report output)
   - Unit: KG
5. Click "Create GRN"
6. ✅ GRN created with number (e.g., GRN-000001)

RESULT:
- ✅ Inventory AUTOMATICALLY UPDATED!
- Hydraulic Oil ISO 68: 0 → 995 KG
- Inventory movement record created (type: grn_add)
- Audit trail maintained

================================================================================
STEP 10: VIEW INVENTORY (Verify Stock Added)
================================================================================

LOGIN: Any role
PAGE: /inventory

ACTIONS:
1. Click "Inventory" in sidebar
2. View stock levels:
   - Hydraulic Oil ISO 68: 995 KG ✅
   - Shows: Current Stock, Min Stock, Status
3. Click "View Movements" to see audit trail
4. Shows:
   - GRN-000001: +995 KG (from 0 to 995)
   - Date, Time, Who created it
   - Reference: JOB-000001

STOCK LOCATION UNDERSTANDING:
- Finished products can be in:
  * DRUMS (200L each) - Ready for customer dispatch
  * STORAGE TANKS (5000-50000L) - Bulk storage before drumming
- System tracks in KG, conversion to drums happens during filling

================================================================================
STEP 11: CREATE DELIVERY ORDER (Dispatch to Customer)
================================================================================

LOGIN: security@erp.com / security123
PAGE: /delivery-orders

ACTIONS:
1. Click "Delivery Orders" in sidebar
2. Click "+ Create Delivery Order" button
3. Fill details:
   - Job Order: JOB-000001
   - Shipping Booking: (optional, if export)
   - Vehicle Number: DXB-12345
   - Driver Name: Ahmed Ali
   - Notes: Delivery to ABC Trading LLC
4. System shows:
   - Product: Hydraulic Oil ISO 68
   - Quantity: 100 KG (from job order, or can adjust)
5. Click "Create Delivery Order"
6. ✅ Delivery Order created (DO-000001)

RESULT:
- DO created with status
- ✅ Inventory AUTOMATICALLY DEDUCTED!
- Hydraulic Oil ISO 68: 995 → 895 KG
- Inventory movement record created (type: do_deduct)
- Job Order status → "DISPATCHED"

================================================================================
STEP 12: COMPLETE FLOW SUMMARY
================================================================================

FULL WORKFLOW VISUALIZATION:

Customer Creation → Quotation (PFI) → Finance Approval → Sales Order (SPA)
                                                              ↓
                                                         Payment Recording
                                                              ↓
                                                         Job Order Created
                                                              ↓
                                              Status: PENDING (check materials)
                                                              ↓
                                              Status: IN_PRODUCTION (start work)
                                                              ↓
                                              Create Blend Report (document production)
                                                              ↓
                                       Status: READY_FOR_DISPATCH (production done)
                                                              ↓
                           ┌──────────────────────────────────┴──────────────────┐
                           ↓                                                      ↓
                   Create GRN (Internal)                              Create Delivery Order
                   "Finished Goods Receipt"                           "Dispatch to Customer"
                   ✅ ADDS to Inventory                               ✅ DEDUCTS from Inventory
                   Hydraulic Oil: 0 → 995 KG                          Hydraulic Oil: 995 → 895 KG
                           ↓                                                      ↓
                   Product now in stock                               Product delivered to customer
                   (Can be sold to other customers)                   (Job complete, customer satisfied)


INVENTORY UPDATE POINTS:
========================
1. GRN Creation → ADDS to inventory (Raw materials from supplier OR Finished goods from production)
2. Delivery Order → DEDUCTS from inventory (Finished goods to customer)
3. (Future) Production Start → DEDUCTS raw materials automatically
4. (Future) QC Approval → MOVES from WIP to Finished Goods

CURRENT vs FUTURE FLOW:
========================

CURRENT SYSTEM:
- Raw materials tracked in inventory_items + inventory_balances
- Finished products tracked in products.current_stock
- Manual GRN for finished goods from production
- Automatic deduction on Delivery Order

FUTURE ENHANCEMENT (When QC Integration Complete):
- Production Start → Auto deduct RAW materials
- Production Complete → Adds to "Work in Progress" inventory
- QC Approval → Moves from WIP to "Finished Goods" inventory
- No manual GRN needed for internal production

================================================================================
TROUBLESHOOTING & COMMON QUESTIONS
================================================================================

Q1: I started production but don't see inventory increase. Why?
A: In current system, you need to create a GRN (Goods Receipt Note) for the
   finished product to add it to inventory. This is Step 9, Option B.
   
Q2: Can I dispatch without adding to inventory first?
A: Yes! Create Delivery Order directly. System will deduct from product's
   current_stock. But if stock is 0, the DO will still be created (negative
   stock allowed currently).

Q3: How do I know if materials are available before starting production?
A: When creating Job Order, the system shows "Available Quantity" for each
   BOM item. If insufficient, status will be "PROCUREMENT".

Q4: Where can I see the audit trail of inventory changes?
A: Go to Inventory page → Click "View Movements" button
   Shows all GRN adds, DO deductions with timestamps and references.

Q5: Can I partially dispatch a job order?
A: Yes! When creating Delivery Order, you can adjust the quantity.
   Create multiple DOs for the same job order.

Q6: What's the difference between Drums and Storage Tanks?
A: Both are storage methods:
   - Storage Tanks: Bulk liquid storage (5000-50000L) in tank farm
   - Drums: Individual containers (200L) for customer delivery
   System tracks in KG, you can convert using net weight per drum.

Q7: How does Drum Production Scheduling work?
A: Go to "Drum Schedule (NEW)" in sidebar:
   - Shows weekly view (7 days)
   - Daily capacity: 600 drums
   - Consolidates similar products
   - Checks material availability (RAW + PACK)
   - Auto-generates procurement requisitions for shortages

================================================================================
QUICK REFERENCE - USER ROLES & Access
================================================================================

Admin:           Full access to everything
Sales:           Customers, Quotations, Sales Orders, Products
Finance:         Approve Quotations, Record Payments, View Financial Data
Production:      Job Orders, Production Schedule, Blend Reports, Status Updates
Procurement:     Procurement List, Suppliers, Purchase Orders
Inventory:       Inventory, GRN, Stock Movements
Security:        GRN, Delivery Orders, Dispatch Dashboard, Gate Management
QC:              QC Batches, Approve Blend Reports, Quality Testing
Shipping:        Shipping Bookings, CRO Updates, Container Management
Transport:       Transport Schedules, Vehicle Assignments
Documentation:   Export Documents, Commercial Invoice, B/L, COO

================================================================================
END OF USER MANUAL
================================================================================

For technical support or feature requests, contact system administrator.

Version: 1.0
Last Updated: December 28, 2025
