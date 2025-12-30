# Manufacturing ERP System - Complete Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Workflow by Incoterm](#workflow-by-incoterm)
3. [Module Documentation](#module-documentation)
4. [Database Schema](#database-schema)
5. [API Reference](#api-reference)
6. [Test Credentials](#test-credentials)

---

## System Overview

The Manufacturing ERP is a full-stack application built for managing the complete lifecycle of manufacturing operations including:
- Sales & Quotation Management
- Production Planning & Scheduling
- Inventory & Procurement
- Quality Control & Security
- Shipping & Logistics
- Finance (Payables/Receivables)

### Technology Stack
- **Frontend:** React + TailwindCSS + Shadcn/UI
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **Authentication:** JWT

---

## Workflow by Incoterm

### EXW (Ex Works) - Inward
```
Finance Approves PO → Transport Window (Inward EXW) → Security Gate (Checklist + Weighment) 
→ QC Inspection → GRN Generated → Stock Updated → Payables Notified
```

### DDP (Delivered Duty Paid) - Inward
```
Finance Approves PO → Direct to Security Gate → QC Inspection → GRN Generated 
→ Stock Updated → Payables Notified
```

### FOB/CFR/CIF - Import
```
Finance Approves PO → Import Window (Document Checklist) → Customs Clearance 
→ Transport Window (Inward Import) → Security Gate → QC Inspection → GRN → Stock Update
```

### Local Dispatch (EXW/DDP)
```
Job Order Approved → Production → Ready for Dispatch → Transport Planner 
→ Security Gate (Checklist + Weighment) → QC Inspection → Delivery Order 
→ Tax Invoice Generated → Receivables Notified
```

### Export Container (FOB/CFR/CIF)
```
Job Order Approved → Production → Ready for Dispatch → Shipping Booking (CRO) 
→ Transport Window (Export Container) → Security Gate → QC Inspection 
→ Delivery Order + Packing List + COO + BL Draft + COA Generated 
→ Commercial Invoice → Receivables Notified
```

---

## Module Documentation

### 1. Quotations Module (`/quotations`)

**Purpose:** Create and manage sales quotations for local and export orders.

**Features:**
- Export Orders:
  - Container type selection (20ft, 40ft, ISO Tank, Bulk Tanker)
  - Number of containers with capacity validation
  - Country of origin/destination
  - Incoterm selection (FOB, CFR, CIF, etc.)
- Local Orders:
  - Point of loading/discharge
  - 5% VAT calculation
  - Incoterm selection
- Document checklist management
- Payment terms configuration
- PDF generation

**Container Capacity Validation:**
| Container Type | Max Capacity |
|---------------|--------------|
| 20ft Container | 28 MT |
| 40ft Container | 28 MT |
| ISO Tank | 25 MT |
| Bulk Tanker 45T | 45 MT |
| Bulk Tanker 25T | 25 MT |

**Error Handling:**
- "Max cargo exceeded" error when total weight exceeds container capacity
- Solution: Increase number of containers

---

### 2. Job Orders Module (`/job-orders`)

**Purpose:** Manage production job orders with automatic BOM loading and material availability check.

**Features:**
- Auto-fill from Sales Agreement (SPA)
- Auto-load BOM from BOM Management
- Real-time material availability check
- `procurement_required` flag calculation
- Label confirmation field
- Schedule timing (date-time + shift selection)
- Shift options: Morning (6AM-2PM), Evening (2PM-10PM), Night (10PM-6AM)

**Roles with Access:**
- Admin
- Production
- Procurement
- Sales ✅

**Status Flow:**
```
Pending → Approved → In Production → Ready for Dispatch → Dispatched
```

---

### 3. Procurement Module (`/procurement`)

**Purpose:** Generate Purchase Orders directly from material shortages.

**Workflow:**
1. View material shortages from approved job orders
2. Select shortages (single selection - checkbox bug fixed)
3. Enter unit price for each item
4. Select vendor (with address autofill)
5. Generate PO directly
6. PO appears on Finance Approval page with DRAFT status

**Key Changes (Phase 2):**
- Changed from RFQ model to "Generate PO" model
- Unit price entry during PO generation
- Immediate finance approval routing

---

### 4. Security Gate Module (`/security`)

**Purpose:** Manage security checkpoints for inward and outward cargo.

**Three Windows:**
1. **Inward Transport** - EXW cargo arriving at facility
2. **Outward Transport** - Dispatch cargo leaving facility
3. **RFQ Window** - View all RFQ statuses

**Security Checklist Items:**
- Vehicle inspected
- Driver ID verified
- Seal number checked
- Documents verified
- Weight recorded

**Weighment Entry:**
- Gross weight
- Tare weight
- Net weight (auto-calculated)

**Flow:**
```
Security Checklist → Weighment → Complete → Routes to QC
```

---

### 5. QC Inspection Module (`/qc-inspection`)

**Purpose:** Quality control inspections with COA generation.

**Three Tabs:**
1. **Pending Inspection** - Items requiring QC
2. **Completed** - Passed/Failed inspections
3. **COA Management** - Certificate of Analysis generation

**Standard QC Tests:**
- Appearance
- Color (Pass/Fail/N/A)
- Moisture Content (%)
- pH Level
- Density (g/cm³)
- Purity (%)
- Viscosity (cP)

**Additional Fields (Phase 2.1):**
- Supplier
- Items/Materials
- Quantity
- Inspection Status (Accept/Reject)
- Sampling Size

**QC Report Contains:**
- Supplier
- Vehicle Number
- Quantity
- Product
- PO Number
- Accept/Reject status
- All inspection data

**Flow on Pass:**
- **Inward:** GRN Created → Stock Updated → Payables Notified
- **Outward:** Delivery Order → Invoice (Tax for local, Commercial for export) → Receivables Notified

---

### 6. Transport Window Module (`/transport-window`)

**Purpose:** Manage all transport operations with 4 separate views.

**Four Tabs:**
1. **Inward (EXW)** - Supplier-arranged transport
2. **Inward (Import/Logistics)** - International imports via shipping
3. **Local Dispatch** - Tanker/trailer deliveries
4. **Export Container** - Container shipments for export

**Status Flow:**
- Inward: Pending → In Transit → Arrived → Completed
- Outward: Pending → Loading → Dispatched → Delivered/At Port → Shipped

---

### 7. Transportation Operation Module (`/transport-operation`)

**Purpose:** Manage day-to-day transport operations with scheduling.

**Columns:**
- JO/PO
- Quantity
- Product
- Tanker/Trailer/Container
- Transporter
- Status
- ETA/Time

**Status Options:**
1. **On the Way** - Prompts for ETA
2. **Scheduled** - Prompts for scheduled time
3. **Rescheduled** - Prompts for new transporter and new delivery date

**Features:**
- 7-day view with hierarchical date grouping
- Auto-expand today's date
- Reschedule tracking

---

### 8. Transportation Planner Module (`/transport-planner`)

**Purpose:** Plan and book transports for all operations.

**Three Tabs:**
1. **Inward (EXW)** - View approved EXW POs needing transport booking
2. **Inward (Import)** - International imports
3. **Dispatch** - Jobs ready for dispatch needing transport

**Features:**
- View items needing transport booking
- Book transport with transporter details
- Vehicle type selection (Tanker/Trailer/Container)
- Scheduling

---

### 9. Settings Module (`/settings`)

**Purpose:** Configure system settings.

**Configuration Options:**
1. **Vendors/Suppliers** - Manage vendor information with address autofill
2. **Companies** - Billing and shipping company addresses
3. **Payment Terms** - Net 30, Net 60, Advance, LC, COD
4. **Document Templates** - Required documents for export/local orders
5. **Container Types** - Container types with capacity limits

---

### 10. Finance Approval Module (`/finance-approval`)

**Purpose:** Finance team approves POs before routing to transport.

**Workflow:**
1. View DRAFT status POs
2. Review PO details and amount
3. Approve PO
4. System auto-routes based on incoterm:
   - **EXW:** → Transport Window (Inward)
   - **DDP:** → Security Gate directly
   - **FOB/CFR/CIF:** → Import Window

---

### 11. Payables Module (`/payables`)

**Purpose:** Track accounts payable and GRN-based payments.

**Features:**
- View GRNs pending payment review
- Access QC reports for verification
- Payment scheduling

---

### 12. Receivables Module (`/receivables`)

**Purpose:** Track accounts receivable and invoice generation.

**Invoice Types:**
- **Local Customer:** Tax Invoice (with 5% VAT)
- **International Customer:** Commercial Invoice

---

## Database Schema

### Key Collections

```javascript
// quotations
{
  id: String,
  quotation_number: String,
  customer_id: String,
  order_type: "local" | "export",
  incoterm: String,
  container_type: String,
  container_count: Number,
  country_of_origin: String,
  country_of_destination: String,
  port_of_loading: String,
  port_of_discharge: String,
  payment_terms: String,
  include_vat: Boolean,
  vat_rate: Number,
  required_documents: Array,
  items: Array,
  subtotal: Number,
  vat_amount: Number,
  total: Number,
  status: String
}

// job_orders
{
  id: String,
  job_number: String,
  sales_order_id: String,
  product_id: String,
  quantity: Number,
  packaging: String,
  bom: Array,
  procurement_required: Boolean,
  label_confirmation: String,
  schedule_date: String,
  schedule_shift: String,
  status: String
}

// purchase_orders
{
  id: String,
  po_number: String,
  supplier_id: String,
  supplier_name: String,
  incoterm: String,
  payment_terms: String,
  currency: String,
  total_amount: Number,
  status: "DRAFT" | "APPROVED" | "SENT",
  routed_to: String
}

// security_checklists
{
  id: String,
  checklist_number: String,
  ref_type: "INWARD" | "OUTWARD",
  ref_id: String,
  vehicle_number: String,
  driver_name: String,
  seal_number: String,
  gross_weight: Number,
  tare_weight: Number,
  net_weight: Number,
  checklist_items: Object,
  status: String
}

// qc_inspections
{
  id: String,
  qc_number: String,
  ref_type: "INWARD" | "OUTWARD",
  ref_id: String,
  test_results: Object,
  passed: Boolean,
  coa_generated: Boolean,
  coa_number: String,
  status: String
}

// transport_inward / transport_outward
{
  id: String,
  transport_number: String,
  po_id: String,
  incoterm: String,
  transporter_name: String,
  vehicle_type: String,
  vehicle_number: String,
  operation_status: "ON_THE_WAY" | "SCHEDULED" | "RESCHEDULED",
  eta: String,
  scheduled_time: String,
  rescheduled_date: String,
  status: String
}
```

---

## API Reference

### Quotations
- `GET /api/quotations` - List all quotations
- `POST /api/quotations` - Create quotation
- `PUT /api/quotations/{id}/approve` - Approve quotation

### Job Orders
- `GET /api/job-orders` - List job orders
- `POST /api/job-orders` - Create job order
- `PUT /api/job-orders/{id}/status` - Update status (pending/approved/in_production/ready_for_dispatch/dispatched)

### Procurement
- `GET /api/procurement/shortages` - Get material shortages
- `POST /api/purchase-orders/generate` - Generate PO directly

### Security
- `GET /api/security/dashboard` - Security dashboard stats
- `GET /api/security/inward` - Inward transports for check
- `GET /api/security/outward` - Outward transports for check
- `POST /api/security/checklists` - Create checklist
- `PUT /api/security/checklists/{id}/complete` - Complete checklist

### QC
- `GET /api/qc/dashboard` - QC dashboard stats
- `GET /api/qc/inspections` - List inspections
- `PUT /api/qc/inspections/{id}/pass` - Pass inspection
- `PUT /api/qc/inspections/{id}/fail` - Fail inspection
- `POST /api/qc/inspections/{id}/generate-coa` - Generate COA

### Transport
- `GET /api/transport/inward` - Inward transports
- `GET /api/transport/outward` - Outward transports
- `PUT /api/transport/inward/{id}/operation-status` - Update operation status
- `PUT /api/transport/outward/{id}/operation-status` - Update operation status
- `POST /api/transport/inward/book` - Book inward transport
- `POST /api/transport/outward/book` - Book outward transport

### Finance
- `PUT /api/purchase-orders/{id}/finance-approve` - Finance approve PO (auto-routes by incoterm)

---

## Test Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@erp.com | admin123 |
| Finance | finance@erp.com | finance123 |

---

## Version History

### Phase 1 (Completed)
- Unified Production Scheduling
- Transport Window (4 tabs)
- Import Window with document checklist
- Incoterm-based PO routing
- BOM Management
- Material availability check

### Phase 2 (Completed - December 30, 2025)
- Quotation enhancements (container types, VAT, documents)
- Job Order automation (SPA auto-fill, BOM check)
- Procurement flow rework (Generate PO model)
- Security Gate module
- QC Inspection module with COA
- Shipping/Transport integration

### Phase 2.1 (Current - December 30, 2025)
- Container count validation with max cargo error
- Label confirmation & schedule timing for job orders
- Sales role access to job orders
- Local quotation incoterm dropdown
- Transport Window restructured (4 separate tabs)
- Transportation Operation module
- Transportation Planner module
- Settings page for configuration
- Finance approval auto-routes by incoterm

---

## Support

For technical issues, contact the system administrator.
