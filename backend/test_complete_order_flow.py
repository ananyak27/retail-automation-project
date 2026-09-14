import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend folder is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.database import SessionLocal
from app.models import User, Shop, Product, Order, SalesHistory, Alert

client = TestClient(app)

def test_complete_customer_owner_order_flow():
    db = SessionLocal()
    try:
        owner_user = db.query(User).filter(User.role == 'owner').first()
        customer_user = db.query(User).filter(User.role == 'customer').first()
        owner_phone = owner_user.phone_number
        customer_phone = customer_user.phone_number
    finally:
        db.close()

    # 1. Login Customer
    cust_res = client.post("/api/auth/login", json={"phone_number": customer_phone, "role": "customer", "firebase_id_token": "mock_token"})
    assert cust_res.status_code == 200, cust_res.text
    cust_token = cust_res.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}
    
    # 2. Login Owner
    owner_res = client.post("/api/auth/login", json={"phone_number": owner_phone, "role": "owner", "firebase_id_token": "mock_token"})
    assert owner_res.status_code == 200, owner_res.text
    owner_token = owner_res.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # Get shop_id = 1 product
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.shop_id == 1, Product.stock > 10).first()
        assert product is not None
        product_id = product.id
        initial_stock = product.stock
        sales_count_before = db.query(SalesHistory).filter(SalesHistory.product_id == product_id).count()
    finally:
        db.close()

    # 3. Customer submits order (immediately creates order with status pending_payment)
    draft_payload = {
        "shop_id": 1,
        "items": [
            {
                "product_id": product_id,
                "quantity": 2.0,
                "unit": "kg",
                "price_at_order": 50.0
            }
        ],
        "notes": "Direct customer submission"
    }
    create_res = client.post("/api/orders/create-draft", json=draft_payload, headers=cust_headers)
    assert create_res.status_code == 200, create_res.text
    order_data = create_res.json()
    order_id = order_data["id"]
    assert order_data["status"] == "pending_payment"
    assert order_data["customer_name"] is not None
    assert order_data["customer_phone"] == customer_phone
    assert order_data["created_at"].endswith("Z")

    # 4. Immediate Customer Payment Choice: Create Razorpay Order
    rzp_res = client.post(f"/api/payments/create-razorpay-order/{order_id}", headers=cust_headers)
    assert rzp_res.status_code == 200, rzp_res.text
    rzp_data = rzp_res.json()
    assert "razorpay_order_id" in rzp_data
    assert rzp_data["amount"] == 100.0

    # 5. Verify Razorpay Signature & Process Payment automatically on backend
    verify_payload = {
        "order_id": order_id,
        "razorpay_order_id": rzp_data["razorpay_order_id"],
        "razorpay_payment_id": "pay_test_123456",
        "razorpay_signature": "test_signature"
    }
    verify_res = client.post("/api/payments/verify-razorpay-signature", json=verify_payload, headers=cust_headers)
    assert verify_res.status_code == 200, verify_res.text
    assert verify_res.json()["status"] == "success"

    # 6. Check updated order via API for both customer and owner
    cust_order_res = client.get(f"/api/orders/{order_id}", headers=cust_headers)
    assert cust_order_res.status_code == 200
    paid_order = cust_order_res.json()
    assert paid_order["id"] == order_id
    assert paid_order["status"] == "paid"
    assert paid_order["payment_status"] == "paid"
    assert paid_order["paid_at"].endswith("Z")

    # Owner views the exact same order
    owner_orders_res = client.get(f"/api/orders/?shop_id=1", headers=owner_headers)
    assert owner_orders_res.status_code == 200
    owner_orders = owner_orders_res.json()
    matched_owner_order = next((o for o in owner_orders if o["id"] == order_id), None)
    assert matched_owner_order is not None
    assert matched_owner_order["id"] == order_id
    assert matched_owner_order["payment_status"] == "paid"
    assert matched_owner_order["customer_phone"] == customer_phone

    # 7. Check stock deduction & single sales history record added
    db = SessionLocal()
    try:
        updated_product = db.query(Product).filter(Product.id == product_id).first()
        assert updated_product.stock == initial_stock - 2.0
        
        sales_count_after = db.query(SalesHistory).filter(SalesHistory.product_id == product_id).count()
        assert sales_count_after == sales_count_before + 1
    finally:
        db.close()

    # 8. Test duplicate payment attempt (Safety check)
    dup_res = client.post("/api/payments/verify-razorpay-signature", json=verify_payload, headers=cust_headers)
    assert dup_res.status_code == 200
    assert "already paid" in dup_res.json()["message"].lower()

    # Verify stock remained initial_stock - 2.0 (not double deducted)
    db = SessionLocal()
    try:
        updated_product = db.query(Product).filter(Product.id == product_id).first()
        assert updated_product.stock == initial_stock - 2.0
    finally:
        db.close()

    # 9. Test Chat History persistence & retrieval
    msg_payload = {
        "shop_id": 1,
        "sender_role": "customer",
        "message": "Hello shop owner, is this item available?"
    }
    chat_post_res = client.post("/api/chat/messages", json=msg_payload, headers=cust_headers)
    assert chat_post_res.status_code == 200, chat_post_res.text
    chat_msg = chat_post_res.json()
    assert chat_msg["message"] == msg_payload["message"]
    assert chat_msg["created_at"].endswith("Z")

    chat_get_res = client.get("/api/chat/messages?shop_id=1", headers=cust_headers)
    assert chat_get_res.status_code == 200
    msgs = chat_get_res.json()
    assert len(msgs) >= 1
    assert msgs[-1]["message"] == msg_payload["message"]

    # 10. Test Owner Order Deletion & Authorization Safety
    new_order_res = client.post("/api/orders/create-draft", json=draft_payload, headers=cust_headers)
    assert new_order_res.status_code == 200
    to_delete_id = new_order_res.json()["id"]

    # Unauthorized delete attempt by customer
    cust_del_res = client.delete(f"/api/orders/{to_delete_id}", headers=cust_headers)
    assert cust_del_res.status_code == 403

    # 11. Test Shop-specific product catalog filtering
    catalog_res1 = client.get("/api/products/?shop_id=1")
    assert catalog_res1.status_code == 200
    cat1_items = catalog_res1.json()
    assert all(p["shop_id"] == 1 for p in cat1_items)

    catalog_res2 = client.get("/api/products/?shop_id=2")
    assert catalog_res2.status_code == 200
    cat2_items = catalog_res2.json()
    assert all(p["shop_id"] == 2 for p in cat2_items)

    # 12. Test draft order creation with edited items & recalculated total
    if len(cat1_items) >= 2:
        item1 = cat1_items[0]
        item2 = cat1_items[1]
        edited_draft_payload = {
            "shop_id": 1,
            "items": [
                {
                    "product_id": item1["id"],
                    "quantity": 3.0,
                    "unit": item1["unit"],
                    "price_at_order": item1["price"]
                },
                {
                    "product_id": item2["id"],
                    "quantity": 2.0,
                    "unit": item2["unit"],
                    "price_at_order": item2["price"]
                }
            ],
            "notes": "Edited shopping list with 2 items"
        }
        edited_res = client.post("/api/orders/create-draft", json=edited_draft_payload, headers=cust_headers)
        assert edited_res.status_code == 200
        edited_order = edited_res.json()
        expected_total = (3.0 * item1["price"]) + (2.0 * item2["price"])
        assert abs(edited_order["total_amount"] - expected_total) < 0.01
        assert len(edited_order["items"]) == 2

