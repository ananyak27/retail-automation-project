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
from typing import Optional

from app.database import get_db
from app.models import Order, Product, SalesHistory, Alert, Shop, User
from app.config import settings
from app.routers.auth import get_current_user
from app.websocket_manager import manager
from app.services.forecast_service import get_predicted_demand

router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Razorpay Client Initialization
# ---------------------------------------------------------------------------
_PLACEHOLDER_KEY_IDS = {"rzp_test_placeholder", "rzp_test_placeholder_id", ""}
_PLACEHOLDER_SECRETS = {"rzp_test_placeholder_secret", "rzp_secret_placeholder", ""}

def _is_real_razorpay_configured() -> bool:
    """Returns True only when real (non-placeholder) Razorpay credentials are set."""
    key = settings.RAZORPAY_KEY_ID or ""
    secret = settings.RAZORPAY_KEY_SECRET or ""
    return (
        bool(key)
        and key not in _PLACEHOLDER_KEY_IDS
        and not key == "rzp_test_placeholder_id"
        and bool(secret)
        and secret not in _PLACEHOLDER_SECRETS
    )

try:
    if _is_real_razorpay_configured():
        razorpay_client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        logger.info("Razorpay client initialized with configured credentials.")
    else:
        razorpay_client = None
        logger.info(
            "Razorpay client not initialized: placeholder credentials detected. "
            "Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env to enable live/test mode."
        )
except Exception as e:
    razorpay_client = None
    logger.error(f"Failed to initialize Razorpay Client: {e}")

# ---------------------------------------------------------------------------
# Helper: is environment production?
# ---------------------------------------------------------------------------
def _is_production() -> bool:
    return getattr(settings, "ENVIRONMENT", "development").lower() not in (
        "development", "dev", "local", "test"
    )

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------
class RazorpayVerifyPayload(BaseModel):
    order_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

