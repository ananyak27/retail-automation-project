from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    phone_number: str

class TokenData(BaseModel):
    phone_number: Optional[str] = None
    role: Optional[str] = None

# User Schemas
class UserLogin(BaseModel):
    phone_number: str
    firebase_id_token: str
    role: Optional[str] = "customer"  # "owner" or "customer"

class CustomerRegister(BaseModel):
    phone_number: str
    firebase_id_token: str
    customer_name: Optional[str] = None

class CheckAccountRequest(BaseModel):
    phone_number: str
    name: Optional[str] = None

class CheckAccountResponse(BaseModel):
    exists: bool
    role: Optional[str] = None
    phone_number: str

class OwnerRegister(BaseModel):
    owner_name: str
    phone_number: str
    firebase_id_token: str
    shop_name: str
    shop_address: str
    bank_account_holder_name: str
    bank_name: str
    account_number: str
    ifsc_code: str
    upi_id: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    phone_number: str
    role: str
    created_at: datetime
    owner_name: Optional[str] = None
    bank_account_holder_name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    upi_id: Optional[str] = None

    class Config:
        from_attributes = True

# Shop Schemas
class ShopCreate(BaseModel):
    name: str
    address: Optional[str] = None

class ShopResponse(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Product Schemas
class ProductCreate(BaseModel):
    name: str
    unit: str
    price: float
    stock: float
    min_stock_threshold: float = 10.0

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[float] = None
    min_stock_threshold: Optional[float] = None

class ProductResponse(BaseModel):
    id: int
    shop_id: int
    name: str
    unit: str
    price: float
    stock: float
    min_stock_threshold: float
    created_at: datetime

    class Config:
        from_attributes = True

# Order Item Schemas
class OrderItemCreate(BaseModel):
    product_id: int
    quantity: float
    unit: str
    price_at_order: float

class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: float
    unit: str
    price_at_order: float
    product_name: Optional[str] = None  # Helper property populated dynamically

    class Config:
        from_attributes = True

# Order Schemas
class OrderCreate(BaseModel):
    shop_id: int
    items: List[OrderItemCreate]
    notes: Optional[str] = None

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    total_amount: Optional[float] = None
    notes: Optional[str] = None
    items: Optional[List[OrderItemCreate]] = None

class OrderResponse(BaseModel):
    id: int
    customer_id: int
    shop_id: int
    status: str
    total_amount: float
    notes: Optional[str] = None
    payment_method: Optional[str] = None
    payment_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]

    class Config:
        from_attributes = True

# Alert Schemas
class AlertResponse(BaseModel):
    id: int
    shop_id: int
    type: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Forecast Schemas
class ForecastItem(BaseModel):
    ds: str
    yhat: float
    yhat_lower: float
    yhat_upper: float

class ForecastResponse(BaseModel):
    product_id: int
    product_name: str
    forecast: List[ForecastItem]
