import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import auth, shop, product, order, payment, forecast, alert
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

from sqlalchemy import text

# Startup Database Auto-Initialization
@app.on_event("startup")
def startup_db_init():
    logger.info("Initializing PostgreSQL Database Tables...")
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS owner_name VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS bank_account_holder_name VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS bank_name VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS account_number VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS ifsc_code VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS upi_id VARCHAR;"))
            conn.execute(text("ALTER TABLE shops ADD COLUMN IF NOT EXISTS address VARCHAR;"))
            conn.commit()
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.critical(f"Database table initialization failed: {e}")
        logger.critical("Please ensure your PostgreSQL server is running and database configuration in .env is correct.")

# Connect Routers
app.include_router(auth.router)
app.include_router(shop.router)
app.include_router(product.router)
app.include_router(order.router)
app.include_router(payment.router)
app.include_router(forecast.router)
app.include_router(alert.router)

# WebSocket Endpoint for real-time sync
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await manager.connect(user_id, websocket)
    try:
        while True:
            # Maintain active connection and listen for heartbeat
            data = await websocket.receive_text()
            # Echo or process heartbeat if required
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
