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
    total: float = 0

class QuotationCreate(BaseModel):
    customer_id: str
    customer_name: str
    items: List[QuotationItem]
    currency: str = "USD"  # USD, AED, EUR
    order_type: str = "local"  # local or export
    incoterm: Optional[str] = None  # CFR, FOB, CIF, etc.
    port_of_loading: Optional[str] = None
    delivery_place: Optional[str] = None
    payment_terms: str = "Cash"  # LC, CAD, Cash
    validity_days: int = 30
    notes: Optional[str] = None

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
    quantity: float
    bom: List[BOMItem] = []
    priority: str = "normal"  # low, normal, high, urgent
    notes: Optional[str] = None

class JobOrder(JobOrderCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_number: str = ""
    spa_number: str = ""
    status: str = "pending"  # pending, in_production, procurement, ready_for_dispatch, dispatched
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
    
    subtotal = sum(item.quantity * item.unit_price for item in data.items)
    items_with_total = []
    for item in data.items:
        item_dict = item.model_dump()
        item_dict["total"] = item.quantity * item.unit_price
        items_with_total.append(item_dict)
    
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
    
    # Send email notification and create in-app notification
    quotation = await db.quotations.find_one({"id": quotation_id}, {"_id": 0})
    if quotation:
        asyncio.create_task(notify_quotation_approved(quotation))
        # Create in-app notification
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
    
    return {"message": "Quotation approved"}

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
    
    return grn

@api_router.get("/grn", response_model=List[GRN])
async def get_grns(current_user: dict = Depends(get_current_user)):
    grns = await db.grn.find({}, {"_id": 0}).sort("received_at", -1).to_list(1000)
    return grns

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
        
        bom['items'] = bom_items
    
    return boms

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
