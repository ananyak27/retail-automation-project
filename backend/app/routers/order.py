from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from app.database import get_db
from app.models import Order, OrderItem, Product, Shop, User, Alert
from app.schemas import OrderCreate, OrderUpdate, OrderResponse
from app.routers.auth import get_current_user
from app.services.ocr_service import perform_ocr
from app.services.nlp_service import extract_entities
from app.services.matching_service import match_extracted_items
from app.websocket_manager import manager

router = APIRouter(prefix="/api/orders", tags=["orders"])

def serialize_order(order: Order, db: Session) -> dict:
    """
    Helper function to serialize an order with product names populated and shop-specific order number.
    """
    items_data = []
    for item in order.items:
        prod = db.query(Product).filter(Product.id == item.product_id).first()
        items_data.append({
            "id": item.id,
            "product_id": item.product_id,
            "product_name": prod.name if prod else "Unknown Product",
            "quantity": item.quantity,
            "unit": item.unit,
            "price_at_order": item.price_at_order
        })
        
    cust = db.query(User).filter(User.id == order.customer_id).first()
    cust_name = (cust.owner_name or cust.phone_number) if cust else f"Customer #{order.customer_id}"
    cust_phone = cust.phone_number if cust else "N/A"

    created_at_str = order.created_at.isoformat() + "Z" if order.created_at else None
    updated_at_str = order.updated_at.isoformat() + "Z" if order.updated_at else None
    paid_at_str = order.paid_at.isoformat() + "Z" if getattr(order, 'paid_at', None) else None
    
    order_num = getattr(order, 'shop_order_number', None) or order.id

    return {
        "id": order.id,
        "order_number": order_num,
        "customer_id": order.customer_id,
        "customer_name": cust_name,
        "customer_phone": cust_phone,
        "shop_id": order.shop_id,
        "status": order.status,
        "payment_status": getattr(order, 'payment_status', 'pending') or 'pending',
        "total_amount": order.total_amount,
        "notes": order.notes,
        "payment_method": order.payment_method,
        "payment_id": order.payment_id,
        "razorpay_order_id": getattr(order, 'razorpay_order_id', None),
        "razorpay_payment_id": getattr(order, 'razorpay_payment_id', None),
        "paid_at": paid_at_str,
        "created_at": created_at_str,
        "updated_at": updated_at_str,
        "items": items_data
    }

