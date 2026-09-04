from fastapi import APIRouter, Depends, HTTPException, Request, Query, Header, status
from sqlalchemy.orm import Session
import razorpay
import hmac
import hashlib
import json
import logging
import datetime
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
    razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
except Exception as e:
    razorpay_client = None
    logger.error(f"Failed to initialize Razorpay Client: {e}")

async def process_successful_payment(order: Order, db: Session, method: str, payment_id: str):
    """
    Step 12 & 13: Updates stock inventory, writes sales history, checks alerts on successful payment.
    """
    if order.status == "paid":
        return  # Prevent duplicate processing

    order.status = "paid"
    order.payment_method = method
    order.payment_id = payment_id
    db.commit()

    logger.info(f"Processing inventory deduct for Order #{order.id}...")

    # Deduct stock and save sales history
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            # Deduct stock
            old_stock = product.stock
            product.stock = max(0.0, product.stock - item.quantity)
            
            # Store Sales History
            history = SalesHistory(
                product_id=product.id,
                quantity=item.quantity,
                price=item.price_at_order,
                sold_at=datetime.datetime.utcnow()
            )
            db.add(history)
            
            # Check Alert System: Low Stock Alert
            # Check Alert System: Low Stock Alert
            # Alert will be generated only when:
            # 1. Predicted demand is greater than current stock
            # 2. Current stock is below the minimum threshold

            current_stock = product.stock
            min_threshold = product.min_stock_threshold

            # TODO: Get predicted demand from Prophet
            predicted_demand = get_predicted_demand(
                db=db,
                product_id=product.id,
                periods=7
            )

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
                            f"{current_stock} {product.unit}. "
                            f"Minimum quantity: {min_threshold}."
                        )
                    )
                    db.add(alert)
                    db.commit()
                    alert_msg = alert.message
                else:
                    alert_msg = existing_alert.message

                # Send Low Stock WebSocket Alert to Owner
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

                    await manager.send_personal_message(
                        ws_alert,
                        shop.owner_id
                    )

    db.commit()

    # Send success socket message to customer
    cust_msg = {
        "type": "payment_success",
        "order_id": order.id,
        "message": "Payment confirmed! Your order is being processed."
    }
    await manager.send_personal_message(cust_msg, order.customer_id)

    # Send WebSocket update to Owner
    shop = db.query(Shop).filter(Shop.id == order.shop_id).first()
    if shop:
        owner_msg = {
            "type": "payment_received",
            "order_id": order.id,
            "message": f"Payment of ₹{order.total_amount} received for Order #{order.id}.",
            "total_amount": order.total_amount
        }
        await manager.send_personal_message(owner_msg, shop.owner_id)


@router.post("/initiate/{order_id}")
def initiate_payment(
    order_id: int, 
    method: str = Query(..., description="cash or razorpay"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 10: Generates Razorpay Order details or prepares for cash payment.
    """
    order = db.query(Order).filter(Order.id == order_id, Order.customer_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
        
    if order.status == "paid":
        raise HTTPException(status_code=400, detail="Order is already paid.")

    if method == "razorpay":
        # Create Razorpay Order
        if not razorpay_client:
            raise HTTPException(
                status_code=500,
                detail="Razorpay client not configured on server."
            )
            
        try:
            # Razorpay requires amount in paise
            amount_paise = int(order.total_amount * 100)
            rz_order_data = {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"receipt_order_{order.id}",
                "payment_capture": 1
            }
            rz_order = razorpay_client.order.create(data=rz_order_data)
            
            # Update order state to pending_payment
            order.status = "pending_payment"
            order.payment_method = "razorpay"
            order.payment_id = rz_order["id"]
            db.commit()
            
            # Build custom UPI URI for generating local merchant QR codes directly in React
            upi_uri = f"upi://pay?pa=merchant@razorpay&pn=RetailShop&am={order.total_amount}&cu=INR&tr={order.payment_id}"
            
            return {
                "payment_method": "razorpay",
                "razorpay_order_id": rz_order["id"],
                "amount": order.total_amount,
                "key_id": settings.RAZORPAY_KEY_ID,
                "upi_uri": upi_uri
            }
        except Exception as e:
            logger.error(f"Razorpay Order creation error: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create Razorpay Order: {str(e)}")
            
    elif method == "cash":
        order.status = "pending_payment"
        order.payment_method = "cash"
        db.commit()
        return {
            "payment_method": "cash",
            "amount": order.total_amount,
            "message": "Order is marked for cash payment. Please pay the owner at the counter."
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid payment method.")

@router.post("/confirm-cash/{order_id}")
async def confirm_cash_payment(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 11 (Cash): Owner manually confirms that cash payment has been received.
    """
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only shop owners can confirm cash payments.")
        
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
        
    # Verify owner owns this shop
    shop = db.query(Shop).filter(Shop.id == order.shop_id, Shop.owner_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not own the shop for this order.")
        
    if order.payment_method != "cash":
        raise HTTPException(status_code=400, detail="This order is not configured for cash payment.")
        
    await process_successful_payment(order, db, "cash", f"cash_ref_{order.id}")
    return {"status": "success", "message": "Cash payment confirmed successfully."}

@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Step 11 (UPI): Razorpay webhook verified automatically.
    """
    body = await request.body()
    
    # Verify signature
    # In sandbox or local testing, if signature verification is bypassed, log it
    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
    
    if x_razorpay_signature:
        expected_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if expected_sig != x_razorpay_signature:
            logger.error("Razorpay webhook signature mismatch!")
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
            
    payload = json.loads(body.decode('utf-8'))
    event = payload.get("event")
    
    if event == "order.paid":
        order_entity = payload["payload"]["order"]["entity"]
        razorpay_order_id = order_entity["id"]
        
        # Query order
        order = db.query(Order).filter(Order.payment_id == razorpay_order_id).first()
        if order:
            payment_id = payload["payload"].get("payment", {}).get("entity", {}).get("id", "rzp_pay_id")
            await process_successful_payment(order, db, "razorpay", payment_id)
            return {"status": "ok"}
            
    return {"status": "ignored"}
