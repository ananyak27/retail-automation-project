import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, default="customer", nullable=False)  # "owner" or "customer"
    firebase_uid = Column(String, unique=True, index=True, nullable=True)
    owner_name = Column(String, nullable=True)
    bank_account_holder_name = Column(String, nullable=True)
    bank_name = Column(String, nullable=True)
    account_number = Column(String, nullable=True)
    ifsc_code = Column(String, nullable=True)
    upi_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    shops = relationship("Shop", back_populates="owner")
    orders = relationship("Order", back_populates="customer")


class Shop(Base):
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    last_order_number = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="shops")
    products = relationship("Product", back_populates="shop")
    orders = relationship("Order", back_populates="shop")
    alerts = relationship("Alert", back_populates="shop")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False, index=True)
    unit = Column(String, nullable=False)  # "kg", "litre", "piece", etc.
    price = Column(Float, nullable=False)
    stock = Column(Float, nullable=False)
    min_stock_threshold = Column(Float, default=10.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    shop = relationship("Shop", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")
    sales_history = relationship("SalesHistory", back_populates="product")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    shop_order_number = Column(Integer, nullable=True, index=True)
    # Order Statuses: pending_owner, pending_customer, confirmed, paid, cancelled, rejected
    status = Column(String, default="pending_owner", nullable=False, index=True)
    # Payment Statuses: pending, cash_pending, online_pending, paid, failed
    payment_status = Column(String, default="pending", nullable=False, index=True)
    total_amount = Column(Float, default=0.0, nullable=False)
    notes = Column(String, nullable=True)
    payment_method = Column(String, nullable=True)  # "cash" or "razorpay"
    payment_id = Column(String, nullable=True)  # Legacy payment ID or transaction reference
    razorpay_order_id = Column(String, nullable=True)
    razorpay_payment_id = Column(String, nullable=True)
    razorpay_signature = Column(String, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    from sqlalchemy import UniqueConstraint
    __table_args__ = (
        UniqueConstraint('shop_id', 'shop_order_number', name='_shop_order_number_uc'),
    )

    # Relationships
    customer = relationship("User", back_populates="orders")
    shop = relationship("Shop", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    price_at_order = Column(Float, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class SalesHistory(Base):
    __tablename__ = "sales_history"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    sold_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    # Relationships
    product = relationship("Product", back_populates="sales_history")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)  # "low_stock", "pending_payment", "new_order"
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    shop = relationship("Shop", back_populates="alerts")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_role = Column(String, nullable=False)  # "customer", "bot", or "owner"
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    shop = relationship("Shop")
    customer = relationship("User")

