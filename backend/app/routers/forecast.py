from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Product, Shop, User
from app.schemas import ForecastResponse
from app.routers.auth import get_current_user
from app.services.forecast_service import generate_forecast

router = APIRouter(prefix="/api/forecasts", tags=["forecasts"])

@router.get("/product/{product_id}", response_model=ForecastResponse)
def get_product_forecast(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 14: Calculates Prophet forecast for a specific product.
    Restricted to shop owner.
    """
    if current_user.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only shop owners can access forecasting.")
        
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
        
    # Verify owner owns this product's shop
    shop = db.query(Shop).filter(Shop.id == product.shop_id, Shop.owner_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not own this shop's forecasting.")
        
    forecast_data = generate_forecast(db, product_id, periods=7)
    
    return {
        "product_id": product.id,
        "product_name": product.name,
        "forecast": forecast_data
    }

@router.get("/shop/{shop_id}", response_model=List[ForecastResponse])
def get_shop_forecasts(
    shop_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves predictions for all products in the selected shop.
    """
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only shop owners can access forecasting.")
        
    shop = db.query(Shop).filter(Shop.id == shop_id, Shop.owner_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not own this shop.")
        
    products = db.query(Product).filter(Product.shop_id == shop_id).all()
    
    results = []
    for p in products:
        forecast_data = generate_forecast(db, p.id, periods=7)
        if forecast_data:
            results.append({
                "product_id": p.id,
                "product_name": p.name,
                "forecast": forecast_data
            })
            
    return results
