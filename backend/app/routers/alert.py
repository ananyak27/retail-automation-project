from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Alert, Shop, User
from app.schemas import AlertResponse
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

@router.get("/", response_model=List[AlertResponse])
def get_alerts(shop_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Step 13: Retrieves all alerts for a shop. Restricted to owner.
    """
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only shop owners can access alerts.")
        
    shop = db.query(Shop).filter(Shop.id == shop_id, Shop.owner_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not own this shop.")
        
    return db.query(Alert).filter(Alert.shop_id == shop_id).order_by(Alert.created_at.desc()).all()

@router.put("/{alert_id}/read", response_model=AlertResponse)
def mark_alert_as_read(alert_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Marks a low-stock or payment alert as read.
    """
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only shop owners can modify alerts.")
        
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
        
    shop = db.query(Shop).filter(Shop.id == alert.shop_id, Shop.owner_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not own the shop this alert belongs to.")
        
    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert
