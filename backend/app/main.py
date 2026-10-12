import logging
import json
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db, SessionLocal
from app.routers import auth, shop, product, order, payment, forecast, alert, chat
from app.routers.auth import verify_token_string
from app.websocket_manager import manager
from app.config import settings

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

origins = [
    o.strip().rstrip("/")
    for o in settings.CORS_ORIGINS.split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


async def handle_ws_connection(websocket: WebSocket, token: Optional[str] = None):
    auth_user = None
    if token:
        db = SessionLocal()
        try:
            auth_user = verify_token_string(token, db)
        finally:
            db.close()

    if not auth_user:
        logger.warning("Rejecting unauthenticated WebSocket connection. Valid JWT token required.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    effective_user_id = auth_user.id
    await manager.connect(effective_user_id, websocket)
    try:
        while True:
            # Maintain active connection and listen for heartbeat
            data = await websocket.receive_text()
            if data == "ping" or '"type":"ping"' in data.replace(" ", ""):
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(effective_user_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for user {effective_user_id}: {e}")
        manager.disconnect(effective_user_id, websocket)

# WebSocket Endpoints for real-time sync
@app.websocket("/ws")
async def websocket_endpoint_token(websocket: WebSocket, token: Optional[str] = Query(None)):
    await handle_ws_connection(websocket, token)

@app.websocket("/ws/{user_id}")
async def websocket_endpoint_user(websocket: WebSocket, user_id: str, token: Optional[str] = Query(None)):
    await handle_ws_connection(websocket, token)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "project": "AI-Powered Multimodal Retail Automation and Predictive Business Intelligence System",
        "documentation": "/docs"
    }

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    return {
        "status": "online" if db_status == "healthy" else "degraded",
        "database": db_status,
        "environment": settings.ENVIRONMENT,
        "websocket_active_users": len(manager.active_connections)
    }
