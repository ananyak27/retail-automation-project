from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Product, Shop, User
from app.schemas import ForecastResponse
from app.routers.auth import get_current_user
from app.services.forecast_service import generate_forecast

router = APIRouter(
    prefix="/api/forecasts",
    tags=["forecasts"]
)


# ============================================================
# PRODUCT FORECAST
# ============================================================

@router.get(
    "/product/{product_id}",
    response_model=ForecastResponse
)
def get_product_forecast(
    product_id: int,

    periods: int = Query(
        7,
        description="Forecast horizon: 7, 14, or 30 days"
    ),

    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    """
    Generate demand forecast for a specific product
    using the already-trained Prophet model.
    """

    # --------------------------------------------------------
    # Validate forecast horizon
    # --------------------------------------------------------

    if periods not in [7, 14, 30]:
        raise HTTPException(
            status_code=400,
            detail="Forecast period must be 7, 14, or 30 days."
        )

    # --------------------------------------------------------
    # Owner check
    # --------------------------------------------------------

    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only shop owners can access forecasting."
        )

    # --------------------------------------------------------
    # Product check
    # --------------------------------------------------------

    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Product not found."
        )

    # --------------------------------------------------------
    # Shop ownership check
    # --------------------------------------------------------

    shop = (
        db.query(Shop)
        .filter(
            Shop.id == product.shop_id,
            Shop.owner_id == current_user.id
        )
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=403,
            detail="You do not own this shop's forecasting."
        )

    # --------------------------------------------------------
    # Use already-trained Prophet model
    # --------------------------------------------------------

    forecast_data = generate_forecast(
        db,
        product_id,
        periods=periods
    )

    if not forecast_data:
        raise HTTPException(
            status_code=404,
            detail="No trained forecasting model found for this product."
        )

    return {
        "product_id": product.id,
        "product_name": product.name,
        "forecast": forecast_data
    }


# ============================================================
# SHOP FORECAST
# ============================================================

@router.get(
    "/shop/{shop_id}",
    response_model=List[ForecastResponse]
)
def get_shop_forecasts(
    shop_id: int,

    periods: int = Query(
        7,
        description="Forecast horizon: 7, 14, or 30 days"
    ),

    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    """
    Generate forecasts for all products in a shop
    using the already-trained Prophet models.
    """

    # --------------------------------------------------------
    # Validate forecast horizon
    # --------------------------------------------------------

    if periods not in [7, 14, 30]:
        raise HTTPException(
            status_code=400,
            detail="Forecast period must be 7, 14, or 30 days."
        )

    # --------------------------------------------------------
    # Owner check
    # --------------------------------------------------------

    if current_user.role != "owner":
        raise HTTPException(
            status_code=403,
            detail="Only shop owners can access forecasting."
        )

    # --------------------------------------------------------
    # Shop ownership check
    # --------------------------------------------------------

    shop = (
        db.query(Shop)
        .filter(
            Shop.id == shop_id,
            Shop.owner_id == current_user.id
        )
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=403,
            detail="You do not own this shop."
        )

    # --------------------------------------------------------
    # Get shop products
    # --------------------------------------------------------

    products = (
        db.query(Product)
        .filter(Product.shop_id == shop_id)
        .all()
    )

    results = []

    # --------------------------------------------------------
    # Generate forecast for every product
    # --------------------------------------------------------

    for product in products:

        forecast_data = generate_forecast(
            db,
            product.id,
            periods=periods
        )

        if forecast_data:
            results.append({
                "product_id": product.id,
                "product_name": product.name,
                "forecast": forecast_data
            })

    return results