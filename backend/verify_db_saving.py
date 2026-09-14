import os
import sqlite3
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def test_full_database_persistence():
    print(f"Connecting to target database: {settings.DATABASE_URL}")
    
    # 1. Clean up test numbers in retail_automation.db if present
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    test_cust_phone = "+917000011111"
    test_owner_phone = "+918000011111"
    unreg_phone = "+917000099999"
    
    cursor.execute("DELETE FROM shops WHERE owner_id IN (SELECT id FROM users WHERE phone_number IN (?, ?))", (test_cust_phone, test_owner_phone))
    cursor.execute("DELETE FROM users WHERE phone_number IN (?, ?)", (test_cust_phone, test_owner_phone))
    conn.commit()
    conn.close()

    # 2. Test Customer Registration (New Number) -> Expect SUCCESS
    reg_res = client.post("/api/auth/register-customer", json={
        "phone_number": test_cust_phone,
        "firebase_id_token": f"mock_token_{test_cust_phone}",
        "customer_name": "Verified Customer"
    })
    print("Customer Registration Response:", reg_res.status_code, reg_res.json())
    assert reg_res.status_code == 200
    assert reg_res.json()["phone_number"] == test_cust_phone
    assert reg_res.json()["role"] == "customer"

    # Verify directly in SQLite retail_automation.db file
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, phone_number, role, firebase_uid, created_at FROM users WHERE phone_number = ?", (test_cust_phone,))
    row = cursor.fetchone()
    print("Direct SQLite Row Query Result:", row)
    assert row is not None
    assert row[1] == test_cust_phone
    assert row[2] == "customer"
    conn.close()

    # 3. Test Duplicate Registration (Same Customer Number) -> Expect 400 Bad Request
    dup_reg = client.post("/api/auth/register-customer", json={
        "phone_number": test_cust_phone,
        "firebase_id_token": f"mock_token_{test_cust_phone}",
        "customer_name": "Duplicate Customer"
    })
    print("Duplicate Registration Response:", dup_reg.status_code, dup_reg.json())
    assert dup_reg.status_code == 400
    assert "already exists" in dup_reg.json()["detail"].lower()

    # 4. Test Customer Login (Existing Customer Number) -> Expect 200 SUCCESS
    login_res = client.post("/api/auth/login", json={
        "phone_number": test_cust_phone,
        "firebase_id_token": f"mock_token_{test_cust_phone}",
        "role": "customer"
    })
    print("Customer Login Response:", login_res.status_code, login_res.json())
    assert login_res.status_code == 200
    assert login_res.json()["phone_number"] == test_cust_phone

    # 5. Test Login with Unregistered Number -> Expect 404 Not Found
    unreg_login = client.post("/api/auth/login", json={
        "phone_number": unreg_phone,
        "firebase_id_token": f"mock_token_{unreg_phone}",
        "role": "customer"
    })
    print("Unregistered Login Response:", unreg_login.status_code, unreg_login.json())
    assert unreg_login.status_code == 404
    assert "not available" in unreg_login.json()["detail"].lower()

    # 6. Test Owner Registration (New Owner Number) -> Expect 200 SUCCESS
    owner_reg = client.post("/api/auth/register-owner", json={
        "owner_name": "Verified Owner",
        "phone_number": test_owner_phone,
        "firebase_id_token": f"mock_token_{test_owner_phone}",
        "shop_name": "Verified Mart",
        "shop_address": "789 Main Blvd",
        "bank_account_holder_name": "Verified Owner",
        "bank_name": "Axis Bank",
        "account_number": "112233445566",
        "ifsc_code": "UTIB0001234"
    })
    print("Owner Registration Response:", owner_reg.status_code, owner_reg.json())
    assert owner_reg.status_code == 200
    assert owner_reg.json()["phone_number"] == test_owner_phone
    assert owner_reg.json()["role"] == "owner"

    # Verify Owner and Shop directly in SQLite retail_automation.db file
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, phone_number, role FROM users WHERE phone_number = ?", (test_owner_phone,))
    owner_row = cursor.fetchone()
    assert owner_row is not None
    assert owner_row[1] == test_owner_phone
    assert owner_row[2] == "owner"

    cursor.execute("SELECT id, name, address, owner_id FROM shops WHERE owner_id = ?", (owner_row[0],))
    shop_row = cursor.fetchone()
    assert shop_row is not None
    assert shop_row[1] == "Verified Mart"
    conn.close()

    print("\n--- ALL VERIFICATION TESTS PASSED SUCCESSFULLY ON retail_automation.db ---")

if __name__ == "__main__":
    test_full_database_persistence()

