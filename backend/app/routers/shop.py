from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Shop, User
from app.schemas import ShopCreate, ShopResponse
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/shops", tags=["shops"])

@router.post("/", response_model=ShopResponse)
def create_shop(payload: ShopCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Registers a new shop. Restricted to users with 'owner' role.
    """
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only shop owners can register a shop."
        )
        
    # Check if shop name already exists for this owner
    existing_shop = db.query(Shop).filter(Shop.name == payload.name, Shop.owner_id == current_user.id).first()
    if existing_shop:
        raise HTTPException(
            status_code=400,
            detail="You have already registered a shop with this name."
        )
        
    shop = Shop(name=payload.name, address=payload.address, owner_id=current_user.id)
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return shop

@router.get("/", response_model=List[ShopResponse])
def get_shops(db: Session = Depends(get_db)):
    """
    Retrieves a list of all registered shops.
    """
    return db.query(Shop).all()

@router.get("/my-shop", response_model=ShopResponse)
def get_my_shop(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieves the shop owned by the current logged-in owner.
    """
    if current_user.role != "owner":
        raise HTTPException(
            status_code=403,
            detail="Only owners have registered shops."
        )
    shop = db.query(Shop).filter(Shop.owner_id == current_user.id).first()
    if not shop:
        raise HTTPException(
            status_code=404,
            detail="No shop registered under your account yet."
        )
    return shop

@router.get("/{shop_id}", response_model=ShopResponse)
def get_shop(shop_id: int, db: Session = Depends(get_db)):
    """
    Retrieves details of a specific shop.
    """
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found.")
    return shop
