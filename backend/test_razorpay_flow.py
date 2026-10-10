import os
import sys
import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.config import settings
from app.models import User, Shop, Product, Order, SalesHistory
from conftest import TestingSessionLocal

client = TestClient(app)

CUSTOMER_PHONE = "+917777711111"
OWNER_PHONE = "+918888822222"

def get_tokens():
    cust_res = client.post("/api/auth/login", json={
        "phone_number": CUSTOMER_PHONE,
        "role": "customer",
        "firebase_id_token": "mock_token"
    })
    assert cust_res.status_code == 200, cust_res.text
    cust_token = cust_res.json()["access_token"]

    owner_res = client.post("/api/auth/login", json={
        "phone_number": OWNER_PHONE,
        "role": "owner",
        "firebase_id_token": "mock_token"
    })
    assert owner_res.status_code == 200, owner_res.text
    owner_token = owner_res.json()["access_token"]

    return {
        "customer": {"Authorization": f"Bearer {cust_token}"},
        "owner": {"Authorization": f"Bearer {owner_token}"}
    }

def make_signature(rzp_order_id: str, payment_id: str) -> str:
    secret = settings.RAZORPAY_KEY_SECRET or ""
    if secret:
        return hmac.new(
            secret.encode("utf-8"),
            f"{rzp_order_id}|{payment_id}".encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
    return "test_signature"


def test_01_config_and_test_mode_detection():
    """Verify backend settings load Razorpay credentials and defaults properly."""
    assert hasattr(settings, "RAZORPAY_KEY_ID")
    assert hasattr(settings, "RAZORPAY_KEY_SECRET")
    assert hasattr(settings, "RAZORPAY_WEBHOOK_SECRET")
    assert hasattr(settings, "MERCHANT_UPI_VPA")
    assert settings.MERCHANT_UPI_VPA is not None


def test_02_create_razorpay_order_success():
    """Customer can create a Razorpay order with valid amount and fields."""
    headers = get_tokens()
    db = TestingSessionLocal()
    try:
        prod = db.query(Product).filter(Product.shop_id == 1, Product.stock >= 5).first()
        assert prod is not None
        prod_id = prod.id
        price = prod.price
    finally:
        db.close()

    # Create draft order
    draft_res = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod_id, "quantity": 2.0, "unit": "kg", "price_at_order": price}],
        "notes": "Razorpay test order"
    }, headers=headers["customer"])
    assert draft_res.status_code == 200, draft_res.text
    order_id = draft_res.json()["id"]

    # Create Razorpay order
    rzp_res = client.post(f"/api/payments/create-razorpay-order/{order_id}", headers=headers["customer"])
    assert rzp_res.status_code == 200, rzp_res.text
    data = rzp_res.json()

    assert data["payment_method"] == "razorpay"
    assert "razorpay_order_id" in data
    assert data["razorpay_order_id"].startswith("order_rzp_") or data["razorpay_order_id"].startswith("order_")
    assert data["amount"] == 2.0 * price
    assert data["amount_paise"] == int(round(2.0 * price * 100))
    assert data["currency"] == "INR"
    assert "key_id" in data
    assert "upi_uri" in data
    assert settings.MERCHANT_UPI_VPA in data["upi_uri"]

    # Verify order state in DB
    order_check = client.get(f"/api/orders/{order_id}", headers=headers["customer"]).json()
    assert order_check["status"] == "pending_payment"
    assert order_check["payment_status"] == "online_pending"
    assert order_check["razorpay_order_id"] == data["razorpay_order_id"]


def test_03_insufficient_stock_prevents_order_and_payment():
    """Attempting to initiate payment when stock is insufficient fails with HTTP 400."""
    headers = get_tokens()
    db = TestingSessionLocal()
    try:
        # Create a low-stock product
        prod = Product(
            shop_id=1,
            name="Limited Product",
            unit="piece",
            price=100.0,
            stock=1.0,
            min_stock_threshold=2.0,
            is_active=True
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)
        prod_id = prod.id
    finally:
        db.close()

    # Draft order for 1 piece (stock ok at draft time)
    draft_res = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod_id, "quantity": 1.0, "unit": "piece", "price_at_order": 100.0}],
    }, headers=headers["customer"])
    assert draft_res.status_code == 200
    order_id = draft_res.json()["id"]

    # Reduce product stock to 0 to simulate concurrency
    db = TestingSessionLocal()
    try:
        p = db.query(Product).filter(Product.id == prod_id).first()
        p.stock = 0.0
        db.commit()
    finally:
        db.close()

    # Now attempt to initiate payment -> must fail with HTTP 400
    pay_res = client.post(f"/api/payments/create-razorpay-order/{order_id}", headers=headers["customer"])
    assert pay_res.status_code == 400
    assert "Insufficient stock" in pay_res.json()["detail"]


