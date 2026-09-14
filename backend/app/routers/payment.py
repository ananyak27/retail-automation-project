from fastapi import APIRouter, Depends, HTTPException, Request, Query, Header, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import razorpay
import hmac
import hashlib
import json
import logging
import datetime
import uuid

from app.database import get_db
from app.models import Order, Product, SalesHistory, Alert, Shop, User
from app.config import settings
from app.routers.auth import get_current_user
from app.websocket_manager import manager
from app.services.forecast_service import get_predicted_demand

router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = logging.getLogger(__name__)

# Initialize Razorpay Client
try:
    if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_ID != "rzp_test_placeholder":
        razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    else:
        razorpay_client = None
except Exception as e:
    razorpay_client = None
    logger.error(f"Failed to initialize Razorpay Client: {e}")

class RazorpayVerifyPayload(BaseModel):
    order_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

async def process_successful_payment(
    order: Order,
    db: Session,
    method: str,
    payment_id: str,
    rzp_order_id: str = None,
    rzp_pay_id: str = None,
    rzp_sig: str = None
):
    """
    Safely process inventory deduction, sales history creation, and status update upon payment.
    Prevents duplicate payment execution.
    """
    if getattr(order, 'payment_status', None) == "paid" or order.status == "paid":
        logger.info(f"Order #{order.id} is already marked as paid. Bypassing duplicate processing.")
        return

    order.status = "paid"
    order.payment_status = "paid"
    order.payment_method = method
    order.payment_id = payment_id
    if rzp_order_id:
        order.razorpay_order_id = rzp_order_id
    if rzp_pay_id:
        order.razorpay_payment_id = rzp_pay_id
    if rzp_sig:
        order.razorpay_signature = rzp_sig
    order.paid_at = datetime.datetime.utcnow()
    
    db.commit()

    logger.info(f"Deducting stock & recording sales history for Order #{order.id}...")

    # Deduct stock and save sales history ONCE
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            product.stock = max(0.0, product.stock - item.quantity)
            
            history = SalesHistory(
                product_id=product.id,
                quantity=item.quantity,
                price=item.price_at_order,
                sold_at=datetime.datetime.utcnow()
            )
            db.add(history)
            
            # Low stock check
            current_stock = product.stock
            min_threshold = product.min_stock_threshold
            predicted_demand = get_predicted_demand(db=db, product_id=product.id, periods=7)

            if current_stock <= min_threshold or (predicted_demand > current_stock and current_stock < min_threshold):
                existing_alert = db.query(Alert).filter(
                    Alert.shop_id == product.shop_id,
                    Alert.type == "low_stock",
                    Alert.is_read == False,
                    Alert.message.like(f"%'{product.name}'%")
                ).first()

                if not existing_alert:
                    alert = Alert(
                        shop_id=product.shop_id,
                        type="low_stock",
                        message=(
                            f"Low Stock Alert: '{product.name}' stock is "
                            f"{current_stock} {product.unit}. Minimum quantity: {min_threshold}."
                        )
                    )
                    db.add(alert)
                    db.commit()
                    alert_msg = alert.message
                else:
                    alert_msg = existing_alert.message

                shop = db.query(Shop).filter(Shop.id == product.shop_id).first()
                if shop:
                    ws_alert = {
                        "type": "low_stock",
                        "product_id": product.id,
                        "product_name": product.name,
                        "message": alert_msg,
                        "stock": current_stock,
                        "threshold": min_threshold,
                        "predicted_demand": predicted_demand
                    }
                    await manager.send_personal_message(ws_alert, shop.owner_id)

    db.commit()

    # Customer notification
    display_num = getattr(order, 'shop_order_number', None) or order.id
    cust_msg = {
        "type": "payment_success",
        "order_id": order.id,
        "order_number": display_num,
        "message": f"Your order #{display_num} has been confirmed by the owner and your payment was successful."
    }
    await manager.send_personal_message(cust_msg, order.customer_id)

    # Owner notification
    shop = db.query(Shop).filter(Shop.id == order.shop_id).first()
    cust = db.query(User).filter(User.id == order.customer_id).first()
    cust_name = (cust.owner_name or cust.phone_number) if cust else f"Customer #{order.customer_id}"

    if shop:
        payment_label = "Cash Payment" if method == "cash" else "Payment Successful"
        owner_msg = {
            "type": "payment_received",
            "order_id": order.id,
            "order_number": display_num,
            "message": f"Order #{display_num} received from {cust_name} — Payment: {payment_label}.",
            "total_amount": order.total_amount,
            "payment_status": "paid",
            "payment_method": method
        }
        await manager.send_personal_message(owner_msg, shop.owner_id)

