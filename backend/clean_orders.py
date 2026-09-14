import os
import sys
from sqlalchemy import text

# Ensure backend folder is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database import engine, SessionLocal, Base
from app.models import Order, OrderItem, User, Shop, Product, Alert, ChatMessage, SalesHistory

def clean_orders_and_reset_sequence():
    print("Connecting to PostgreSQL database to clean existing test orders...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Count existing orders and items
        order_count = db.query(Order).count()
        item_count = db.query(OrderItem).count()
        print(f"Found {order_count} orders and {item_count} order items to delete.")

        # Delete order_items and orders
        db.query(OrderItem).delete(synchronize_session=False)
        db.query(Order).delete(synchronize_session=False)
        db.commit()

        # Reset sequence orders_id_seq to 1
        with engine.connect() as conn:
            conn.execute(text("ALTER SEQUENCE orders_id_seq RESTART WITH 1;"))
            conn.commit()

        print("Successfully deleted all test orders and reset orders_id_seq to 1.")

        # Verify preserved entities
        user_count = db.query(User).count()
        shop_count = db.query(Shop).count()
        prod_count = db.query(Product).count()
        chat_count = db.query(ChatMessage).count()
        alert_count = db.query(Alert).count()

        print(f"Preserved data check: Users={user_count}, Shops={shop_count}, Products={prod_count}, ChatMessages={chat_count}, Alerts={alert_count}.")

    except Exception as e:
        db.rollback()
        print(f"Error during order cleanup: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    clean_orders_and_reset_sequence()
