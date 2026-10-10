import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app as fastapi_app
import app.database as app_db
from app.models import User, Shop, Product

# 1. Create Isolated In-Memory SQLite Test Engine
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="session", autouse=True)
def setup_isolated_test_db():
    """Sets up an isolated SQLite in-memory database with test data for automated testing."""
    # Create schema
    Base.metadata.create_all(bind=test_engine)

    # Monkeypatch global SessionLocal to use test_engine
    app_db.SessionLocal = TestingSessionLocal

    db = TestingSessionLocal()
    try:
        # Seed Test Owner
        owner = User(
            phone_number="+918888822222",
            role="owner",
            firebase_uid="mock_uid_918888822222",
            owner_name="Test Owner",
            bank_account_holder_name="Test Owner",
            bank_name="SBI",
            account_number="1234567890",
            ifsc_code="SBIN0001234",
            upi_id="owner@upi"
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

        # Seed Test Customer
        customer = User(
            phone_number="+917777711111",
            role="customer",
            firebase_uid="mock_uid_917777711111",
            owner_name="Test Customer"
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        # Seed Test Shop 1
        shop1 = Shop(
            id=1,
            name="General Store",
            address="123 Main St",
            owner_id=owner.id,
            last_order_number=0
        )
        db.add(shop1)

        # Seed Test Shop 2
        shop2 = Shop(
            id=2,
            name="Supermart",
            address="456 Market St",
            owner_id=owner.id,
            last_order_number=0
        )
        db.add(shop2)
        db.commit()

        # Seed Test Products for Shop 1
        p1 = Product(
            id=1,
            shop_id=1,
            name="Rice",
            unit="kg",
            price=50.0,
            stock=100.0,
            min_stock_threshold=10.0,
            is_active=True
        )
        p2 = Product(
            id=2,
            shop_id=1,
            name="Sugar",
            unit="kg",
            price=40.0,
            stock=80.0,
            min_stock_threshold=10.0,
            is_active=True
        )
        # Seed Test Product for Shop 2
        p3 = Product(
            id=3,
            shop_id=2,
            name="Milk",
            unit="litre",
            price=30.0,
            stock=50.0,
            min_stock_threshold=5.0,
            is_active=True
        )
        db.add_all([p1, p2, p3])
        db.commit()
    finally:
        db.close()

    # Override get_db dependency in FastAPI app
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield
    fastapi_app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
