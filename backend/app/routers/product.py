from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import Product, Shop, User, Alert
from app.schemas import ProductCreate, ProductUpdate, ProductResponse
from app.routers.auth import get_current_user
from app.services.forecast_service import seed_historical_sales
from app.websocket_manager import manager

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

    # Duplicate check: check if product with same name already exists in this shop catalog
    existing_product = db.query(Product).filter(
        Product.shop_id == shop_id,
        Product.is_active == True,
        func.lower(Product.name) == payload.name.strip().lower()
    ).first()

    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A product named '{existing_product.name}' already exists in your shop catalog. Please use 'Update Product' mode to edit it."
        )
        
    product = Product(
        shop_id=shop_id,
        name=payload.name.strip(),
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
    Lists all products of a specific shop ordered alphabetically (A-Z) by name.
    """
    return db.query(Product).filter(
        Product.shop_id == shop_id,
        Product.is_active == True
    ).order_by(Product.name.asc()).all()

@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
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

    # Manage low stock alerts upon stock update
    if product.stock > product.min_stock_threshold:
        # Stock restocked above threshold -> resolve/read any unread low_stock alert for this product
        unread_alerts = db.query(Alert).filter(
            Alert.shop_id == product.shop_id,
            Alert.type == "low_stock",
            Alert.is_read == False,
            Alert.message.like(f"%'{product.name}'%")
        ).all()
        for a in unread_alerts:
            a.is_read = True
        db.commit()
    elif product.stock <= product.min_stock_threshold:
        # Stock at or below threshold -> ensure an unread low_stock alert exists
        existing_alert = db.query(Alert).filter(
            Alert.shop_id == product.shop_id,
            Alert.type == "low_stock",
            Alert.is_read == False,
            Alert.message.like(f"%'{product.name}'%")
        ).first()
        if not existing_alert:
            new_alert = Alert(
                shop_id=product.shop_id,
                type="low_stock",
                message=f"Low Stock Alert: '{product.name}' stock is {product.stock} {product.unit} (Min Quantity: {product.min_stock_threshold})."
            )
            db.add(new_alert)
            db.commit()

    # Send WebSocket update to all connected owner devices
    await manager.send_personal_message({
        "type": "stock_updated",
        "product_id": product.id,
        "product_name": product.name,
        "stock": product.stock,
        "threshold": product.min_stock_threshold
    }, shop.owner_id)

    return product

@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "owner":
        raise HTTPException(
            status_code=403,
            detail="Only shop owners can delete products."
        )

    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Product not found."
        )

    shop = db.query(Shop).filter(
        Shop.id == product.shop_id,
        Shop.owner_id == current_user.id
    ).first()

    if not shop:
        raise HTTPException(
            status_code=403,
            detail="You do not own this product."
        )

    # Soft delete: keep order/sales/forecast history
    product.is_active = False

    db.commit()

    return {
        "message": "Product deleted successfully"
    }
