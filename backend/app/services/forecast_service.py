import datetime
import random
import os
import joblib
import logging

from sqlalchemy.orm import Session
from app.models import SalesHistory, Product

logger = logging.getLogger(__name__)


# ============================================================
# TRAINED PROPHET MODELS
# ============================================================

MODEL_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "ml_models",
        "prophet_final_models.pkl"
    )
)

_prophet_models = None


def load_prophet_models():
    """
    Load the already-trained Prophet models.
    Models are loaded once and reused.
    """

    global _prophet_models

    if _prophet_models is None:

        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Prophet model file not found: {MODEL_PATH}"
            )

        logger.info(
            f"Loading Prophet models from: {MODEL_PATH}"
        )

        _prophet_models = joblib.load(MODEL_PATH)

        logger.info(
            f"Loaded {len(_prophet_models)} trained Prophet models."
        )

    return _prophet_models


def get_product_model(product_id: int):
    """
    Get the already-trained Prophet model for a product.
    """

    models = load_prophet_models()

    if product_id in models:
        return models[product_id]

    if str(product_id) in models:
        return models[str(product_id)]

    return None


# ============================================================
# FORECAST GENERATION
# ============================================================

def generate_forecast(
    db: Session,
    product_id: int,
    periods: int = 7
) -> list:
    """
    Generate future demand using the already-trained Prophet model.

    Supported:
        7 days
        14 days
        30 days
    """

    # --------------------------------------------------------
    # Validate forecast period
    # --------------------------------------------------------

    if periods not in [7, 14, 30]:
        raise ValueError(
            "Forecast period must be 7, 14, or 30 days."
        )

    # --------------------------------------------------------
    # Check product exists in database
    # --------------------------------------------------------

    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:
        logger.warning(
            f"Product ID {product_id} not found."
        )
        return []

    # --------------------------------------------------------
    # Load trained model
    # --------------------------------------------------------

    try:

        model = get_product_model(product_id)

    except Exception as e:

        logger.error(
            f"Failed to load Prophet models: {e}"
        )

        return []

    if model is None:

        logger.warning(
            f"No trained Prophet model found for "
            f"product ID {product_id}."
        )

        return []

    # --------------------------------------------------------
    # Generate future dates
    # --------------------------------------------------------

    try:

        future = model.make_future_dataframe(
            periods=periods,
            freq="D",
            include_history=False
        )

        forecast = model.predict(future)

        forecast_results = []

        for _, row in forecast.iterrows():

            yhat = max(
                0.0,
                float(row["yhat"])
            )

            yhat_lower = max(
                0.0,
                float(row["yhat_lower"])
            )

            yhat_upper = max(
                0.0,
                float(row["yhat_upper"])
            )

            forecast_results.append({
                "ds": row["ds"].strftime("%Y-%m-%d"),
                "yhat": round(yhat, 2),
                "yhat_lower": round(yhat_lower, 2),
                "yhat_upper": round(yhat_upper, 2)
            })

        logger.info(
            f"Generated {periods}-day forecast for "
            f"product ID {product_id}"
        )

        return forecast_results

    except Exception as e:

        logger.exception(
            f"Error generating forecast for "
            f"product ID {product_id}: {e}"
        )

        return []

def get_predicted_demand(
    db: Session,
    product_id: int,
    periods: int = 7
) -> float:
    """
    Return total predicted demand for the next N days.
    """

    forecast = generate_forecast(
        db=db,
        product_id=product_id,
        periods=periods
    )

    if not forecast:
        return 0.0

    predicted_demand = sum(
        item["yhat"]
        for item in forecast
    )

    return round(predicted_demand, 2)

# ============================================================
# MODEL COUNT
# ============================================================

def get_model_count() -> int:
    """
    Return number of trained Prophet models.
    """

    models = load_prophet_models()

    return len(models)


# ============================================================
# EXISTING SALES SEEDING
# ============================================================

def seed_historical_sales(
    db: Session,
    product_id: int,
    days: int = 90
):
    """
    Seeds database with realistic historical sales for a product.
    Includes weekly cycles and random noise.
    """

    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:
        return

    logger.info(
        f"Seeding historical sales data for product: "
        f"{product.name}..."
    )

    start_date = (
        datetime.datetime.utcnow()
        - datetime.timedelta(days=days)
    )

    base_qty = (
        15.0
        if product.price < 50
        else (
            5.0
            if product.price < 150
            else 2.0
        )
    )

    sales_to_add = []

    for day_idx in range(days):

        sold_at = (
            start_date
            + datetime.timedelta(days=day_idx)
        )

        day_of_week = sold_at.weekday()

        cycle_factor = (
            1.4
            if day_of_week in [4, 5, 6]
            else 0.85
        )

        quantity = max(
            1.0,
            round(
                base_qty * cycle_factor
                + random.uniform(-2, 2),
                1
            )
        )

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

    logger.info(
        f"Seeded {len(sales_to_add)} sales records "
        f"for product ID {product_id}."
    )