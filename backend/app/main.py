import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import auth, shop, product, order, payment, forecast, alert, chat
from app.websocket_manager import manager


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize FastAPI App
app = FastAPI(
    title="AI Retail Automation & Predictive Business Intelligence System API",
    description="Backend services for OCR extraction, spaCy parsing, Razorpay, and Prophet forecasting.",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from sqlalchemy import text, inspect
from app.config import settings

# Startup Database Auto-Initialization
@app.on_event("startup")
def startup_db_init():
    logger.info(f"Initializing PostgreSQL Database Tables using {settings.DATABASE_URL}...")
    try:
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS owner_name VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS bank_account_holder_name VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS bank_name VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS account_number VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS ifsc_code VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS upi_id VARCHAR;"))
            conn.execute(text("ALTER TABLE shops ADD COLUMN IF NOT EXISTS address VARCHAR;"))
            conn.execute(text("ALTER TABLE shops ADD COLUMN IF NOT EXISTS last_order_number INTEGER DEFAULT 0;"))
            conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS shop_order_number INTEGER;"))
            conn.commit()
        logger.info("PostgreSQL Database tables initialized successfully.")
    except Exception as e:
        logger.warning(f"PostgreSQL Database table check notice: {e}")


# Connect Routers
app.include_router(auth.router)
app.include_router(shop.router)
app.include_router(product.router)
app.include_router(order.router)
app.include_router(payment.router)
app.include_router(forecast.router)
app.include_router(alert.router)
app.include_router(chat.router)


import json

# WebSocket Endpoint for real-time sync
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await manager.connect(user_id, websocket)
    try:
        while True:
            # Maintain active connection and listen for heartbeat
            data = await websocket.receive_text()
            if data == "ping" or '"type":"ping"' in data.replace(" ", ""):
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(user_id, websocket)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "project": "AI-Powered Multimodal Retail Automation and Predictive Business Intelligence System",
        "documentation": "/docs"
    }