def test_04_verify_signature_success_and_atomic_stock_deduction():
    """Valid signature verification confirms payment, deducts stock atomically, and records sales history."""
    headers = get_tokens()
    db = TestingSessionLocal()
    try:
        prod = db.query(Product).filter(Product.shop_id == 1, Product.stock >= 10).first()
        prod_id = prod.id
        initial_stock = prod.stock
    finally:
        db.close()

    # Create draft order for 2 units
    draft_res = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod_id, "quantity": 2.0, "unit": prod.unit, "price_at_order": prod.price}],
    }, headers=headers["customer"])
    order_id = draft_res.json()["id"]

    # Create Razorpay order
    rzp_res = client.post(f"/api/payments/create-razorpay-order/{order_id}", headers=headers["customer"])
    rzp_order_id = rzp_res.json()["razorpay_order_id"]

    # Verify with valid HMAC signature
    valid_sig = make_signature(rzp_order_id, "pay_test_signature_123")
    verify_res = client.post("/api/payments/verify-razorpay-signature", json={
        "order_id": order_id,
        "razorpay_order_id": rzp_order_id,
        "razorpay_payment_id": "pay_test_signature_123",
        "razorpay_signature": valid_sig
    }, headers=headers["customer"])
    assert verify_res.status_code == 200, verify_res.text
    assert verify_res.json()["status"] == "success"

    # Verify order is marked paid
    order_chk = client.get(f"/api/orders/{order_id}", headers=headers["customer"]).json()
    assert order_chk["status"] == "paid"
    assert order_chk["payment_status"] == "paid"

    # Verify inventory was deducted by exactly 2.0
    db = TestingSessionLocal()
    try:
        updated_prod = db.query(Product).filter(Product.id == prod_id).first()
        assert updated_prod.stock == initial_stock - 2.0

        # Verify SalesHistory record was written
        sales = db.query(SalesHistory).filter(SalesHistory.product_id == prod_id).all()
        assert len(sales) > 0
    finally:
        db.close()


def test_05_invalid_signature_rejected():
    """Invalid signature is rejected with HTTP 400 and does NOT deduct stock."""
    headers = get_tokens()
    db = TestingSessionLocal()
    try:
        prod = db.query(Product).filter(Product.shop_id == 1, Product.stock >= 5).first()
        prod_id = prod.id
        initial_stock = prod.stock
    finally:
        db.close()

    draft_res = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod_id, "quantity": 1.0, "unit": prod.unit, "price_at_order": prod.price}],
    }, headers=headers["customer"])
    order_id = draft_res.json()["id"]

    rzp_res = client.post(f"/api/payments/create-razorpay-order/{order_id}", headers=headers["customer"])
    rzp_order_id = rzp_res.json()["razorpay_order_id"]

    # Invalid signature attempt
    verify_res = client.post("/api/payments/verify-razorpay-signature", json={
        "order_id": order_id,
        "razorpay_order_id": rzp_order_id,
        "razorpay_payment_id": "pay_fake_999",
        "razorpay_signature": "completely_invalid_signature_hash"
    }, headers=headers["customer"])
    assert verify_res.status_code == 400
    assert "Invalid Razorpay payment signature" in verify_res.json()["detail"]

    # Verify order is STILL pending, stock NOT deducted
    order_chk = client.get(f"/api/orders/{order_id}", headers=headers["customer"]).json()
    assert order_chk["payment_status"] != "paid"

    db = TestingSessionLocal()
    try:
        p = db.query(Product).filter(Product.id == prod_id).first()
        assert p.stock == initial_stock
    finally:
        db.close()


