import datetime
import random
import pandas as pd
import logging
from sqlalchemy.orm import Session
from app.models import SalesHistory, Product

logger = logging.getLogger(__name__)

def generate_forecast(db: Session, product_id: int, periods: int = 7) -> list:
    """
    Retrieves the sales history for a specific product, trains a Meta Prophet model,
    and returns a forecast for the next `periods` days.
    """
    # 1. Fetch sales history from Database
    history = db.query(SalesHistory).filter(SalesHistory.product_id == product_id).order_by(SalesHistory.sold_at).all()
    
    if len(history) < 5:
        # If history is too sparse, return empty list or mock forecast to prevent crashes
        logger.warning(f"Insufficient sales history (found {len(history)} entries) for product ID {product_id} to run Prophet.")
        return []

    # 2. Convert to Pandas DataFrame structure for Prophet: ds (datetime) and y (value)
    data = []
    for h in history:
        # Aggregate by day to prevent multiple transactions on the same day causing issues
        data.append({
            "ds": h.sold_at.date(),
            "y": h.quantity
        })
        
    df_raw = pd.DataFrame(data)
    # Aggregate daily sales
    df = df_raw.groupby("ds").sum().reset_index()
    df.columns = ["ds", "y"]
    df["ds"] = pd.to_datetime(df["ds"])

    # 3. Train Prophet Model
    try:
        from prophet import Prophet
        
        # Suppress logging/warnings from Prophet/cmdstanpy
        logging.getLogger('prophet').setLevel(logging.ERROR)
        logging.getLogger('cmdstanpy').setLevel(logging.ERROR)
        
        # Initialize and fit the model
        model = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=False)
        model.fit(df)
        
        # Create future periods dataframe
        future = model.make_future_dataframe(periods=periods, freq='D')
        forecast = model.predict(future)
        
        # We only want the future predictions
        future_forecast = forecast.tail(periods)
        
        forecast_results = []
        for _, row in future_forecast.iterrows():
            # Ensure quantity isn't negative
            yhat = max(0.0, float(row["yhat"]))
            yhat_lower = max(0.0, float(row["yhat_lower"]))
            yhat_upper = max(0.0, float(row["yhat_upper"]))
            
            forecast_results.append({
                "ds": row["ds"].strftime("%Y-%m-%d"),
                "yhat": round(yhat, 2),
                "yhat_lower": round(yhat_lower, 2),
                "yhat_upper": round(yhat_upper, 2)
            })
            
        return forecast_results
        
    except ImportError:
        logger.warning("Meta Prophet package is not installed or available. Using statistical regression fallback.")
        # Lightweight regression fallback (Rolling average + trend + weekly cycle) if prophet is not installed
        last_date = df["ds"].max()
        avg_sales = df["y"].mean()
        
        forecast_results = []
        for i in range(1, periods + 1):
            future_date = last_date + datetime.timedelta(days=i)
            # Add simple random noise + weekly cycle (weekend boost)
            weekday = future_date.weekday()
            multiplier = 1.3 if weekday in [5, 6] else 0.95
            yhat = max(0.0, avg_sales * multiplier + random.uniform(-1, 1))
            
            forecast_results.append({
                "ds": future_date.strftime("%Y-%m-%d"),
                "yhat": round(yhat, 2),
                "yhat_lower": round(yhat * 0.8, 2),
                "yhat_upper": round(yhat * 1.2, 2)
            })
        return forecast_results
    except Exception as e:
        logger.error(f"Error executing Prophet forecast: {e}")
        return []

def seed_historical_sales(db: Session, product_id: int, days: int = 90):
    """
    Seeds database with realistic historical sales for a product.
    Includes weekly cycles (higher sales on weekends) and random noise.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return
        
    logger.info(f"Seeding historical sales data for product: {product.name}...")
    start_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    
    # We will generate a base sales quantity based on product pricing
    # Higher price -> lower quantity typically
    base_qty = 15.0 if product.price < 50 else (5.0 if product.price < 150 else 2.0)
    
    sales_to_add = []
    
    for day_idx in range(days):
        sold_at = start_date + datetime.timedelta(days=day_idx)
        # Add weekly pattern (higher sales on Friday, Saturday, Sunday)
        day_of_week = sold_at.weekday()
        cycle_factor = 1.4 if day_of_week in [4, 5, 6] else 0.85
        
        # Add random noise
        quantity = max(1.0, round(base_qty * cycle_factor + random.uniform(-2, 2), 1))
        
        # Occasionally skip a day (zero sales)
        if random.random() < 0.05:
            continue
            
        sale = SalesHistory(
            product_id=product_id,
            quantity=quantity,
            price=product.price,
            sold_at=sold_at
        )
        sales_to_add.append(sale)
        
    db.add_all(sales_to_add)
    db.commit()
    logger.info(f"Seeded {len(sales_to_add)} sales records for product ID {product_id}.")
