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
    Helper function to serialize an order with product names populated.
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
        
    return {
        "id": order.id,
        "customer_id": order.customer_id,
        "shop_id": order.shop_id,
        "status": order.status,
        "total_amount": order.total_amount,
        "notes": order.notes,
        "payment_method": order.payment_method,
        "payment_id": order.payment_id,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
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
    Step 7: Creates a draft order in the database and alerts the owner.
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

    # 2. Save Order (status: pending_owner as draft goes to owner review)
    order = Order(
        customer_id=current_user.id,
        shop_id=payload.shop_id,
        status="pending_owner",  # Draft created, goes to owner to review
        total_amount=total,
        notes=payload.notes,
        items=order_items
    )
    
    db.add(order)
    db.commit()
    db.refresh(order)
    
    # 3. Create database Alert for owner
    shop = db.query(Shop).filter(Shop.id == payload.shop_id).first()
    if shop:
        alert = Alert(
            shop_id=shop.id,
            type="new_order",
            message=f"New order #{order.id} received from customer phone {current_user.phone_number}."
        )
        db.add(alert)
        db.commit()
        
        # 4. Notify Owner in real-time via WebSocket
        ws_msg = {
            "type": "new_order",
            "order_id": order.id,
            "message": alert.message,
            "shop_id": shop.id
        }
        await manager.send_personal_message(ws_msg, shop.owner_id)
        
    return serialize_order(order, db)

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