def test_06_order_id_mismatch_rejected():
    """If razorpay_order_id does not match the order record, verify returns HTTP 400."""
    headers = get_tokens()
    db = TestingSessionLocal()
    try:
        prod = db.query(Product).filter(Product.shop_id == 1).first()
        prod_id = prod.id
    finally:
        db.close()

    draft_res = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod_id, "quantity": 1.0, "unit": prod.unit, "price_at_order": prod.price}],
    }, headers=headers["customer"])
    order_id = draft_res.json()["id"]

    client.post(f"/api/payments/create-razorpay-order/{order_id}", headers=headers["customer"])

    # Provide mismatched order id
    verify_res = client.post("/api/payments/verify-razorpay-signature", json={
        "order_id": order_id,
        "razorpay_order_id": "order_mismatched_9999",
        "razorpay_payment_id": "pay_test_123",
        "razorpay_signature": "test_signature"
    }, headers=headers["customer"])
    assert verify_res.status_code == 400
    assert "mismatch" in verify_res.json()["detail"].lower()


def test_07_duplicate_verification_is_idempotent():
    """Submitting verification twice for the same order returns success without double-deduction."""
    headers = get_tokens()
    db = TestingSessionLocal()
    try:
        prod = db.query(Product).filter(Product.shop_id == 1, Product.stock >= 10).first()
        prod_id = prod.id
        initial_stock = prod.stock
    finally:
        db.close()

    draft_res = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod_id, "quantity": 1.0, "unit": prod.unit, "price_at_order": prod.price}],
    }, headers=headers["customer"])
    order_id = draft_res.json()["id"]

    rzp_res = client.post(f"/api/payments/create-razorpay-order/{order_id}", headers=headers["customer"])
    rzp_order_id = rzp_res.json()["razorpay_order_id"]

    valid_sig = make_signature(rzp_order_id, "pay_dup_1")

    # First verification
    res1 = client.post("/api/payments/verify-razorpay-signature", json={
        "order_id": order_id,
        "razorpay_order_id": rzp_order_id,
        "razorpay_payment_id": "pay_dup_1",
        "razorpay_signature": valid_sig
    }, headers=headers["customer"])
    assert res1.status_code == 200

    # Second (duplicate) verification
    res2 = client.post("/api/payments/verify-razorpay-signature", json={
        "order_id": order_id,
        "razorpay_order_id": rzp_order_id,
        "razorpay_payment_id": "pay_dup_1",
        "razorpay_signature": valid_sig
    }, headers=headers["customer"])
    assert res2.status_code == 200
    assert "already paid" in res2.json()["message"].lower()

    # Stock should only be deducted ONCE (1.0, not 2.0)
    db = TestingSessionLocal()
    try:
        p = db.query(Product).filter(Product.id == prod_id).first()
        assert p.stock == initial_stock - 1.0
    finally:
        db.close()


def test_08_webhook_payment_captured_and_deduction():
    """Webhook handling for payment.captured marks order paid and deducts inventory."""
    headers = get_tokens()
    db = TestingSessionLocal()
    try:
        prod = db.query(Product).filter(Product.shop_id == 1, Product.stock >= 5).first()
        prod_id = prod.id
        initial_stock = prod.stock
    finally:
        db.close()

    draft_res = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod_id, "quantity": 1.0, "unit": prod.unit, "price_at_order": prod.price}],
    }, headers=headers["customer"])
    order_id = draft_res.json()["id"]

    rzp_res = client.post(f"/api/payments/create-razorpay-order/{order_id}", headers=headers["customer"])
    rzp_order_id = rzp_res.json()["razorpay_order_id"]

    # Simulate webhook payment.captured
    webhook_res = client.post("/api/payments/webhook", json={
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_wh_captured_123",
                    "order_id": rzp_order_id,
                    "amount": int(prod.price * 100),
                    "currency": "INR",
                    "status": "captured"
                }
            }
        }
    }, headers={"x-razorpay-signature": "sandbox_bypass"})
    assert webhook_res.status_code == 200
    assert webhook_res.json()["status"] == "success"

    # Verify order is paid
    order_chk = client.get(f"/api/orders/{order_id}", headers=headers["customer"]).json()
    assert order_chk["status"] == "paid"
    assert order_chk["payment_status"] == "paid"

    # Stock deducted
    db = TestingSessionLocal()
    try:
        p = db.query(Product).filter(Product.id == prod_id).first()
        assert p.stock == initial_stock - 1.0
    finally:
        db.close()