# ---------------------------------------------------------------------------
# Core Payment Processor (shared by all payment methods)
# ---------------------------------------------------------------------------
async def process_successful_payment(
    order: Order,
    db: Session,
    method: str,
    payment_id: str,
    rzp_order_id: str = None,
    rzp_pay_id: str = None,
    rzp_sig: str = None,
):
    """
    Atomically updates order status, deducts inventory, records sales history,
    creates low-stock alerts, and sends WebSocket notifications.

    Idempotent: silently returns if the order is already marked paid.
    """
    # 0. Acquire row-level lock on the Order row to serialize concurrent payment confirmations
    # (e.g. race condition between customer checkout verification and background webhook delivery)
    locked_order = (
        db.query(Order)
        .filter(Order.id == order.id)
        .with_for_update()
        .first()
    )
    if not locked_order:
        logger.warning(f"Order #{order.id} not found during payment processing.")
        return

    if getattr(locked_order, "payment_status", None) == "paid" or locked_order.status == "paid":
        logger.info(
            f"Order #{locked_order.id} is already marked as paid. Skipping duplicate processing."
        )
        return

    # 1. Lock and verify stock sufficiency for ALL items before touching anything
    for item in locked_order.items:
        product = (
            db.query(Product)
            .filter(Product.id == item.product_id)
            .with_for_update()
            .first()
        )
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product ID {item.product_id} no longer exists.",
            )
        if product.stock < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot complete payment for Order #{locked_order.id}: "
                    f"Insufficient stock for '{product.name}'. "
                    f"Available: {product.stock} {product.unit}, "
                    f"Required: {item.quantity} {product.unit}."
                ),
            )

    # 2. Mark order as paid
    locked_order.status = "paid"
    locked_order.payment_status = "paid"
    locked_order.payment_method = method
    locked_order.payment_id = payment_id
    if rzp_order_id:
        locked_order.razorpay_order_id = rzp_order_id
    if rzp_pay_id:
        locked_order.razorpay_payment_id = rzp_pay_id
    if rzp_sig:
        locked_order.razorpay_signature = rzp_sig
    locked_order.paid_at = datetime.datetime.utcnow()

    logger.info(f"Deducting stock & recording sales history for Order #{locked_order.id}…")

    # 3. Deduct stock and record sales history; collect alerts to send after commit
    low_stock_alerts_to_send = []

    for item in locked_order.items:
        product = (
            db.query(Product).filter(Product.id == item.product_id).first()
        )
        if not product:
            continue

        product.stock = max(0.0, product.stock - item.quantity)

        history = SalesHistory(
            shop_id=locked_order.shop_id,
            product_id=product.id,
            quantity=item.quantity,
            price=item.price_at_order,
            sold_at=locked_order.paid_at or datetime.datetime.utcnow(),
        )
        db.add(history)

        # Evaluate low-stock condition BEFORE commit (using updated value)
        current_stock = product.stock
        min_threshold = product.min_stock_threshold
        predicted_demand = get_predicted_demand(
            db=db, product_id=product.id, periods=7
        )

        needs_alert = current_stock <= min_threshold or (
            predicted_demand > current_stock and current_stock < min_threshold
        )

        if needs_alert:
            existing_alert = (
                db.query(Alert)
                .filter(
                    Alert.shop_id == product.shop_id,
                    Alert.type == "low_stock",
                    Alert.is_read == False,
                    Alert.message.like(f"%'{product.name}'%"),
                )
                .first()
            )

            if not existing_alert:
                alert = Alert(
                    shop_id=product.shop_id,
                    type="low_stock",
                    message=(
                        f"Low Stock Alert: '{product.name}' stock is "
                        f"{current_stock} {product.unit}. "
                        f"Minimum quantity: {min_threshold}."
                    ),
                )
                db.add(alert)
                low_stock_alerts_to_send.append(
                    (product.shop_id, product.id, product.name, current_stock, min_threshold, predicted_demand, None)
                )
            else:
                low_stock_alerts_to_send.append(
                    (product.shop_id, product.id, product.name, current_stock, min_threshold, predicted_demand, existing_alert.message)
                )

    # 4. Single commit for everything above (order status + stock + sales history + new alerts)
    db.commit()

    # 5. Send WebSocket low-stock alerts after commit (safe: DB is consistent now)
    for (shop_id, prod_id, prod_name, stock, threshold, pred_demand, existing_msg) in low_stock_alerts_to_send:
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if shop:
            # Fetch the newly committed alert message if we created it
            if existing_msg is None:
                new_alert = (
                    db.query(Alert)
                    .filter(
                        Alert.shop_id == shop_id,
                        Alert.type == "low_stock",
                        Alert.is_read == False,
                        Alert.message.like(f"%'{prod_name}'%"),
                    )
                    .order_by(Alert.id.desc())
                    .first()
                )
                alert_msg = new_alert.message if new_alert else f"Low Stock: '{prod_name}'"
            else:
                alert_msg = existing_msg

            ws_alert = {
                "type": "low_stock",
                "product_id": prod_id,
                "product_name": prod_name,
                "message": alert_msg,
                "stock": stock,
                "threshold": threshold,
                "predicted_demand": pred_demand,
            }
            await manager.send_personal_message(ws_alert, shop.owner_id)

    # 6. Notify customer
    display_num = getattr(locked_order, "shop_order_number", None) or locked_order.id
    await manager.send_personal_message(
        {
            "type": "payment_success",
            "order_id": locked_order.id,
            "order_number": display_num,
            "message": (
                f"Your order #{display_num} has been confirmed and "
                f"your payment was successful."
            ),
        },
        locked_order.customer_id,
    )

    # 7. Notify owner
    shop = db.query(Shop).filter(Shop.id == locked_order.shop_id).first()
    cust = db.query(User).filter(User.id == locked_order.customer_id).first()
    cust_name = (
        (cust.owner_name or cust.phone_number) if cust else f"Customer #{locked_order.customer_id}"
    )

    if shop:
        if method == "cash":
            payment_label = "Cash Payment"
        elif method == "simulated_demo":
            payment_label = "Simulated Demo (Not Real Money)"
        else:
            payment_label = "Payment Successful (Razorpay Online)"

        await manager.send_personal_message(
            {
                "type": "payment_received",
                "order_id": locked_order.id,
                "order_number": display_num,
                "message": (
                    f"Order #{display_num} received from {cust_name} — "
                    f"Payment: {payment_label}."
                ),
                "total_amount": locked_order.total_amount,
                "payment_status": "paid",
                "payment_method": method,
            },
            shop.owner_id,
        )


