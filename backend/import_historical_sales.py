import os
import sys
import io
import time
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, SessionLocal
from app.models import Shop, Product, SalesHistory
from sqlalchemy import text

def import_historical_data():
    print("=" * 60)
    print("STARTING HISTORICAL SALES IMPORT FOR BOTH SHOPS")
    print("=" * 60)

    csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sales_data_1year.csv"))
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Historical sales file not found at: {csv_path}")

    db = SessionLocal()
    try:
        # 1. Verify shops
        shop_hebbar = db.query(Shop).filter(Shop.id == 2).first()
        shop_fresh = db.query(Shop).filter(Shop.id == 3).first()

        if not shop_hebbar or not shop_fresh:
            raise ValueError(f"Required shops not found. Shop 2: {shop_hebbar}, Shop 3: {shop_fresh}")

        print(f"Shop 1: ID={shop_hebbar.id}, Name='{shop_hebbar.name}'")
        print(f"Shop 2: ID={shop_fresh.id}, Name='{shop_fresh.name}'")

        # 2. Check existing 1-year historical records for idempotency
        s2_existing = db.query(SalesHistory).filter(
            SalesHistory.shop_id == 2,
            SalesHistory.sold_at >= '2025-08-18',
            SalesHistory.sold_at <= '2026-08-18'
        ).count()

        s3_existing = db.query(SalesHistory).filter(
            SalesHistory.shop_id == 3,
            SalesHistory.sold_at >= '2025-08-18',
            SalesHistory.sold_at <= '2026-08-18'
        ).count()

        print(f"Existing historical records: Shop 2 (Hebbar) = {s2_existing}, Shop 3 (FreshSupermart) = {s3_existing}")

        # Map Shop 2 products by name (case-insensitive)
        s2_products = db.query(Product).filter(Product.shop_id == 2).all()
        s2_map = {p.name.strip().lower(): p.id for p in s2_products}
        print(f"Loaded {len(s2_map)} products for Shop 2 (Hebbar General Stores)")

        # Map Shop 3 products (42 items)
        s3_products = db.query(Product).filter(Product.shop_id == 3).all()
        s3_special_map = {
            'sona masuri rice': 'sona masoori rice',
            'nandini milk': 'cow milk',
            'byadagi dried chillies': 'dry red chilli',
            'fresh coconut': 'coconut',
            'idli / dosa batter': 'idli rice',
            'maddur vada': 'instant vada',
            'bakery rusk': 'rusk',
            'dust tea powder': 'tea powder',
            'mysore sandal soap': 'soap',
            'coconut hair oil': 'coconut oil',
            'shikakai powder': 'soap',
            'agarbatti': 'matchbox',
            'puja oil': 'sesame oil',
            'dishwash bars': 'dishwash bar',
            'ginger-garlic paste': 'ginger garlic paste',
            'bread': 'white bread',
            'congress kadlekai': 'roasted peanuts',
        }

        s3_target_to_prod = {}
        for p in s3_products:
            base = p.name.split('(')[0].strip().lower()
            target = s3_special_map.get(base) or base
            s3_target_to_prod[target] = p

        print(f"Loaded {len(s3_target_to_prod)} product mappings for Shop 3 (FreshSupermart)")

    finally:
        db.close()

    # Load CSV
    print(f"Reading dataset: {csv_path}...")
    t0 = time.time()
    df = pd.read_csv(csv_path)
    print(f"Read {len(df)} rows in {time.time() - t0:.2f}s")

    # Format datetime strings to ISO YYYY-MM-DD HH:MM:SS
    print("Formatting timestamps...")
    df['dt'] = pd.to_datetime(df['sold_at'], format='%d-%m-%Y %H:%M')
    df['dt_str'] = df['dt'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df['pname_lower'] = df['product_name'].str.strip().str.lower()

    raw_conn = engine.raw_connection()
    cursor = raw_conn.cursor()

    try:
        # Import for Shop 2 if needed
        if s2_existing < 10000:
            print("Preparing data stream for Shop 2 (Hebbar General Stores)...")
            s2_pids = df['pname_lower'].map(s2_map)
            valid_mask = s2_pids.notna()

            s2_df = pd.DataFrame({
                'shop_id': 2,
                'product_id': s2_pids[valid_mask].astype(int),
                'quantity': df.loc[valid_mask, 'quantity'],
                'price': df.loc[valid_mask, 'price'],
                'sold_at': df.loc[valid_mask, 'dt_str']
            })

            print(f"Streaming {len(s2_df)} records for Shop 2 into PostgreSQL...")
            t1 = time.time()
            sio = io.StringIO()
            s2_df.to_csv(sio, index=False, header=False)
            sio.seek(0)
            cursor.copy_expert("COPY sales_history (shop_id, product_id, quantity, price, sold_at) FROM STDIN WITH CSV", sio)
            raw_conn.commit()
            print(f"Successfully imported {len(s2_df)} records for Shop 2 in {time.time() - t1:.2f}s!")
        else:
            print(f"Shop 2 already has {s2_existing} records. Skipping import for idempotency.")

        # Import for Shop 3 if needed
        if s3_existing < 1000:
            print("Preparing data stream for Shop 3 (FreshSupermart)...")
            s3_rows = []
            for target_name, prod in s3_target_to_prod.items():
                subset = df[df['pname_lower'] == target_name]
                if not subset.empty:
                    s3_sub = pd.DataFrame({
                        'shop_id': 3,
                        'product_id': prod.id,
                        'quantity': subset['quantity'],
                        'price': prod.price,
                        'sold_at': subset['dt_str']
                    })
                    s3_rows.append(s3_sub)

            if s3_rows:
                s3_df = pd.concat(s3_rows, ignore_index=True)
                print(f"Streaming {len(s3_df)} records for Shop 3 into PostgreSQL...")
                t2 = time.time()
                sio3 = io.StringIO()
                s3_df.to_csv(sio3, index=False, header=False)
                sio3.seek(0)
                cursor.copy_expert("COPY sales_history (shop_id, product_id, quantity, price, sold_at) FROM STDIN WITH CSV", sio3)
                raw_conn.commit()
                print(f"Successfully imported {len(s3_df)} records for Shop 3 in {time.time() - t2:.2f}s!")
        else:
            print(f"Shop 3 already has {s3_existing} records. Skipping import for idempotency.")

    finally:
        cursor.close()
        raw_conn.close()

    # Final verification
    db = SessionLocal()
    try:
        final_s2 = db.query(SalesHistory).filter(SalesHistory.shop_id == 2).count()
        final_s3 = db.query(SalesHistory).filter(SalesHistory.shop_id == 3).count()
        print("=" * 60)
        print("IMPORT COMPLETED SUCCESSFULLY!")
        print(f"Shop 2 (Hebbar General Stores): {final_s2} total records")
        print(f"Shop 3 (FreshSupermart):        {final_s3} total records")
        print("=" * 60)
    finally:
        db.close()

if __name__ == "__main__":
    import_historical_data()