def test_09_webhook_duplicate_delivery_is_safe():
    """Duplicate delivery of payment.captured webhook does not deduct stock twice."""
    headers = get_tokens()
    db = TestingSessionLocal()
    try:
        prod = db.query(Product).filter(Product.shop_id == 1, Product.stock >= 5).first()
        prod_id = prod.id
        initial_stock = prod.stock
    finally:
        db.close()

    draft_res = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod_id, "quantity": 1.0, "unit": prod.unit, "price_at_order": prod.price}],
    }, headers=headers["customer"])
    order_id = draft_res.json()["id"]

    rzp_res = client.post(f"/api/payments/create-razorpay-order/{order_id}", headers=headers["customer"])
    rzp_order_id = rzp_res.json()["razorpay_order_id"]

    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_dup_wh_1",
                    "order_id": rzp_order_id,
                    "amount": int(prod.price * 100)
                }
            }
        }
    }

    # Delivery 1
    wh1 = client.post("/api/payments/webhook", json=payload, headers={"x-razorpay-signature": "sandbox_bypass"})
    assert wh1.status_code == 200

    # Delivery 2 (retry)
    wh2 = client.post("/api/payments/webhook", json=payload, headers={"x-razorpay-signature": "sandbox_bypass"})
    assert wh2.status_code == 200

    # Stock deducted only ONCE
    db = TestingSessionLocal()
    try:
        p = db.query(Product).filter(Product.id == prod_id).first()
        assert p.stock == initial_stock - 1.0
    finally:
        db.close()


def test_10_webhook_payment_failed_does_not_deduct_inventory():
    """Webhook payment.failed event marks payment as failed and does NOT touch inventory."""
    headers = get_tokens()
    db = TestingSessionLocal()
    try:
        prod = db.query(Product).filter(Product.shop_id == 1, Product.stock >= 5).first()
        prod_id = prod.id
        initial_stock = prod.stock
    finally:
        db.close()

    draft_res = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod_id, "quantity": 1.0, "unit": prod.unit, "price_at_order": prod.price}],
    }, headers=headers["customer"])
    order_id = draft_res.json()["id"]

    rzp_res = client.post(f"/api/payments/create-razorpay-order/{order_id}", headers=headers["customer"])
    rzp_order_id = rzp_res.json()["razorpay_order_id"]

    # Send payment.failed webhook
    fail_res = client.post("/api/payments/webhook", json={
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_failed_123",
                    "order_id": rzp_order_id,
                    "error_description": "Card declined by issuing bank"
                }
            }
        }
    }, headers={"x-razorpay-signature": "sandbox_bypass"})
    assert fail_res.status_code == 200
    assert fail_res.json()["event"] == "payment.failed"

    # Order payment_status should be failed, not paid
    order_chk = client.get(f"/api/orders/{order_id}", headers=headers["customer"]).json()
    assert order_chk["payment_status"] == "failed"
    assert order_chk["status"] != "paid"

    # Inventory must remain completely untouched
    db = TestingSessionLocal()
    try:
        p = db.query(Product).filter(Product.id == prod_id).first()
        assert p.stock == initial_stock
    finally:
        db.close()


def test_11_cash_payment_flow():
    """Cash payment workflow: customer selects cash, owner confirms, inventory deducted."""
    headers = get_tokens()
    db = TestingSessionLocal()
    try:
        prod = db.query(Product).filter(Product.shop_id == 1, Product.stock >= 5).first()
        prod_id = prod.id
        initial_stock = prod.stock
    finally:
        db.close()

    draft_res = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod_id, "quantity": 1.0, "unit": prod.unit, "price_at_order": prod.price}],
    }, headers=headers["customer"])
    order_id = draft_res.json()["id"]

    # Customer selects cash
    cash_init = client.post(f"/api/payments/initiate/{order_id}?method=cash", headers=headers["customer"])
    assert cash_init.status_code == 200
    assert cash_init.json()["payment_status"] == "cash_pending"

    # Customer CANNOT confirm cash payment (HTTP 403)
    cust_confirm = client.post(f"/api/payments/confirm-cash/{order_id}", headers=headers["customer"])
    assert cust_confirm.status_code == 403

    # Owner confirms cash payment
    owner_confirm = client.post(f"/api/payments/confirm-cash/{order_id}", headers=headers["owner"])
    assert owner_confirm.status_code == 200
    assert owner_confirm.json()["status"] == "success"

    # Order marked paid, inventory deducted
    order_chk = client.get(f"/api/orders/{order_id}", headers=headers["customer"]).json()
    assert order_chk["status"] == "paid"
    assert order_chk["payment_status"] == "paid"
    assert order_chk["payment_method"] == "cash"

    db = TestingSessionLocal()
    try:
        p = db.query(Product).filter(Product.id == prod_id).first()
        assert p.stock == initial_stock - 1.0
    finally:
        db.close()