# ---------------------------------------------------------------------------
# POST /api/payments/create-razorpay-order/{order_id}
# ---------------------------------------------------------------------------
@router.post("/create-razorpay-order/{order_id}")
async def create_razorpay_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 1 of online payment flow.
    Creates a Razorpay Order ID and returns it along with the public Key ID
    so the frontend can open the Razorpay Checkout widget.
    """
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.customer_id == current_user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if getattr(order, "payment_status", None) == "paid" or order.status == "paid":
        raise HTTPException(status_code=400, detail="Order is already paid.")

    if order.status == "cancelled":
        raise HTTPException(
            status_code=400, detail="Cannot initiate payment for a cancelled order."
        )

    # Best-effort stock check (race-condition safe final check is in process_successful_payment)
    for item in order.items:
        product = (
            db.query(Product).filter(Product.id == item.product_id).first()
        )
        if product and product.stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot initiate payment: Insufficient stock for '{product.name}'. "
                    f"Available: {product.stock} {product.unit}, "
                    f"Required: {item.quantity} {product.unit}."
                ),
            )

    amount_paise = int(round(order.total_amount * 100))

    # Create Razorpay order — real SDK if credentials are set, UUID fallback otherwise
    if razorpay_client:
        try:
            rz_order = razorpay_client.order.create(
                data={
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": f"receipt_order_{order.id}",
                    "payment_capture": 1,
                }
            )
            rz_order_id = rz_order["id"]
        except Exception as e:
            logger.error(f"Razorpay API Error creating order: {e}")
            rz_order_id = f"order_rzp_{order.id}_{uuid.uuid4().hex[:8]}"
    else:
        # No real credentials — generate a local stub for testing UI flow
        rz_order_id = f"order_rzp_{order.id}_{uuid.uuid4().hex[:8]}"
        logger.info(
            f"Razorpay stub mode: generated local order ID {rz_order_id} for Order #{order.id}."
        )

    order.status = "pending_payment"
    order.payment_method = "razorpay"
    order.payment_status = "online_pending"
    order.razorpay_order_id = rz_order_id
    db.commit()

    # UPI deep-link using configured merchant VPA
    upi_uri = (
        f"upi://pay?pa={settings.MERCHANT_UPI_VPA}"
        f"&pn=RetailShop"
        f"&am={order.total_amount}"
        f"&cu=INR"
        f"&tr={rz_order_id}"
    )

    # Notify owner of payment initiation
    shop = db.query(Shop).filter(Shop.id == order.shop_id).first()
    cust_name = current_user.owner_name or current_user.phone_number
    if shop:
        await manager.send_personal_message(
            {
                "type": "payment_initiated",
                "order_id": order.id,
                "message": (
                    f"Customer {cust_name} initiated Online Payment for Order #{order.id}."
                ),
                "payment_method": "razorpay",
                "payment_status": "online_pending",
            },
            shop.owner_id,
        )

    return {
        "payment_method": "razorpay",
        "razorpay_order_id": rz_order_id,
        "amount": order.total_amount,
        "amount_paise": amount_paise,
        "currency": "INR",
        # key_id is intentionally included — Razorpay Checkout requires it in the browser.
        # It is the PUBLIC key (rzp_test_... or rzp_live_...) and is safe to expose.
        "key_id": settings.RAZORPAY_KEY_ID,
        "upi_uri": upi_uri,
    }


# ---------------------------------------------------------------------------
# POST /api/payments/verify-razorpay-signature
# ---------------------------------------------------------------------------
@router.post("/verify-razorpay-signature")
async def verify_razorpay_signature(
    payload: RazorpayVerifyPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 2 of online payment flow — called by the frontend Checkout.js handler.

    Verifies the HMAC-SHA256 signature using the backend KEY_SECRET,
    optionally cross-checks the payment amount with the Razorpay API,
    then marks the order paid and deducts inventory.

    This is the ONLY authorised path for confirming an online payment.
    """
    order = (
        db.query(Order)
        .filter(Order.id == payload.order_id, Order.customer_id == current_user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if getattr(order, "payment_status", None) == "paid" or order.status == "paid":
        return {
            "status": "success",
            "message": "Order is already paid.",
            "order_id": order.id,
        }

    # Verify Razorpay Order ID matches the DB record
    if order.razorpay_order_id and payload.razorpay_order_id != order.razorpay_order_id:
        raise HTTPException(status_code=400, detail="Razorpay order ID mismatch.")

    expected_amount_paise = int(round(order.total_amount * 100))

    # Optional live amount + currency verification via Razorpay API
    if razorpay_client:
        try:
            payment_details = razorpay_client.payment.fetch(payload.razorpay_payment_id)
            if payment_details:
                if payment_details.get("amount") != expected_amount_paise:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Payment amount mismatch. Expected {expected_amount_paise} paise "
                            f"(₹{order.total_amount:.2f}), "
                            f"received {payment_details.get('amount')} paise."
                        ),
                    )
                if payment_details.get("currency") != "INR":
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid payment currency. Expected INR.",
                    )
                if (
                    payment_details.get("order_id")
                    and payment_details.get("order_id") != payload.razorpay_order_id
                ):
                    raise HTTPException(
                        status_code=400,
                        detail="Payment does not belong to the specified Razorpay order ID.",
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Razorpay payment fetch skipped or failed: {e}")

    # HMAC-SHA256 signature verification
    secret = settings.RAZORPAY_KEY_SECRET or ""
    secret_is_real = (
        bool(secret)
        and secret not in _PLACEHOLDER_SECRETS
        and not secret.startswith("rzp_test_")
    )

    # In production, ALWAYS verify the signature — no bypass allowed.
    # In dev/test without real credentials, allow test signatures for local UI testing.
    if secret_is_real:
        generated_signature = hmac.new(
            secret.encode("utf-8"),
            f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(generated_signature, payload.razorpay_signature):
            logger.warning(
                f"Signature verification FAILED for Order #{order.id}, "
                f"payment_id={payload.razorpay_payment_id}"
            )
            raise HTTPException(
                status_code=400, detail="Invalid Razorpay payment signature."
            )
    else:
        # No real secret: only allow the explicit test bypass values in non-production
        if _is_production():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Razorpay is not properly configured for production. "
                    "Set RAZORPAY_KEY_SECRET in backend .env."
                ),
            )
        # Dev/test mode: accept test signatures so the UI flow can be exercised locally
        allowed_test_sigs = {"test_signature", "sandbox_bypass", "demo_bypass"}
        if payload.razorpay_signature not in allowed_test_sigs:
            # Try verifying with whatever secret we have anyway
            generated_signature = hmac.new(
                secret.encode("utf-8") if secret else b"",
                f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(generated_signature, payload.razorpay_signature):
                logger.warning(
                    f"Signature check failed in dev mode for Order #{order.id}. "
                    f"Rejecting unrecognised signature."
                )
                raise HTTPException(
                    status_code=400,
                    detail="Invalid Razorpay payment signature.",
                )

    await process_successful_payment(
        order=order,
        db=db,
        method="razorpay",
        payment_id=payload.razorpay_payment_id,
        rzp_order_id=payload.razorpay_order_id,
        rzp_pay_id=payload.razorpay_payment_id,
        rzp_sig=payload.razorpay_signature,
    )

    return {
        "status": "success",
        "message": f"Razorpay payment verified successfully for ₹{order.total_amount:.2f}.",
        "order_id": order.id,
        "amount_verified": order.total_amount,
        "amount_paise": expected_amount_paise,
    }


# ---------------------------------------------------------------------------
# POST /api/payments/initiate/{order_id}   (cash only)
# ---------------------------------------------------------------------------
@router.post("/initiate/{order_id}")
async def initiate_payment(
    order_id: int,
    method: str = Query(..., description="Only 'cash' is accepted here. Use /create-razorpay-order for online payment."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Marks a customer order for cash payment.
    Online (Razorpay) payment must use /create-razorpay-order instead.
    """
    if method != "cash":
        raise HTTPException(
            status_code=400,
            detail="Use /create-razorpay-order for online payment. Only 'cash' is accepted here.",
        )

    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.customer_id == current_user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    # Stock availability check
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product and product.stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot initiate payment: Insufficient stock for '{product.name}'. "
                    f"Available: {product.stock} {product.unit}, "
                    f"Required: {item.quantity} {product.unit}."
                ),
            )

    order.status = "pending_payment"
    order.payment_method = "cash"
    order.payment_status = "cash_pending"
    db.commit()

    shop = db.query(Shop).filter(Shop.id == order.shop_id).first()
    cust_name = current_user.owner_name or current_user.phone_number
    if shop:
        await manager.send_personal_message(
            {
                "type": "payment_initiated",
                "order_id": order.id,
                "message": (
                    f"Customer {cust_name} selected Cash Payment for Order #{order.id}."
                ),
                "payment_method": "cash",
                "payment_status": "cash_pending",
            },
            shop.owner_id,
        )

    return {
        "payment_method": "cash",
        "payment_status": "cash_pending",
        "amount": order.total_amount,
        "message": "Order is marked for Cash Payment. Please pay the owner at counter.",
    }


# ---------------------------------------------------------------------------
# POST /api/payments/confirm-cash/{order_id}   (owner only)
# ---------------------------------------------------------------------------
@router.post("/confirm-cash/{order_id}")
async def confirm_cash_payment(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Owner confirms that cash payment was physically received.
    """
    if current_user.role != "owner":
        raise HTTPException(
            status_code=403, detail="Only shop owners can confirm cash payments."
        )

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    shop = (
        db.query(Shop)
        .filter(Shop.id == order.shop_id, Shop.owner_id == current_user.id)
        .first()
    )
    if not shop:
        raise HTTPException(
            status_code=403, detail="You do not own the shop for this order."
        )

    if getattr(order, "payment_status", None) == "paid" or order.status == "paid":
        return {"status": "success", "message": "Cash payment already confirmed."}

    await process_successful_payment(
        order=order,
        db=db,
        method="cash",
        payment_id=f"cash_ref_{order.id}_{uuid.uuid4().hex[:6]}",
    )

    return {"status": "success", "message": "Cash payment confirmed successfully."}


# ---------------------------------------------------------------------------
# POST /api/payments/webhook
# Razorpay Webhook endpoint
# Webhook URL to register in Razorpay Dashboard: https://<your-domain>/api/payments/webhook
# Supported events: payment.captured, payment.failed, order.paid
# ---------------------------------------------------------------------------
@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: Optional[str] = Header(None),
):
    """
    Razorpay Webhook endpoint.

    Register this URL in the Razorpay Dashboard after deploying to a public HTTPS address:
        https://<your-domain>/api/payments/webhook

    Supported events:
      - payment.captured  (preferred: fires when payment is confirmed by Razorpay)
      - payment.failed    (logs the failure; order remains unpaid)
      - order.paid        (legacy compatibility)

    Security:
      - In production: HMAC-SHA256 signature on the raw request body is ALWAYS required.
      - Bypass signatures (sandbox_bypass, test_signature) are REJECTED in production.
      - Unsigned or incorrectly signed webhooks are rejected with HTTP 400.
      - Duplicate delivery is handled idempotently (already-paid orders are skipped).
    """
    try:
        raw_body = await request.body()
        body_json = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as e:
        logger.error(f"Invalid JSON body in webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event = body_json.get("event", "")
    logger.info(f"Received Razorpay webhook event: '{event}'")

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------
    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET or ""
    secret_is_real = (
        bool(webhook_secret)
        and webhook_secret != "razorpay_webhook_secret_123"
        and not webhook_secret.startswith("rzp_test_")
    )

    bypass_values = {"sandbox_bypass", "test_signature"}
    sig_is_bypass = x_razorpay_signature in bypass_values

    if _is_production():
        # In production: bypass signatures are always rejected
        if sig_is_bypass:
            logger.error(
                "Webhook rejected: bypass signature not permitted in production."
            )
            raise HTTPException(
                status_code=403,
                detail="Bypass signatures are not permitted in production.",
            )
        if not x_razorpay_signature:
            raise HTTPException(
                status_code=400, detail="Missing X-Razorpay-Signature header."
            )
        if not secret_is_real:
            raise HTTPException(
                status_code=503,
                detail="Webhook secret not configured. Set RAZORPAY_WEBHOOK_SECRET in .env.",
            )
        # Verify signature
        expected_sig = hmac.new(
            webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, x_razorpay_signature):
            logger.error("Razorpay webhook signature verification FAILED.")
            raise HTTPException(
                status_code=400, detail="Invalid webhook signature."
            )
    else:
        # Development/test: verify signature if a real secret is set; allow bypass otherwise
        if x_razorpay_signature and not sig_is_bypass and secret_is_real:
            expected_sig = hmac.new(
                webhook_secret.encode("utf-8"),
                raw_body,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected_sig, x_razorpay_signature):
                logger.error("Webhook signature verification FAILED (dev mode).")
                raise HTTPException(
                    status_code=400, detail="Invalid webhook signature."
                )

    # ------------------------------------------------------------------
    # Handle payment.failed — log and return without deducting inventory
    # ------------------------------------------------------------------
    if event == "payment.failed":
        payload = body_json.get("payload", {})
        payment_entity = payload.get("payment", {}).get("entity", {})
        failed_order_id = payment_entity.get("order_id")
        payment_id = payment_entity.get("id", "unknown")
        error_desc = payment_entity.get("error_description", "Unknown error")
        logger.warning(
            f"Payment FAILED event received — Razorpay Order ID: {failed_order_id}, "
            f"Payment ID: {payment_id}, Reason: {error_desc}"
        )
        # Optionally look up and update order status to failed
        if failed_order_id:
            order = (
                db.query(Order)
                .filter(Order.razorpay_order_id == str(failed_order_id))
                .first()
            )
            if order and order.payment_status not in ("paid",):
                order.payment_status = "failed"
                db.commit()
        return {"status": "received", "event": event}

    # ------------------------------------------------------------------
    # Handle payment.captured / order.paid — confirm the payment
    # ------------------------------------------------------------------
    if event not in ("payment.captured", "order.paid", ""):
        # Acknowledge unknown events without processing them
        logger.info(f"Webhook event '{event}' is not handled by this implementation.")
        return {"status": "received", "event": event}

    payload = body_json.get("payload", {})
    rzp_order_id = None
    rzp_pay_id = None

    if isinstance(payload, dict):
        if "order" in payload and isinstance(payload["order"], dict):
            rzp_order_id = payload["order"].get("entity", {}).get("id")
        if "payment" in payload and isinstance(payload["payment"], dict):
            pay_entity = payload["payment"].get("entity", {})
            rzp_pay_id = pay_entity.get("id")
            if not rzp_order_id:
                rzp_order_id = pay_entity.get("order_id")

    # Fallback: flat body fields (used by frontend simulation and test scripts)
    if not rzp_order_id:
        rzp_order_id = body_json.get("razorpay_order_id") or body_json.get("order_id")
    if not rzp_pay_id:
        rzp_pay_id = body_json.get("razorpay_payment_id") or f"pay_wh_{uuid.uuid4().hex[:8]}"

    if not rzp_order_id:
        raise HTTPException(
            status_code=400,
            detail="Missing razorpay_order_id or order reference in webhook payload.",
        )

    # Resolve to internal Order
    order = (
        db.query(Order)
        .filter(Order.razorpay_order_id == str(rzp_order_id))
        .first()
    )

    if not order:
        # Try parsing our stub IDs: order_rzp_<order_id>_<hex>
        try:
            if str(rzp_order_id).isdigit():
                order = db.query(Order).filter(Order.id == int(rzp_order_id)).first()
            elif str(rzp_order_id).startswith("order_rzp_"):
                parts = str(rzp_order_id).split("_")
                if len(parts) >= 3 and parts[2].isdigit():
                    order = db.query(Order).filter(Order.id == int(parts[2])).first()
        except Exception:
            pass

    if not order:
        logger.warning(
            f"Webhook received for unknown Razorpay Order ID: {rzp_order_id}"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Order not found for Razorpay order ID '{rzp_order_id}'.",
        )

    await process_successful_payment(
        order=order,
        db=db,
        method="razorpay",
        payment_id=rzp_pay_id,
        rzp_order_id=str(rzp_order_id),
        rzp_pay_id=rzp_pay_id,
        rzp_sig=x_razorpay_signature or "webhook_verified",
    )

    return {
        "status": "success",
        "message": f"Webhook processed for Order #{order.id}.",
        "order_id": order.id,
        "event": event,
        "payment_status": "paid",
    }


# ---------------------------------------------------------------------------
# POST /api/payments/demo-payment-success   (development only)
# ---------------------------------------------------------------------------
@router.post("/demo-payment-success")
async def demo_payment_success(
    request_data: dict,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Simulates a successful Razorpay payment without real credentials.
    Strictly disabled in production.
    """
    if _is_production():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo payment simulation is disabled in production.",
        )

    rzp_order_id = request_data.get("razorpay_order_id")
    order_id = request_data.get("order_id")

    order = None
    if rzp_order_id:
        order = (
            db.query(Order)
            .filter(Order.razorpay_order_id == str(rzp_order_id))
            .first()
        )
    if not order and order_id:
        try:
            order = db.query(Order).filter(Order.id == int(order_id)).first()
        except (ValueError, TypeError):
            pass

    if not order:
        raise HTTPException(
            status_code=404, detail="Order not found for payment simulation."
        )

    # Ownership check: if authenticated, verify the caller owns this order
    if current_user and current_user.role == "customer":
        if order.customer_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to simulate payment for this order.",
            )

    pay_id = request_data.get("razorpay_payment_id") or f"pay_demo_{uuid.uuid4().hex[:8]}"

    await process_successful_payment(
        order=order,
        db=db,
        method="simulated_demo",
        payment_id=pay_id,
        rzp_order_id=order.razorpay_order_id or str(rzp_order_id or ""),
        rzp_pay_id=pay_id,
        rzp_sig="demo_bypass",
    )

    return {
        "status": "success",
        "message": f"Demo payment simulated successfully for Order #{order.id}.",
        "order_id": order.id,
        "payment_status": "paid",
        "payment_method": "simulated_demo",
    }
