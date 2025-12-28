from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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

class Product(ProductCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    current_stock: float = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Quotation/PFI Model
class QuotationItem(BaseModel):
    product_id: str
    product_name: str
    sku: str
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
    product_id: str
    product_name: str
    sku: str
    required_qty: float
    available_qty: float = 0
    unit: str = "KG"

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
    sku: str
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
    
    schedule_number = await generate_sequence("TRN", "transport_schedules")
    schedule = TransportSchedule(
        **data.model_dump(),
        schedule_number=schedule_number,
        booking_number=booking["booking_number"],
        created_by=current_user["id"]
    )
    await db.transport_schedules.insert_one(schedule.model_dump())
    return schedule

@api_router.get("/transport-schedules", response_model=List[TransportSchedule])
async def get_transport_schedules(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    schedules = await db.transport_schedules.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return schedules

@api_router.put("/transport-schedules/{schedule_id}")
async def update_transport_schedule(
    schedule_id: str,
    status: Optional[str] = None,
    vehicle_number: Optional[str] = None,
    driver_name: Optional[str] = None,
    driver_phone: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    update_data = {}
    if status:
        update_data["status"] = status
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
    return {"message": "Schedule updated"}

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

@api_router.get("/")
async def root():
    return {"message": "Manufacturing ERP API", "version": "1.0.0"}

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