@router.post("/process-image")
async def process_image_list(
    file: UploadFile = File(...), 
    shop_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Step 5 & 6: Receives image, processes with TrOCR + spaCy, performs catalog matching.
    """
    contents = await file.read()
    
    # 1. TrOCR extracts raw text
    extracted_text = perform_ocr(contents)
    
    # 2. spaCy extracts quantities and products
    extracted_items = extract_entities(extracted_text)
    
    # 3. Fuzzy match against catalog
    matches = match_extracted_items(db, shop_id, extracted_items)
    
    return {
        "raw_text": extracted_text,
        "extracted_items": matches
    }

@router.post("/process-text")
def process_text_list(
    text: str = Form(...), 
    shop_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Step 5 & 6: Receives text message list, parses with spaCy, performs catalog matching.
    """
    # 1. spaCy extracts quantities and products
    extracted_items = extract_entities(text)
    
    # 2. Fuzzy match against catalog
    matches = match_extracted_items(db, shop_id, extracted_items)
    
    return {
        "extracted_items": matches
    }

@router.post("/create-draft")
async def create_draft_order(
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 7: Creates a draft order in the database with shop-specific sequential order number and alerts the owner.
    """
    # 1. Calculate initial total amount
    total = 0.0
    order_items = []
    
    for item_data in payload.items:
        prod = db.query(Product).filter(Product.id == item_data.product_id).first()
        if not prod:
            raise HTTPException(status_code=404, detail=f"Product ID {item_data.product_id} not found.")
            
        price = item_data.price_at_order if item_data.price_at_order > 0 else prod.price
        item_total = price * item_data.quantity
        total += item_total
        
        order_items.append(OrderItem(
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            unit=item_data.unit,
            price_at_order=price
        ))

    # 2. Increment shop's order counter atomically with for_update locking
    shop = db.query(Shop).filter(Shop.id == payload.shop_id).with_for_update().first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found.")

    current_last = getattr(shop, 'last_order_number', 0) or 0
    next_shop_num = current_last + 1
    shop.last_order_number = next_shop_num

    # 3. Save Order with shop_order_number
    order = Order(
        customer_id=current_user.id,
        shop_id=payload.shop_id,
        shop_order_number=next_shop_num,
        status="pending_payment",
        payment_status="pending",
        total_amount=total,
        notes=payload.notes,
        items=order_items
    )
    
    db.add(order)
    db.commit()
    db.refresh(order)
    
    serialized = serialize_order(order, db)

    # 4. Create database Alert for owner
    cust_display_name = current_user.owner_name or current_user.phone_number
    display_num = order.shop_order_number or order.id
    alert = Alert(
        shop_id=shop.id,
        type="new_order",
        message=f"New Order #{display_num} received from {cust_display_name} ({current_user.phone_number}). Total: ₹{order.total_amount:.2f}."
    )
    db.add(alert)
    db.commit()
    
    # 5. Notify Owner in real-time via WebSocket with COMPLETE order details
    ws_msg = {
        "type": "new_order",
        "order_id": order.id,
        "order_number": display_num,
        "message": alert.message,
        "shop_id": shop.id,
        "customer_name": cust_display_name,
        "customer_phone": current_user.phone_number,
        "order_details": serialized
    }
    await manager.send_personal_message(ws_msg, shop.owner_id)
    
    return serialized

@router.put("/{order_id}/review")
async def owner_review_order(
    order_id: int,
    payload: OrderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 8: Owner reviews, modifies, and sends updated order back to the customer.
    """
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only shop owners can review orders.")
        
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
        
    # Verify owner owns this shop
    shop = db.query(Shop).filter(Shop.id == order.shop_id, Shop.owner_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not own the shop for this order.")
        
    # Update items if provided in payload
    if payload.items is not None:
        # Delete old items
        db.query(OrderItem).filter(OrderItem.order_id == order_id).delete()
        
        # Add updated items
        new_total = 0.0
        for item_data in payload.items:
            prod = db.query(Product).filter(Product.id == item_data.product_id).first()
            price = item_data.price_at_order if item_data.price_at_order > 0 else (prod.price if prod else 0)
            new_total += price * item_data.quantity
            
            db_item = OrderItem(
                order_id=order_id,
                product_id=item_data.product_id,
                quantity=item_data.quantity,
                unit=item_data.unit,
                price_at_order=price
            )
            db.add(db_item)
        order.total_amount = new_total
        
    if payload.notes is not None:
        order.notes = payload.notes
        
    # Transition status: owner reviewed -> pending client confirmation
    order.status = "pending_customer"
    db.commit()
    db.refresh(order)
    
    # Notify Customer via WebSocket
    ws_msg = {
        "type": "order_reviewed",
        "order_id": order.id,
        "message": f"Your order #{order.id} has been reviewed by the shop owner. Please confirm.",
        "status": order.status
    }
    await manager.send_personal_message(ws_msg, order.customer_id)
    
    return serialize_order(order, db)

@router.get("/", response_model=List[dict])
def list_orders(
    shop_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List orders. Customers get their own orders; owners get their shop's orders.
    """
    query = db.query(Order)
    
    if current_user.role == "owner":
        # Check shops owned by owner
        owner_shops = db.query(Shop).filter(Shop.owner_id == current_user.id).all()
        owner_shop_ids = [s.id for s in owner_shops]
        
        if shop_id:
            if shop_id not in owner_shop_ids:
                raise HTTPException(status_code=403, detail="You do not own this shop.")
            query = query.filter(Order.shop_id == shop_id)
        else:
            query = query.filter(Order.shop_id.in_(owner_shop_ids))
    else:
        # Customers get their own orders
        query = query.filter(Order.customer_id == current_user.id)
        if shop_id:
            query = query.filter(Order.shop_id == shop_id)
            
    orders = query.order_by(Order.created_at.desc()).all()
    return [serialize_order(o, db) for o in orders]

@router.get("/{order_id}")
def get_order_details(order_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Gets details of a specific order.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
        
    # Check permissions
    if current_user.role == "owner":
        shop = db.query(Shop).filter(Shop.id == order.shop_id, Shop.owner_id == current_user.id).first()
        if not shop:
            raise HTTPException(status_code=403, detail="You do not own this shop.")
    else:
        if order.customer_id != current_user.id:
            raise HTTPException(status_code=403, detail="This is not your order.")
            
    return serialize_order(order, db)

@router.put("/{order_id}/reject")
async def reject_order(order_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Owner rejects an incoming order.
    """
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only shop owners can reject orders.")
        
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
        
    shop = db.query(Shop).filter(Shop.id == order.shop_id, Shop.owner_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not own the shop for this order.")
        
    if order.status == "paid" or order.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Cannot reject an order that has already been paid.")
        
    order.status = "rejected"
    order.payment_status = "failed"
    db.commit()
    db.refresh(order)
    
    # Notify customer via WebSocket
    ws_msg = {
        "type": "order_rejected",
        "order_id": order.id,
        "message": f"Your order #{order.id} was declined/rejected by the shop owner.",
        "status": "rejected"
    }
    await manager.send_personal_message(ws_msg, order.customer_id)
    
    return serialize_order(order, db)

@router.delete("/{order_id}")
async def delete_order(order_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Owner deletes an order and its order items safely from the database.
    """
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only shop owners can delete orders.")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    shop = db.query(Shop).filter(Shop.id == order.shop_id, Shop.owner_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not own the shop for this order.")

    customer_id = order.customer_id
    db.delete(order)
    db.commit()

    ws_msg = {
        "type": "order_deleted",
        "order_id": order_id,
        "message": f"Order #{order_id} was deleted by the shop owner."
    }
    await manager.send_personal_message(ws_msg, customer_id)
    await manager.send_personal_message(ws_msg, current_user.id)

    return {
        "status": "success",
        "message": f"Order #{order_id} deleted successfully.",
        "order_id": order_id
    }

