from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import Product, Shop, User
from app.schemas import ProductCreate, ProductUpdate, ProductResponse
from app.routers.auth import get_current_user
from app.services.forecast_service import seed_historical_sales

router = APIRouter(prefix="/api/products", tags=["products"])

@router.post("/", response_model=ProductResponse)
def create_product(
    payload: ProductCreate, 
    shop_id: int = Query(...), 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Adds a new product to the shop's catalog. Seeding historical data for Prophet is executed automatically.
    """
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only shop owners can add products."
        )
        
    # Verify owner owns this shop
    shop = db.query(Shop).filter(Shop.id == shop_id, Shop.owner_id == current_user.id).first()
    if not shop:
        raise HTTPException(
            status_code=403,
            detail="You can only add products to shops that you own."
        )
        
    product = Product(
        shop_id=shop_id,
        name=payload.name,
        unit=payload.unit,
        price=payload.price,
        stock=payload.stock,
        min_stock_threshold=payload.min_stock_threshold
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    
    # Auto-seed historical sales data so Meta Prophet works immediately on the dashboard!
    seed_historical_sales(db, product.id, days=90)
    
    return product

@router.get("/", response_model=List[ProductResponse])
def get_products(shop_id: int = Query(...), db: Session = Depends(get_db)):
    """
    Lists all products of a specific shop.
    """
    return db.query(Product).filter(Product.shop_id == shop_id).all()

@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates details of an existing product (restricted to shop owner).
    """
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only shop owners can edit products.")
        
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
        
    # Verify owner owns this product's shop
    shop = db.query(Shop).filter(Shop.id == product.shop_id, Shop.owner_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not own the shop this product belongs to.")
        
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)
        
    db.commit()
    db.refresh(product)
    return product

@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deletes a product from the catalog.
    """
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only shop owners can delete products.")
        
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
        
    shop = db.query(Shop).filter(Shop.id == product.shop_id, Shop.owner_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not own the shop this product belongs to.")
        
    db.delete(product)
    db.commit()
    return