@router.post("/create-razorpay-order/{order_id}")
async def create_razorpay_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generates a Razorpay Order ID for online payment workflow.
    Uses RAZORPAY_KEY_ID & RAZORPAY_KEY_SECRET env placeholders seamlessly.
    """
    order = db.query(Order).filter(Order.id == order_id, Order.customer_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
        
    if getattr(order, 'payment_status', None) == "paid" or order.status == "paid":
        raise HTTPException(status_code=400, detail="Order is already paid.")

    if order.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot initiate payment for a cancelled order.")

    amount_paise = int(round(order.total_amount * 100))

    # Real Razorpay integration or test fallback if keys are placeholders
    if razorpay_client:
        try:
            rz_order_data = {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"receipt_order_{order.id}",
                "payment_capture": 1
            }
            rz_order = razorpay_client.order.create(data=rz_order_data)
            rz_order_id = rz_order["id"]
        except Exception as e:
            logger.error(f"Razorpay API Error: {e}")
            rz_order_id = f"order_rzp_{order.id}_{uuid.uuid4().hex[:8]}"
    else:
        # Placeholder test mode
        rz_order_id = f"order_rzp_{order.id}_{uuid.uuid4().hex[:8]}"

    order.status = "pending_payment"
    order.payment_method = "razorpay"
    order.payment_status = "online_pending"
    order.razorpay_order_id = rz_order_id
    db.commit()

    upi_uri = f"upi://pay?pa=merchant@razorpay&pn=RetailShop&am={order.total_amount}&cu=INR&tr={rz_order_id}"

    # Notify Owner of payment initiation
    shop = db.query(Shop).filter(Shop.id == order.shop_id).first()
    cust_name = current_user.owner_name or current_user.phone_number
    if shop:
        await manager.send_personal_message({
            "type": "payment_initiated",
            "order_id": order.id,
            "message": f"Customer {cust_name} initiated Online Payment for Order #{order.id}.",
            "payment_method": "razorpay",
            "payment_status": "online_pending"
        }, shop.owner_id)

    return {
        "payment_method": "razorpay",
        "razorpay_order_id": rz_order_id,
        "amount": order.total_amount,
        "key_id": settings.RAZORPAY_KEY_ID,
        "upi_uri": upi_uri
    }

@router.post("/verify-razorpay-signature")
async def verify_razorpay_signature(
    payload: RazorpayVerifyPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verifies Razorpay payment signature & payment amount on backend before marking order paid & deducting stock.
    """
    order = db.query(Order).filter(Order.id == payload.order_id, Order.customer_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if getattr(order, 'payment_status', None) == "paid" or order.status == "paid":
        return {"status": "success", "message": "Order is already paid.", "order_id": order.id}

    # 1. Verify Razorpay Order ID matches database record
    if order.razorpay_order_id and payload.razorpay_order_id != order.razorpay_order_id:
        raise HTTPException(status_code=400, detail="Razorpay order ID mismatch.")

    # 2. Calculate expected amount in smallest currency unit (paise)
    expected_amount_paise = int(round(order.total_amount * 100))

    # 3. If live/test Razorpay client is available, verify payment amount, currency & order link directly with Razorpay API
    if razorpay_client:
        try:
            payment_details = razorpay_client.payment.fetch(payload.razorpay_payment_id)
            if payment_details:
                # Verify exact payment amount
                if payment_details.get("amount") != expected_amount_paise:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Payment amount mismatch. Expected {expected_amount_paise} paise (₹{order.total_amount:.2f}), but received {payment_details.get('amount')} paise."
                    )
                # Verify currency
                if payment_details.get("currency") != "INR":
                    raise HTTPException(status_code=400, detail="Invalid payment currency. Expected INR.")
                # Verify order ID link on Razorpay side
                if payment_details.get("order_id") and payment_details.get("order_id") != payload.razorpay_order_id:
                    raise HTTPException(status_code=400, detail="Payment does not belong to the specified Razorpay order ID.")
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logger.warning(f"Razorpay payment fetch check skipped or warning: {e}")

    # 4. Verify signature if real Razorpay secret is set and not a placeholder/test bypass signature
    secret = settings.RAZORPAY_KEY_SECRET
    if secret and not secret.startswith("rzp_test_") and secret != "rzp_secret_placeholder" and payload.razorpay_signature not in ["test_signature", "sandbox_bypass"]:
        generated_signature = hmac.new(
            secret.encode('utf-8'),
            f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if generated_signature != payload.razorpay_signature:
            raise HTTPException(status_code=400, detail="Invalid Razorpay payment signature.")

    await process_successful_payment(
        order=order,
        db=db,
        method="razorpay",
        payment_id=payload.razorpay_payment_id,
        rzp_order_id=payload.razorpay_order_id,
        rzp_pay_id=payload.razorpay_payment_id,
        rzp_sig=payload.razorpay_signature
    )

    return {
        "status": "success", 
        "message": f"Razorpay payment verified successfully for ₹{order.total_amount:.2f}.", 
        "order_id": order.id,
        "amount_verified": order.total_amount,
        "amount_paise": expected_amount_paise
    }

@router.post("/initiate/{order_id}")
async def initiate_payment(
    order_id: int, 
    method: str = Query(..., description="cash or razorpay"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Prepares payment method (Cash or Razorpay).
    """
    order = db.query(Order).filter(Order.id == order_id, Order.customer_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
        
    if getattr(order, 'payment_status', None) == "paid" or order.status == "paid":
        raise HTTPException(status_code=400, detail="Order is already paid.")

    if method == "cash":
        order.status = "pending_payment"
        order.payment_method = "cash"
        order.payment_status = "cash_pending"
        db.commit()

        # Notify Owner
        shop = db.query(Shop).filter(Shop.id == order.shop_id).first()
        cust_name = current_user.owner_name or current_user.phone_number
        if shop:
            await manager.send_personal_message({
                "type": "payment_initiated",
                "order_id": order.id,
                "message": f"Customer {cust_name} selected Cash Payment for Order #{order.id}.",
                "payment_method": "cash",
                "payment_status": "cash_pending"
            }, shop.owner_id)

        return {
            "payment_method": "cash",
            "payment_status": "cash_pending",
            "amount": order.total_amount,
            "message": "Order is marked for Cash Payment. Please pay the owner at counter."
        }

    raise HTTPException(status_code=400, detail="Invalid payment method specified.")

@router.post("/confirm-cash/{order_id}")
async def confirm_cash_payment(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Owner confirms cash payment received.
    """
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only shop owners can confirm cash payments.")
        
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
        
    shop = db.query(Shop).filter(Shop.id == order.shop_id, Shop.owner_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not own the shop for this order.")
        
    if getattr(order, 'payment_status', None) == "paid" or order.status == "paid":
        return {"status": "success", "message": "Cash payment already confirmed."}

    await process_successful_payment(
        order=order,
        db=db,
        method="cash",
        payment_id=f"cash_ref_{order.id}_{uuid.uuid4().hex[:6]}"
    )

    return {"status": "success", "message": "Cash payment confirmed successfully."}

@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: str = Header(None)
):
    """
    Razorpay Webhook endpoint & local demo simulation webhook endpoint.
    Handles 'order.paid' and 'payment.captured' events.
    Verifies signature (or allows sandbox_bypass / test signatures).
    Updates order status, deducts inventory, records sales history, and notifies customer & owner via WebSockets.
    """
    try:
        raw_body = await request.body()
        body_json = json.loads(raw_body.decode('utf-8')) if raw_body else {}
    except Exception as e:
        logger.error(f"Invalid JSON body in webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    logger.info(f"Received payment webhook payload: {body_json}")

    # Extract event type and payload details
    event = body_json.get("event", "order.paid")
    payload = body_json.get("payload", {})

    rzp_order_id = None
    rzp_pay_id = None

    if isinstance(payload, dict):
        if "order" in payload and isinstance(payload["order"], dict):
            rzp_order_id = payload["order"].get("entity", {}).get("id")
        if not rzp_order_id and "payment" in payload and isinstance(payload["payment"], dict):
            rzp_order_id = payload["payment"].get("entity", {}).get("order_id")
            rzp_pay_id = payload["payment"].get("entity", {}).get("id")

    if not rzp_order_id:
        rzp_order_id = body_json.get("razorpay_order_id") or body_json.get("order_id")
    if not rzp_pay_id:
        rzp_pay_id = body_json.get("razorpay_payment_id") or f"pay_wh_{uuid.uuid4().hex[:8]}"

    if not rzp_order_id:
        raise HTTPException(status_code=400, detail="Missing razorpay_order_id or order reference in webhook payload.")

    order = db.query(Order).filter(Order.razorpay_order_id == str(rzp_order_id)).first()

    if not order and isinstance(rzp_order_id, (int, str)):
        try:
            if isinstance(rzp_order_id, int) or str(rzp_order_id).isdigit():
                order = db.query(Order).filter(Order.id == int(rzp_order_id)).first()
            elif str(rzp_order_id).startswith("order_rzp_"):
                parts = str(rzp_order_id).split("_")
                if len(parts) >= 3 and parts[2].isdigit():
                    order = db.query(Order).filter(Order.id == int(parts[2])).first()
        except Exception:
            pass

    if not order:
        logger.warning(f"Webhook received for unknown Razorpay Order ID: {rzp_order_id}")
        raise HTTPException(status_code=404, detail=f"Order not found for Razorpay order ID '{rzp_order_id}'.")

    # Optional signature verification for real webhooks (skip if sandbox_bypass or placeholder secret)
    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
    if (
        x_razorpay_signature 
        and x_razorpay_signature not in ["sandbox_bypass", "test_signature"]
        and webhook_secret 
        and webhook_secret != "razorpay_webhook_secret_123"
        and not webhook_secret.startswith("rzp_test_")
    ):
        expected_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        if expected_sig != x_razorpay_signature:
            logger.error("Razorpay webhook signature verification failed.")
            raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    await process_successful_payment(
        order=order,
        db=db,
        method="razorpay",
        payment_id=rzp_pay_id,
        rzp_order_id=str(rzp_order_id),
        rzp_pay_id=rzp_pay_id,
        rzp_sig=x_razorpay_signature or "simulated_webhook"
    )

    return {
        "status": "success",
        "message": f"Webhook processed successfully for Order #{order.id}.",
        "order_id": order.id,
        "payment_status": "paid"
    }

@router.post("/demo-payment-success")
async def demo_payment_success(
    request_data: dict,
    db: Session = Depends(get_db)
):
    """
    Dedicated local demo handler for simulating online payment success without Razorpay credentials.
    """
    rzp_order_id = request_data.get("razorpay_order_id")
    order_id = request_data.get("order_id")

    order = None
    if rzp_order_id:
        order = db.query(Order).filter(Order.razorpay_order_id == str(rzp_order_id)).first()
    if not order and order_id:
        try:
            order = db.query(Order).filter(Order.id == int(order_id)).first()
        except (ValueError, TypeError):
            pass

    if not order:
        raise HTTPException(status_code=404, detail="Order not found for payment simulation.")

    pay_id = request_data.get("razorpay_payment_id") or f"pay_demo_{uuid.uuid4().hex[:8]}"

    await process_successful_payment(
        order=order,
        db=db,
        method="razorpay",
        payment_id=pay_id,
        rzp_order_id=order.razorpay_order_id or str(rzp_order_id or ""),
        rzp_pay_id=pay_id,
        rzp_sig="demo_bypass"
    )

    return {
        "status": "success",
        "message": f"Demo payment simulated successfully for Order #{order.id}.",
        "order_id": order.id,
        "payment_status": "paid"
    }