def test_payment_webhook_and_demo_flow():
    db = SessionLocal()
    try:
        customer_user = db.query(User).filter(User.role == 'customer').first()
        customer_phone = customer_user.phone_number
        product = db.query(Product).filter(Product.shop_id == 1, Product.stock > 5).first()
        product_id = product.id
    finally:
        db.close()

    cust_res = client.post("/api/auth/login", json={"phone_number": customer_phone, "role": "customer", "firebase_id_token": "mock_token"})
    cust_token = cust_res.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # 1. Create order
    create_res = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": product_id, "quantity": 1.0, "unit": "kg", "price_at_order": 20.0}],
        "notes": "Webhook test order"
    }, headers=cust_headers)
    assert create_res.status_code == 200
    order_id = create_res.json()["id"]

    # 2. Initiate Razorpay order
    rzp_res = client.post(f"/api/payments/create-razorpay-order/{order_id}", headers=cust_headers)
    assert rzp_res.status_code == 200
    rzp_order_id = rzp_res.json()["razorpay_order_id"]

    # 3. Simulate Webhook
    webhook_res = client.post("/api/payments/webhook", json={
        "event": "order.paid",
        "order_id": order_id,
        "razorpay_order_id": rzp_order_id,
        "payload": {
            "order": {"entity": {"id": rzp_order_id}},
            "payment": {"entity": {"id": "pay_test_webhook_123"}}
        }
    }, headers={"x-razorpay-signature": "sandbox_bypass"})
    assert webhook_res.status_code == 200
    assert webhook_res.json()["status"] == "success"

    # Verify order is now paid
    order_chk = client.get(f"/api/orders/{order_id}", headers=cust_headers).json()
    assert order_chk["status"] == "paid"
    assert order_chk["payment_status"] == "paid"

def test_shop_specific_sequential_order_numbers():
    db = SessionLocal()
    try:
        customer_user = db.query(User).filter(User.role == 'customer').first()
        customer_phone = customer_user.phone_number
        prod1 = db.query(Product).filter(Product.shop_id == 1).first()
        prod2 = db.query(Product).filter(Product.shop_id == 2).first()
        assert prod1 is not None and prod2 is not None
    finally:
        db.close()

    cust_res = client.post("/api/auth/login", json={"phone_number": customer_phone, "role": "customer", "firebase_id_token": "mock_token"})
    cust_token = cust_res.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # Order 1 for Shop 1
    o1_s1 = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod1.id, "quantity": 1.0, "unit": prod1.unit, "price_at_order": prod1.price}],
        "notes": "Order 1 for Shop 1"
    }, headers=cust_headers).json()

    # Order 2 for Shop 1
    o2_s1 = client.post("/api/orders/create-draft", json={
        "shop_id": 1,
        "items": [{"product_id": prod1.id, "quantity": 1.0, "unit": prod1.unit, "price_at_order": prod1.price}],
        "notes": "Order 2 for Shop 1"
    }, headers=cust_headers).json()

    # Order 1 for Shop 2 (starts independently at #1)
    o1_s2 = client.post("/api/orders/create-draft", json={
        "shop_id": 2,
        "items": [{"product_id": prod2.id, "quantity": 1.0, "unit": prod2.unit, "price_at_order": prod2.price}],
        "notes": "Order 1 for Shop 2"
    }, headers=cust_headers).json()

    assert o2_s1["order_number"] == o1_s1["order_number"] + 1
    assert o1_s2["order_number"] >= 1

if __name__ == "__main__":
    pytest.main([__file__])




