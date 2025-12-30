from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
import resend
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Resend Email Configuration
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

app = FastAPI(title="Manufacturing ERP System")
api_router = APIRouter(prefix="/api")

# JWT Configuration
SECRET_KEY = os.environ.get('JWT_SECRET', 'erp-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer()

# ==================== MODELS ====================

# User Roles
ROLES = ['admin', 'sales', 'finance', 'production', 'procurement', 'inventory', 'security', 'qc', 'shipping', 'transport', 'documentation']

class UserBase(BaseModel):
    email: str
    name: str
    role: str
    department: Optional[str] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_active: bool = True

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

# Customer Model
class CustomerCreate(BaseModel):
    name: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    tax_id: Optional[str] = None
    customer_type: str = "local"  # local or export

class Customer(CustomerCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Product Model
class ProductCreate(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    unit: str = "KG"
    price_usd: float = 0
    price_aed: float = 0
    price_eur: float = 0
    category: str = "finished_product"  # raw_material, packaging, finished_product
    min_stock: float = 0
    type: str = "MANUFACTURED"  # MANUFACTURED or TRADED (for production scheduling)
    density_kg_per_l: Optional[float] = None  # For volume to weight conversion

class Product(ProductCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    current_stock: float = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Quotation/PFI Model
class QuotationItem(BaseModel):
    product_id: str
    product_name: str
    sku: Optional[str] = None  # Make optional for backwards compatibility
    quantity: float
    unit_price: float
    packaging: str = "Bulk"
    net_weight_kg: Optional[float] = None  # Net weight per unit for packaging
    weight_mt: Optional[float] = None  # Total weight in MT
    total: float = 0

class QuotationCreate(BaseModel):
    customer_id: str
    customer_name: str
    items: List[QuotationItem]
    currency: str = "USD"  # USD, AED, EUR
    order_type: str = "local"  # local or export
    incoterm: Optional[str] = None  # CFR, FOB, CIF, EXW, DDP
    container_type: Optional[str] = None  # 20ft, 40ft, iso_tank, bulk_tanker_45, etc.
    port_of_loading: Optional[str] = None
    port_of_discharge: Optional[str] = None
    delivery_place: Optional[str] = None
    country_of_origin: Optional[str] = "UAE"
    country_of_destination: Optional[str] = None
    payment_terms: str = "Cash"  # LC, CAD, Cash, TT, Net 30
    validity_days: int = 30
    notes: Optional[str] = None
    required_documents: List[str] = []  # List of document type IDs
    include_vat: bool = True
    vat_rate: float = 0.0
    vat_amount: float = 0.0
    total_weight_mt: float = 0.0

class Quotation(QuotationCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pfi_number: str = ""
    status: str = "pending"  # pending, approved, rejected, converted
    subtotal: float = 0
    tax: float = 0
    total: float = 0
    created_by: str = ""
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Sales Order (SPA) Model
class SalesOrderCreate(BaseModel):
    quotation_id: str
    expected_delivery_date: Optional[str] = None
    notes: Optional[str] = None

class SalesOrder(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    quotation_id: str
    spa_number: str = ""
    customer_id: str = ""
    customer_name: str = ""
    items: List[QuotationItem] = []
    currency: str = "USD"
    total: float = 0
    payment_status: str = "pending"  # pending, partial, paid
    amount_paid: float = 0
    balance: float = 0
    status: str = "active"  # active, completed, cancelled
    expected_delivery_date: Optional[str] = None
    notes: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Payment Model
class PaymentCreate(BaseModel):
    sales_order_id: str
    amount: float
    currency: str = "USD"
    payment_method: str = "bank_transfer"  # bank_transfer, lc, cad, cash
    reference: Optional[str] = None
    notes: Optional[str] = None

class Payment(PaymentCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payment_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    recorded_by: str = ""

# Job Order Model
class BOMItem(BaseModel):
    model_config = ConfigDict(extra="allow")  # Allow extra fields
    # Support both old and new field names
    product_id: Optional[str] = None
    material_id: Optional[str] = None
    product_name: Optional[str] = None
    material_name: Optional[str] = None
    sku: Optional[str] = None
    required_qty: Optional[float] = None
    required_quantity: Optional[float] = None
    available_qty: Optional[float] = 0
    available_quantity: Optional[float] = 0
    unit: str = "KG"
    status: Optional[str] = None

class JobOrderCreate(BaseModel):
    sales_order_id: str
    product_id: str
    product_name: str
    product_sku: Optional[str] = None
    quantity: float
    packaging: Optional[str] = "Bulk"
    delivery_date: Optional[str] = None
    bom: List[BOMItem] = []
    priority: str = "normal"  # low, normal, high, urgent
    notes: Optional[str] = None
    procurement_required: bool = False
    material_shortages: List[Dict] = []

class JobOrder(JobOrderCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_number: str = ""
    spa_number: str = ""
    status: str = "pending"  # pending, approved, in_production, procurement, ready_for_dispatch, dispatched
    procurement_status: str = "not_required"  # not_required, pending, complete
    production_start: Optional[str] = None
    production_end: Optional[str] = None
    batch_number: Optional[str] = None
    blend_report: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# GRN Model (Goods Received Note)
class GRNItem(BaseModel):
    product_id: str
    product_name: str
    sku: Optional[str] = None  # Make optional
    quantity: float
    unit: str = "KG"

class GRNCreate(BaseModel):
    supplier: str
    items: List[GRNItem]
    delivery_note: Optional[str] = None
    notes: Optional[str] = None

class GRN(GRNCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    grn_number: str = ""
    received_by: str = ""
    received_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Phase 9: Payables review fields
    review_status: str = "PENDING_PAYABLES"  # PENDING_PAYABLES, APPROVED, HOLD, REJECTED
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None
    po_id: Optional[str] = None  # Link to Purchase Order)

# Delivery Order Model
class DeliveryOrderCreate(BaseModel):
    job_order_id: str
    shipping_booking_id: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    notes: Optional[str] = None

class DeliveryOrder(DeliveryOrderCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    do_number: str = ""
    job_number: str = ""
    product_name: str = ""
    quantity: float = 0
    issued_by: str = ""
    issued_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Shipping Booking Model
class ShippingBookingCreate(BaseModel):
    job_order_ids: List[str]
    shipping_line: str
    container_type: str = "20ft"  # 20ft, 40ft, 40ft_hc
    container_count: int = 1
    port_of_loading: str
    port_of_discharge: str
    cargo_description: Optional[str] = None
    cargo_weight: Optional[float] = None
    is_dg: bool = False  # Dangerous Goods
    dg_class: Optional[str] = None
    notes: Optional[str] = None

class ShippingBookingUpdate(BaseModel):
    cro_number: Optional[str] = None
    vessel_name: Optional[str] = None
    vessel_date: Optional[str] = None  # Vessel departure date
    cutoff_date: Optional[str] = None  # Container cutoff at port
    gate_cutoff: Optional[str] = None  # Gate cutoff time
    vgm_cutoff: Optional[str] = None  # VGM submission cutoff
    freight_rate: Optional[float] = None
    freight_currency: str = "USD"
    freight_charges: Optional[float] = None  # Total freight charges
    pull_out_date: Optional[str] = None  # Container pull out date
    si_cutoff: Optional[str] = None  # SI (Shipping Instructions) cutoff
    gate_in_date: Optional[str] = None  # Gate in date at port
    status: Optional[str] = None

class ShippingBooking(ShippingBookingCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    booking_number: str = ""
    cro_number: Optional[str] = None
    vessel_name: Optional[str] = None
    vessel_date: Optional[str] = None
    cutoff_date: Optional[str] = None
    gate_cutoff: Optional[str] = None
    vgm_cutoff: Optional[str] = None
    freight_rate: Optional[float] = None
    freight_currency: str = "USD"
    freight_charges: Optional[float] = None  # Total freight charges
    pull_out_date: Optional[str] = None  # Container pull out date
    si_cutoff: Optional[str] = None  # SI cutoff
    gate_in_date: Optional[str] = None  # Gate in date
    pickup_date: Optional[str] = None  # Auto-calculated: cutoff - 3 days
    status: str = "pending"  # pending, cro_received, transport_scheduled, loaded, shipped
    created_by: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Transport Schedule Model
class TransportScheduleCreate(BaseModel):
    shipping_booking_id: str
    transporter: Optional[str] = None
    vehicle_type: str = "Container Chassis"
    pickup_date: str
    pickup_location: str = "Factory"
    notes: Optional[str] = None

class TransportSchedule(TransportScheduleCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schedule_number: str = ""
    booking_number: str = ""
    cro_number: Optional[str] = None
    vessel_name: Optional[str] = None
    vessel_date: Optional[str] = None
    cutoff_date: Optional[str] = None
    container_type: str = ""
    container_count: int = 1
    port_of_loading: str = ""
    job_numbers: List[str] = []
    product_names: List[str] = []
    status: str = "pending"  # pending, assigned, dispatched, at_factory, loaded, delivered_to_port
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    created_by: str = ""
    auto_generated: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Dispatch Schedule Model (for Security to see incoming containers)
class DispatchSchedule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transport_schedule_id: str
    schedule_number: str
    booking_number: str
    job_numbers: List[str]
    product_names: List[str]
    container_type: str
    container_count: int
    pickup_date: str
    expected_arrival: str  # At factory
    vessel_date: str
    cutoff_date: str
    transporter: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    status: str = "scheduled"  # scheduled, in_transit, arrived, loading, loaded, departed
    loading_start: Optional[str] = None
    loading_end: Optional[str] = None
    notes: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Export Document Model
class ExportDocumentCreate(BaseModel):
    shipping_booking_id: str
    document_type: str  # invoice, packing_list, bill_of_lading, certificate_of_origin
    document_number: str
    notes: Optional[str] = None

class ExportDocument(ExportDocumentCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    booking_number: str = ""
    status: str = "draft"  # draft, issued, sent
    created_by: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# QC Batch Model
class QCBatchCreate(BaseModel):
    job_order_id: str
    batch_number: str
    specifications: Dict[str, Any] = {}
    test_results: Dict[str, Any] = {}
    notes: Optional[str] = None

class QCBatch(QCBatchCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_number: str = ""
    product_name: str = ""
    status: str = "pending"  # pending, passed, failed, hold
    inspected_by: str = ""
    inspected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Inventory Movement Model
class InventoryMovement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str
    product_name: str
    sku: str
    movement_type: str  # grn_add, do_deduct, adjustment
    quantity: float
    reference_type: str  # grn, delivery_order, adjustment
    reference_id: str
    reference_number: str
    previous_stock: float
    new_stock: float
    created_by: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# ==================== HELPER FUNCTIONS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_user_from_token(token: str):
    """Get user from token string (for PDF downloads via query param)"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def generate_sequence(prefix: str, collection: str) -> str:
    counter = await db.counters.find_one_and_update(
        {"collection": collection},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    seq = counter.get("seq", 1)
    return f"{prefix}-{str(seq).zfill(6)}"

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/register", response_model=User)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    if user_data.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {ROLES}")
    
    user = User(**user_data.model_dump())
    user_dict = user.model_dump()
    user_dict["password"] = hash_password(user_data.password)
    
    await db.users.insert_one(user_dict)
    return user

@api_router.post("/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Account disabled")
    
    access_token = create_access_token({"sub": user["id"]})
    user_response = {k: v for k, v in user.items() if k not in ["_id", "password"]}
    return Token(access_token=access_token, token_type="bearer", user=user_response)

@api_router.get("/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

# ==================== CUSTOMER ROUTES ====================

@api_router.post("/customers", response_model=Customer)
async def create_customer(data: CustomerCreate, current_user: dict = Depends(get_current_user)):
    customer = Customer(**data.model_dump())
    await db.customers.insert_one(customer.model_dump())
    return customer

@api_router.get("/customers", response_model=List[Customer])
async def get_customers(current_user: dict = Depends(get_current_user)):
    customers = await db.customers.find({}, {"_id": 0}).to_list(1000)
    return customers

@api_router.get("/customers/{customer_id}", response_model=Customer)
async def get_customer(customer_id: str, current_user: dict = Depends(get_current_user)):
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

# ==================== PRODUCT ROUTES ====================

@api_router.post("/products", response_model=Product)
async def create_product(data: ProductCreate, current_user: dict = Depends(get_current_user)):
    existing = await db.products.find_one({"sku": data.sku})
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")
    
    product = Product(**data.model_dump())
    await db.products.insert_one(product.model_dump())
    return product

@api_router.get("/products", response_model=List[Product])
async def get_products(category: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if category:
        query["category"] = category
    products = await db.products.find(query, {"_id": 0}).to_list(1000)
    return products

@api_router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str, current_user: dict = Depends(get_current_user)):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@api_router.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: str, data: ProductCreate, current_user: dict = Depends(get_current_user)):
    result = await db.products.update_one({"id": product_id}, {"$set": data.model_dump()})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return await db.products.find_one({"id": product_id}, {"_id": 0})

# ==================== QUOTATION ROUTES ====================

@api_router.post("/quotations", response_model=Quotation)
async def create_quotation(data: QuotationCreate, current_user: dict = Depends(get_current_user)):
    pfi_number = await generate_sequence("PFI", "quotations")
    
    items_with_total = []
    subtotal = 0
    
    for item in data.items:
        item_dict = item.model_dump()
        
        # Calculate total based on packaging type
        # For packaged items: (net_weight_kg * qty) / 1000 = MT, then MT * unit_price
        # For Bulk: qty (assumed MT) * unit_price
        if item.packaging != "Bulk" and item.net_weight_kg:
            weight_mt = (item.net_weight_kg * item.quantity) / 1000
            item_total = weight_mt * item.unit_price
            item_dict["weight_mt"] = weight_mt
        else:
            # Bulk: quantity is in MT
            weight_mt = item.quantity
            item_total = item.quantity * item.unit_price
            item_dict["weight_mt"] = weight_mt
        
        item_dict["total"] = item_total
        items_with_total.append(item_dict)
        subtotal += item_total
    
    quotation = Quotation(
        **data.model_dump(exclude={"items"}),
        items=items_with_total,
        pfi_number=pfi_number,
        subtotal=subtotal,
        total=subtotal,
        created_by=current_user["id"]
    )
    await db.quotations.insert_one(quotation.model_dump())
    return quotation

@api_router.get("/quotations", response_model=List[Quotation])
async def get_quotations(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    quotations = await db.quotations.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return quotations

@api_router.get("/quotations/{quotation_id}", response_model=Quotation)
async def get_quotation(quotation_id: str, current_user: dict = Depends(get_current_user)):
    quotation = await db.quotations.find_one({"id": quotation_id}, {"_id": 0})
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return quotation

@api_router.put("/quotations/{quotation_id}/approve")
async def approve_quotation(quotation_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "finance"]:
        raise HTTPException(status_code=403, detail="Only finance can approve quotations")
    
    result = await db.quotations.update_one(
        {"id": quotation_id, "status": "pending"},
        {"$set": {
            "status": "approved",
            "approved_by": current_user["id"],
            "approved_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Quotation not found or already processed")
    
    # Get quotation details
    quotation = await db.quotations.find_one({"id": quotation_id}, {"_id": 0})
    if quotation:
        # Send email notification and create in-app notification
        asyncio.create_task(notify_quotation_approved(quotation))
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "title": "Quotation Approved",
            "message": f"Quotation {quotation.get('pfi_number')} for {quotation.get('customer_name')} has been approved",
            "type": "success",
            "link": "/quotations",
            "user_id": None,
            "is_read": False,
            "created_by": "system",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # PHASE 1: Check material availability and create shortages
        material_check = await check_material_availability_for_quotation(quotation)
        
        if material_check["has_shortages"]:
            # Create notification for procurement about shortages
            await create_notification(
                event_type="MATERIAL_SHORTAGE",
                title="Material Shortage Detected",
                message=f"Quotation {quotation.get('pfi_number')} approved but {len(material_check['shortages'])} materials need procurement",
                link="/procurement",
                target_roles=["admin", "procurement"],
                notification_type="warning"
            )
    
    return {"message": "Quotation approved", "material_check": material_check if quotation else None}


async def check_material_availability_for_quotation(quotation: dict) -> dict:
    """
    Check raw materials and packaging availability for a quotation.
    Creates RFQ suggestions for shortages.
    """
    shortages = []
    items = quotation.get("items", [])
    
    for item in items:
        product_id = item.get("product_id")
        quantity = item.get("quantity", 0)
        packaging = item.get("packaging", "Bulk")
        net_weight_kg = item.get("net_weight_kg", 200)  # Default 200kg per unit
        
        # Calculate total KG needed
        if packaging != "Bulk":
            total_kg = quantity * net_weight_kg
        else:
            total_kg = quantity * 1000  # Assume quantity is in MT for bulk
        
        # Get active product BOM
        product_bom = await db.product_boms.find_one({
            "product_id": product_id,
            "is_active": True
        }, {"_id": 0})
        
        if product_bom:
            bom_items = await db.product_bom_items.find({
                "bom_id": product_bom["id"]
            }, {"_id": 0}).to_list(100)
            
            for bom_item in bom_items:
                material_id = bom_item.get("material_item_id")
                qty_per_kg = bom_item.get("qty_kg_per_kg_finished", 0)
                required_qty = total_kg * qty_per_kg
                
                material = await db.inventory_items.find_one({"id": material_id}, {"_id": 0})
                if not material:
                    continue
                
                balance = await db.inventory_balances.find_one({"item_id": material_id}, {"_id": 0})
                on_hand = balance.get("on_hand", 0) if balance else 0
                reserved = balance.get("reserved", 0) if balance else 0
                available = on_hand - reserved
                
                shortage = max(0, required_qty - available)
                
                if shortage > 0:
                    shortages.append({
                        "type": "RAW_MATERIAL",
                        "item_id": material_id,
                        "item_name": material.get("name"),
                        "item_sku": material.get("sku"),
                        "required_qty": required_qty,
                        "available": available,
                        "shortage": shortage,
                        "uom": material.get("uom", "KG"),
                        "product_name": item.get("product_name"),
                        "quotation_id": quotation.get("id"),
                        "pfi_number": quotation.get("pfi_number")
                    })
        
        # Check packaging availability (for non-bulk)
        if packaging != "Bulk":
            # Find packaging type
            packaging_type = await db.packaging.find_one({
                "name": {"$regex": packaging, "$options": "i"}
            }, {"_id": 0})
            
            if packaging_type:
                packaging_bom = await db.packaging_boms.find_one({
                    "packaging_id": packaging_type["id"],
                    "is_active": True
                }, {"_id": 0})
                
                if packaging_bom:
                    pack_items = await db.packaging_bom_items.find({
                        "packaging_bom_id": packaging_bom["id"]
                    }, {"_id": 0}).to_list(100)
                    
                    for pack_item in pack_items:
                        pack_id = pack_item.get("pack_item_id")
                        qty_per_drum = pack_item.get("qty_per_drum", 1)
                        required_qty = quantity * qty_per_drum
                        
                        pack_material = await db.inventory_items.find_one({"id": pack_id}, {"_id": 0})
                        if not pack_material:
                            continue
                        
                        balance = await db.inventory_balances.find_one({"item_id": pack_id}, {"_id": 0})
                        on_hand = balance.get("on_hand", 0) if balance else 0
                        reserved = balance.get("reserved", 0) if balance else 0
                        available = on_hand - reserved
                        
                        shortage = max(0, required_qty - available)
                        
                        if shortage > 0:
                            shortages.append({
                                "type": "PACKAGING",
                                "item_id": pack_id,
                                "item_name": pack_material.get("name"),
                                "item_sku": pack_material.get("sku"),
                                "required_qty": required_qty,
                                "available": available,
                                "shortage": shortage,
                                "uom": pack_material.get("uom", "EA"),
                                "product_name": item.get("product_name"),
                                "quotation_id": quotation.get("id"),
                                "pfi_number": quotation.get("pfi_number")
                            })
    
    # Store shortages in material_shortage collection for RFQ
    if shortages:
        for shortage in shortages:
            existing = await db.material_shortages.find_one({
                "item_id": shortage["item_id"],
                "quotation_id": shortage["quotation_id"],
                "status": "PENDING"
            })
            if not existing:
                shortage["id"] = str(uuid.uuid4())
                shortage["status"] = "PENDING"
                shortage["created_at"] = datetime.now(timezone.utc).isoformat()
                await db.material_shortages.insert_one(shortage)
    
    return {
        "has_shortages": len(shortages) > 0,
        "shortages": shortages,
        "total_shortage_items": len(shortages)
    }

@api_router.put("/quotations/{quotation_id}/reject")
async def reject_quotation(quotation_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "finance"]:
        raise HTTPException(status_code=403, detail="Only finance can reject quotations")
    
    result = await db.quotations.update_one(
        {"id": quotation_id, "status": "pending"},
        {"$set": {"status": "rejected"}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Quotation not found or already processed")
    return {"message": "Quotation rejected"}

# ==================== SALES ORDER ROUTES ====================

@api_router.post("/sales-orders", response_model=SalesOrder)
async def create_sales_order(data: SalesOrderCreate, current_user: dict = Depends(get_current_user)):
    quotation = await db.quotations.find_one({"id": data.quotation_id, "status": "approved"}, {"_id": 0})
    if not quotation:
        raise HTTPException(status_code=400, detail="Quotation not found or not approved")
    
    spa_number = await generate_sequence("SPA", "sales_orders")
    
    sales_order = SalesOrder(
        quotation_id=data.quotation_id,
        spa_number=spa_number,
        customer_id=quotation["customer_id"],
        customer_name=quotation["customer_name"],
        items=quotation["items"],
        currency=quotation["currency"],
        total=quotation["total"],
        balance=quotation["total"],
        expected_delivery_date=data.expected_delivery_date,
        notes=data.notes
    )
    
    await db.sales_orders.insert_one(sales_order.model_dump())
    await db.quotations.update_one({"id": data.quotation_id}, {"$set": {"status": "converted"}})
    return sales_order

@api_router.get("/sales-orders", response_model=List[SalesOrder])
async def get_sales_orders(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    orders = await db.sales_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return orders

@api_router.get("/sales-orders/{order_id}", response_model=SalesOrder)
async def get_sales_order(order_id: str, current_user: dict = Depends(get_current_user)):
    order = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return order

# ==================== PAYMENT ROUTES ====================

@api_router.post("/payments", response_model=Payment)
async def record_payment(data: PaymentCreate, current_user: dict = Depends(get_current_user)):
    order = await db.sales_orders.find_one({"id": data.sales_order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")
    
    payment = Payment(**data.model_dump(), recorded_by=current_user["id"])
    await db.payments.insert_one(payment.model_dump())
    
    new_paid = order["amount_paid"] + data.amount
    new_balance = order["total"] - new_paid
    payment_status = "paid" if new_balance <= 0 else ("partial" if new_paid > 0 else "pending")
    
    await db.sales_orders.update_one(
        {"id": data.sales_order_id},
        {"$set": {"amount_paid": new_paid, "balance": new_balance, "payment_status": payment_status}}
    )
    return payment

@api_router.get("/payments", response_model=List[Payment])
async def get_payments(sales_order_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if sales_order_id:
        query["sales_order_id"] = sales_order_id
    payments = await db.payments.find(query, {"_id": 0}).sort("payment_date", -1).to_list(1000)
    return payments

# ==================== JOB ORDER ROUTES ====================

@api_router.post("/job-orders", response_model=JobOrder)
async def create_job_order(data: JobOrderCreate, current_user: dict = Depends(get_current_user)):
    order = await db.sales_orders.find_one({"id": data.sales_order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")
    
    job_number = await generate_sequence("JOB", "job_orders")
    
    # Check BOM availability
    bom_with_stock = []
    needs_procurement = False
    for item in data.bom:
        product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        available = product["current_stock"] if product else 0
        item_dict = item.model_dump()
        item_dict["available_qty"] = available
        bom_with_stock.append(item_dict)
        if available < item.required_qty:
            needs_procurement = True
    
    job_order = JobOrder(
        **data.model_dump(exclude={"bom"}),
        bom=bom_with_stock,
        job_number=job_number,
        spa_number=order["spa_number"],
        procurement_status="pending" if needs_procurement else "not_required"
    )
    await db.job_orders.insert_one(job_order.model_dump())
    return job_order

@api_router.get("/job-orders", response_model=List[JobOrder])
async def get_job_orders(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    jobs = await db.job_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return jobs

@api_router.get("/job-orders/{job_id}", response_model=JobOrder)
async def get_job_order(job_id: str, current_user: dict = Depends(get_current_user)):
    job = await db.job_orders.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job order not found")
    return job

@api_router.put("/job-orders/{job_id}/status")
async def update_job_status(job_id: str, status: str, current_user: dict = Depends(get_current_user)):
    valid_statuses = ["pending", "in_production", "procurement", "ready_for_dispatch", "dispatched"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    update_data = {"status": status}
    if status == "in_production":
        update_data["production_start"] = datetime.now(timezone.utc).isoformat()
    elif status == "ready_for_dispatch":
        update_data["production_end"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.job_orders.update_one({"id": job_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job order not found")
    
    # Send email notification and create in-app notification
    job = await db.job_orders.find_one({"id": job_id}, {"_id": 0})
    if job:
        asyncio.create_task(notify_job_order_status_change(job, status))
        # Create in-app notification
        notification_types = {
            "in_production": ("info", "Production Started"),
            "ready_for_dispatch": ("success", "Ready for Dispatch"),
            "dispatched": ("success", "Job Dispatched"),
            "procurement": ("warning", "Procurement Needed")
        }
        ntype, ntitle = notification_types.get(status, ("info", "Status Updated"))
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "title": ntitle,
            "message": f"Job {job.get('job_number')} ({job.get('product_name')}) - {status.replace('_', ' ').title()}",
            "type": ntype,
            "link": "/job-orders",
            "user_id": None,
            "is_read": False,
            "created_by": "system",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    return {"message": f"Job status updated to {status}"}

# ==================== GRN ROUTES ====================

@api_router.post("/grn", response_model=GRN)
async def create_grn(data: GRNCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "security", "inventory"]:
        raise HTTPException(status_code=403, detail="Only security/inventory can create GRN")
    
    grn_number = await generate_sequence("GRN", "grn")
    grn = GRN(**data.model_dump(), grn_number=grn_number, received_by=current_user["id"])
    await db.grn.insert_one(grn.model_dump())
    
    # Update inventory - ADD
    for item in data.items:
        product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        if product:
            prev_stock = product["current_stock"]
            new_stock = prev_stock + item.quantity
            await db.products.update_one({"id": item.product_id}, {"$set": {"current_stock": new_stock}})
            
            movement = InventoryMovement(
                product_id=item.product_id,
                product_name=item.product_name,
                sku=item.sku,
                movement_type="grn_add",
                quantity=item.quantity,
                reference_type="grn",
                reference_id=grn.id,
                reference_number=grn_number,
                previous_stock=prev_stock,
                new_stock=new_stock,
                created_by=current_user["id"]
            )
            await db.inventory_movements.insert_one(movement.model_dump())
    
    # Phase 9: Create notification for GRN pending payables review
    await create_notification(
        event_type="GRN_PAYABLES_REVIEW",
        title=f"GRN Pending Review: {grn_number}",
        message=f"New GRN from {data.supplier} with {len(data.items)} items requires payables review",
        link="/grn",
        ref_type="GRN",
        ref_id=grn.id,
        target_roles=["admin", "finance"],
        notification_type="warning"
    )
    
    return grn

@api_router.get("/grn", response_model=List[GRN])
async def get_grns(current_user: dict = Depends(get_current_user)):
    grns = await db.grn.find({}, {"_id": 0}).sort("received_at", -1).to_list(1000)
    return grns

# ==================== PHASE 9: GRN PAYABLES REVIEW ====================

@api_router.get("/grn/pending-payables")
async def get_grns_pending_payables(current_user: dict = Depends(get_current_user)):
    """Get GRNs pending payables review"""
    grns = await db.grn.find(
        {"review_status": {"$in": ["PENDING_PAYABLES", None]}},
        {"_id": 0}
    ).sort("received_at", -1).to_list(1000)
    return grns

@api_router.put("/grn/{grn_id}/payables-approve")
async def payables_approve_grn(grn_id: str, notes: str = "", current_user: dict = Depends(get_current_user)):
    """Payables approves a GRN for AP posting"""
    if current_user["role"] not in ["admin", "finance"]:
        raise HTTPException(status_code=403, detail="Only admin/finance can approve GRN for payables")
    
    grn = await db.grn.find_one({"id": grn_id}, {"_id": 0})
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    
    await db.grn.update_one(
        {"id": grn_id},
        {"$set": {
            "review_status": "APPROVED",
            "reviewed_by": current_user["id"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "review_notes": notes
        }}
    )
    
    return {"success": True, "message": "GRN approved for payables"}

@api_router.put("/grn/{grn_id}/payables-hold")
async def payables_hold_grn(grn_id: str, reason: str = "", current_user: dict = Depends(get_current_user)):
    """Payables puts a GRN on hold"""
    if current_user["role"] not in ["admin", "finance"]:
        raise HTTPException(status_code=403, detail="Only admin/finance can hold GRN")
    
    await db.grn.update_one(
        {"id": grn_id},
        {"$set": {
            "review_status": "HOLD",
            "reviewed_by": current_user["id"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "review_notes": reason
        }}
    )
    
    return {"success": True, "message": "GRN put on hold"}

@api_router.put("/grn/{grn_id}/payables-reject")
async def payables_reject_grn(grn_id: str, reason: str = "", current_user: dict = Depends(get_current_user)):
    """Payables rejects a GRN"""
    if current_user["role"] not in ["admin", "finance"]:
        raise HTTPException(status_code=403, detail="Only admin/finance can reject GRN")
    
    await db.grn.update_one(
        {"id": grn_id},
        {"$set": {
            "review_status": "REJECTED",
            "reviewed_by": current_user["id"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "review_notes": reason
        }}
    )
    
    return {"success": True, "message": "GRN rejected by payables"}

# ==================== DELIVERY ORDER ROUTES ====================

@api_router.post("/delivery-orders", response_model=DeliveryOrder)
async def create_delivery_order(data: DeliveryOrderCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "security"]:
        raise HTTPException(status_code=403, detail="Only security can create delivery orders")
    
    job = await db.job_orders.find_one({"id": data.job_order_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job order not found")
    
    do_number = await generate_sequence("DO", "delivery_orders")
    delivery_order = DeliveryOrder(
        **data.model_dump(),
        do_number=do_number,
        job_number=job["job_number"],
        product_name=job["product_name"],
        quantity=job["quantity"],
        issued_by=current_user["id"]
    )
    await db.delivery_orders.insert_one(delivery_order.model_dump())
    
    # Update job status
    await db.job_orders.update_one({"id": data.job_order_id}, {"$set": {"status": "dispatched"}})
    
    # Update inventory - DEDUCT (for finished product)
    product = await db.products.find_one({"id": job["product_id"]}, {"_id": 0})
    if product:
        prev_stock = product["current_stock"]
        new_stock = max(0, prev_stock - job["quantity"])
        await db.products.update_one({"id": job["product_id"]}, {"$set": {"current_stock": new_stock}})
        
        movement = InventoryMovement(
            product_id=job["product_id"],
            product_name=job["product_name"],
            sku=product["sku"],
            movement_type="do_deduct",
            quantity=job["quantity"],
            reference_type="delivery_order",
            reference_id=delivery_order.id,
            reference_number=do_number,
            previous_stock=prev_stock,
            new_stock=new_stock,
            created_by=current_user["id"]
        )
        await db.inventory_movements.insert_one(movement.model_dump())
    
    return delivery_order

@api_router.get("/delivery-orders", response_model=List[DeliveryOrder])
async def get_delivery_orders(current_user: dict = Depends(get_current_user)):
    orders = await db.delivery_orders.find({}, {"_id": 0}).sort("issued_at", -1).to_list(1000)
    return orders

# ==================== SHIPPING ROUTES ====================

@api_router.post("/shipping-bookings", response_model=ShippingBooking)
async def create_shipping_booking(data: ShippingBookingCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "shipping"]:
        raise HTTPException(status_code=403, detail="Only shipping can create bookings")
    
    booking_number = await generate_sequence("SHP", "shipping_bookings")
    booking = ShippingBooking(**data.model_dump(), booking_number=booking_number, created_by=current_user["id"])
    await db.shipping_bookings.insert_one(booking.model_dump())
    return booking

@api_router.get("/shipping-bookings", response_model=List[ShippingBooking])
async def get_shipping_bookings(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    bookings = await db.shipping_bookings.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return bookings

@api_router.get("/shipping-bookings/{booking_id}")
async def get_shipping_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
    booking = await db.shipping_bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Get linked job orders details
    job_orders = []
    for job_id in booking.get("job_order_ids", []):
        job = await db.job_orders.find_one({"id": job_id}, {"_id": 0})
        if job:
            job_orders.append(job)
    
    return {**booking, "job_orders": job_orders}

@api_router.put("/shipping-bookings/{booking_id}/cro")
async def update_shipping_cro(booking_id: str, data: ShippingBookingUpdate, current_user: dict = Depends(get_current_user)):
    """Update CRO details and auto-generate transport schedules"""
    if current_user["role"] not in ["admin", "shipping"]:
        raise HTTPException(status_code=403, detail="Only shipping can update bookings")
    
    booking = await db.shipping_bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    
    # Calculate pickup date (3 days before cutoff)
    if data.cutoff_date:
        cutoff = datetime.fromisoformat(data.cutoff_date)
        pickup = cutoff - timedelta(days=3)
        update_data["pickup_date"] = pickup.strftime("%Y-%m-%d")
    
    # Update status to cro_received if CRO number provided
    if data.cro_number and booking.get("status") == "pending":
        update_data["status"] = "cro_received"
    
    await db.shipping_bookings.update_one({"id": booking_id}, {"$set": update_data})
    
    # Auto-generate transport schedule if CRO received and cutoff set
    if data.cro_number and data.cutoff_date:
        existing_schedule = await db.transport_schedules.find_one({"shipping_booking_id": booking_id})
        
        if not existing_schedule:
            # Get job order details
            job_numbers = []
            product_names = []
            for job_id in booking.get("job_order_ids", []):
                job = await db.job_orders.find_one({"id": job_id}, {"_id": 0})
                if job:
                    job_numbers.append(job["job_number"])
                    product_names.append(job["product_name"])
            
            # Create transport schedule
            schedule_number = await generate_sequence("TRN", "transport_schedules")
            pickup_date = (datetime.fromisoformat(data.cutoff_date) - timedelta(days=3)).strftime("%Y-%m-%d")
            
            transport_schedule = TransportSchedule(
                shipping_booking_id=booking_id,
                transporter=None,
                vehicle_type="Container Chassis",
                pickup_date=pickup_date,
                pickup_location="Factory",
                schedule_number=schedule_number,
                booking_number=booking["booking_number"],
                cro_number=data.cro_number,
                vessel_name=data.vessel_name,
                vessel_date=data.vessel_date,
                cutoff_date=data.cutoff_date,
                container_type=booking["container_type"],
                container_count=booking["container_count"],
                port_of_loading=booking["port_of_loading"],
                job_numbers=job_numbers,
                product_names=product_names,
                auto_generated=True,
                created_by=current_user["id"]
            )
            await db.transport_schedules.insert_one(transport_schedule.model_dump())
            
            # Create dispatch schedule for security
            dispatch_schedule = DispatchSchedule(
                transport_schedule_id=transport_schedule.id,
                schedule_number=schedule_number,
                booking_number=booking["booking_number"],
                job_numbers=job_numbers,
                product_names=product_names,
                container_type=booking["container_type"],
                container_count=booking["container_count"],
                pickup_date=pickup_date,
                expected_arrival=pickup_date,  # Same day arrival at factory
                vessel_date=data.vessel_date or "",
                cutoff_date=data.cutoff_date
            )
            await db.dispatch_schedules.insert_one(dispatch_schedule.model_dump())
            
            # Update booking status
            await db.shipping_bookings.update_one({"id": booking_id}, {"$set": {"status": "transport_scheduled"}})
            
            # Send email notification to Transport and Security
            updated_booking = await db.shipping_bookings.find_one({"id": booking_id}, {"_id": 0})
            await notify_cro_received(updated_booking, transport_schedule.model_dump())
            
            # Create transport_outward record for Transport Window
            transport_out_number = await generate_sequence("TOUT", "transport_outward")
            # Get customer from first job order
            customer_name = ""
            if booking.get("job_order_ids"):
                first_job = await db.job_orders.find_one({"id": booking["job_order_ids"][0]}, {"_id": 0})
                if first_job:
                    so = await db.sales_orders.find_one({"id": first_job.get("sales_order_id")}, {"_id": 0})
                    if so:
                        customer_name = so.get("customer_name", "")
            
            transport_outward = {
                "id": str(uuid.uuid4()),
                "transport_number": transport_out_number,
                "shipping_booking_id": booking_id,
                "booking_number": booking["booking_number"],
                "cro_number": data.cro_number,
                "job_numbers": job_numbers,
                "customer_name": customer_name,
                "transport_type": "CONTAINER",
                "container_number": None,
                "container_type": booking.get("container_type"),
                "destination": booking.get("port_of_discharge"),
                "dispatch_date": None,
                "delivery_date": None,
                "status": "PENDING",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.transport_outward.insert_one(transport_outward)
    
    return {"message": "CRO details updated and transport schedule generated"}

@api_router.put("/shipping-bookings/{booking_id}")
async def update_shipping_booking(booking_id: str, cro_number: Optional[str] = None, status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    update_data = {}
    if cro_number:
        update_data["cro_number"] = cro_number
    if status:
        update_data["status"] = status
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    result = await db.shipping_bookings.update_one({"id": booking_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Booking not found")
    return {"message": "Booking updated"}

# ==================== TRANSPORT ROUTES ====================

@api_router.post("/transport-schedules", response_model=TransportSchedule)
async def create_transport_schedule(data: TransportScheduleCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "transport"]:
        raise HTTPException(status_code=403, detail="Only transport can create schedules")
    
    booking = await db.shipping_bookings.find_one({"id": data.shipping_booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Shipping booking not found")
    
    # Get job order details
    job_numbers = []
    product_names = []
    for job_id in booking.get("job_order_ids", []):
        job = await db.job_orders.find_one({"id": job_id}, {"_id": 0})
        if job:
            job_numbers.append(job["job_number"])
            product_names.append(job["product_name"])
    
    schedule_number = await generate_sequence("TRN", "transport_schedules")
    schedule = TransportSchedule(
        **data.model_dump(),
        schedule_number=schedule_number,
        booking_number=booking["booking_number"],
        cro_number=booking.get("cro_number"),
        vessel_name=booking.get("vessel_name"),
        vessel_date=booking.get("vessel_date"),
        cutoff_date=booking.get("cutoff_date"),
        container_type=booking["container_type"],
        container_count=booking["container_count"],
        port_of_loading=booking["port_of_loading"],
        job_numbers=job_numbers,
        product_names=product_names,
        created_by=current_user["id"]
    )
    await db.transport_schedules.insert_one(schedule.model_dump())
    return schedule

@api_router.get("/transport-schedules", response_model=List[TransportSchedule])
async def get_transport_schedules(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    schedules = await db.transport_schedules.find(query, {"_id": 0}).sort("pickup_date", 1).to_list(1000)
    return schedules

@api_router.get("/transport-schedules/pending")
async def get_pending_transport_schedules(current_user: dict = Depends(get_current_user)):
    """Get transport schedules pending assignment (for transport department)"""
    schedules = await db.transport_schedules.find(
        {"status": {"$in": ["pending", "assigned"]}},
        {"_id": 0}
    ).sort("pickup_date", 1).to_list(1000)
    return schedules

@api_router.put("/transport-schedules/{schedule_id}")
async def update_transport_schedule(
    schedule_id: str,
    status: Optional[str] = None,
    transporter: Optional[str] = None,
    vehicle_number: Optional[str] = None,
    driver_name: Optional[str] = None,
    driver_phone: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    update_data = {}
    if status:
        update_data["status"] = status
    if transporter:
        update_data["transporter"] = transporter
    if vehicle_number:
        update_data["vehicle_number"] = vehicle_number
    if driver_name:
        update_data["driver_name"] = driver_name
    if driver_phone:
        update_data["driver_phone"] = driver_phone
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    result = await db.transport_schedules.update_one({"id": schedule_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Update dispatch schedule as well
    if any([transporter, vehicle_number, driver_name, driver_phone]):
        dispatch_update = {}
        if transporter:
            dispatch_update["transporter"] = transporter
        if vehicle_number:
            dispatch_update["vehicle_number"] = vehicle_number
        if driver_name:
            dispatch_update["driver_name"] = driver_name
        if driver_phone:
            dispatch_update["driver_phone"] = driver_phone
        await db.dispatch_schedules.update_one(
            {"transport_schedule_id": schedule_id},
            {"$set": dispatch_update}
        )
    
    return {"message": "Schedule updated"}

# ==================== DISPATCH ROUTES (Security View) ====================

@api_router.get("/dispatch-schedules")
async def get_dispatch_schedules(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get dispatch schedules for security/dispatch department"""
    query = {}
    if status:
        query["status"] = status
    schedules = await db.dispatch_schedules.find(query, {"_id": 0}).sort("pickup_date", 1).to_list(1000)
    return schedules

@api_router.get("/dispatch-schedules/today")
async def get_todays_dispatch_schedules(current_user: dict = Depends(get_current_user)):
    """Get today's expected container arrivals for security"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    schedules = await db.dispatch_schedules.find(
        {"pickup_date": today},
        {"_id": 0}
    ).sort("expected_arrival", 1).to_list(1000)
    return schedules

@api_router.get("/dispatch-schedules/upcoming")
async def get_upcoming_dispatch_schedules(days: int = 7, current_user: dict = Depends(get_current_user)):
    """Get upcoming container arrivals for the next N days"""
    today = datetime.now(timezone.utc)
    end_date = today + timedelta(days=days)
    
    schedules = await db.dispatch_schedules.find(
        {
            "pickup_date": {
                "$gte": today.strftime("%Y-%m-%d"),
                "$lte": end_date.strftime("%Y-%m-%d")
            }
        },
        {"_id": 0}
    ).sort("pickup_date", 1).to_list(1000)
    return schedules

@api_router.put("/dispatch-schedules/{schedule_id}/status")
async def update_dispatch_status(schedule_id: str, status: str, current_user: dict = Depends(get_current_user)):
    """Update dispatch status (for security to track loading progress)"""
    valid_statuses = ["scheduled", "in_transit", "arrived", "loading", "loaded", "departed"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    update_data = {"status": status}
    if status == "loading":
        update_data["loading_start"] = datetime.now(timezone.utc).isoformat()
    elif status == "loaded":
        update_data["loading_end"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.dispatch_schedules.update_one({"id": schedule_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Dispatch schedule not found")
    
    return {"message": f"Dispatch status updated to {status}"}

# ==================== DOCUMENTATION ROUTES ====================

@api_router.post("/export-documents", response_model=ExportDocument)
async def create_export_document(data: ExportDocumentCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "documentation"]:
        raise HTTPException(status_code=403, detail="Only documentation can create export documents")
    
    booking = await db.shipping_bookings.find_one({"id": data.shipping_booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Shipping booking not found")
    
    document = ExportDocument(**data.model_dump(), booking_number=booking["booking_number"], created_by=current_user["id"])
    await db.export_documents.insert_one(document.model_dump())
    return document

@api_router.get("/export-documents", response_model=List[ExportDocument])
async def get_export_documents(shipping_booking_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if shipping_booking_id:
        query["shipping_booking_id"] = shipping_booking_id
    docs = await db.export_documents.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return docs

# ==================== QC ROUTES ====================

@api_router.post("/qc-batches", response_model=QCBatch)
async def create_qc_batch(data: QCBatchCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "qc"]:
        raise HTTPException(status_code=403, detail="Only QC can create batches")
    
    job = await db.job_orders.find_one({"id": data.job_order_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job order not found")
    
    batch = QCBatch(
        **data.model_dump(),
        job_number=job["job_number"],
        product_name=job["product_name"],
        inspected_by=current_user["id"]
    )
    await db.qc_batches.insert_one(batch.model_dump())
    
    # Update job order with batch number
    await db.job_orders.update_one({"id": data.job_order_id}, {"$set": {"batch_number": data.batch_number}})
    
    return batch

@api_router.get("/qc-batches", response_model=List[QCBatch])
async def get_qc_batches(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    batches = await db.qc_batches.find(query, {"_id": 0}).sort("inspected_at", -1).to_list(1000)
    return batches

@api_router.put("/qc-batches/{batch_id}/status")
async def update_qc_status(batch_id: str, status: str, current_user: dict = Depends(get_current_user)):
    valid_statuses = ["pending", "passed", "failed", "hold"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    result = await db.qc_batches.update_one({"id": batch_id}, {"$set": {"status": status}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="QC batch not found")
    return {"message": f"QC status updated to {status}"}

# ==================== INVENTORY ROUTES ====================

@api_router.get("/inventory")
async def get_inventory(category: Optional[str] = None, low_stock: Optional[bool] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if category:
        query["category"] = category
    
    products = await db.products.find(query, {"_id": 0}).to_list(1000)
    
    if low_stock:
        products = [p for p in products if p["current_stock"] < p["min_stock"]]
    
    return products

@api_router.get("/inventory/movements")
async def get_inventory_movements(product_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if product_id:
        query["product_id"] = product_id
    movements = await db.inventory_movements.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return movements

# ==================== DASHBOARD ROUTES ====================

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    pending_quotations = await db.quotations.count_documents({"status": "pending"})
    active_sales_orders = await db.sales_orders.count_documents({"status": "active"})
    pending_jobs = await db.job_orders.count_documents({"status": "pending"})
    in_production = await db.job_orders.count_documents({"status": "in_production"})
    ready_dispatch = await db.job_orders.count_documents({"status": "ready_for_dispatch"})
    pending_shipments = await db.shipping_bookings.count_documents({"status": "pending"})
    low_stock_count = await db.products.count_documents({"$expr": {"$lt": ["$current_stock", "$min_stock"]}})
    
    return {
        "pending_quotations": pending_quotations,
        "active_sales_orders": active_sales_orders,
        "pending_jobs": pending_jobs,
        "in_production": in_production,
        "ready_for_dispatch": ready_dispatch,
        "pending_shipments": pending_shipments,
        "low_stock_items": low_stock_count
    }

@api_router.get("/dashboard/recent-activities")
async def get_recent_activities(current_user: dict = Depends(get_current_user)):
    recent_quotations = await db.quotations.find({}, {"_id": 0}).sort("created_at", -1).to_list(5)
    recent_orders = await db.sales_orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(5)
    recent_jobs = await db.job_orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(5)
    
    return {
        "recent_quotations": recent_quotations,
        "recent_orders": recent_orders,
        "recent_jobs": recent_jobs
    }

# ==================== EMAIL NOTIFICATION SERVICE ====================

async def send_email_notification(to_emails: List[str], subject: str, html_content: str):
    """Send email notification using Resend"""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured, skipping email")
        return None
    
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": to_emails,
            "subject": subject,
            "html": html_content
        }
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email sent to {to_emails}: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return None

async def notify_cro_received(booking: dict, transport_schedule: dict):
    """Send notification when CRO is received"""
    # Get users from transport and security departments
    transport_users = await db.users.find({"role": {"$in": ["transport", "security", "admin"]}, "is_active": True}, {"_id": 0}).to_list(100)
    emails = [u["email"] for u in transport_users if u.get("email")]
    
    if not emails:
        return
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #0ea5e9; color: white; padding: 20px; text-align: center;">
            <h1 style="margin: 0;">📦 CRO Received - Action Required</h1>
        </div>
        <div style="padding: 20px; background: #f8f9fa;">
            <h2 style="color: #333;">Container Pickup Required</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Booking #:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{booking.get('booking_number')}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>CRO #:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{booking.get('cro_number')}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Shipping Line:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{booking.get('shipping_line')}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Vessel:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{booking.get('vessel_name')} ({booking.get('vessel_date')})</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Container:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{booking.get('container_count')}x {booking.get('container_type', '').upper()}</td></tr>
                <tr style="background: #fff3cd;"><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>⚠️ Cutoff Date:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd; color: #856404;"><strong>{booking.get('cutoff_date')}</strong></td></tr>
                <tr style="background: #d1ecf1;"><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>🚚 Pickup Date:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd; color: #0c5460;"><strong>{transport_schedule.get('pickup_date')}</strong></td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Route:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{booking.get('port_of_loading')} → {booking.get('port_of_discharge')}</td></tr>
            </table>
            <div style="margin-top: 20px; padding: 15px; background: #e7f3ff; border-radius: 5px;">
                <p style="margin: 0;"><strong>Transport Schedule:</strong> {transport_schedule.get('schedule_number')}</p>
                <p style="margin: 5px 0 0 0;">Jobs: {', '.join(transport_schedule.get('job_numbers', []))}</p>
            </div>
            <p style="margin-top: 20px; color: #666;">Please assign a transporter and vehicle for this pickup.</p>
        </div>
        <div style="background: #333; color: #999; padding: 10px; text-align: center; font-size: 12px;">
            Manufacturing ERP System
        </div>
    </div>
    """
    
    await send_email_notification(
        emails,
        f"🚨 CRO Received - Pickup Required by {transport_schedule.get('pickup_date')} - {booking.get('booking_number')}",
        html_content
    )

# ==================== PRODUCTION SCHEDULING ALGORITHM ====================

class ProductionScheduleItem(BaseModel):
    job_id: str
    job_number: str
    product_name: str
    quantity: float
    priority: str
    spa_number: str
    material_status: str  # ready, partial, not_ready
    ready_percentage: float
    missing_materials: List[Dict[str, Any]]
    available_materials: List[Dict[str, Any]]
    recommended_action: str
    estimated_start: Optional[str] = None

@api_router.get("/production/schedule")
async def get_production_schedule(current_user: dict = Depends(get_current_user)):
    """Get production schedule based on material availability"""
    # Get all pending job orders
    pending_jobs = await db.job_orders.find(
        {"status": {"$in": ["pending", "procurement"]}},
        {"_id": 0}
    ).sort([("priority", -1), ("created_at", 1)]).to_list(1000)
    
    schedule = []
    ready_jobs = []
    partial_jobs = []
    not_ready_jobs = []
    
    for job in pending_jobs:
        bom = job.get("bom", [])
        missing_materials = []
        available_materials = []
        total_items = len(bom)
        ready_items = 0
        
        for item in bom:
            # Support both old (product_id) and new (material_id) BOM structures
            material_id = item.get("product_id") or item.get("material_id")
            material_name = item.get("product_name") or item.get("material_name", "Unknown")
            sku = item.get("sku", "N/A")
            required = item.get("required_qty") or item.get("required_quantity", 0)
            
            if not material_id:
                continue
            
            # Check if it's an inventory item (new structure) or product (old structure)
            product = await db.products.find_one({"id": material_id}, {"_id": 0})
            if product:
                current_stock = product["current_stock"]
            else:
                # Check inventory_balances for new structure
                inventory_item = await db.inventory_items.find_one({"id": material_id}, {"_id": 0})
                if inventory_item:
                    balance = await db.inventory_balances.find_one({"item_id": material_id}, {"_id": 0})
                    current_stock = balance["on_hand"] if balance else 0
                else:
                    current_stock = 0
            
            material_info = {
                "product_id": material_id,
                "product_name": material_name,
                "sku": sku,
                "required_qty": required,
                "available_qty": current_stock,
                "shortage": max(0, required - current_stock),
                "unit": item.get("unit", "KG")
            }
            
            if current_stock >= required:
                ready_items += 1
                available_materials.append(material_info)
            else:
                missing_materials.append(material_info)
        
        ready_percentage = (ready_items / total_items * 100) if total_items > 0 else 100
        
        if ready_percentage == 100:
            material_status = "ready"
            recommended_action = "Start production immediately"
        elif ready_percentage >= 50:
            material_status = "partial"
            recommended_action = "Procure missing materials or start partial production"
        else:
            material_status = "not_ready"
            recommended_action = "Wait for procurement - insufficient materials"
        
        schedule_item = ProductionScheduleItem(
            job_id=job["id"],
            job_number=job["job_number"],
            product_name=job["product_name"],
            quantity=job["quantity"],
            priority=job["priority"],
            spa_number=job["spa_number"],
            material_status=material_status,
            ready_percentage=round(ready_percentage, 1),
            missing_materials=missing_materials,
            available_materials=available_materials,
            recommended_action=recommended_action
        )
        
        if material_status == "ready":
            ready_jobs.append(schedule_item)
        elif material_status == "partial":
            partial_jobs.append(schedule_item)
        else:
            not_ready_jobs.append(schedule_item)
    
    # Sort by priority within each category
    priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    ready_jobs.sort(key=lambda x: priority_order.get(x.priority, 2))
    partial_jobs.sort(key=lambda x: priority_order.get(x.priority, 2))
    not_ready_jobs.sort(key=lambda x: priority_order.get(x.priority, 2))
    
    return {
        "summary": {
            "total_pending": len(pending_jobs),
            "ready_to_produce": len(ready_jobs),
            "partial_materials": len(partial_jobs),
            "awaiting_procurement": len(not_ready_jobs)
        },
        "ready_jobs": [j.model_dump() for j in ready_jobs],
        "partial_jobs": [j.model_dump() for j in partial_jobs],
        "not_ready_jobs": [j.model_dump() for j in not_ready_jobs]
    }

@api_router.get("/production/procurement-list")
async def get_procurement_list(current_user: dict = Depends(get_current_user)):
    """Get list of materials needed for all pending jobs"""
    pending_jobs = await db.job_orders.find(
        {"status": {"$in": ["pending", "procurement"]}},
        {"_id": 0}
    ).to_list(1000)
    
    material_needs = {}
    
    for job in pending_jobs:
        for item in job.get("bom", []):
            # Support both old and new BOM structures
            material_id = item.get("product_id") or item.get("material_id")
            material_name = item.get("product_name") or item.get("material_name", "Unknown")
            sku = item.get("sku", "N/A")
            required = item.get("required_qty") or item.get("required_quantity", 0)
            
            if not material_id:
                continue
            
            if material_id not in material_needs:
                # Check products first (old structure)
                product = await db.products.find_one({"id": material_id}, {"_id": 0})
                if product:
                    current_stock = product["current_stock"]
                else:
                    # Check inventory items (new structure)
                    inventory_item = await db.inventory_items.find_one({"id": material_id}, {"_id": 0})
                    if inventory_item:
                        balance = await db.inventory_balances.find_one({"item_id": material_id}, {"_id": 0})
                        current_stock = balance["on_hand"] if balance else 0
                    else:
                        current_stock = 0
                
                material_needs[material_id] = {
                    "product_id": material_id,
                    "product_name": material_name,
                    "sku": sku,
                    "unit": item.get("unit", "KG"),
                    "current_stock": current_stock,
                    "total_required": 0,
                    "total_shortage": 0,
                    "jobs": []
                }
            
            material_needs[material_id]["total_required"] += required
            material_needs[material_id]["jobs"].append({
                "job_number": job["job_number"],
                "required_qty": required
            })
    
    # Calculate shortages
    procurement_list = []
    for material in material_needs.values():
        shortage = max(0, material["total_required"] - material["current_stock"])
        material["total_shortage"] = shortage
        if shortage > 0:
            procurement_list.append(material)
    
    procurement_list.sort(key=lambda x: x["total_shortage"], reverse=True)
    
    return {
        "total_materials_needed": len(procurement_list),
        "procurement_list": procurement_list
    }

# ==================== BLEND REPORT ====================

class BlendReportCreate(BaseModel):
    job_order_id: str
    batch_number: str
    blend_date: str
    operator_name: str
    materials_used: List[Dict[str, Any]]  # [{product_id, product_name, sku, batch_lot, quantity_used}]
    process_parameters: Dict[str, Any] = {}  # {temperature, mixing_time, speed, etc}
    quality_checks: Dict[str, Any] = {}  # {viscosity, ph, density, etc}
    output_quantity: float
    yield_percentage: float
    notes: Optional[str] = None

class BlendReport(BlendReportCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    report_number: str = ""
    job_number: str = ""
    product_name: str = ""
    status: str = "draft"  # draft, submitted, approved
    created_by: str = ""
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@api_router.post("/blend-reports", response_model=BlendReport)
async def create_blend_report(data: BlendReportCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "production", "qc"]:
        raise HTTPException(status_code=403, detail="Only production/QC can create blend reports")
    
    job = await db.job_orders.find_one({"id": data.job_order_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job order not found")
    
    report_number = await generate_sequence("BLR", "blend_reports")
    
    report = BlendReport(
        **data.model_dump(),
        report_number=report_number,
        job_number=job["job_number"],
        product_name=job["product_name"],
        created_by=current_user["id"]
    )
    await db.blend_reports.insert_one(report.model_dump())
    
    # Update job order with blend report reference
    await db.job_orders.update_one(
        {"id": data.job_order_id},
        {"$set": {"blend_report": report_number}}
    )
    
    return report

@api_router.get("/blend-reports")
async def get_blend_reports(job_order_id: Optional[str] = None, status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if job_order_id:
        query["job_order_id"] = job_order_id
    if status:
        query["status"] = status
    
    reports = await db.blend_reports.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return reports

@api_router.get("/blend-reports/{report_id}")
async def get_blend_report(report_id: str, current_user: dict = Depends(get_current_user)):
    report = await db.blend_reports.find_one({"id": report_id}, {"_id": 0})
    if not report:
        raise HTTPException(status_code=404, detail="Blend report not found")
    return report

@api_router.put("/blend-reports/{report_id}/approve")
async def approve_blend_report(report_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "qc"]:
        raise HTTPException(status_code=403, detail="Only QC can approve blend reports")
    
    result = await db.blend_reports.update_one(
        {"id": report_id},
        {"$set": {
            "status": "approved",
            "approved_by": current_user["id"],
            "approved_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Blend report not found")
    return {"message": "Blend report approved"}

# ==================== PDF GENERATION ====================

def generate_cro_pdf(booking: dict, job_orders: list) -> BytesIO:
    """Generate CRO/Loading Instructions PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, alignment=TA_CENTER, spaceAfter=20)
    elements.append(Paragraph("CONTAINER RELEASE ORDER / LOADING INSTRUCTIONS", title_style))
    elements.append(Spacer(1, 10))
    
    # Booking Details
    booking_data = [
        ["Booking Number:", booking.get("booking_number", ""), "CRO Number:", booking.get("cro_number", "")],
        ["Shipping Line:", booking.get("shipping_line", ""), "Vessel:", booking.get("vessel_name", "")],
        ["Container:", f"{booking.get('container_count', 1)}x {booking.get('container_type', '').upper()}", "Vessel Date:", booking.get("vessel_date", "")],
        ["Port of Loading:", booking.get("port_of_loading", ""), "Port of Discharge:", booking.get("port_of_discharge", "")],
        ["Cutoff Date:", booking.get("cutoff_date", ""), "Gate Cutoff:", booking.get("gate_cutoff", "")],
        ["Pickup Date:", booking.get("pickup_date", ""), "VGM Cutoff:", booking.get("vgm_cutoff", "")],
    ]
    
    booking_table = Table(booking_data, colWidths=[2.5*cm, 5*cm, 2.5*cm, 5*cm])
    booking_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(booking_table)
    elements.append(Spacer(1, 20))
    
    # Cargo Details
    elements.append(Paragraph("CARGO TO LOAD:", styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    cargo_header = ["Job Number", "Product", "Quantity", "Packaging"]
    cargo_data = [cargo_header]
    
    for job in job_orders:
        cargo_data.append([
            job.get("job_number", ""),
            job.get("product_name", ""),
            str(job.get("quantity", "")),
            job.get("packaging", "Bulk")
        ])
    
    cargo_table = Table(cargo_data, colWidths=[3.5*cm, 7*cm, 2.5*cm, 2.5*cm])
    cargo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0ea5e9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
    ]))
    elements.append(cargo_table)
    elements.append(Spacer(1, 20))
    
    # Instructions
    elements.append(Paragraph("LOADING INSTRUCTIONS:", styles['Heading2']))
    instructions = """
    1. Ensure container is clean and dry before loading<br/>
    2. Check container for any damage or holes<br/>
    3. Verify seal numbers before and after loading<br/>
    4. Take photos of empty container, during loading, and sealed container<br/>
    5. Complete VGM declaration before gate cutoff<br/>
    6. Ensure all cargo matches the job order quantities<br/>
    """
    elements.append(Paragraph(instructions, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Footer
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_blend_report_pdf(report: dict) -> BytesIO:
    """Generate Blend Report PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, alignment=TA_CENTER, spaceAfter=20)
    elements.append(Paragraph("BLEND / PRODUCTION REPORT", title_style))
    elements.append(Spacer(1, 10))
    
    # Report Info
    info_data = [
        ["Report Number:", report.get("report_number", ""), "Job Number:", report.get("job_number", "")],
        ["Product:", report.get("product_name", ""), "Batch Number:", report.get("batch_number", "")],
        ["Blend Date:", report.get("blend_date", ""), "Operator:", report.get("operator_name", "")],
        ["Output Quantity:", str(report.get("output_quantity", "")), "Yield:", f"{report.get('yield_percentage', '')}%"],
    ]
    
    info_table = Table(info_data, colWidths=[3*cm, 5*cm, 3*cm, 4.5*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))
    
    # Materials Used
    elements.append(Paragraph("MATERIALS USED:", styles['Heading2']))
    mat_header = ["Material", "SKU", "Batch/Lot", "Quantity Used"]
    mat_data = [mat_header]
    
    for mat in report.get("materials_used", []):
        mat_data.append([
            mat.get("product_name", ""),
            mat.get("sku", ""),
            mat.get("batch_lot", ""),
            str(mat.get("quantity_used", ""))
        ])
    
    mat_table = Table(mat_data, colWidths=[5.5*cm, 3*cm, 3.5*cm, 3.5*cm])
    mat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(mat_table)
    elements.append(Spacer(1, 20))
    
    # Process Parameters
    if report.get("process_parameters"):
        elements.append(Paragraph("PROCESS PARAMETERS:", styles['Heading2']))
        param_data = [[k, str(v)] for k, v in report.get("process_parameters", {}).items()]
        if param_data:
            param_table = Table(param_data, colWidths=[5*cm, 10.5*cm])
            param_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('PADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(param_table)
            elements.append(Spacer(1, 20))
    
    # Quality Checks
    if report.get("quality_checks"):
        elements.append(Paragraph("QUALITY CHECKS:", styles['Heading2']))
        qc_data = [[k, str(v)] for k, v in report.get("quality_checks", {}).items()]
        if qc_data:
            qc_table = Table(qc_data, colWidths=[5*cm, 10.5*cm])
            qc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('PADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(qc_table)
            elements.append(Spacer(1, 20))
    
    # Status and Approval
    status_text = f"Status: {report.get('status', 'draft').upper()}"
    if report.get("approved_at"):
        status_text += f" | Approved: {report.get('approved_at')}"
    elements.append(Paragraph(status_text, styles['Normal']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

@api_router.get("/pdf/cro/{booking_id}")
async def download_cro_pdf(booking_id: str, token: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Download CRO / Loading Instructions PDF"""
    if token:
        await get_user_from_token(token)
    
    booking = await db.shipping_bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Get job orders
    job_orders = []
    for job_id in booking.get("job_order_ids", []):
        job = await db.job_orders.find_one({"id": job_id}, {"_id": 0})
        if job:
            job_orders.append(job)
    
    pdf_buffer = generate_cro_pdf(booking, job_orders)
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=CRO_{booking.get('booking_number', 'unknown')}.pdf"}
    )

@api_router.get("/pdf/blend-report/{report_id}")
async def download_blend_report_pdf(report_id: str, token: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Download Blend Report PDF"""
    if token:
        await get_user_from_token(token)
    
    report = await db.blend_reports.find_one({"id": report_id}, {"_id": 0})
    if not report:
        raise HTTPException(status_code=404, detail="Blend report not found")
    
    pdf_buffer = generate_blend_report_pdf(report)
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=BlendReport_{report.get('report_number', 'unknown')}.pdf"}
    )

# ==================== QUOTATION PDF GENERATION ====================

def generate_quotation_pdf(quotation: dict) -> BytesIO:
    """Generate Quotation/PFI PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, alignment=TA_CENTER, spaceAfter=20)
    elements.append(Paragraph("PROFORMA INVOICE / QUOTATION", title_style))
    elements.append(Spacer(1, 10))
    
    # Header Info
    header_data = [
        ["PFI Number:", quotation.get("pfi_number", ""), "Date:", quotation.get("created_at", "")[:10]],
        ["Customer:", quotation.get("customer_name", ""), "Currency:", quotation.get("currency", "USD")],
        ["Order Type:", quotation.get("order_type", "").upper(), "Payment Terms:", quotation.get("payment_terms", "")],
    ]
    
    if quotation.get("order_type") == "export":
        header_data.append(["Incoterm:", quotation.get("incoterm", ""), "Port of Loading:", quotation.get("port_of_loading", "")])
        header_data.append(["Delivery Place:", quotation.get("delivery_place", ""), "Validity:", f"{quotation.get('validity_days', 30)} days"])
    
    header_table = Table(header_data, colWidths=[3*cm, 5*cm, 3*cm, 5*cm])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 20))
    
    # Items Table
    items_header = ["#", "Product", "SKU", "Qty", "Unit Price", "Packaging", "Total"]
    items_data = [items_header]
    
    currency_symbol = {"USD": "$", "AED": "AED ", "EUR": "€"}.get(quotation.get("currency", "USD"), "$")
    
    for idx, item in enumerate(quotation.get("items", []), 1):
        items_data.append([
            str(idx),
            item.get("product_name", ""),
            item.get("sku", ""),
            str(item.get("quantity", 0)),
            f"{currency_symbol}{item.get('unit_price', 0):,.2f}",
            item.get("packaging", ""),
            f"{currency_symbol}{item.get('total', 0):,.2f}"
        ])
    
    items_table = Table(items_data, colWidths=[0.8*cm, 5*cm, 2.5*cm, 1.5*cm, 2.5*cm, 2*cm, 2.5*cm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (3, 0), (6, -1), 'RIGHT'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 15))
    
    # Totals
    totals_data = [
        ["", "", "", "", "", "Subtotal:", f"{currency_symbol}{quotation.get('subtotal', 0):,.2f}"],
        ["", "", "", "", "", "Total:", f"{currency_symbol}{quotation.get('total', 0):,.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[0.8*cm, 5*cm, 2.5*cm, 1.5*cm, 2.5*cm, 2*cm, 2.5*cm])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (5, 0), (6, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (5, 0), (6, -1), 'RIGHT'),
        ('LINEABOVE', (5, 0), (6, 0), 1, colors.black),
        ('LINEBELOW', (5, -1), (6, -1), 2, colors.black),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 20))
    
    # Notes
    if quotation.get("notes"):
        elements.append(Paragraph("<b>Notes:</b>", styles['Normal']))
        elements.append(Paragraph(quotation.get("notes", ""), styles['Normal']))
    
    # Status
    elements.append(Spacer(1, 20))
    status_style = ParagraphStyle('Status', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12)
    elements.append(Paragraph(f"Status: {quotation.get('status', '').upper()}", status_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

@api_router.get("/pdf/quotation/{quotation_id}")
async def download_quotation_pdf(quotation_id: str, token: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Download Quotation/PFI PDF"""
    # If token provided via query param, use it (for browser downloads)
    if token:
        await get_user_from_token(token)
    
    quotation = await db.quotations.find_one({"id": quotation_id}, {"_id": 0})
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    
    pdf_buffer = generate_quotation_pdf(quotation)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=PFI_{quotation.get('pfi_number', 'unknown')}.pdf"}
    )

# ==================== ADDITIONAL EMAIL NOTIFICATIONS ====================

async def notify_quotation_approved(quotation: dict):
    """Send notification when quotation is approved"""
    # Get sales users
    sales_users = await db.users.find({"role": {"$in": ["sales", "admin"]}, "is_active": True}, {"_id": 0}).to_list(100)
    emails = [u["email"] for u in sales_users if u.get("email")]
    
    if not emails:
        return
    
    currency_symbol = {"USD": "$", "AED": "AED ", "EUR": "€"}.get(quotation.get("currency", "USD"), "$")
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #10b981; color: white; padding: 20px; text-align: center;">
            <h1 style="margin: 0;">✅ Quotation Approved</h1>
        </div>
        <div style="padding: 20px; background: #f8f9fa;">
            <h2 style="color: #333;">Quotation {quotation.get('pfi_number')} has been approved!</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>PFI Number:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{quotation.get('pfi_number')}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Customer:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{quotation.get('customer_name')}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Total:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{currency_symbol}{quotation.get('total', 0):,.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Payment Terms:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{quotation.get('payment_terms')}</td></tr>
            </table>
            <p style="margin-top: 20px;">You can now convert this quotation to a Sales Order.</p>
        </div>
        <div style="background: #333; color: #999; padding: 10px; text-align: center; font-size: 12px;">
            Manufacturing ERP System
        </div>
    </div>
    """
    
    await send_email_notification(
        emails,
        f"✅ Quotation Approved - {quotation.get('pfi_number')} - {quotation.get('customer_name')}",
        html_content
    )

async def notify_job_order_status_change(job: dict, new_status: str):
    """Send notification when job order status changes"""
    # Get relevant users based on status
    roles_to_notify = {
        "in_production": ["production", "admin"],
        "procurement": ["procurement", "admin"],
        "ready_for_dispatch": ["shipping", "security", "admin"],
        "dispatched": ["shipping", "security", "transport", "admin"]
    }
    
    roles = roles_to_notify.get(new_status, ["admin"])
    users = await db.users.find({"role": {"$in": roles}, "is_active": True}, {"_id": 0}).to_list(100)
    emails = [u["email"] for u in users if u.get("email")]
    
    if not emails:
        return
    
    status_colors = {
        "in_production": "#f59e0b",
        "procurement": "#ef4444",
        "ready_for_dispatch": "#10b981",
        "dispatched": "#3b82f6"
    }
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: {status_colors.get(new_status, '#6b7280')}; color: white; padding: 20px; text-align: center;">
            <h1 style="margin: 0;">📦 Job Order Update</h1>
        </div>
        <div style="padding: 20px; background: #f8f9fa;">
            <h2 style="color: #333;">Job {job.get('job_number')} - Status Changed</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Job Number:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{job.get('job_number')}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>SPA Number:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{job.get('spa_number')}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Product:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{job.get('product_name')}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Quantity:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{job.get('quantity')}</td></tr>
                <tr style="background: #e7f3ff;"><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>New Status:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">{new_status.replace('_', ' ').upper()}</td></tr>
            </table>
        </div>
        <div style="background: #333; color: #999; padding: 10px; text-align: center; font-size: 12px;">
            Manufacturing ERP System
        </div>
    </div>
    """
    
    await send_email_notification(
        emails,
        f"📦 Job Order {job.get('job_number')} - {new_status.replace('_', ' ').title()}",
        html_content
    )

async def notify_dispatch_ready(job: dict, dispatch_schedule: dict):
    """Send notification when a dispatch is scheduled"""
    # Get security and transport users
    users = await db.users.find({"role": {"$in": ["security", "transport", "admin"]}, "is_active": True}, {"_id": 0}).to_list(100)
    emails = [u["email"] for u in users if u.get("email")]
    
    if not emails:
        return
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #8b5cf6; color: white; padding: 20px; text-align: center;">
            <h1 style="margin: 0;">🚛 Dispatch Ready</h1>
        </div>
        <div style="padding: 20px; background: #f8f9fa;">
            <h2 style="color: #333;">Container pickup scheduled!</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Schedule #:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{dispatch_schedule.get('schedule_number')}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Booking #:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{dispatch_schedule.get('booking_number')}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Job Numbers:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{', '.join(dispatch_schedule.get('job_numbers', []))}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Products:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{', '.join(dispatch_schedule.get('product_names', []))}</td></tr>
                <tr style="background: #d1ecf1;"><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Pickup Date:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">{dispatch_schedule.get('pickup_date')}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Container:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{dispatch_schedule.get('container_count')}x {dispatch_schedule.get('container_type')}</td></tr>
            </table>
            <p style="margin-top: 20px; color: #666;">Please prepare for container loading at the scheduled time.</p>
        </div>
        <div style="background: #333; color: #999; padding: 10px; text-align: center; font-size: 12px;">
            Manufacturing ERP System
        </div>
    </div>
    """
    
    await send_email_notification(
        emails,
        f"🚛 Dispatch Ready - Pickup on {dispatch_schedule.get('pickup_date')}",
        html_content
    )

# ==================== NOTIFICATIONS ====================

class NotificationCreate(BaseModel):
    title: str
    message: str
    type: str = "info"  # info, warning, success, error
    link: Optional[str] = None
    user_id: Optional[str] = None  # If null, notification is for all users

class Notification(NotificationCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    is_read: bool = False
    created_by: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@api_router.post("/notifications", response_model=Notification)
async def create_notification(data: NotificationCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Only admin can create notifications")
    
    notification = Notification(**data.model_dump(), created_by=current_user["id"])
    await db.notifications.insert_one(notification.model_dump())
    return notification

@api_router.get("/notifications")
async def get_notifications(unread_only: bool = False, current_user: dict = Depends(get_current_user)):
    query = {
        "$or": [
            {"user_id": None},
            {"user_id": current_user["id"]}
        ]
    }
    if unread_only:
        query["is_read"] = False
    
    notifications = await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return notifications

@api_router.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.notifications.update_one(
        {"id": notification_id},
        {"$set": {"is_read": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}

@api_router.put("/notifications/read-all")
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    await db.notifications.update_many(
        {"$or": [{"user_id": None}, {"user_id": current_user["id"]}]},
        {"$set": {"is_read": True}}
    )
    return {"message": "All notifications marked as read"}

@api_router.get("/notifications/recent")
async def get_recent_notifications(current_user: dict = Depends(get_current_user)):
    """Get recent notifications with unread count for dashboard"""
    query = {
        "$or": [
            {"user_id": None},
            {"user_id": current_user["id"]}
        ]
    }
    
    notifications = await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).to_list(10)
    unread_count = await db.notifications.count_documents({**query, "is_read": False})
    
    return {
        "notifications": notifications,
        "unread_count": unread_count
    }

# ==================== USER MANAGEMENT ====================

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None

class UserPasswordChange(BaseModel):
    new_password: str

@api_router.get("/users")
async def get_users(current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Only admin can view users")
    
    users = await db.users.find({}, {"_id": 0, "password": 0}).sort("created_at", -1).to_list(1000)
    return users

@api_router.get("/users/{user_id}")
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin"] and current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Only admin can view other users")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@api_router.put("/users/{user_id}")
async def update_user(user_id: str, data: UserUpdate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Only admin can update users")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    
    if "role" in update_data and update_data["role"] not in ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {ROLES}")
    
    result = await db.users.update_one({"id": user_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    return user

@api_router.put("/users/{user_id}/password")
async def change_user_password(user_id: str, data: UserPasswordChange, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Only admin can change passwords")
    
    hashed = hash_password(data.new_password)
    result = await db.users.update_one({"id": user_id}, {"$set": {"password": hashed}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Password updated successfully"}

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Only admin can delete users")
    
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}

# Helper to create system notifications
async def create_system_notification(title: str, message: str, type: str = "info", link: Optional[str] = None, user_id: Optional[str] = None):
    notification = {
        "id": str(uuid.uuid4()),
        "title": title,
        "message": message,
        "type": type,
        "link": link,
        "user_id": user_id,
        "is_read": False,
        "created_by": "system",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.notifications.insert_one(notification)
    return notification

@api_router.get("/")
async def root():
    return {"message": "Manufacturing ERP API", "version": "1.0.0"}

# ==================== PRODUCTION SCHEDULING APIs (DRUMS-ONLY) ====================

from production_scheduling import (
    ProductionScheduler,
    Packaging, PackagingCreate,
    InventoryItem, InventoryItemCreate, InventoryBalance, InventoryReservation,
    JobOrderItem, JobOrderItemCreate,
    ProductBOM, ProductBOMCreate, ProductBOMItem, ProductBOMItemCreate,
    ProductPackagingSpec, ProductPackagingSpecCreate,
    PackagingBOM, PackagingBOMCreate, PackagingBOMItem, PackagingBOMItemCreate,
    Supplier, SupplierCreate,
    ProcurementRequisition, ProcurementRequisitionLine,
    PurchaseOrder, PurchaseOrderCreate, PurchaseOrderLine, PurchaseOrderLineCreate,
    EmailOutbox,
    ProductionCampaign, ProductionScheduleDay
)

# Initialize scheduler
scheduler = ProductionScheduler(db)

# Packaging Management
@api_router.post("/packaging", response_model=Packaging)
async def create_packaging(data: PackagingCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "inventory"]:
        raise HTTPException(status_code=403, detail="Only admin/inventory can create packaging")
    
    packaging = Packaging(**data.model_dump())
    await db.packaging.insert_one(packaging.model_dump())
    return packaging

@api_router.get("/packaging", response_model=List[Packaging])
async def get_packaging(category: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {'is_active': True}
    if category:
        query['category'] = category
    packaging_list = await db.packaging.find(query, {"_id": 0}).to_list(1000)
    return packaging_list

@api_router.put("/packaging/{packaging_id}", response_model=Packaging)
async def update_packaging(packaging_id: str, data: PackagingCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "inventory"]:
        raise HTTPException(status_code=403, detail="Only admin/inventory can update packaging")
    
    result = await db.packaging.update_one({"id": packaging_id}, {"$set": data.model_dump()})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Packaging not found")
    return await db.packaging.find_one({"id": packaging_id}, {"_id": 0})

# Inventory Items Management
@api_router.post("/inventory-items", response_model=InventoryItem)
async def create_inventory_item(data: InventoryItemCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "inventory"]:
        raise HTTPException(status_code=403, detail="Only admin/inventory can create inventory items")
    
    item = InventoryItem(**data.model_dump())
    await db.inventory_items.insert_one(item.model_dump())
    
    # Create initial balance record
    balance = InventoryBalance(item_id=item.id)
    await db.inventory_balances.insert_one(balance.model_dump())
    
    return item

@api_router.get("/inventory-items")
async def get_inventory_items(item_type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get inventory items with balance and calculated availability status"""
    query = {'is_active': True}
    if item_type:
        query['item_type'] = item_type
    items = await db.inventory_items.find(query, {"_id": 0}).to_list(1000)
    
    # Enrich with balance data and calculate status
    enriched_items = []
    for item in items:
        balance = await db.inventory_balances.find_one({"item_id": item["id"]}, {"_id": 0})
        on_hand = balance.get("on_hand", 0) if balance else 0
        
        # Calculate reserved quantity from reservations
        reservations = await db.inventory_reservations.find({"item_id": item["id"]}, {"_id": 0}).to_list(1000)
        reserved = sum(r.get("qty", 0) for r in reservations)
        
        # Calculate inbound from open PO lines
        po_lines = await db.purchase_order_lines.find({
            "item_id": item["id"],
            "status": {"$in": ["OPEN", "PARTIAL"]}
        }, {"_id": 0}).to_list(1000)
        inbound = sum(line.get("qty", 0) - line.get("received_qty", 0) for line in po_lines)
        
        # Calculate availability
        available = on_hand - reserved
        
        # Determine status
        if available > 0:
            status = "IN_STOCK"
        elif inbound > 0:
            status = "INBOUND"
        else:
            status = "OUT_OF_STOCK"
        
        enriched_item = {
            **item,
            "on_hand": on_hand,
            "reserved": reserved,
            "available": available,
            "inbound": inbound,
            "status": status
        }
        enriched_items.append(enriched_item)
    
    return enriched_items

@api_router.get("/inventory-items/{item_id}/availability")
async def get_inventory_item_availability(item_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed availability for a specific inventory item (Phase 1)"""
    item = await db.inventory_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    # Get balance
    balance = await db.inventory_balances.find_one({"item_id": item_id}, {"_id": 0})
    on_hand = balance.get("on_hand", 0) if balance else 0
    
    # Get reservations
    reservations = await db.inventory_reservations.find({"item_id": item_id}, {"_id": 0}).to_list(1000)
    reserved = sum(r.get("qty", 0) for r in reservations)
    
    # Get inbound from open PO lines
    po_lines = await db.purchase_order_lines.find({
        "item_id": item_id,
        "status": {"$in": ["OPEN", "PARTIAL"]}
    }, {"_id": 0}).to_list(1000)
    
    inbound_details = []
    total_inbound = 0
    for line in po_lines:
        remaining = line.get("qty", 0) - line.get("received_qty", 0)
        if remaining > 0:
            po = await db.purchase_orders.find_one({"id": line.get("po_id")}, {"_id": 0})
            inbound_details.append({
                "po_number": po.get("po_number") if po else "N/A",
                "qty": remaining,
                "promised_delivery_date": line.get("promised_delivery_date"),
                "supplier_name": po.get("supplier_name") if po else "N/A"
            })
            total_inbound += remaining
    
    # Calculate availability
    available = on_hand - reserved
    
    # Determine status
    if available > 0:
        status = "IN_STOCK"
    elif total_inbound > 0:
        status = "INBOUND"
    else:
        status = "OUT_OF_STOCK"
    
    return {
        "item": item,
        "on_hand": on_hand,
        "reserved": reserved,
        "available": available,
        "inbound": total_inbound,
        "inbound_details": inbound_details,
        "status": status,
        "reservations": reservations
    }

# Job Order Items Management
@api_router.post("/job-order-items", response_model=JobOrderItem)
async def create_job_order_item(data: JobOrderItemCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "production", "sales"]:
        raise HTTPException(status_code=403, detail="Only admin/production/sales can create job order items")
    
    item = JobOrderItem(**data.model_dump())
    await db.job_order_items.insert_one(item.model_dump())
    return item

@api_router.get("/job-order-items")
async def get_job_order_items(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query['status'] = status
    items = await db.job_order_items.find(query, {"_id": 0}).to_list(1000)
    return items

# Product BOM Management
@api_router.post("/product-boms", response_model=ProductBOM)
async def create_product_bom(data: ProductBOMCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "production"]:
        raise HTTPException(status_code=403, detail="Only admin/production can create BOMs")
    
    # If this is set as active, deactivate other BOMs for same product
    if data.is_active:
        await db.product_boms.update_many(
            {"product_id": data.product_id, "is_active": True},
            {"$set": {"is_active": False}}
        )
    
    bom = ProductBOM(**data.model_dump())
    await db.product_boms.insert_one(bom.model_dump())
    return bom

@api_router.post("/product-bom-items", response_model=ProductBOMItem)
async def create_product_bom_item(data: ProductBOMItemCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "production"]:
        raise HTTPException(status_code=403, detail="Only admin/production can create BOM items")
    
    item = ProductBOMItem(**data.model_dump())
    await db.product_bom_items.insert_one(item.model_dump())
    return item

@api_router.get("/product-boms/{product_id}")
async def get_product_boms(product_id: str, current_user: dict = Depends(get_current_user)):
    boms = await db.product_boms.find({"product_id": product_id}, {"_id": 0}).to_list(1000)
    
    # For each BOM, get its items
    for bom in boms:
        bom_items = await db.product_bom_items.find({"bom_id": bom['id']}, {"_id": 0}).to_list(1000)
        
        # Enrich with material details
        for item in bom_items:
            material = await db.inventory_items.find_one({"id": item['material_item_id']}, {"_id": 0})
            item['material'] = material
            if material:
                item['material_name'] = material.get('name', 'Unknown')
                item['material_sku'] = material.get('sku', '-')
                item['uom'] = material.get('uom', 'KG')
        
        bom['items'] = bom_items
    
    return boms

# Product-Packaging Conversion Specs
@api_router.post("/product-packaging-specs", response_model=ProductPackagingSpec)
async def create_product_packaging_spec(data: ProductPackagingSpecCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "production"]:
        raise HTTPException(status_code=403, detail="Only admin/production can create conversion specs")
    
    spec = ProductPackagingSpec(**data.model_dump())
    await db.product_packaging_specs.insert_one(spec.model_dump())
    return spec

@api_router.get("/product-packaging-specs/{product_id}")
async def get_product_packaging_specs(product_id: str, current_user: dict = Depends(get_current_user)):
    specs = await db.product_packaging_specs.find({"product_id": product_id}, {"_id": 0}).to_list(1000)
    return specs

# Packaging BOM Management
@api_router.post("/packaging-boms", response_model=PackagingBOM)
async def create_packaging_bom(data: PackagingBOMCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "inventory"]:
        raise HTTPException(status_code=403, detail="Only admin/inventory can create packaging BOMs")
    
    bom = PackagingBOM(**data.model_dump())
    await db.packaging_boms.insert_one(bom.model_dump())
    return bom

@api_router.post("/packaging-bom-items", response_model=PackagingBOMItem)
async def create_packaging_bom_item(data: PackagingBOMItemCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "inventory"]:
        raise HTTPException(status_code=403, detail="Only admin/inventory can create packaging BOM items")
    
    item = PackagingBOMItem(**data.model_dump())
    await db.packaging_bom_items.insert_one(item.model_dump())
    return item

@api_router.get("/packaging-boms/{packaging_id}")
async def get_packaging_boms(packaging_id: str, current_user: dict = Depends(get_current_user)):
    boms = await db.packaging_boms.find({"packaging_id": packaging_id}, {"_id": 0}).to_list(1000)
    
    for bom in boms:
        bom_items = await db.packaging_bom_items.find({"packaging_bom_id": bom['id']}, {"_id": 0}).to_list(1000)
        
        # Enrich with pack item details
        for item in bom_items:
            pack_item = await db.inventory_items.find_one({"id": item['pack_item_id']}, {"_id": 0})
            item['pack_item'] = pack_item
            if pack_item:
                item['pack_item_name'] = pack_item.get('name', 'Unknown')
                item['pack_item_sku'] = pack_item.get('sku', '-')
        
        bom['items'] = bom_items
    
    return boms

# BOM Activation Endpoints
@api_router.put("/product-boms/{bom_id}/activate")
async def activate_product_bom(bom_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "production"]:
        raise HTTPException(status_code=403, detail="Only admin/production can activate BOMs")
    
    bom = await db.product_boms.find_one({"id": bom_id}, {"_id": 0})
    if not bom:
        raise HTTPException(status_code=404, detail="BOM not found")
    
    # Deactivate all other BOMs for this product
    await db.product_boms.update_many(
        {"product_id": bom["product_id"], "is_active": True},
        {"$set": {"is_active": False}}
    )
    
    # Activate this BOM
    await db.product_boms.update_one(
        {"id": bom_id},
        {"$set": {"is_active": True}}
    )
    
    return {"message": "BOM activated successfully"}

@api_router.put("/packaging-boms/{bom_id}/activate")
async def activate_packaging_bom(bom_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "inventory"]:
        raise HTTPException(status_code=403, detail="Only admin/inventory can activate packaging BOMs")
    
    bom = await db.packaging_boms.find_one({"id": bom_id}, {"_id": 0})
    if not bom:
        raise HTTPException(status_code=404, detail="Packaging BOM not found")
    
    # Deactivate all other BOMs for this packaging
    await db.packaging_boms.update_many(
        {"packaging_id": bom["packaging_id"], "is_active": True},
        {"$set": {"is_active": False}}
    )
    
    # Activate this BOM
    await db.packaging_boms.update_one(
        {"id": bom_id},
        {"$set": {"is_active": True}}
    )
    
    return {"message": "Packaging BOM activated successfully"}

# Suppliers Management
@api_router.post("/suppliers", response_model=Supplier)
async def create_supplier(data: SupplierCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "procurement"]:
        raise HTTPException(status_code=403, detail="Only admin/procurement can create suppliers")
    
    supplier = Supplier(**data.model_dump())
    await db.suppliers.insert_one(supplier.model_dump())
    return supplier

@api_router.get("/suppliers")
async def get_suppliers(current_user: dict = Depends(get_current_user)):
    suppliers = await db.suppliers.find({"is_active": True}, {"_id": 0}).to_list(1000)
    return suppliers

# Purchase Orders Management
@api_router.post("/purchase-orders", response_model=PurchaseOrder)
async def create_purchase_order(data: PurchaseOrderCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "procurement"]:
        raise HTTPException(status_code=403, detail="Only admin/procurement can create POs")
    
    po_number = await generate_sequence("PO", "purchase_orders")
    po = PurchaseOrder(**data.model_dump(), po_number=po_number)
    await db.purchase_orders.insert_one(po.model_dump())
    return po

@api_router.post("/purchase-order-lines", response_model=PurchaseOrderLine)
async def create_purchase_order_line(data: PurchaseOrderLineCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "procurement"]:
        raise HTTPException(status_code=403, detail="Only admin/procurement can create PO lines")
    
    line = PurchaseOrderLine(**data.model_dump())
    await db.purchase_order_lines.insert_one(line.model_dump())
    return line

@api_router.get("/purchase-orders")
async def get_purchase_orders(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query['status'] = status
    pos = await db.purchase_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return pos

@api_router.get("/purchase-orders/pending-approval")
async def get_pos_pending_approval(current_user: dict = Depends(get_current_user)):
    """Get POs pending finance approval"""
    pos = await db.purchase_orders.find(
        {"status": "DRAFT"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    
    # Enrich with lines
    enriched_pos = []
    for po in pos:
        lines = await db.purchase_order_lines.find({"po_id": po["id"]}, {"_id": 0}).to_list(1000)
        for line in lines:
            item = await db.inventory_items.find_one({"id": line.get("item_id")}, {"_id": 0})
            line["item_name"] = item.get("name") if item else "Unknown"
        po["lines"] = lines
        enriched_pos.append(po)
    
    return enriched_pos

@api_router.get("/purchase-orders/{po_id}")
async def get_purchase_order(po_id: str, current_user: dict = Depends(get_current_user)):
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    
    # Get PO lines with item details
    lines = await db.purchase_order_lines.find({"po_id": po_id}, {"_id": 0}).to_list(1000)
    
    for line in lines:
        item = await db.inventory_items.find_one({"id": line['item_id']}, {"_id": 0})
        line['item'] = item
    
    po['lines'] = lines
    
    # Get supplier details
    supplier = await db.suppliers.find_one({"id": po['supplier_id']}, {"_id": 0})
    po['supplier'] = supplier
    
    return po

@api_router.put("/purchase-orders/{po_id}/status")
async def update_po_status(po_id: str, status: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "procurement"]:
        raise HTTPException(status_code=403, detail="Only admin/procurement can update PO status")
    
    valid_statuses = ["DRAFT", "APPROVED", "SENT", "PARTIAL", "RECEIVED"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    update_data = {"status": status}
    
    # If status is SENT, create email outbox entry (don't auto-send)
    if status == "SENT":
        update_data["sent_at"] = datetime.now(timezone.utc).isoformat()
        
        # Get PO and supplier details
        po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
        supplier = await db.suppliers.find_one({"id": po['supplier_id']}, {"_id": 0})
        
        if supplier and supplier.get('email'):
            # Create email outbox entry
            email = EmailOutbox(
                to=supplier['email'],
                subject=f"Purchase Order {po['po_number']}",
                body=f"Please find attached Purchase Order {po['po_number']}",
                ref_type="PO",
                ref_id=po_id
            )
            await db.email_outbox.insert_one(email.model_dump())
            update_data["email_status"] = "QUEUED"
        else:
            update_data["email_status"] = "NOT_CONFIGURED"
    
    result = await db.purchase_orders.update_one({"id": po_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="PO not found")
    
    return {"message": f"PO status updated to {status}"}

# Procurement Requisitions
@api_router.get("/procurement-requisitions")
async def get_procurement_requisitions(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "procurement", "production"]:
        raise HTTPException(status_code=403, detail="Only admin/procurement/production can view PRs")
    
    query = {}
    if status:
        query['status'] = status
    
    prs = await db.procurement_requisitions.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    # Get lines for each PR
    for pr in prs:
        lines = await db.procurement_requisition_lines.find({"pr_id": pr['id']}, {"_id": 0}).to_list(1000)
        
        # Enrich with item details
        for line in lines:
            item = await db.inventory_items.find_one({"id": line['item_id']}, {"_id": 0})
            line['item'] = item
        
        pr['lines'] = lines
    
    return prs

# Production Scheduling - Main APIs
@api_router.post("/production/drum-schedule/regenerate")
async def regenerate_drum_schedule(week_start: str, current_user: dict = Depends(get_current_user)):
    """Regenerate weekly drum production schedule"""
    if current_user["role"] not in ["admin", "production"]:
        raise HTTPException(status_code=403, detail="Only admin/production can regenerate schedule")
    
    try:
        result = await scheduler.regenerate_schedule(week_start)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/production/drum-schedule")
async def get_drum_schedule(week_start: str, current_user: dict = Depends(get_current_user)):
    """Get weekly drum production schedule"""
    # Get schedule days for the week
    schedule_days = await db.production_schedule_days.find(
        {"week_start": week_start},
        {"_id": 0}
    ).sort("schedule_date", 1).to_list(1000)
    
    # Enrich with campaign and requirement details
    for day in schedule_days:
        # Get campaign
        campaign = await db.production_campaigns.find_one({"id": day['campaign_id']}, {"_id": 0})
        if campaign:
            # Get product and packaging details
            product = await db.products.find_one({"id": campaign['product_id']}, {"_id": 0})
            packaging = await db.packaging.find_one({"id": campaign['packaging_id']}, {"_id": 0})
            
            campaign['product'] = product
            campaign['packaging'] = packaging
            
            # Get job links
            job_links = await db.production_campaign_job_links.find(
                {"campaign_id": campaign['id']},
                {"_id": 0}
            ).to_list(1000)
            
    # Enrich job links with job order details
            for link in job_links:
                job_order = await db.job_orders.find_one({"id": link['job_order_item_id']}, {"_id": 0})
                if job_order:
                    link['job_order'] = job_order
            
            campaign['job_links'] = job_links
            day['campaign'] = campaign
        
        # Get requirements
        requirements = await db.production_day_requirements.find(
            {"schedule_day_id": day['id']},
            {"_id": 0}
        ).to_list(1000)
        
        # Enrich requirements with item details
        for req in requirements:
            item = await db.inventory_items.find_one({"id": req['item_id']}, {"_id": 0})
            req['item'] = item
        
        day['requirements'] = requirements
    
    # Calculate daily capacity usage
    daily_usage = {}
    for day in schedule_days:
        date_key = day['schedule_date']
        if date_key not in daily_usage:
            daily_usage[date_key] = 0
        daily_usage[date_key] += day['planned_drums']
    
    return {
        'week_start': week_start,
        'schedule_days': schedule_days,
        'daily_capacity': 600,
        'daily_usage': daily_usage
    }

@api_router.get("/production/campaign/{campaign_id}")
async def get_campaign(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Get campaign details with job orders and requirements"""
    campaign = await db.production_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get product and packaging
    product = await db.products.find_one({"id": campaign['product_id']}, {"_id": 0})
    packaging = await db.packaging.find_one({"id": campaign['packaging_id']}, {"_id": 0})
    
    campaign['product'] = product
    campaign['packaging'] = packaging
    
    # Get job links
    job_links = await db.production_campaign_job_links.find(
        {"campaign_id": campaign_id},
        {"_id": 0}
    ).to_list(1000)
    
    for link in job_links:
        job_order = await db.job_orders.find_one({"id": link['job_order_item_id']}, {"_id": 0})
        if job_order:
            link['job_order'] = job_order
    
    campaign['job_links'] = job_links
    
    # Get all schedule days for this campaign
    schedule_days = await db.production_schedule_days.find(
        {"campaign_id": campaign_id},
        {"_id": 0}
    ).sort("schedule_date", 1).to_list(1000)
    
    campaign['schedule_days'] = schedule_days
    
    return campaign

@api_router.get("/production/arrivals")
async def get_arrivals(week_start: str, current_user: dict = Depends(get_current_user)):
    """Get incoming RAW + PACK materials for the week from PO ETAs"""
    from datetime import datetime, timedelta
    
    week_start_date = datetime.fromisoformat(week_start)
    week_end_date = week_start_date + timedelta(days=7)
    
    # Get PO lines with promised delivery dates in this week
    pipeline = [
        {'$match': {
            'promised_delivery_date': {
                '$gte': week_start_date.isoformat(),
                '$lt': week_end_date.isoformat()
            }
        }},
        {'$lookup': {
            'from': 'purchase_orders',
            'localField': 'po_id',
            'foreignField': 'id',
            'as': 'po'
        }},
        {'$unwind': '$po'},
        {'$match': {
            'po.status': {'$in': ['SENT', 'PARTIAL']}
        }},
        {'$lookup': {
            'from': 'inventory_items',
            'localField': 'item_id',
            'foreignField': 'id',
            'as': 'item'
        }},
        {'$unwind': '$item'},
        {'$project': {
            '_id': 0,
            'po_number': '$po.po_number',
            'item_id': 1,
            'item_name': '$item.name',
            'item_type': 1,
            'qty': 1,
            'uom': 1,
            'received_qty': 1,
            'remaining_qty': {'$subtract': ['$qty', '$received_qty']},
            'promised_delivery_date': 1,
            'required_by': 1
        }}
    ]
    
    arrivals = await db.purchase_order_lines.aggregate(pipeline).to_list(1000)
    
    # Group by item type
    raw_arrivals = [a for a in arrivals if a['item_type'] == 'RAW']
    pack_arrivals = [a for a in arrivals if a['item_type'] == 'PACK']
    
    return {
        'week_start': week_start,
        'raw_arrivals': raw_arrivals,
        'pack_arrivals': pack_arrivals,
        'total_arrivals': len(arrivals)
    }

@api_router.post("/production/schedule/approve")
async def approve_schedule(week_start: str, current_user: dict = Depends(get_current_user)):
    """Approve schedule and create material reservations for READY days"""
    if current_user["role"] not in ["admin", "production"]:
        raise HTTPException(status_code=403, detail="Only admin/production can approve schedule")
    
    # Get all READY schedule days for this week
    ready_days = await db.production_schedule_days.find({
        "week_start": week_start,
        "status": "READY"
    }, {"_id": 0}).to_list(1000)
    
    reservations_created = 0
    
    for day in ready_days:
        # Get all requirements for this day
        requirements = await db.production_day_requirements.find({
            "schedule_day_id": day['id']
        }, {"_id": 0}).to_list(1000)
        
        # Create reservations
        for req in requirements:
            reservation = InventoryReservation(
                item_id=req['item_id'],
                ref_type="SCHEDULE_DAY",
                ref_id=day['id'],
                qty=req['required_qty']
            )
            await db.inventory_reservations.insert_one(reservation.model_dump())
            reservations_created += 1
        
        # Update day status (could add "APPROVED" status if needed)
        await db.production_schedule_days.update_one(
            {"id": day['id']},
            {"$set": {"status": "READY"}}  # Keep as READY for now
        )
    
    return {
        "success": True,
        "message": f"Schedule approved and {reservations_created} material reservations created",
        "ready_days_approved": len(ready_days),
        "reservations_created": reservations_created
    }

# ==================== NOTIFICATIONS (STRICT EVENT-BASED) ====================

class NotificationCreate(BaseModel):
    title: str
    message: str
    type: str = "info"  # info, success, warning, error
    link: Optional[str] = None
    event_type: str  # RFQ_QUOTE_RECEIVED, PO_PENDING_APPROVAL, PRODUCTION_BLOCKED, GRN_PAYABLES_REVIEW
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None

async def create_notification(
    event_type: str,
    title: str,
    message: str,
    link: str = None,
    ref_type: str = None,
    ref_id: str = None,
    target_roles: List[str] = None,
    notification_type: str = "info"
):
    """Create notifications for specific events - STRICT, NO NOISE"""
    valid_events = [
        "RFQ_QUOTE_RECEIVED",
        "PO_PENDING_APPROVAL", 
        "PRODUCTION_BLOCKED",
        "GRN_PAYABLES_REVIEW"
    ]
    
    if event_type not in valid_events:
        return None  # Silently ignore invalid events
    
    notification = {
        "id": str(uuid.uuid4()),
        "title": title,
        "message": message,
        "type": notification_type,
        "link": link,
        "event_type": event_type,
        "ref_type": ref_type,
        "ref_id": ref_id,
        "target_roles": target_roles,
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.notifications.insert_one(notification)
    return notification

@api_router.get("/notifications/unread-count")
async def get_unread_notification_count(current_user: dict = Depends(get_current_user)):
    """Get count of unread notifications for current user's role"""
    user_role = current_user.get("role", "")
    
    query = {
        "is_read": False,
        "$or": [
            {"target_roles": {"$exists": False}},
            {"target_roles": None},
            {"target_roles": {"$in": [user_role, "all"]}}
        ]
    }
    
    count = await db.notifications.count_documents(query)
    return {"unread_count": count}

@api_router.get("/notifications/bell")
async def get_bell_notifications(current_user: dict = Depends(get_current_user)):
    """Get notifications for bell icon - strict event-based only"""
    user_role = current_user.get("role", "")
    
    # Only show notifications relevant to user's role
    role_events = {
        "procurement": ["RFQ_QUOTE_RECEIVED", "PRODUCTION_BLOCKED"],
        "finance": ["PO_PENDING_APPROVAL", "GRN_PAYABLES_REVIEW"],
        "production": ["PRODUCTION_BLOCKED", "PO_PENDING_APPROVAL"],
        "admin": ["RFQ_QUOTE_RECEIVED", "PO_PENDING_APPROVAL", "PRODUCTION_BLOCKED", "GRN_PAYABLES_REVIEW"]
    }
    
    allowed_events = role_events.get(user_role, role_events.get("admin", []))
    
    notifications = await db.notifications.find({
        "event_type": {"$in": allowed_events},
        "$or": [
            {"target_roles": {"$exists": False}},
            {"target_roles": None},
            {"target_roles": {"$in": [user_role, "all"]}}
        ]
    }, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    
    unread_count = await db.notifications.count_documents({
        "event_type": {"$in": allowed_events},
        "is_read": False,
        "$or": [
            {"target_roles": {"$exists": False}},
            {"target_roles": None},
            {"target_roles": {"$in": [user_role, "all"]}}
        ]
    })
    
    return {
        "notifications": notifications,
        "unread_count": unread_count
    }

@api_router.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    """Mark a notification as read"""
    await db.notifications.update_one(
        {"id": notification_id},
        {"$set": {"is_read": True}}
    )
    return {"success": True}

@api_router.put("/notifications/read-all")
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    """Mark all notifications as read for current user's role"""
    user_role = current_user.get("role", "")
    await db.notifications.update_many(
        {
            "is_read": False,
            "$or": [
                {"target_roles": {"$exists": False}},
                {"target_roles": None},
                {"target_roles": {"$in": [user_role, "all"]}}
            ]
        },
        {"$set": {"is_read": True}}
    )
    return {"success": True}

# ==================== PHASE 3: SMTP EMAIL QUEUE ====================

class EmailQueueCreate(BaseModel):
    to_email: str
    subject: str
    body_html: str
    body_text: Optional[str] = None
    ref_type: Optional[str] = None  # PO, QUOTATION, etc.
    ref_id: Optional[str] = None

class EmailQueueItem(EmailQueueCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "QUEUED"  # QUEUED, SENT, FAILED
    attempts: int = 0
    last_error: Optional[str] = None
    sent_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@api_router.post("/email/queue")
async def queue_email(data: EmailQueueCreate, current_user: dict = Depends(get_current_user)):
    """Queue an email for sending via SMTP"""
    email_item = EmailQueueItem(**data.model_dump())
    await db.email_outbox.insert_one(email_item.model_dump())
    return {"success": True, "email_id": email_item.id, "status": "QUEUED"}

@api_router.get("/email/outbox")
async def get_email_outbox(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get email queue with SMTP configuration status"""
    query = {}
    if status:
        query["status"] = status
    emails = await db.email_outbox.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    # Check if SMTP is configured
    smtp_host = os.environ.get('SMTP_HOST')
    smtp_configured = smtp_host is not None and smtp_host != ''
    
    return {
        "smtp_configured": smtp_configured,
        "smtp_status": "CONFIGURED" if smtp_configured else "NOT_CONFIGURED",
        "emails": emails
    }

@api_router.post("/email/process-queue")
async def process_email_queue(current_user: dict = Depends(get_current_user)):
    """Process queued emails using SMTP (if configured)"""
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Only admin can process email queue")
    
    # Check SMTP configuration
    smtp_host = os.environ.get('SMTP_HOST')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_user = os.environ.get('SMTP_USER')
    smtp_pass = os.environ.get('SMTP_PASS')
    smtp_from = os.environ.get('SMTP_FROM', smtp_user)
    
    if not smtp_host:
        return {
            "success": False,
            "message": "SMTP not configured. Emails remain QUEUED.",
            "processed": 0
        }
    
    # Get queued emails
    queued_emails = await db.email_outbox.find(
        {"status": "QUEUED"},
        {"_id": 0}
    ).limit(50).to_list(50)
    
    processed = 0
    failed = 0
    
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    for email in queued_emails:
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = email['subject']
            msg['From'] = smtp_from
            msg['To'] = email['to_email']
            
            if email.get('body_text'):
                msg.attach(MIMEText(email['body_text'], 'plain'))
            msg.attach(MIMEText(email['body_html'], 'html'))
            
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, email['to_email'], msg.as_string())
            
            await db.email_outbox.update_one(
                {"id": email['id']},
                {"$set": {
                    "status": "SENT",
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "attempts": email.get('attempts', 0) + 1
                }}
            )
            processed += 1
        except Exception as e:
            await db.email_outbox.update_one(
                {"id": email['id']},
                {"$set": {
                    "status": "FAILED" if email.get('attempts', 0) >= 2 else "QUEUED",
                    "last_error": str(e),
                    "attempts": email.get('attempts', 0) + 1
                }}
            )
            failed += 1
    
    return {
        "success": True,
        "processed": processed,
        "failed": failed,
        "message": f"Processed {processed} emails, {failed} failed"
    }

# ==================== PHASE 4: AUTO PROCUREMENT FROM SHORTAGES ====================

@api_router.get("/procurement/shortages")
async def get_procurement_shortages(current_user: dict = Depends(get_current_user)):
    """Get ALL material shortages derived from BOMs - NOT from job_orders.bom
    
    THIS IS THE SOURCE OF TRUTH FOR PROCUREMENT NEEDS.
    Raw materials come from product_boms/product_bom_items.
    Packaging materials come from packaging_boms/packaging_bom_items.
    """
    
    # Get all pending job orders
    pending_jobs = await db.job_orders.find(
        {"status": {"$in": ["pending", "procurement", "in_production"]}},
        {"_id": 0}
    ).to_list(1000)
    
    shortages = {}  # {item_id: {details}}
    
    for job in pending_jobs:
        product_id = job.get("product_id")
        quantity = job.get("quantity", 0)
        job_number = job.get("job_number", "Unknown")
        
        # Step 1: Get active product BOM for this product
        product_bom = await db.product_boms.find_one({
            "product_id": product_id,
            "is_active": True
        }, {"_id": 0})
        
        if product_bom:
            # Get BOM items (RAW materials)
            bom_items = await db.product_bom_items.find({
                "bom_id": product_bom["id"]
            }, {"_id": 0}).to_list(100)
            
            for bom_item in bom_items:
                material_id = bom_item.get("material_item_id")
                qty_per_kg = bom_item.get("qty_kg_per_kg_finished", 0)
                
                # Get product-packaging spec for net weight
                spec = await db.product_packaging_specs.find_one({
                    "product_id": product_id
                }, {"_id": 0})
                
                net_weight_kg = spec.get("net_weight_kg", 200) if spec else 200  # Default 200kg per drum
                
                # Calculate total RAW material needed
                finished_kg = quantity * net_weight_kg
                required_qty = finished_kg * qty_per_kg
                
                # Get material details from inventory_items
                material = await db.inventory_items.find_one({"id": material_id}, {"_id": 0})
                if not material:
                    continue
                
                # Get current balance
                balance = await db.inventory_balances.find_one({"item_id": material_id}, {"_id": 0})
                on_hand = balance.get("on_hand", 0) if balance else 0
                
                # Get reservations
                reservations = await db.inventory_reservations.find({"item_id": material_id}, {"_id": 0}).to_list(1000)
                reserved = sum(r.get("qty", 0) for r in reservations)
                
                available = on_hand - reserved
                shortage = max(0, required_qty - available)
                
                if shortage > 0:
                    if material_id not in shortages:
                        shortages[material_id] = {
                            "item_id": material_id,
                            "item_name": material.get("name", "Unknown"),
                            "item_sku": material.get("sku", "N/A"),
                            "item_type": "RAW",
                            "uom": material.get("uom", "KG"),
                            "on_hand": on_hand,
                            "reserved": reserved,
                            "available": available,
                            "total_required": 0,
                            "total_shortage": 0,
                            "jobs": []
                        }
                    
                    shortages[material_id]["total_required"] += required_qty
                    shortages[material_id]["total_shortage"] = max(0, shortages[material_id]["total_required"] - available)
                    shortages[material_id]["jobs"].append({
                        "job_number": job_number,
                        "product_name": job.get("product_name", "Unknown"),
                        "required_qty": required_qty
                    })
        
        # Step 2: Get packaging BOM (PACK materials)
        # First find the packaging used for this job (from sales order or default)
        sales_order = await db.sales_orders.find_one({"id": job.get("sales_order_id")}, {"_id": 0})
        if sales_order:
            for item in sales_order.get("items", []):
                if item.get("product_id") == product_id:
                    packaging_name = item.get("packaging", "DRUM")
                    break
            else:
                packaging_name = "DRUM"
        else:
            packaging_name = "DRUM"
        
        # Find packaging by name
        packaging = await db.packaging.find_one({
            "name": {"$regex": packaging_name, "$options": "i"}
        }, {"_id": 0})
        
        if packaging:
            packaging_bom = await db.packaging_boms.find_one({
                "packaging_id": packaging["id"],
                "is_active": True
            }, {"_id": 0})
            
            if packaging_bom:
                pack_items = await db.packaging_bom_items.find({
                    "packaging_bom_id": packaging_bom["id"]
                }, {"_id": 0}).to_list(100)
                
                for pack_item in pack_items:
                    pack_id = pack_item.get("pack_item_id")
                    qty_per_drum = pack_item.get("qty_per_drum", 1)
                    
                    required_qty = quantity * qty_per_drum
                    
                    # Get pack material details
                    pack_material = await db.inventory_items.find_one({"id": pack_id}, {"_id": 0})
                    if not pack_material:
                        continue
                    
                    # Get balance
                    balance = await db.inventory_balances.find_one({"item_id": pack_id}, {"_id": 0})
                    on_hand = balance.get("on_hand", 0) if balance else 0
                    
                    # Get reservations
                    reservations = await db.inventory_reservations.find({"item_id": pack_id}, {"_id": 0}).to_list(1000)
                    reserved = sum(r.get("qty", 0) for r in reservations)
                    
                    available = on_hand - reserved
                    shortage = max(0, required_qty - available)
                    
                    if shortage > 0:
                        if pack_id not in shortages:
                            shortages[pack_id] = {
                                "item_id": pack_id,
                                "item_name": pack_material.get("name", "Unknown"),
                                "item_sku": pack_material.get("sku", "N/A"),
                                "item_type": "PACK",
                                "uom": pack_material.get("uom", "EA"),
                                "on_hand": on_hand,
                                "reserved": reserved,
                                "available": available,
                                "total_required": 0,
                                "total_shortage": 0,
                                "jobs": []
                            }
                        
                        shortages[pack_id]["total_required"] += required_qty
                        shortages[pack_id]["total_shortage"] = max(0, shortages[pack_id]["total_required"] - available)
                        shortages[pack_id]["jobs"].append({
                            "job_number": job_number,
                            "product_name": job.get("product_name", "Unknown"),
                            "required_qty": required_qty
                        })
    
    # Convert to list and sort by shortage
    shortage_list = sorted(shortages.values(), key=lambda x: x["total_shortage"], reverse=True)
    
    return {
        "total_shortages": len(shortage_list),
        "raw_shortages": [s for s in shortage_list if s["item_type"] == "RAW"],
        "pack_shortages": [s for s in shortage_list if s["item_type"] == "PACK"],
        "all_shortages": shortage_list
    }

@api_router.post("/procurement/auto-generate")
async def auto_generate_procurement(current_user: dict = Depends(get_current_user)):
    """Auto-generate procurement requisitions from BOM-derived shortages (Phase 4)
    
    THIS READS FROM product_boms AND packaging_boms - NOT from job_orders.bom
    """
    if current_user["role"] not in ["admin", "production", "procurement"]:
        raise HTTPException(status_code=403, detail="Only admin/production/procurement can auto-generate")
    
    # Get ALL shortages from BOMs
    # Get all pending job orders
    pending_jobs = await db.job_orders.find(
        {"status": {"$in": ["pending", "procurement", "in_production"]}},
        {"_id": 0}
    ).to_list(1000)
    
    shortages = {}  # {item_id: {details}}
    
    for job in pending_jobs:
        product_id = job.get("product_id")
        quantity = job.get("quantity", 0)
        job_number = job.get("job_number", "Unknown")
        delivery_date = job.get("delivery_date")
        
        # Get active product BOM
        product_bom = await db.product_boms.find_one({
            "product_id": product_id,
            "is_active": True
        }, {"_id": 0})
        
        if product_bom:
            bom_items = await db.product_bom_items.find({
                "bom_id": product_bom["id"]
            }, {"_id": 0}).to_list(100)
            
            for bom_item in bom_items:
                material_id = bom_item.get("material_item_id")
                qty_per_kg = bom_item.get("qty_kg_per_kg_finished", 0)
                
                spec = await db.product_packaging_specs.find_one({"product_id": product_id}, {"_id": 0})
                net_weight_kg = spec.get("net_weight_kg", 200) if spec else 200
                
                finished_kg = quantity * net_weight_kg
                required_qty = finished_kg * qty_per_kg
                
                material = await db.inventory_items.find_one({"id": material_id}, {"_id": 0})
                if not material:
                    continue
                
                balance = await db.inventory_balances.find_one({"item_id": material_id}, {"_id": 0})
                on_hand = balance.get("on_hand", 0) if balance else 0
                
                reservations = await db.inventory_reservations.find({"item_id": material_id}, {"_id": 0}).to_list(1000)
                reserved = sum(r.get("qty", 0) for r in reservations)
                
                available = on_hand - reserved
                shortage = max(0, required_qty - available)
                
                if shortage > 0:
                    if material_id not in shortages:
                        shortages[material_id] = {
                            "item_id": material_id,
                            "item_name": material.get("name", "Unknown"),
                            "item_type": "RAW",
                            "uom": material.get("uom", "KG"),
                            "total_shortage": 0,
                            "required_by": delivery_date,
                            "jobs": []
                        }
                    shortages[material_id]["total_shortage"] += shortage
                    shortages[material_id]["jobs"].append(job_number)
        
        # Packaging BOM
        packaging = await db.packaging.find_one({"name": {"$regex": "DRUM", "$options": "i"}}, {"_id": 0})
        if packaging:
            packaging_bom = await db.packaging_boms.find_one({
                "packaging_id": packaging["id"],
                "is_active": True
            }, {"_id": 0})
            
            if packaging_bom:
                pack_items = await db.packaging_bom_items.find({
                    "packaging_bom_id": packaging_bom["id"]
                }, {"_id": 0}).to_list(100)
                
                for pack_item in pack_items:
                    pack_id = pack_item.get("pack_item_id")
                    qty_per_drum = pack_item.get("qty_per_drum", 1)
                    required_qty = quantity * qty_per_drum
                    
                    pack_material = await db.inventory_items.find_one({"id": pack_id}, {"_id": 0})
                    if not pack_material:
                        continue
                    
                    balance = await db.inventory_balances.find_one({"item_id": pack_id}, {"_id": 0})
                    on_hand = balance.get("on_hand", 0) if balance else 0
                    
                    reservations = await db.inventory_reservations.find({"item_id": pack_id}, {"_id": 0}).to_list(1000)
                    reserved = sum(r.get("qty", 0) for r in reservations)
                    
                    available = on_hand - reserved
                    shortage = max(0, required_qty - available)
                    
                    if shortage > 0:
                        if pack_id not in shortages:
                            shortages[pack_id] = {
                                "item_id": pack_id,
                                "item_name": pack_material.get("name", "Unknown"),
                                "item_type": "PACK",
                                "uom": pack_material.get("uom", "EA"),
                                "total_shortage": 0,
                                "required_by": delivery_date,
                                "jobs": []
                            }
                        shortages[pack_id]["total_shortage"] += shortage
                        shortages[pack_id]["jobs"].append(job_number)
    
    if not shortages:
        return {"success": True, "message": "No shortages found from BOMs", "lines_created": 0}
    
    # Find or create draft PR
    existing_pr = await db.procurement_requisitions.find_one({"status": "DRAFT"}, {"_id": 0})
    if not existing_pr:
        pr = ProcurementRequisition(notes=f"Auto-generated from BOM shortages on {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
        await db.procurement_requisitions.insert_one(pr.model_dump())
        existing_pr = pr.model_dump()
    
    lines_created = 0
    
    for item_id, shortage_data in shortages.items():
        # Check if line already exists
        existing_line = await db.procurement_requisition_lines.find_one({
            "pr_id": existing_pr["id"],
            "item_id": item_id
        })
        
        if existing_line:
            # Update qty if larger
            if shortage_data["total_shortage"] > existing_line.get("qty", 0):
                await db.procurement_requisition_lines.update_one(
                    {"id": existing_line["id"]},
                    {"$set": {"qty": shortage_data["total_shortage"]}}
                )
        else:
            pr_line = ProcurementRequisitionLine(
                pr_id=existing_pr["id"],
                item_id=item_id,
                item_type=shortage_data["item_type"],
                qty=shortage_data["total_shortage"],
                uom=shortage_data["uom"],
                required_by=shortage_data.get("required_by"),
                reason=f"Shortage for jobs: {', '.join(shortage_data['jobs'][:3])}"
            )
            await db.procurement_requisition_lines.insert_one(pr_line.model_dump())
            lines_created += 1
    
    # Create notification for blocked production
    if lines_created > 0:
        await create_notification(
            event_type="PRODUCTION_BLOCKED",
            title="Material Shortages Detected",
            message=f"{lines_created} items need procurement. View requisition for details.",
            link="/procurement",
            target_roles=["admin", "procurement"],
            notification_type="warning"
        )
    
    return {
        "success": True,
        "message": f"Created {lines_created} procurement requisition lines from BOM shortages",
        "pr_id": existing_pr["id"],
        "lines_created": lines_created,
        "shortages": list(shortages.values())
    }

# ==================== PHASE 5: RFQ FLOW ====================

class RFQCreate(BaseModel):
    supplier_id: str
    rfq_type: str = "PRODUCT"  # PRODUCT or PACKAGING
    lines: List[Dict[str, Any]]  # [{item_id, qty, required_by, job_numbers}]
    billing_company: Optional[str] = None
    billing_address: Optional[str] = None
    shipping_company: Optional[str] = None
    shipping_address: Optional[str] = None
    delivery_date: Optional[str] = None
    payment_terms: Optional[str] = None
    incoterm: Optional[str] = None
    notes: Optional[str] = None

class RFQ(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rfq_number: str = ""
    rfq_type: str = "PRODUCT"  # PRODUCT or PACKAGING
    supplier_id: str
    supplier_name: str = ""
    supplier_address: str = ""
    billing_company: Optional[str] = None
    billing_address: Optional[str] = None
    shipping_company: Optional[str] = None
    shipping_address: Optional[str] = None
    delivery_date: Optional[str] = None
    payment_terms: Optional[str] = None
    incoterm: Optional[str] = None
    status: str = "DRAFT"  # DRAFT, SENT, QUOTED, CONVERTED, CANCELLED
    lines: List[Dict[str, Any]] = []
    total_amount: float = 0
    currency: str = "USD"
    notes: Optional[str] = None
    quoted_at: Optional[str] = None
    converted_po_id: Optional[str] = None
    created_by: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class RFQLineQuote(BaseModel):
    item_id: str
    unit_price: float
    lead_time_days: Optional[int] = None

class RFQQuoteUpdate(BaseModel):
    lines: List[RFQLineQuote]
    notes: Optional[str] = None

@api_router.post("/rfq")
async def create_rfq(data: RFQCreate, current_user: dict = Depends(get_current_user)):
    """Create a new RFQ (Request for Quotation)"""
    if current_user["role"] not in ["admin", "procurement"]:
        raise HTTPException(status_code=403, detail="Only admin/procurement can create RFQs")
    
    supplier = await db.suppliers.find_one({"id": data.supplier_id}, {"_id": 0})
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    rfq_number = await generate_sequence("RFQ", "rfq")
    
    # Enrich lines with item details
    enriched_lines = []
    for line in data.lines:
        item = await db.inventory_items.find_one({"id": line.get("item_id")}, {"_id": 0})
        enriched_lines.append({
            **line,
            "item_name": item.get("name") if item else "Unknown",
            "item_sku": item.get("sku") if item else "N/A",
            "uom": item.get("uom") if item else "KG",
            "unit_price": 0,
            "lead_time_days": None
        })
    
    rfq = RFQ(
        rfq_number=rfq_number,
        rfq_type=data.rfq_type,
        supplier_id=data.supplier_id,
        supplier_name=supplier.get("name", "Unknown"),
        supplier_address=supplier.get("address", ""),
        billing_company=data.billing_company,
        billing_address=data.billing_address,
        shipping_company=data.shipping_company,
        shipping_address=data.shipping_address,
        delivery_date=data.delivery_date,
        payment_terms=data.payment_terms,
        incoterm=data.incoterm,
        lines=enriched_lines,
        notes=data.notes,
        created_by=current_user["id"]
    )
    
    await db.rfq.insert_one(rfq.model_dump())
    return rfq.model_dump()

@api_router.get("/rfq")
async def get_rfqs(status: Optional[str] = None, rfq_type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get all RFQs"""
    query = {}
    if status:
        query["status"] = status
    if rfq_type:
        query["rfq_type"] = rfq_type
    rfqs = await db.rfq.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return rfqs

# Companies endpoint for billing/shipping
@api_router.get("/companies")
async def get_companies(current_user: dict = Depends(get_current_user)):
    """Get all companies for billing/shipping selection"""
    companies = await db.companies.find({}, {"_id": 0}).to_list(100)
    if not companies:
        # Return default companies if none exist
        return [
            {"id": "1", "name": "Main Factory", "address": "123 Industrial Area, Manufacturing City"},
            {"id": "2", "name": "Warehouse A", "address": "456 Storage Zone, Distribution City"}
        ]
    return companies

@api_router.get("/rfq/{rfq_id}")
async def get_rfq(rfq_id: str, current_user: dict = Depends(get_current_user)):
    """Get RFQ details"""
    rfq = await db.rfq.find_one({"id": rfq_id}, {"_id": 0})
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    return rfq

@api_router.put("/rfq/{rfq_id}/send")
async def send_rfq(rfq_id: str, current_user: dict = Depends(get_current_user)):
    """Mark RFQ as SENT and queue email to supplier"""
    if current_user["role"] not in ["admin", "procurement"]:
        raise HTTPException(status_code=403, detail="Only admin/procurement can send RFQs")
    
    rfq = await db.rfq.find_one({"id": rfq_id}, {"_id": 0})
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    supplier = await db.suppliers.find_one({"id": rfq["supplier_id"]}, {"_id": 0})
    
    # Queue email
    if supplier and supplier.get("email"):
        items_list = "<br>".join([f"- {l.get('item_name')}: {l.get('qty')} {l.get('uom')}" for l in rfq.get("lines", [])])
        email_body = f"""
        <h2>Request for Quotation: {rfq.get('rfq_number')}</h2>
        <p>Dear {supplier.get('name')},</p>
        <p>Please provide your best quotation for the following items:</p>
        <p>{items_list}</p>
        <p>Notes: {rfq.get('notes', 'N/A')}</p>
        <p>Thank you.</p>
        """
        email_item = EmailQueueItem(
            to_email=supplier.get("email"),
            subject=f"RFQ {rfq.get('rfq_number')} - Request for Quotation",
            body_html=email_body,
            ref_type="RFQ",
            ref_id=rfq_id
        )
        await db.email_outbox.insert_one(email_item.model_dump())
    
    await db.rfq.update_one({"id": rfq_id}, {"$set": {"status": "SENT"}})
    
    return {"success": True, "message": "RFQ sent to supplier", "email_queued": bool(supplier and supplier.get("email"))}

@api_router.put("/rfq/{rfq_id}/quote")
async def update_rfq_quote(rfq_id: str, data: RFQQuoteUpdate, current_user: dict = Depends(get_current_user)):
    """Update RFQ with supplier's quoted prices"""
    if current_user["role"] not in ["admin", "procurement"]:
        raise HTTPException(status_code=403, detail="Only admin/procurement can update RFQ quotes")
    
    rfq = await db.rfq.find_one({"id": rfq_id}, {"_id": 0})
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    # Update lines with quoted prices
    updated_lines = rfq.get("lines", [])
    total_amount = 0
    
    for quote_line in data.lines:
        for line in updated_lines:
            if line.get("item_id") == quote_line.item_id:
                line["unit_price"] = quote_line.unit_price
                line["lead_time_days"] = quote_line.lead_time_days
                line["total"] = line.get("qty", 0) * quote_line.unit_price
                total_amount += line["total"]
    
    await db.rfq.update_one(
        {"id": rfq_id},
        {"$set": {
            "lines": updated_lines,
            "total_amount": total_amount,
            "status": "QUOTED",
            "quoted_at": datetime.now(timezone.utc).isoformat(),
            "notes": data.notes or rfq.get("notes")
        }}
    )
    
    # Create notification for RFQ quote received
    await create_notification(
        event_type="RFQ_QUOTE_RECEIVED",
        title=f"Quote Received: {rfq.get('rfq_number')}",
        message=f"Supplier {rfq.get('supplier_name')} quoted {rfq.get('currency', 'USD')} {total_amount:.2f}",
        link="/procurement",
        ref_type="RFQ",
        ref_id=rfq_id,
        target_roles=["admin", "procurement"],
        notification_type="success"
    )
    
    return {"success": True, "message": "RFQ quote updated", "total_amount": total_amount}

@api_router.post("/rfq/{rfq_id}/convert-to-po")
async def convert_rfq_to_po(rfq_id: str, current_user: dict = Depends(get_current_user)):
    """Convert a quoted RFQ to a Purchase Order"""
    if current_user["role"] not in ["admin", "procurement"]:
        raise HTTPException(status_code=403, detail="Only admin/procurement can convert RFQ to PO")
    
    rfq = await db.rfq.find_one({"id": rfq_id}, {"_id": 0})
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    if rfq.get("status") != "QUOTED":
        raise HTTPException(status_code=400, detail="Only QUOTED RFQs can be converted to PO")
    
    # Create PO
    po_number = await generate_sequence("PO", "purchase_orders")
    
    po = PurchaseOrder(
        po_number=po_number,
        supplier_id=rfq["supplier_id"],
        supplier_name=rfq.get("supplier_name", ""),
        currency=rfq.get("currency", "USD"),
        total_amount=rfq.get("total_amount", 0),
        rfq_id=rfq_id,
        status="DRAFT",  # Requires finance approval
        created_by=current_user["id"]
    )
    await db.purchase_orders.insert_one(po.model_dump())
    
    # Create PO lines
    for line in rfq.get("lines", []):
        po_line = PurchaseOrderLine(
            po_id=po.id,
            item_id=line.get("item_id"),
            item_type=line.get("item_type", "RAW"),
            qty=line.get("qty", 0),
            uom=line.get("uom", "KG"),
            unit_price=line.get("unit_price", 0),
            required_by=line.get("required_by")
        )
        await db.purchase_order_lines.insert_one(po_line.model_dump())
    
    # Update RFQ status
    await db.rfq.update_one({"id": rfq_id}, {"$set": {"status": "CONVERTED", "converted_po_id": po.id}})
    
    # Create notification for PO pending approval
    await create_notification(
        event_type="PO_PENDING_APPROVAL",
        title=f"PO Pending Approval: {po_number}",
        message=f"New PO from {rfq.get('supplier_name')} for {rfq.get('currency', 'USD')} {rfq.get('total_amount', 0):.2f} requires finance approval",
        link="/finance-approval",
        ref_type="PO",
        ref_id=po.id,
        target_roles=["admin", "finance"],
        notification_type="warning"
    )
    
    return {"success": True, "message": f"PO {po_number} created from RFQ", "po_id": po.id, "po_number": po_number}


# ==================== PHASE 2: GENERATE PO DIRECTLY (Bug 5 Fix) ====================

class GeneratePORequest(BaseModel):
    supplier_id: str
    supplier_name: str = ""
    billing_company: Optional[str] = None
    billing_address: Optional[str] = None
    shipping_company: Optional[str] = None
    shipping_address: Optional[str] = None
    delivery_date: Optional[str] = None
    payment_terms: str = "Net 30"
    incoterm: str = "EXW"
    currency: str = "USD"
    total_amount: float = 0
    lines: List[Dict[str, Any]] = []
    notes: Optional[str] = None

@api_router.post("/purchase-orders/generate")
async def generate_po_directly(data: GeneratePORequest, current_user: dict = Depends(get_current_user)):
    """
    Generate PO directly from procurement shortages (Phase 2 - Bug 5 fix).
    This bypasses the RFQ process and creates a PO with status DRAFT
    that goes immediately to Finance Approval.
    """
    if current_user["role"] not in ["admin", "procurement"]:
        raise HTTPException(status_code=403, detail="Only admin/procurement can generate POs")
    
    if not data.lines:
        raise HTTPException(status_code=400, detail="No items provided")
    
    # Generate PO number
    po_number = await generate_sequence("PO", "purchase_orders")
    
    # Create PO with DRAFT status (pending finance approval)
    po = PurchaseOrder(
        supplier_id=data.supplier_id,
        supplier_name=data.supplier_name,
        currency=data.currency,
        total_amount=data.total_amount,
        notes=data.notes,
        po_number=po_number,
        status="DRAFT",  # Will require finance approval
        created_by=current_user["id"]
    )
    await db.purchase_orders.insert_one(po.model_dump())
    
    # Create PO lines
    for line_data in data.lines:
        # Lookup item details
        item = await db.inventory_items.find_one({"id": line_data.get("item_id")}, {"_id": 0})
        item_name = line_data.get("item_name") or (item.get("name") if item else "Unknown")
        
        po_line = PurchaseOrderLine(
            po_id=po.id,
            item_id=line_data.get("item_id"),
            item_type=line_data.get("item_type", "RAW"),
            qty=line_data.get("qty", 0),
            uom=line_data.get("uom", "KG"),
            unit_price=line_data.get("unit_price", 0),
            required_by=data.delivery_date
        )
        po_line_dict = po_line.model_dump()
        po_line_dict["item_name"] = item_name
        po_line_dict["job_numbers"] = line_data.get("job_numbers", [])
        await db.purchase_order_lines.insert_one(po_line_dict)
        
        # Clear the material shortage for this item
        await db.material_shortages.update_many(
            {"item_id": line_data.get("item_id"), "status": "PENDING"},
            {"$set": {"status": "PO_CREATED", "po_id": po.id, "po_number": po_number}}
        )
    
    # Create notification for Finance
    await create_notification(
        event_type="PO_PENDING_APPROVAL",
        title=f"PO Pending Approval: {po_number}",
        message=f"New PO from {data.supplier_name} for {data.currency} {data.total_amount:.2f} requires finance approval",
        link="/finance-approval",
        ref_type="PO",
        ref_id=po.id,
        target_roles=["admin", "finance"],
        notification_type="warning"
    )
    
    return {
        "success": True,
        "message": f"PO {po_number} created and sent to Finance Approval",
        "po_id": po.id,
        "po_number": po_number
    }


# ==================== PHASE 6: FINANCE APPROVAL ====================

@api_router.put("/purchase-orders/{po_id}/finance-approve")
async def finance_approve_po(po_id: str, current_user: dict = Depends(get_current_user)):
    """Finance approves a PO (Phase 6)"""
    if current_user["role"] not in ["admin", "finance"]:
        raise HTTPException(status_code=403, detail="Only admin/finance can approve POs")
    
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    
    if po.get("status") != "DRAFT":
        raise HTTPException(status_code=400, detail="Only DRAFT POs can be approved")
    
    await db.purchase_orders.update_one(
        {"id": po_id},
        {"$set": {
            "status": "APPROVED",
            "approved_by": current_user["id"],
            "approved_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"success": True, "message": "PO approved by finance"}

@api_router.put("/purchase-orders/{po_id}/finance-reject")
async def finance_reject_po(po_id: str, reason: str = "", current_user: dict = Depends(get_current_user)):
    """Finance rejects a PO"""
    if current_user["role"] not in ["admin", "finance"]:
        raise HTTPException(status_code=403, detail="Only admin/finance can reject POs")
    
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    
    await db.purchase_orders.update_one(
        {"id": po_id},
        {"$set": {
            "status": "REJECTED",
            "rejected_by": current_user["id"],
            "rejected_at": datetime.now(timezone.utc).isoformat(),
            "rejection_reason": reason
        }}
    )
    
    return {"success": True, "message": "PO rejected by finance"}

@api_router.put("/purchase-orders/{po_id}/send")
async def send_po_to_supplier(po_id: str, current_user: dict = Depends(get_current_user)):
    """Send approved PO to supplier via email queue"""
    if current_user["role"] not in ["admin", "procurement", "finance"]:
        raise HTTPException(status_code=403, detail="Only admin/procurement/finance can send POs")
    
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    
    if po.get("status") != "APPROVED":
        raise HTTPException(status_code=400, detail="Only APPROVED POs can be sent")
    
    supplier = await db.suppliers.find_one({"id": po.get("supplier_id")}, {"_id": 0})
    
    # Get PO lines
    lines = await db.purchase_order_lines.find({"po_id": po_id}, {"_id": 0}).to_list(1000)
    items_list = ""
    for line in lines:
        item = await db.inventory_items.find_one({"id": line.get("item_id")}, {"_id": 0})
        items_list += f"<tr><td>{item.get('name') if item else 'Unknown'}</td><td>{line.get('qty')} {line.get('uom')}</td><td>{line.get('unit_price')}</td><td>{line.get('qty', 0) * line.get('unit_price', 0):.2f}</td></tr>"
    
    # Queue email
    if supplier and supplier.get("email"):
        email_body = f"""
        <h2>Purchase Order: {po.get('po_number')}</h2>
        <p>Dear {supplier.get('name')},</p>
        <p>Please find below our Purchase Order:</p>
        <table border="1" cellpadding="5">
            <tr><th>Item</th><th>Qty</th><th>Unit Price</th><th>Total</th></tr>
            {items_list}
        </table>
        <p><strong>Total: {po.get('currency', 'USD')} {po.get('total_amount', 0):.2f}</strong></p>
        <p>Please confirm receipt and expected delivery date.</p>
        <p>Thank you.</p>
        """
        email_item = EmailQueueItem(
            to_email=supplier.get("email"),
            subject=f"Purchase Order {po.get('po_number')}",
            body_html=email_body,
            ref_type="PO",
            ref_id=po_id
        )
        await db.email_outbox.insert_one(email_item.model_dump())
    
    await db.purchase_orders.update_one(
        {"id": po_id},
        {"$set": {
            "status": "SENT",
            "sent_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {
        "success": True,
        "message": f"PO {po.get('po_number')} sent to supplier",
        "email_queued": bool(supplier and supplier.get("email"))
    }

# ==================== PHASE 8: INCOTERM-BASED LOGISTICS ROUTING ====================

INCOTERM_ROUTING = {
    # LOCAL incoterms
    "EXW": {"type": "LOCAL", "route": "TRANSPORTATION_INWARD", "description": "Ex Works - buyer arranges transport"},
    "DDP": {"type": "LOCAL", "route": "SECURITY_QC_INWARD", "description": "Delivered Duty Paid - seller delivers to buyer"},
    "DAP": {"type": "LOCAL", "route": "TRANSPORTATION_INWARD", "description": "Delivered at Place"},
    # IMPORT incoterms
    "FOB": {"type": "IMPORT", "route": "SHIPPING_BOOKING", "description": "Free On Board - import via sea"},
    "CFR": {"type": "IMPORT", "route": "IMPORT_INWARD", "description": "Cost and Freight - import with freight"},
    "CIF": {"type": "IMPORT", "route": "IMPORT_INWARD", "description": "Cost Insurance Freight - full import"},
    "FCA": {"type": "IMPORT", "route": "SHIPPING_BOOKING", "description": "Free Carrier - import via air/land"},
}

@api_router.get("/logistics/routing-options")
async def get_routing_options(current_user: dict = Depends(get_current_user)):
    """Get available incoterm routing options"""
    return {
        "incoterms": INCOTERM_ROUTING,
        "local_terms": ["EXW", "DDP", "DAP"],
        "import_terms": ["FOB", "CFR", "CIF", "FCA"]
    }

@api_router.post("/logistics/route-po/{po_id}")
async def route_po_logistics(po_id: str, incoterm: str, current_user: dict = Depends(get_current_user)):
    """Route PO to appropriate logistics flow based on incoterm (Phase 8)"""
    if current_user["role"] not in ["admin", "procurement", "finance"]:
        raise HTTPException(status_code=403, detail="Only admin/procurement/finance can route POs")
    
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    
    if incoterm not in INCOTERM_ROUTING:
        raise HTTPException(status_code=400, detail=f"Invalid incoterm: {incoterm}")
    
    routing = INCOTERM_ROUTING[incoterm]
    
    # Create logistics routing record
    routing_record = {
        "id": str(uuid.uuid4()),
        "po_id": po_id,
        "po_number": po.get("po_number"),
        "incoterm": incoterm,
        "routing_type": routing["type"],
        "route": routing["route"],
        "status": "PENDING",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await db.logistics_routing.insert_one(routing_record)
    
    # Update PO with incoterm
    await db.purchase_orders.update_one(
        {"id": po_id},
        {"$set": {
            "incoterm": incoterm,
            "logistics_routing_id": routing_record["id"]
        }}
    )
    
    # For IMPORT types, create import checklist
    if routing["type"] == "IMPORT":
        import_checklist = {
            "id": str(uuid.uuid4()),
            "po_id": po_id,
            "routing_id": routing_record["id"],
            "status": "PRE_IMPORT",
            "pre_import_docs": [],
            "post_import_docs": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.import_checklists.insert_one(import_checklist)
        routing_record["import_checklist_id"] = import_checklist["id"]
    
    return {
        "success": True,
        "routing": routing_record,
        "message": f"PO routed via {routing['route']} ({routing['description']})"
    }

@api_router.get("/logistics/routing")
async def get_logistics_routing(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get all logistics routing records"""
    query = {}
    if status:
        query["status"] = status
    
    routings = await db.logistics_routing.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return routings

# ==================== PHASE 9: PAYABLES & RECEIVABLES (MVP) ====================

# Payables Model
class PayableBillCreate(BaseModel):
    ref_type: str  # PO, TRANSPORT, SHIPPING
    ref_id: str
    supplier_id: str
    amount: float
    currency: str = "USD"
    due_date: Optional[str] = None
    notes: Optional[str] = None

class PayableBill(PayableBillCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bill_number: str = ""
    status: str = "PENDING"  # PENDING, APPROVED, PAID, CANCELLED
    grn_id: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    paid_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Receivables Model
class ReceivableInvoiceCreate(BaseModel):
    invoice_type: str  # LOCAL, EXPORT
    customer_id: str
    sales_order_id: Optional[str] = None
    job_order_id: Optional[str] = None
    amount: float
    currency: str = "USD"
    due_date: Optional[str] = None
    notes: Optional[str] = None

class ReceivableInvoice(ReceivableInvoiceCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    invoice_number: str = ""
    status: str = "PENDING"  # PENDING, SENT, PARTIAL, PAID, OVERDUE
    amount_paid: float = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Payables Endpoints
@api_router.post("/payables/bills")
async def create_payable_bill(data: PayableBillCreate, current_user: dict = Depends(get_current_user)):
    """Create a payable bill"""
    if current_user["role"] not in ["admin", "finance"]:
        raise HTTPException(status_code=403, detail="Only admin/finance can create bills")
    
    bill_number = await generate_sequence("BILL", "payable_bills")
    bill = PayableBill(**data.model_dump(), bill_number=bill_number)
    await db.payable_bills.insert_one(bill.model_dump())
    
    return bill.model_dump()

@api_router.get("/payables/bills")
async def get_payable_bills(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get all payable bills with aging"""
    query = {}
    if status:
        query["status"] = status
    
    bills = await db.payable_bills.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    # Calculate aging buckets
    today = datetime.now(timezone.utc)
    aging = {"current": 0, "30_days": 0, "60_days": 0, "90_plus": 0}
    
    for bill in bills:
        if bill.get("status") in ["PENDING", "APPROVED"]:
            due_date = datetime.fromisoformat(bill.get("due_date", bill["created_at"]).replace("Z", "+00:00"))
            days_overdue = (today - due_date).days
            
            if days_overdue <= 0:
                aging["current"] += bill.get("amount", 0)
            elif days_overdue <= 30:
                aging["30_days"] += bill.get("amount", 0)
            elif days_overdue <= 60:
                aging["60_days"] += bill.get("amount", 0)
            else:
                aging["90_plus"] += bill.get("amount", 0)
    
    return {
        "bills": bills,
        "aging": aging,
        "total_outstanding": sum(aging.values())
    }

@api_router.put("/payables/bills/{bill_id}/approve")
async def approve_payable_bill(bill_id: str, current_user: dict = Depends(get_current_user)):
    """Approve a payable bill for payment"""
    if current_user["role"] not in ["admin", "finance"]:
        raise HTTPException(status_code=403, detail="Only admin/finance can approve bills")
    
    await db.payable_bills.update_one(
        {"id": bill_id},
        {"$set": {
            "status": "APPROVED",
            "approved_by": current_user["id"],
            "approved_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    return {"success": True, "message": "Bill approved for payment"}

@api_router.put("/payables/bills/{bill_id}/pay")
async def pay_payable_bill(bill_id: str, current_user: dict = Depends(get_current_user)):
    """Mark a payable bill as paid"""
    if current_user["role"] not in ["admin", "finance"]:
        raise HTTPException(status_code=403, detail="Only admin/finance can mark bills as paid")
    
    await db.payable_bills.update_one(
        {"id": bill_id},
        {"$set": {
            "status": "PAID",
            "paid_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    return {"success": True, "message": "Bill marked as paid"}

# Receivables Endpoints
@api_router.post("/receivables/invoices")
async def create_receivable_invoice(data: ReceivableInvoiceCreate, current_user: dict = Depends(get_current_user)):
    """Create a receivable invoice"""
    if current_user["role"] not in ["admin", "finance", "sales"]:
        raise HTTPException(status_code=403, detail="Only admin/finance/sales can create invoices")
    
    prefix = "INV-L" if data.invoice_type == "LOCAL" else "INV-E"
    invoice_number = await generate_sequence(prefix, "receivable_invoices")
    
    invoice = ReceivableInvoice(**data.model_dump(), invoice_number=invoice_number)
    await db.receivable_invoices.insert_one(invoice.model_dump())
    
    return invoice.model_dump()

@api_router.get("/receivables/invoices")
async def get_receivable_invoices(status: Optional[str] = None, invoice_type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get all receivable invoices with aging"""
    query = {}
    if status:
        query["status"] = status
    if invoice_type:
        query["invoice_type"] = invoice_type
    
    invoices = await db.receivable_invoices.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    # Calculate aging buckets
    today = datetime.now(timezone.utc)
    aging = {"current": 0, "30_days": 0, "60_days": 0, "90_plus": 0}
    
    for inv in invoices:
        if inv.get("status") in ["PENDING", "SENT", "PARTIAL"]:
            outstanding = inv.get("amount", 0) - inv.get("amount_paid", 0)
            due_date = datetime.fromisoformat(inv.get("due_date", inv["created_at"]).replace("Z", "+00:00"))
            days_overdue = (today - due_date).days
            
            if days_overdue <= 0:
                aging["current"] += outstanding
            elif days_overdue <= 30:
                aging["30_days"] += outstanding
            elif days_overdue <= 60:
                aging["60_days"] += outstanding
            else:
                aging["90_plus"] += outstanding
    
    return {
        "invoices": invoices,
        "aging": aging,
        "total_outstanding": sum(aging.values())
    }

@api_router.put("/receivables/invoices/{invoice_id}/record-payment")
async def record_payment(invoice_id: str, amount: float, current_user: dict = Depends(get_current_user)):
    """Record a payment against an invoice"""
    if current_user["role"] not in ["admin", "finance"]:
        raise HTTPException(status_code=403, detail="Only admin/finance can record payments")
    
    invoice = await db.receivable_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    new_paid = invoice.get("amount_paid", 0) + amount
    new_status = "PAID" if new_paid >= invoice.get("amount", 0) else "PARTIAL"
    
    await db.receivable_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "amount_paid": new_paid,
            "status": new_status
        }}
    )
    
    # Record the payment
    payment_record = {
        "id": str(uuid.uuid4()),
        "invoice_id": invoice_id,
        "amount": amount,
        "recorded_by": current_user["id"],
        "recorded_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payments_received.insert_one(payment_record)
    
    return {"success": True, "message": f"Payment of {amount} recorded", "new_status": new_status}

# ==================== SECURITY & QC (MVP) ====================

@api_router.post("/security/inward-checklist")
async def create_inward_checklist(
    grn_id: str,
    vehicle_number: str,
    driver_name: str,
    weight_in: float,
    notes: str = "",
    current_user: dict = Depends(get_current_user)
):
    """Create security inward checklist"""
    if current_user["role"] not in ["admin", "security"]:
        raise HTTPException(status_code=403, detail="Only admin/security can create inward checklist")
    
    checklist = {
        "id": str(uuid.uuid4()),
        "grn_id": grn_id,
        "type": "INWARD",
        "vehicle_number": vehicle_number,
        "driver_name": driver_name,
        "weight_in": weight_in,
        "weight_out": None,
        "status": "IN_PROGRESS",
        "notes": notes,
        "created_by": current_user["id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.security_checklists.insert_one(checklist)
    return checklist

@api_router.put("/security/checklist/{checklist_id}/complete")
async def complete_security_checklist(
    checklist_id: str,
    weight_out: float,
    current_user: dict = Depends(get_current_user)
):
    """Complete security checklist with weight out"""
    if current_user["role"] not in ["admin", "security"]:
        raise HTTPException(status_code=403, detail="Only admin/security can complete checklist")
    
    await db.security_checklists.update_one(
        {"id": checklist_id},
        {"$set": {
            "weight_out": weight_out,
            "status": "COMPLETED",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    return {"success": True, "message": "Security checklist completed"}

@api_router.get("/security/checklists")
async def get_security_checklists(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get all security checklists"""
    query = {}
    if status:
        query["status"] = status
    
    checklists = await db.security_checklists.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return checklists

# QC Endpoints
@api_router.post("/qc/inspection")
async def create_qc_inspection(
    ref_type: str,  # GRN, JOB_ORDER, BLEND
    ref_id: str,
    batch_number: str,
    current_user: dict = Depends(get_current_user)
):
    """Create QC inspection record"""
    if current_user["role"] not in ["admin", "qc"]:
        raise HTTPException(status_code=403, detail="Only admin/qc can create inspections")
    
    inspection = {
        "id": str(uuid.uuid4()),
        "ref_type": ref_type,
        "ref_id": ref_id,
        "batch_number": batch_number,
        "status": "PENDING",  # PENDING, PASS, FAIL, HOLD
        "results": [],
        "created_by": current_user["id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.qc_inspections.insert_one(inspection)
    return inspection

@api_router.put("/qc/inspection/{inspection_id}/result")
async def update_qc_result(
    inspection_id: str,
    status: str,  # PASS, FAIL, HOLD
    notes: str = "",
    current_user: dict = Depends(get_current_user)
):
    """Update QC inspection result"""
    if current_user["role"] not in ["admin", "qc"]:
        raise HTTPException(status_code=403, detail="Only admin/qc can update inspections")
    
    if status not in ["PASS", "FAIL", "HOLD"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    await db.qc_inspections.update_one(
        {"id": inspection_id},
        {"$set": {
            "status": status,
            "result_notes": notes,
            "inspected_by": current_user["id"],
            "inspected_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    return {"success": True, "message": f"QC inspection marked as {status}"}

@api_router.get("/qc/inspections")
async def get_qc_inspections(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get all QC inspections"""
    query = {}
    if status:
        query["status"] = status
    
    inspections = await db.qc_inspections.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return inspections


# ==================== PHASE 1: TRANSPORT WINDOW (4 Tables) ====================

class TransportInward(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transport_number: str = ""
    po_id: str
    po_number: str
    supplier_name: str
    incoterm: str
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_contact: Optional[str] = None
    eta: Optional[str] = None
    actual_arrival: Optional[str] = None
    status: str = "PENDING"  # PENDING, SCHEDULED, IN_TRANSIT, ARRIVED, COMPLETED
    source: str = "EXW"  # EXW (direct) or IMPORT (post-import)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TransportOutward(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transport_number: str = ""
    do_id: Optional[str] = None
    do_number: Optional[str] = None
    job_order_id: Optional[str] = None
    job_number: Optional[str] = None
    customer_name: str
    transport_type: str = "LOCAL"  # LOCAL, CONTAINER
    vehicle_number: Optional[str] = None
    container_number: Optional[str] = None
    destination: Optional[str] = None
    dispatch_date: Optional[str] = None
    delivery_date: Optional[str] = None
    status: str = "PENDING"  # PENDING, LOADING, DISPATCHED, DELIVERED
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@api_router.get("/transport/inward")
async def get_transport_inward(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get inward transport records"""
    query = {}
    if status:
        query["status"] = status
    records = await db.transport_inward.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return records


@api_router.post("/transport/inward")
async def create_transport_inward(data: dict, current_user: dict = Depends(get_current_user)):
    """Create inward transport record"""
    transport_number = await generate_sequence("TIN", "transport_inward")
    record = TransportInward(
        transport_number=transport_number,
        **data
    )
    await db.transport_inward.insert_one(record.model_dump())
    return record


@api_router.put("/transport/inward/{transport_id}/status")
async def update_transport_inward_status(transport_id: str, status: str, current_user: dict = Depends(get_current_user)):
    """Update inward transport status"""
    update_data = {"status": status}
    if status == "ARRIVED":
        update_data["actual_arrival"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.transport_inward.update_one(
        {"id": transport_id},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Transport record not found")
    
    # If arrived, route to Security & QC
    if status == "ARRIVED":
        transport = await db.transport_inward.find_one({"id": transport_id}, {"_id": 0})
        if transport:
            await create_notification(
                event_type="TRANSPORT_ARRIVED",
                title="Inward Transport Arrived",
                message=f"Transport {transport.get('transport_number')} has arrived at facility",
                link="/security",
                target_roles=["admin", "security", "qc"],
                notification_type="info"
            )
    
    return {"success": True, "message": f"Transport status updated to {status}"}


@api_router.get("/transport/outward")
async def get_transport_outward(
    status: Optional[str] = None, 
    transport_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get outward transport records"""
    query = {}
    if status:
        query["status"] = status
    if transport_type:
        query["transport_type"] = transport_type
    records = await db.transport_outward.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return records


@api_router.post("/transport/outward")
async def create_transport_outward(data: dict, current_user: dict = Depends(get_current_user)):
    """Create outward transport record"""
    transport_number = await generate_sequence("TOUT", "transport_outward")
    record = TransportOutward(
        transport_number=transport_number,
        **data
    )
    await db.transport_outward.insert_one(record.model_dump())
    return record


@api_router.put("/transport/outward/{transport_id}/status")
async def update_transport_outward_status(transport_id: str, status: str, current_user: dict = Depends(get_current_user)):
    """Update outward transport status"""
    update_data = {"status": status}
    if status == "DISPATCHED":
        update_data["dispatch_date"] = datetime.now(timezone.utc).isoformat()
    elif status == "DELIVERED":
        update_data["delivery_date"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.transport_outward.update_one(
        {"id": transport_id},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Transport record not found")
    
    return {"success": True, "message": f"Transport status updated to {status}"}


# ==================== PHASE 1: IMPORT WINDOW ====================

class ImportRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    import_number: str = ""
    po_id: str
    po_number: str
    supplier_name: str
    incoterm: str
    country_of_origin: str = ""
    destination_port: str = ""
    eta: Optional[str] = None
    actual_arrival: Optional[str] = None
    status: str = "PENDING_DOCS"  # PENDING_DOCS, IN_TRANSIT, AT_PORT, CLEARED, COMPLETED
    document_checklist: List[Dict] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def get_default_import_checklist():
    return [
        {"type": "COMMERCIAL_INVOICE", "name": "Commercial Invoice", "required": True, "received": False},
        {"type": "PACKING_LIST", "name": "Packing List", "required": True, "received": False},
        {"type": "BILL_OF_LADING", "name": "Bill of Lading (B/L)", "required": True, "received": False},
        {"type": "CERTIFICATE_OF_ORIGIN", "name": "Certificate of Origin (COO)", "required": True, "received": False},
        {"type": "CERTIFICATE_OF_ANALYSIS", "name": "Certificate of Analysis (COA)", "required": True, "received": False},
        {"type": "INSURANCE_CERT", "name": "Insurance Certificate", "required": False, "received": False},
        {"type": "PHYTO_CERT", "name": "Phytosanitary Certificate", "required": False, "received": False},
        {"type": "MSDS", "name": "Material Safety Data Sheet", "required": False, "received": False},
    ]


@api_router.get("/imports")
async def get_imports(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get import records"""
    query = {}
    if status:
        query["status"] = status
    records = await db.imports.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return records


@api_router.post("/imports")
async def create_import(data: dict, current_user: dict = Depends(get_current_user)):
    """Create import record from PO"""
    import_number = await generate_sequence("IMP", "imports")
    record = ImportRecord(
        import_number=import_number,
        document_checklist=get_default_import_checklist(),
        **data
    )
    await db.imports.insert_one(record.model_dump())
    return record


@api_router.put("/imports/{import_id}/checklist")
async def update_import_checklist(import_id: str, checklist: List[Dict], current_user: dict = Depends(get_current_user)):
    """Update import document checklist"""
    result = await db.imports.update_one(
        {"id": import_id},
        {"$set": {"document_checklist": checklist}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Import record not found")
    return {"success": True, "message": "Checklist updated"}


@api_router.put("/imports/{import_id}/status")
async def update_import_status(import_id: str, status: str, current_user: dict = Depends(get_current_user)):
    """Update import status"""
    update_data = {"status": status}
    if status == "AT_PORT":
        update_data["actual_arrival"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.imports.update_one(
        {"id": import_id},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Import record not found")
    
    # If completed, create inward transport
    if status == "COMPLETED":
        import_record = await db.imports.find_one({"id": import_id}, {"_id": 0})
        if import_record:
            # Auto-create transport inward record
            transport_number = await generate_sequence("TIN", "transport_inward")
            transport = TransportInward(
                transport_number=transport_number,
                po_id=import_record.get("po_id"),
                po_number=import_record.get("po_number"),
                supplier_name=import_record.get("supplier_name"),
                incoterm=import_record.get("incoterm"),
                source="IMPORT"
            )
            await db.transport_inward.insert_one(transport.model_dump())
            
            await create_notification(
                event_type="IMPORT_COMPLETED",
                title="Import Customs Cleared",
                message=f"Import {import_record.get('import_number')} cleared - Transport scheduled",
                link="/transport-window",
                target_roles=["admin", "transport"],
                notification_type="success"
            )
    
    return {"success": True, "message": f"Import status updated to {status}"}


# ==================== PHASE 1: UNIFIED PRODUCTION SCHEDULE ====================

@api_router.get("/production/unified-schedule")
async def get_unified_production_schedule(
    start_date: Optional[str] = None,
    days: int = 14,
    current_user: dict = Depends(get_current_user)
):
    """
    Get unified production schedule with 600 drums/day constraint.
    Combines drum schedule and production schedule into one view.
    """
    if not start_date:
        start_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    DRUMS_PER_DAY = 600
    
    # Get all pending/approved job orders
    job_orders = await db.job_orders.find(
        {"status": {"$in": ["pending", "approved", "in_production"]}},
        {"_id": 0}
    ).sort("delivery_date", 1).to_list(1000)
    
    # Build schedule day by day
    schedule = []
    current_date = datetime.strptime(start_date, "%Y-%m-%d")
    remaining_jobs = list(job_orders)
    
    for day_offset in range(days):
        day_date = current_date + timedelta(days=day_offset)
        day_str = day_date.strftime("%Y-%m-%d")
        
        day_schedule = {
            "date": day_str,
            "day_name": day_date.strftime("%A"),
            "drums_capacity": DRUMS_PER_DAY,
            "drums_scheduled": 0,
            "drums_remaining": DRUMS_PER_DAY,
            "jobs": [],
            "is_full": False,
            "utilization": 0
        }
        
        # Allocate jobs to this day
        jobs_to_remove = []
        for job in remaining_jobs:
            job_drums = job.get("quantity", 0)
            
            # Check if job fits in day's capacity
            if day_schedule["drums_remaining"] >= job_drums:
                # Check material availability
                material_status = await check_job_material_availability(job)
                
                day_schedule["jobs"].append({
                    "job_number": job.get("job_number"),
                    "job_id": job.get("id"),
                    "product_name": job.get("product_name"),
                    "product_sku": job.get("product_sku"),
                    "quantity": job_drums,
                    "packaging": job.get("packaging", "200L Drum"),
                    "delivery_date": job.get("delivery_date"),
                    "priority": job.get("priority", "normal"),
                    "material_ready": material_status["ready"],
                    "shortage_items": material_status.get("shortage_count", 0),
                    "status": job.get("status")
                })
                
                day_schedule["drums_scheduled"] += job_drums
                day_schedule["drums_remaining"] -= job_drums
                jobs_to_remove.append(job)
            elif day_schedule["drums_remaining"] > 0:
                # Partial allocation - split job across days
                partial_drums = day_schedule["drums_remaining"]
                material_status = await check_job_material_availability(job)
                
                day_schedule["jobs"].append({
                    "job_number": job.get("job_number"),
                    "job_id": job.get("id"),
                    "product_name": job.get("product_name"),
                    "product_sku": job.get("product_sku"),
                    "quantity": partial_drums,
                    "packaging": job.get("packaging", "200L Drum"),
                    "delivery_date": job.get("delivery_date"),
                    "priority": job.get("priority", "normal"),
                    "material_ready": material_status["ready"],
                    "shortage_items": material_status.get("shortage_count", 0),
                    "status": job.get("status"),
                    "is_partial": True,
                    "total_quantity": job_drums
                })
                
                day_schedule["drums_scheduled"] += partial_drums
                day_schedule["drums_remaining"] = 0
                
                # Update remaining quantity in job
                job["quantity"] = job_drums - partial_drums
                break
        
        # Remove fully allocated jobs
        for job in jobs_to_remove:
            remaining_jobs.remove(job)
        
        day_schedule["is_full"] = day_schedule["drums_remaining"] == 0
        day_schedule["utilization"] = round((day_schedule["drums_scheduled"] / DRUMS_PER_DAY) * 100, 1)
        schedule.append(day_schedule)
    
    # Summary stats
    total_drums = sum(d["drums_scheduled"] for d in schedule)
    jobs_scheduled = sum(len(d["jobs"]) for d in schedule)
    unscheduled_jobs = len(remaining_jobs)
    
    return {
        "schedule": schedule,
        "summary": {
            "total_drums_scheduled": total_drums,
            "jobs_scheduled": jobs_scheduled,
            "unscheduled_jobs": unscheduled_jobs,
            "days_with_capacity": len([d for d in schedule if not d["is_full"]]),
            "average_utilization": round(sum(d["utilization"] for d in schedule) / len(schedule), 1) if schedule else 0
        },
        "constraints": {
            "drums_per_day": DRUMS_PER_DAY
        }
    }


async def check_job_material_availability(job: dict) -> dict:
    """Check if all materials are available for a job"""
    product_id = job.get("product_id")
    quantity = job.get("quantity", 0)
    
    shortage_count = 0
    
    # Get active product BOM
    product_bom = await db.product_boms.find_one({
        "product_id": product_id,
        "is_active": True
    }, {"_id": 0})
    
    if product_bom:
        bom_items = await db.product_bom_items.find({
            "bom_id": product_bom["id"]
        }, {"_id": 0}).to_list(100)
        
        for bom_item in bom_items:
            material_id = bom_item.get("material_item_id")
            qty_per_kg = bom_item.get("qty_kg_per_kg_finished", 0)
            
            # Assume 200kg per drum
            finished_kg = quantity * 200
            required_qty = finished_kg * qty_per_kg
            
            balance = await db.inventory_balances.find_one({"item_id": material_id}, {"_id": 0})
            available = (balance.get("on_hand", 0) - balance.get("reserved", 0)) if balance else 0
            
            if available < required_qty:
                shortage_count += 1
    
    return {
        "ready": shortage_count == 0,
        "shortage_count": shortage_count
    }


# ==================== INCOTERM ROUTING ON PO APPROVAL ====================

@api_router.put("/purchase-orders/{po_id}/route-by-incoterm")
async def route_po_by_incoterm(po_id: str, current_user: dict = Depends(get_current_user)):
    """
    Route PO to appropriate window based on incoterm:
    - EXW → Transportation Window (Inward)
    - DDP → Security & QC Module
    - FOB → Shipping Module  
    - CFR → Import Window
    """
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    incoterm = po.get("incoterm", "EXW").upper()
    route_result = {"po_id": po_id, "incoterm": incoterm, "routed_to": None}
    
    if incoterm == "EXW":
        # Route to Transportation Window (Inward)
        transport_number = await generate_sequence("TIN", "transport_inward")
        transport = TransportInward(
            transport_number=transport_number,
            po_id=po_id,
            po_number=po.get("po_number"),
            supplier_name=po.get("supplier_name"),
            incoterm=incoterm,
            source="EXW"
        )
        await db.transport_inward.insert_one(transport.model_dump())
        route_result["routed_to"] = "TRANSPORTATION_INWARD"
        route_result["transport_number"] = transport_number
        
    elif incoterm == "DDP":
        # Route to Security & QC
        checklist_number = await generate_sequence("SEC", "security_checklists")
        checklist = {
            "id": str(uuid.uuid4()),
            "checklist_number": checklist_number,
            "ref_type": "PO",
            "ref_id": po_id,
            "ref_number": po.get("po_number"),
            "supplier_name": po.get("supplier_name"),
            "checklist_type": "INWARD",
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.security_checklists.insert_one(checklist)
        route_result["routed_to"] = "SECURITY_QC"
        route_result["checklist_number"] = checklist_number
        
    elif incoterm == "FOB":
        # Route to Shipping Module
        shipping_number = await generate_sequence("SHIP", "shipping_bookings")
        shipping = {
            "id": str(uuid.uuid4()),
            "booking_number": shipping_number,
            "ref_type": "PO_IMPORT",
            "ref_id": po_id,
            "po_number": po.get("po_number"),
            "supplier_name": po.get("supplier_name"),
            "incoterm": incoterm,
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.shipping_bookings.insert_one(shipping)
        route_result["routed_to"] = "SHIPPING"
        route_result["booking_number"] = shipping_number
        
    elif incoterm in ["CFR", "CIF", "CIP"]:
        # Route to Import Window
        import_number = await generate_sequence("IMP", "imports")
        import_record = ImportRecord(
            import_number=import_number,
            po_id=po_id,
            po_number=po.get("po_number"),
            supplier_name=po.get("supplier_name"),
            incoterm=incoterm,
            document_checklist=get_default_import_checklist()
        )
        await db.imports.insert_one(import_record.model_dump())
        route_result["routed_to"] = "IMPORT"
        route_result["import_number"] = import_number
    
    else:
        # Default to EXW behavior
        transport_number = await generate_sequence("TIN", "transport_inward")
        transport = TransportInward(
            transport_number=transport_number,
            po_id=po_id,
            po_number=po.get("po_number"),
            supplier_name=po.get("supplier_name"),
            incoterm=incoterm,
            source="OTHER"
        )
        await db.transport_inward.insert_one(transport.model_dump())
        route_result["routed_to"] = "TRANSPORTATION_INWARD"
        route_result["transport_number"] = transport_number
    
    # Update PO with routing info
    await db.purchase_orders.update_one(
        {"id": po_id},
        {"$set": {
            "routed_to": route_result["routed_to"],
            "routed_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return route_result


# ==================== MATERIAL SHORTAGE ENDPOINTS ====================

@api_router.get("/material-shortages")
async def get_material_shortages(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get material shortages for RFQ creation"""
    query = {}
    if status:
        query["status"] = status
    shortages = await db.material_shortages.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return shortages


@api_router.put("/material-shortages/{shortage_id}/link-rfq")
async def link_shortage_to_rfq(shortage_id: str, rfq_id: str, current_user: dict = Depends(get_current_user)):
    """Link a material shortage to an RFQ"""
    result = await db.material_shortages.update_one(
        {"id": shortage_id},
        {"$set": {"rfq_id": rfq_id, "status": "IN_RFQ"}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Shortage not found")
    return {"success": True, "message": "Shortage linked to RFQ"}


# ==================== PHASE 2: QC & SECURITY MODULE ====================

# Security Checklist Models
class SecurityChecklistCreate(BaseModel):
    ref_type: str  # INWARD, OUTWARD
    ref_id: str  # transport_inward_id or job_order_id
    ref_number: str
    checklist_type: str  # INWARD or OUTWARD
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_license: Optional[str] = None
    seal_number: Optional[str] = None
    gross_weight: Optional[float] = None
    tare_weight: Optional[float] = None
    net_weight: Optional[float] = None
    notes: Optional[str] = None

class SecurityChecklistUpdate(BaseModel):
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_license: Optional[str] = None
    seal_number: Optional[str] = None
    gross_weight: Optional[float] = None
    tare_weight: Optional[float] = None
    net_weight: Optional[float] = None
    container_number: Optional[str] = None
    checklist_items: Optional[Dict[str, bool]] = None
    notes: Optional[str] = None
    status: Optional[str] = None

# QC Inspection Models
class QCInspectionCreate(BaseModel):
    ref_type: str  # INWARD, OUTWARD
    ref_id: str
    ref_number: str
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    batch_number: Optional[str] = None

class QCInspectionUpdate(BaseModel):
    batch_number: Optional[str] = None
    test_results: Optional[Dict[str, Any]] = None
    specifications: Optional[Dict[str, Any]] = None
    passed: Optional[bool] = None
    coa_generated: Optional[bool] = None
    coa_number: Optional[str] = None
    inspector_notes: Optional[str] = None
    status: Optional[str] = None

# ==================== SECURITY ENDPOINTS ====================

@api_router.get("/security/dashboard")
async def get_security_dashboard(current_user: dict = Depends(get_current_user)):
    """Get security dashboard with 3 windows: Inward, Outward, and RFQ status"""
    
    # Inward transport pending security check
    inward_pending = await db.transport_inward.find(
        {"status": {"$in": ["PENDING", "IN_TRANSIT", "ARRIVED"]}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Outward dispatch pending security check
    outward_pending = await db.transport_outward.find(
        {"status": {"$in": ["PENDING", "LOADING"]}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Security checklists
    checklists = await db.security_checklists.find(
        {"status": {"$in": ["PENDING", "IN_PROGRESS"]}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return {
        "inward_pending": inward_pending,
        "outward_pending": outward_pending,
        "checklists": checklists,
        "stats": {
            "inward_count": len(inward_pending),
            "outward_count": len(outward_pending),
            "pending_checklists": len(checklists)
        }
    }

@api_router.get("/security/inward")
async def get_security_inward(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get inward transports for security check"""
    query = {}
    if status:
        query["status"] = status
    
    inward = await db.transport_inward.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    # Enrich with security checklist status
    for transport in inward:
        checklist = await db.security_checklists.find_one({
            "ref_type": "INWARD",
            "ref_id": transport["id"]
        }, {"_id": 0})
        transport["security_checklist"] = checklist
    
    return inward

@api_router.get("/security/outward")
async def get_security_outward(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get outward transports for security check"""
    query = {}
    if status:
        query["status"] = status
    
    outward = await db.transport_outward.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    # Enrich with security checklist status
    for transport in outward:
        checklist = await db.security_checklists.find_one({
            "ref_type": "OUTWARD",
            "ref_id": transport["id"]
        }, {"_id": 0})
        transport["security_checklist"] = checklist
    
    return outward

@api_router.post("/security/checklists")
async def create_security_checklist(data: SecurityChecklistCreate, current_user: dict = Depends(get_current_user)):
    """Create a security checklist for inward or outward transport"""
    if current_user["role"] not in ["admin", "security"]:
        raise HTTPException(status_code=403, detail="Only security can create checklists")
    
    checklist_number = await generate_sequence("SEC", "security_checklists")
    
    checklist = {
        "id": str(uuid.uuid4()),
        "checklist_number": checklist_number,
        **data.model_dump(),
        "checklist_items": {
            "vehicle_inspected": False,
            "driver_verified": False,
            "seal_checked": False,
            "documents_verified": False,
            "weight_recorded": False
        },
        "status": "IN_PROGRESS",
        "created_by": current_user["id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.security_checklists.insert_one(checklist)
    return checklist

@api_router.put("/security/checklists/{checklist_id}")
async def update_security_checklist(checklist_id: str, data: SecurityChecklistUpdate, current_user: dict = Depends(get_current_user)):
    """Update security checklist with weighment and details"""
    if current_user["role"] not in ["admin", "security"]:
        raise HTTPException(status_code=403, detail="Only security can update checklists")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    
    # Calculate net weight if gross and tare provided
    if data.gross_weight and data.tare_weight:
        update_data["net_weight"] = data.gross_weight - data.tare_weight
    
    result = await db.security_checklists.update_one(
        {"id": checklist_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Checklist not found")
    
    return await db.security_checklists.find_one({"id": checklist_id}, {"_id": 0})

@api_router.put("/security/checklists/{checklist_id}/complete")
async def complete_security_checklist(checklist_id: str, current_user: dict = Depends(get_current_user)):
    """
    Complete security checklist and route to QC.
    For INWARD: Creates QC inspection and routes to GRN after QC pass.
    For OUTWARD: Creates QC inspection and generates Delivery Order after QC pass.
    """
    if current_user["role"] not in ["admin", "security"]:
        raise HTTPException(status_code=403, detail="Only security can complete checklists")
    
    checklist = await db.security_checklists.find_one({"id": checklist_id}, {"_id": 0})
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")
    
    if not checklist.get("net_weight"):
        raise HTTPException(status_code=400, detail="Please record weighment before completing")
    
    # Mark checklist as completed
    await db.security_checklists.update_one(
        {"id": checklist_id},
        {"$set": {
            "status": "COMPLETED",
            "completed_by": current_user["id"],
            "completed_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Create QC inspection
    qc_number = await generate_sequence("QC", "qc_inspections")
    qc_inspection = {
        "id": str(uuid.uuid4()),
        "qc_number": qc_number,
        "ref_type": checklist["checklist_type"],
        "ref_id": checklist["ref_id"],
        "ref_number": checklist["ref_number"],
        "security_checklist_id": checklist_id,
        "net_weight": checklist.get("net_weight"),
        "status": "PENDING",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.qc_inspections.insert_one(qc_inspection)
    
    # Notify QC
    await create_notification(
        event_type="QC_INSPECTION_REQUIRED",
        title=f"QC Inspection Required: {qc_number}",
        message=f"{checklist['checklist_type']} cargo requires QC inspection",
        link="/qc",
        ref_type="QC_INSPECTION",
        ref_id=qc_inspection["id"],
        target_roles=["admin", "qc"],
        notification_type="warning"
    )
    
    return {
        "success": True,
        "message": "Security checklist completed. Sent to QC for inspection.",
        "qc_number": qc_number
    }

# ==================== QC ENDPOINTS ====================

@api_router.get("/qc/dashboard")
async def get_qc_dashboard(current_user: dict = Depends(get_current_user)):
    """Get QC dashboard with pending inspections"""
    
    # Pending inspections
    pending = await db.qc_inspections.find(
        {"status": {"$in": ["PENDING", "IN_PROGRESS"]}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Completed today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    completed_today = await db.qc_inspections.find(
        {"status": "PASSED", "completed_at": {"$regex": f"^{today}"}},
        {"_id": 0}
    ).to_list(100)
    
    # COAs generated
    coas = await db.qc_inspections.find(
        {"coa_generated": True},
        {"_id": 0}
    ).sort("coa_generated_at", -1).to_list(50)
    
    return {
        "pending_inspections": pending,
        "completed_today": completed_today,
        "recent_coas": coas,
        "stats": {
            "pending_count": len(pending),
            "completed_today_count": len(completed_today),
            "coas_generated": len(coas)
        }
    }

@api_router.get("/qc/inspections")
async def get_qc_inspections(status: Optional[str] = None, ref_type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get QC inspections"""
    query = {}
    if status:
        query["status"] = status
    if ref_type:
        query["ref_type"] = ref_type
    
    inspections = await db.qc_inspections.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return inspections

@api_router.put("/qc/inspections/{inspection_id}")
async def update_qc_inspection(inspection_id: str, data: QCInspectionUpdate, current_user: dict = Depends(get_current_user)):
    """Update QC inspection with test results"""
    if current_user["role"] not in ["admin", "qc"]:
        raise HTTPException(status_code=403, detail="Only QC can update inspections")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    
    result = await db.qc_inspections.update_one(
        {"id": inspection_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    return await db.qc_inspections.find_one({"id": inspection_id}, {"_id": 0})

@api_router.put("/qc/inspections/{inspection_id}/pass")
async def pass_qc_inspection(inspection_id: str, current_user: dict = Depends(get_current_user)):
    """
    Pass QC inspection and trigger next steps:
    - INWARD: Create GRN and update stock, notify payables
    - OUTWARD: Generate Delivery Order and documents, notify receivables
    """
    if current_user["role"] not in ["admin", "qc"]:
        raise HTTPException(status_code=403, detail="Only QC can pass inspections")
    
    inspection = await db.qc_inspections.find_one({"id": inspection_id}, {"_id": 0})
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    # Update inspection status
    await db.qc_inspections.update_one(
        {"id": inspection_id},
        {"$set": {
            "status": "PASSED",
            "passed": True,
            "completed_by": current_user["id"],
            "completed_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    result_message = ""
    
    if inspection["ref_type"] == "INWARD":
        # Create GRN and update stock
        grn_result = await create_grn_from_qc(inspection, current_user)
        result_message = f"GRN {grn_result['grn_number']} created. Stock updated. Payables notified."
        
    elif inspection["ref_type"] == "OUTWARD":
        # Generate Delivery Order and documents
        do_result = await create_do_from_qc(inspection, current_user)
        result_message = f"Delivery Order {do_result['do_number']} created. Receivables notified."
    
    return {
        "success": True,
        "message": f"QC Passed. {result_message}"
    }

@api_router.put("/qc/inspections/{inspection_id}/fail")
async def fail_qc_inspection(inspection_id: str, reason: str = "", current_user: dict = Depends(get_current_user)):
    """Fail QC inspection"""
    if current_user["role"] not in ["admin", "qc"]:
        raise HTTPException(status_code=403, detail="Only QC can fail inspections")
    
    await db.qc_inspections.update_one(
        {"id": inspection_id},
        {"$set": {
            "status": "FAILED",
            "passed": False,
            "fail_reason": reason,
            "completed_by": current_user["id"],
            "completed_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"success": True, "message": "QC Failed. Material on hold."}

@api_router.post("/qc/inspections/{inspection_id}/generate-coa")
async def generate_coa(inspection_id: str, current_user: dict = Depends(get_current_user)):
    """Generate Certificate of Analysis for outward shipment"""
    if current_user["role"] not in ["admin", "qc"]:
        raise HTTPException(status_code=403, detail="Only QC can generate COA")
    
    inspection = await db.qc_inspections.find_one({"id": inspection_id}, {"_id": 0})
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    if not inspection.get("passed"):
        raise HTTPException(status_code=400, detail="Cannot generate COA for failed inspection")
    
    coa_number = await generate_sequence("COA", "coas")
    
    await db.qc_inspections.update_one(
        {"id": inspection_id},
        {"$set": {
            "coa_generated": True,
            "coa_number": coa_number,
            "coa_generated_by": current_user["id"],
            "coa_generated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"success": True, "coa_number": coa_number}

# Helper function to create GRN from QC pass (Inward flow)
async def create_grn_from_qc(inspection: dict, current_user: dict):
    """Create GRN after QC pass for inward materials"""
    
    # Get transport inward details
    transport = await db.transport_inward.find_one({"id": inspection["ref_id"]}, {"_id": 0})
    if not transport:
        return {"grn_number": "N/A", "error": "Transport not found"}
    
    # Get PO lines to create GRN items
    po_id = transport.get("po_id")
    po_lines = []
    if po_id:
        po_lines = await db.purchase_order_lines.find({"po_id": po_id}, {"_id": 0}).to_list(100)
    
    grn_number = await generate_sequence("GRN", "grn")
    
    grn_items = []
    for line in po_lines:
        item = await db.inventory_items.find_one({"id": line.get("item_id")}, {"_id": 0})
        grn_items.append({
            "product_id": line.get("item_id"),
            "product_name": line.get("item_name") or (item.get("name") if item else "Unknown"),
            "sku": item.get("sku") if item else "-",
            "quantity": line.get("qty", 0),
            "unit": line.get("uom", "KG")
        })
    
    grn = {
        "id": str(uuid.uuid4()),
        "grn_number": grn_number,
        "supplier": transport.get("supplier_name", "Unknown"),
        "items": grn_items,
        "received_by": current_user["id"],
        "received_at": datetime.now(timezone.utc).isoformat(),
        "review_status": "PENDING_PAYABLES",
        "po_id": po_id,
        "qc_inspection_id": inspection["id"],
        "net_weight": inspection.get("net_weight")
    }
    await db.grn.insert_one(grn)
    
    # Update inventory balances
    for item in grn_items:
        await db.inventory_balances.update_one(
            {"item_id": item["product_id"]},
            {"$inc": {"on_hand": item["quantity"]}},
            upsert=True
        )
    
    # Update transport status
    await db.transport_inward.update_one(
        {"id": transport["id"]},
        {"$set": {"status": "COMPLETED", "grn_number": grn_number}}
    )
    
    # Notify Payables
    await create_notification(
        event_type="GRN_PAYABLES_REVIEW",
        title=f"GRN Pending Review: {grn_number}",
        message=f"GRN from {transport.get('supplier_name')} requires payables review",
        link="/payables",
        ref_type="GRN",
        ref_id=grn["id"],
        target_roles=["admin", "finance"],
        notification_type="warning"
    )
    
    return {"grn_number": grn_number, "grn_id": grn["id"]}

# Helper function to create DO from QC pass (Outward flow)
async def create_do_from_qc(inspection: dict, current_user: dict):
    """Create Delivery Order after QC pass for outward dispatch"""
    
    # Get transport outward details
    transport = await db.transport_outward.find_one({"id": inspection["ref_id"]}, {"_id": 0})
    if not transport:
        # Try to find job order directly
        job = await db.job_orders.find_one({"id": inspection.get("ref_id")}, {"_id": 0})
        if not job:
            return {"do_number": "N/A", "error": "Job/Transport not found"}
        transport = {"job_order_id": job["id"], "customer_name": ""}
    
    do_number = await generate_sequence("DO", "delivery_orders")
    
    # Get job details
    job_id = transport.get("job_order_id") or inspection.get("ref_id")
    job = await db.job_orders.find_one({"id": job_id}, {"_id": 0})
    
    # Get customer info from sales order
    customer_name = transport.get("customer_name", "")
    customer_type = "local"
    if job:
        so = await db.sales_orders.find_one({"id": job.get("sales_order_id")}, {"_id": 0})
        if so:
            customer_name = so.get("customer_name", customer_name)
            quotation = await db.quotations.find_one({"id": so.get("quotation_id")}, {"_id": 0})
            if quotation:
                customer_type = quotation.get("order_type", "local")
    
    delivery_order = {
        "id": str(uuid.uuid4()),
        "do_number": do_number,
        "job_order_id": job_id,
        "job_number": job.get("job_number") if job else "-",
        "product_name": job.get("product_name") if job else "-",
        "quantity": job.get("quantity", 0) if job else 0,
        "customer_name": customer_name,
        "customer_type": customer_type,
        "qc_inspection_id": inspection["id"],
        "net_weight": inspection.get("net_weight"),
        "issued_by": current_user["id"],
        "issued_at": datetime.now(timezone.utc).isoformat()
    }
    await db.delivery_orders.insert_one(delivery_order)
    
    # Update job status
    if job:
        await db.job_orders.update_one(
            {"id": job_id},
            {"$set": {"status": "dispatched"}}
        )
        
        # Deduct from inventory
        product = await db.products.find_one({"id": job.get("product_id")}, {"_id": 0})
        if product:
            new_stock = max(0, product.get("current_stock", 0) - job.get("quantity", 0))
            await db.products.update_one(
                {"id": job.get("product_id")},
                {"$set": {"current_stock": new_stock}}
            )
    
    # Update transport status
    if transport.get("id"):
        await db.transport_outward.update_one(
            {"id": transport["id"]},
            {"$set": {"status": "DISPATCHED", "do_number": do_number}}
        )
    
    # Notify Receivables (different invoice type based on customer)
    invoice_type = "Tax Invoice" if customer_type == "local" else "Commercial Invoice"
    await create_notification(
        event_type="DO_RECEIVABLES_INVOICE",
        title=f"Create {invoice_type}: {do_number}",
        message=f"Delivery Order {do_number} for {customer_name} requires {invoice_type}",
        link="/receivables",
        ref_type="DO",
        ref_id=delivery_order["id"],
        target_roles=["admin", "finance"],
        notification_type="info"
    )
    
    return {"do_number": do_number, "do_id": delivery_order["id"], "invoice_type": invoice_type}

# ==================== EXPORT DOCUMENTS GENERATION ====================

@api_router.get("/documents/export/{job_id}")
async def get_export_documents_status(job_id: str, current_user: dict = Depends(get_current_user)):
    """Get status of export documents for a job (Packing List, COO, BL Draft, COA)"""
    
    job = await db.job_orders.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get QC inspection and COA status
    qc = await db.qc_inspections.find_one({
        "ref_type": "OUTWARD",
        "ref_id": job_id
    }, {"_id": 0})
    
    # Get sales order and quotation for export check
    so = await db.sales_orders.find_one({"id": job.get("sales_order_id")}, {"_id": 0})
    quotation = await db.quotations.find_one({"id": so.get("quotation_id") if so else None}, {"_id": 0})
    
    is_export = quotation.get("order_type") == "export" if quotation else False
    
    documents = {
        "delivery_order": {"status": "PENDING", "number": None},
        "packing_list": {"status": "PENDING", "number": None},
        "certificate_of_origin": {"status": "NOT_REQUIRED" if not is_export else "PENDING", "number": None},
        "bl_draft": {"status": "NOT_REQUIRED" if not is_export else "PENDING", "number": None},
        "certificate_of_analysis": {
            "status": "GENERATED" if (qc and qc.get("coa_generated")) else "PENDING",
            "number": qc.get("coa_number") if qc else None
        }
    }
    
    # Check if DO exists
    do = await db.delivery_orders.find_one({"job_order_id": job_id}, {"_id": 0})
    if do:
        documents["delivery_order"] = {"status": "GENERATED", "number": do.get("do_number")}
    
    return {
        "job_number": job.get("job_number"),
        "is_export": is_export,
        "customer_type": quotation.get("order_type") if quotation else "local",
        "documents": documents
    }


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
