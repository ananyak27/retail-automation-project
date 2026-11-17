import datetime
import random
import os
import joblib
import logging
import csv
import difflib
import pandas as pd
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import SalesHistory, Product

logger = logging.getLogger(__name__)


# ============================================================
# TRAINED ML / PROPHET MODEL LOADING
# ============================================================

MODEL_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "ml_models",
        "sales_model.pkl"
    )
)

_prophet_models = None


def load_prophet_models():
    """
    Load the trained sales forecasting model.
    Models and metadata are loaded once and reused.
    """
    global _prophet_models

    if _prophet_models is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Sales model file not found: {MODEL_PATH}"
            )

        logger.info(f"Loading sales forecasting model from: {MODEL_PATH}")
        _prophet_models = joblib.load(MODEL_PATH)
        logger.info("Successfully loaded sales forecasting model package.")

    return _prophet_models


_name_to_model_id = None


def _get_name_to_model_id() -> dict:
    global _name_to_model_id
    if _name_to_model_id is not None:
        return _name_to_model_id

    _name_to_model_id = {}

    # Check forecast_summary in model first
    try:
        models_pkg = load_prophet_models()
        if isinstance(models_pkg, dict) and "forecast_summary" in models_pkg:
            fs = models_pkg["forecast_summary"]
            for _, row in fs.iterrows():
                pname = str(row["product_name"]).strip().lower()
                pid = int(row["product_id"])
                if pname not in _name_to_model_id:
                    _name_to_model_id[pname] = pid
            if _name_to_model_id:
                return _name_to_model_id
    except Exception as e:
        logger.warning(f"Could not load name map from model package: {e}")

    # Fallback to CSV
    possible_paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "sales_data_1year.csv")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sales_data_1year.csv")),
        os.path.abspath(os.path.join(os.getcwd(), "sales_data_1year.csv")),
    ]

    for p in possible_paths:
        if os.path.exists(p):
            try:
                with open(p, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        p_name = row.get("product_name", "").strip().lower()
                        p_id = row.get("product_id")
                        if p_name and p_id and p_name not in _name_to_model_id:
                            try:
                                _name_to_model_id[p_name] = int(p_id)
                            except ValueError:
                                pass
                        if len(_name_to_model_id) >= 1000:
                            break
                return _name_to_model_id
            except Exception as e:
                logger.warning(f"Error reading {p}: {e}")

    return _name_to_model_id


def get_product_model(product_id: int, db: Session = None):
    """
    Returns the loaded model regressor.
    """
    models_pkg = load_prophet_models()
    if isinstance(models_pkg, dict):
        if "model" in models_pkg:
            return models_pkg["model"]
        if product_id in models_pkg:
            return models_pkg[product_id]
    return models_pkg


def get_model_count() -> int:
    """
    Return number of supported products in the forecasting model.
    """
    models_pkg = load_prophet_models()
    if isinstance(models_pkg, dict):
        if "forecast_summary" in models_pkg:
            return len(models_pkg["forecast_summary"])
        if "prod_mean" in models_pkg:
            return len(models_pkg["prod_mean"])
        return len(models_pkg)
    return 1000


# ============================================================
# SHOP-WISE FORECAST GENERATION
# ============================================================

def generate_forecast(
    db: Session,
    product_id: int,
    periods: int = 7
) -> list:
    """
    Generate shop-wise future demand predictions (7, 14, or 30 days)
    using the product's shop-specific historical sales records and the sales model.

    Guarantees:
    - Never mixes sales records between different shops.
    - Uses each shop's own historical sales records.
    - Updated whenever new sales are confirmed for that shop.
    """
    if periods not in [7, 14, 30]:
        raise ValueError("Forecast period must be 7, 14, or 30 days.")

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        logger.warning(f"Product ID {product_id} not found.")
        return []

    shop_id = product.shop_id

    # 1. Query shop-specific sales history aggregated by date
    daily_records = (
        db.query(
            func.date(SalesHistory.sold_at).label("sale_date"),
            func.sum(SalesHistory.quantity).label("total_qty")
        )
        .filter(
            SalesHistory.product_id == product.id,
            SalesHistory.shop_id == shop_id
        )
        .group_by(func.date(SalesHistory.sold_at))
        .order_by(func.date(SalesHistory.sold_at).desc())
        .limit(60)
        .all()
    )

    quantities = [float(r.total_qty) for r in daily_records] if daily_records else []
    recent_mean = sum(quantities) / len(quantities) if quantities else max(1.0, 15.0 if product.price < 50 else (6.0 if product.price < 150 else 2.5))
    roll_7 = sum(quantities[:7]) / len(quantities[:7]) if quantities[:7] else recent_mean
    roll_28 = sum(quantities[:28]) / len(quantities[:28]) if quantities[:28] else recent_mean
    lag_7 = quantities[6] if len(quantities) >= 7 else recent_mean
    lag_14 = quantities[13] if len(quantities) >= 14 else recent_mean
    lag_28 = quantities[27] if len(quantities) >= 28 else recent_mean

    # 2. Match product in trained model package
    models_pkg = load_prophet_models()
    name_map = _get_name_to_model_id()
    norm_name = product.name.strip().lower()

    # Try exact match, base name match, or close match
    model_prod_id = None
    if norm_name in name_map:
        model_prod_id = name_map[norm_name]
    else:
        base_name = norm_name.split("(")[0].strip()
        if base_name in name_map:
            model_prod_id = name_map[base_name]
        elif name_map:
            close = difflib.get_close_matches(base_name, list(name_map.keys()), n=1, cutoff=0.5)
            if close:
                model_prod_id = name_map[close[0]]

    if model_prod_id is None:
        model_prod_id = ((product_id - 1) % 1000) + 1

    # Extract model metadata
    rf_model = models_pkg.get("model") if isinstance(models_pkg, dict) else None
    features = models_pkg.get("features", []) if isinstance(models_pkg, dict) else []
    festivals = [pd.to_datetime(f) for f in models_pkg.get("festivals", [])] if isinstance(models_pkg, dict) else []
    unit_map = models_pkg.get("unit_map", {}) if isinstance(models_pkg, dict) else {}
    price_avg = models_pkg.get("price_avg", {}) if isinstance(models_pkg, dict) else {}
    prod_mean_map = models_pkg.get("prod_mean", {}) if isinstance(models_pkg, dict) else {}

    unit_code = unit_map.get(model_prod_id, 2)
    avg_price = price_avg.get(model_prod_id, product.price)
    model_mean = prod_mean_map.get(model_prod_id, recent_mean)

    # Calculate shop-specific volume adjustment ratio
    volume_ratio = roll_7 / model_mean if (model_mean and model_mean > 0) else 1.0
    volume_ratio = max(0.4, min(volume_ratio, 2.5))

    start_date = datetime.date.today() + datetime.timedelta(days=1)
    forecast_results = []

    for day_idx in range(periods):
        cur_date = start_date + datetime.timedelta(days=day_idx)
        dow = cur_date.weekday()
        is_weekend = 1 if dow in (5, 6) else 0

        yhat = None
        if rf_model is not None and features:
            try:
                ts = pd.to_datetime(cur_date)
                min_fest_dist = min([abs((ts - f).days) for f in festivals]) if festivals else 30
                fest_win = 1 if min_fest_dist <= 3 else 0
                price_change = product.price - avg_price
                price_ratio = product.price / avg_price if avg_price > 0 else 1.0

                row = [
                    model_prod_id, unit_code, dow, cur_date.month, cur_date.day,
                    cur_date.isocalendar()[1], cur_date.timetuple().tm_yday,
                    is_weekend, min_fest_dist, fest_win, product.price, price_change,
                    price_ratio, lag_7, lag_14, lag_28, roll_7, roll_28, model_mean
                ]
                X = pd.DataFrame([row], columns=features)
                raw_pred = float(rf_model.predict(X)[0])
                # Scale with shop-specific sales performance
                yhat = raw_pred * volume_ratio
            except Exception as pred_err:
                logger.debug(f"RF predict fallback for {product.name}: {pred_err}")

        # Fallback if model not available or predict failed
        if yhat is None:
            cycle_factor = 1.35 if dow in (5, 6) else (1.15 if dow == 4 else 0.88)
            yhat = roll_7 * cycle_factor

        yhat = max(0.1, round(float(yhat), 2))
        yhat_lower = max(0.0, round(yhat * 0.85, 2))
        yhat_upper = round(yhat * 1.15, 2)

        forecast_results.append({
            "ds": cur_date.strftime("%Y-%m-%d"),
            "yhat": yhat,
            "yhat_lower": yhat_lower,
            "yhat_upper": yhat_upper
        })

    logger.info(
        f"Generated {periods}-day shop-wise forecast for product '{product.name}' "
        f"(ID: {product_id}, Shop: {shop_id})."
    )

    return forecast_results


def get_predicted_demand(
    db: Session,
    product_id: int,
    periods: int = 7
) -> float:
    """
    Return total predicted demand for the next N days for a specific product.
    """
    forecast = generate_forecast(
        db=db,
        product_id=product_id,
        periods=periods
    )

    if not forecast:
        return 0.0

    predicted_demand = sum(item["yhat"] for item in forecast)
    return round(predicted_demand, 2)


# ============================================================
# NEW PRODUCT SALES SEEDING
# ============================================================

def seed_historical_sales(
    db: Session,
    product_id: int,
    days: int = 90
):
    """
    Seeds database with realistic historical sales for a newly added product.
    Includes weekly cycles and random noise, tied to the product's shop.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return

    logger.info(
        f"Seeding historical sales data for newly added product: "
        f"{product.name} (Shop {product.shop_id})..."
    )

    start_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    base_qty = 15.0 if product.price < 50 else (5.0 if product.price < 150 else 2.0)
    sales_to_add = []

    for day_idx in range(days):
        sold_at = start_date + datetime.timedelta(days=day_idx)
        day_of_week = sold_at.weekday()
        cycle_factor = 1.4 if day_of_week in [4, 5, 6] else 0.85

        quantity = max(
            1.0,
            round(base_qty * cycle_factor + random.uniform(-2, 2), 1)
        )

        if random.random() < 0.05:
            continue

        sale = SalesHistory(
            shop_id=product.shop_id,
            product_id=product_id,
            quantity=quantity,
            price=product.price,
            sold_at=sold_at
        )
        sales_to_add.append(sale)

    db.add_all(sales_to_add)
    db.commit()

    logger.info(
        f"Seeded {len(sales_to_add)} sales records for product ID {product_id} (Shop {product.shop_id})."
    )
