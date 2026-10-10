from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from app.database import get_db
from app.models import ChatMessage, Shop, User
from app.schemas import ChatMessageCreate, ChatMessageResponse
from app.routers.auth import get_current_user
from app.websocket_manager import manager

router = APIRouter(prefix="/api/chat", tags=["chat"])

def serialize_message(msg: ChatMessage) -> dict:
    created_at_str = msg.created_at.isoformat() + "Z" if msg.created_at else datetime.datetime.utcnow().isoformat() + "Z"
    return {
        "id": msg.id,
        "shop_id": msg.shop_id,
        "customer_id": msg.customer_id,
        "sender_role": msg.sender_role,
        "message": msg.message,
        "created_at": created_at_str
    }

@router.get("/messages", response_model=List[ChatMessageResponse])
def get_chat_messages(
    shop_id: int = Query(...),
    customer_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ChatMessage).filter(ChatMessage.shop_id == shop_id)
    
    if current_user.role == 'customer':
        query = query.filter(ChatMessage.customer_id == current_user.id)
    elif current_user.role == 'owner':
        # Verify ownership of the shop
        shop = db.query(Shop).filter(Shop.id == shop_id, Shop.owner_id == current_user.id).first()
        if not shop:
            raise HTTPException(status_code=403, detail="Not authorized to access chat messages for this shop")
        if customer_id:
            query = query.filter(ChatMessage.customer_id == customer_id)
            
    messages = query.order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).all()
    return [serialize_message(m) for m in messages]

@router.post("/messages", response_model=ChatMessageResponse)
async def create_chat_message(
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == 'customer':
        target_customer_id = current_user.id
    else:
        if not payload.customer_id:
            raise HTTPException(status_code=400, detail="customer_id is required when owner sends a message")
        target_customer_id = payload.customer_id

    # Verify shop exists
    shop = db.query(Shop).filter(Shop.id == payload.shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    if current_user.role == 'owner' and shop.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not own this shop.")

    new_msg = ChatMessage(
        shop_id=payload.shop_id,
        customer_id=target_customer_id,
        sender_role=payload.sender_role,
        message=payload.message,
        created_at=datetime.datetime.utcnow()
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)

    serialized = serialize_message(new_msg)

    # Real-time WebSocket notifications to relevant user(s)
    ws_payload = {
        "type": "chat_message",
        "data": serialized
    }

    # Send to owner of the shop
    await manager.send_personal_message(ws_payload, shop.owner_id)
    # Send to customer
    if target_customer_id != shop.owner_id:
        await manager.send_personal_message(ws_payload, target_customer_id)

    return serialized

