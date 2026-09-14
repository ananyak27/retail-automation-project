import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User, Shop

client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup_test_users():
    """Clean up test users before and after tests."""
    db = SessionLocal()
    try:
        test_phones = ["+917777711111", "+918888822222", "+919988776655", "+917000012345", "+918000012345"]
        db.query(Shop).filter(Shop.owner_id.in_(
            db.query(User.id).filter(User.phone_number.in_(test_phones))
        )).delete(synchronize_session=False)
        db.query(User).filter(User.phone_number.in_(test_phones)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(Shop).filter(Shop.owner_id.in_(
            db.query(User.id).filter(User.phone_number.in_(test_phones))
        )).delete(synchronize_session=False)
        db.query(User).filter(User.phone_number.in_(test_phones)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

# TEST CASE 1: Customer login with owner phone number → pre-check detects owner role
def test_customer_login_with_owner_phone():
    """Verify pre-OTP check rejects Customer login for an Owner phone number."""
    # Register Owner
    client.post("/api/auth/register-owner", json={
        "owner_name": "Shop Owner",
        "phone_number": "+918888822222",
        "firebase_id_token": "mock_token_+918888822222",
        "shop_name": "Owner Shop",
        "shop_address": "123 Main St",
        "bank_account_holder_name": "Shop Owner",
        "bank_name": "SBI",
        "account_number": "1234567890",
        "ifsc_code": "SBIN0001234"
    })

    # Pre-OTP check for customer login with owner number
    response = client.post("/api/auth/check-account", json={
        "phone_number": "+918888822222"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] == True
    assert data["role"] == "owner"

# TEST CASE 2: Customer login with customer phone number → pre-check passes
def test_customer_login_with_customer_phone():
    """Verify pre-OTP check passes for Customer login with a Customer phone number."""
    # Register Customer
    client.post("/api/auth/register-customer", json={
        "phone_number": "+917777711111",
        "firebase_id_token": "mock_token_+917777711111",
        "customer_name": "Registered Customer"
    })

    # Pre-OTP check
    response = client.post("/api/auth/check-account", json={
        "phone_number": "+917777711111"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] == True
    assert data["role"] == "customer"

# TEST CASE 3: Customer login with unknown phone number → pre-check returns exists=False
def test_customer_login_with_unknown_phone():
    """Verify pre-OTP check detects unknown phone number for Customer login."""
    response = client.post("/api/auth/check-account", json={
        "phone_number": "+919988776655"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] == False
    assert data["role"] is None

# TEST CASE 4: Owner login with customer phone number → pre-check detects customer role
def test_owner_login_with_customer_phone():
    """Verify pre-OTP check rejects Owner login for a Customer phone number."""
    # Register Customer
    client.post("/api/auth/register-customer", json={
        "phone_number": "+917777711111",
        "firebase_id_token": "mock_token_+917777711111",
        "customer_name": "Customer User"
    })

    # Pre-OTP check for owner login with customer number
    response = client.post("/api/auth/check-account", json={
        "phone_number": "+917777711111"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] == True
    assert data["role"] == "customer"

# TEST CASE 5: Owner login with owner phone number → pre-check passes
def test_owner_login_with_owner_phone():
    """Verify pre-OTP check passes for Owner login with an Owner phone number."""
    # Register Owner
    client.post("/api/auth/register-owner", json={
        "owner_name": "Owner User",
        "phone_number": "+918888822222",
        "firebase_id_token": "mock_token_+918888822222",
        "shop_name": "Supermart",
        "shop_address": "456 Market St",
        "bank_account_holder_name": "Owner User",
        "bank_name": "HDFC",
        "account_number": "9876543210",
        "ifsc_code": "HDFC0001234"
    })

    # Pre-OTP check
    response = client.post("/api/auth/check-account", json={
        "phone_number": "+918888822222"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] == True
    assert data["role"] == "owner"

def test_full_login_endpoints():
    """Verify full login endpoints enforce role and account existence."""
    # Register Customer
    client.post("/api/auth/register-customer", json={
        "phone_number": "+917777711111",
        "firebase_id_token": "mock_token_+917777711111",
        "customer_name": "Registered Customer"
    })

    # Login as Customer -> 200
    res = client.post("/api/auth/login", json={
        "phone_number": "+917777711111",
        "firebase_id_token": "mock_token_+917777711111",
        "role": "customer"
    })
    assert res.status_code == 200

    # Try Customer Login as Owner -> 404
    res_mismatch = client.post("/api/auth/login", json={
        "phone_number": "+917777711111",
        "firebase_id_token": "mock_token_+917777711111",
        "role": "owner"
    })
    assert res_mismatch.status_code == 404