def test_12_demo_payment_simulation_in_dev():
    """Demo payment simulation works in development environment."""
    headers = get_tokens()
    db = TestingSessionLocal()
    try:
        prod = db.query(Product).filter(Product.shop_id == 1, Product.stock >= 5).first()
        prod_id = prod.id
    finally:
        db.close()

    draft_res = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod_id, "quantity": 1.0, "unit": prod.unit, "price_at_order": prod.price}],
    }, headers=headers["customer"])
    order_id = draft_res.json()["id"]

    rzp_res = client.post(f"/api/payments/create-razorpay-order/{order_id}", headers=headers["customer"])
    rzp_order_id = rzp_res.json()["razorpay_order_id"]

    demo_res = client.post("/api/payments/demo-payment-success", json={
        "order_id": order_id,
        "razorpay_order_id": rzp_order_id
    }, headers=headers["customer"])
    assert demo_res.status_code == 200
    assert demo_res.json()["status"] == "success"

    order_chk = client.get(f"/api/orders/{order_id}", headers=headers["customer"]).json()
    assert order_chk["status"] == "paid"
    assert order_chk["payment_method"] == "simulated_demo"


def test_13_production_mode_rejects_bypass_webhook():
    """In production, webhook MUST reject sandbox_bypass / test_signature with HTTP 403."""
    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        webhook_res = client.post("/api/payments/webhook", json={
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_fake_bypass",
                        "order_id": "order_fake"
                    }
                }
            }
        }, headers={"x-razorpay-signature": "sandbox_bypass"})
        assert webhook_res.status_code == 403
        assert "not permitted in production" in webhook_res.json()["detail"]
    finally:
        settings.ENVIRONMENT = orig_env


def test_14_production_mode_rejects_demo_endpoint():
    """In production, demo payment endpoint MUST be blocked with HTTP 403."""
    headers = get_tokens()
    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        demo_res = client.post("/api/payments/demo-payment-success", json={
            "order_id": 1,
            "razorpay_order_id": "order_test"
        }, headers=headers["customer"])
        assert demo_res.status_code == 403
        assert "disabled in production" in demo_res.json()["detail"]
    finally:
        settings.ENVIRONMENT = orig_env


def test_15_race_condition_between_checkout_verify_and_webhook():
    """Simulate concurrent arrival of Checkout signature verification and webhook delivery.
    Confirms inventory deduction and payment confirmation are strictly idempotent.
    """
    headers = get_tokens()
    db = TestingSessionLocal()
    try:
        prod = db.query(Product).filter(Product.shop_id == 1, Product.stock >= 10).first()
        prod_id = prod.id
        initial_stock = prod.stock
    finally:
        db.close()

    draft_res = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod_id, "quantity": 3.0, "unit": prod.unit, "price_at_order": prod.price}],
    }, headers=headers["customer"])
    order_id = draft_res.json()["id"]

    rzp_res = client.post(f"/api/payments/create-razorpay-order/{order_id}", headers=headers["customer"])
    rzp_order_id = rzp_res.json()["razorpay_order_id"]

    valid_sig = make_signature(rzp_order_id, "pay_concurrent_123")

    # Step 1: Frontend Checkout verification arrives first
    verify_res = client.post("/api/payments/verify-razorpay-signature", json={
        "order_id": order_id,
        "razorpay_order_id": rzp_order_id,
        "razorpay_payment_id": "pay_concurrent_123",
        "razorpay_signature": valid_sig
    }, headers=headers["customer"])
    assert verify_res.status_code == 200

    # Step 2: Webhook delivery arrives concurrently for the exact same order
    webhook_res = client.post("/api/payments/webhook", json={
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_concurrent_123",
                    "order_id": rzp_order_id,
                    "amount": int(prod.price * 3.0 * 100)
                }
            }
        }
    }, headers={"x-razorpay-signature": "sandbox_bypass"})
    assert webhook_res.status_code == 200

    # Step 3: Stock MUST be deducted by exactly 3.0 units (not 6.0 units)
    db = TestingSessionLocal()
    try:
        p = db.query(Product).filter(Product.id == prod_id).first()
        assert p.stock == initial_stock - 3.0

        # Verify only 1 sales record was created for this payment
        sales = db.query(SalesHistory).filter(SalesHistory.product_id == prod_id, SalesHistory.quantity == 3.0).all()
        assert len(sales) == 1
    finally:
        db.close()
