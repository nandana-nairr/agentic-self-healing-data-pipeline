import pandas as pd
from sqlalchemy import create_engine, text
from pathlib import Path

# Resolve path relative to this script, not the current working directory
SCRIPT_DIR = Path(__file__).parent
DATA_FOLDER = SCRIPT_DIR / "olist_data"

DB_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/ecommerce_pipeline"

FILES = {
    "olist_orders_dataset.csv": "raw_orders",
    "olist_order_items_dataset.csv": "raw_order_items",
    "olist_customers_dataset.csv": "raw_customers",
    "olist_products_dataset.csv": "raw_products",
    "olist_sellers_dataset.csv": "raw_sellers",
    "olist_order_payments_dataset.csv": "raw_payments",
    "olist_order_reviews_dataset.csv": "raw_reviews",
    "product_category_name_translation.csv": "raw_category_translation",
}


def main():
    engine = create_engine(DB_URL)

    # Fail fast if Postgres isn't reachable — better than discovering it mid-loop
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"❌ Could not connect to Postgres: {e}")
        return

    total_rows = 0
    failed = []

    # Single transaction-scoped connection, reused for every load
    with engine.begin() as conn:
        for filename, table_name in FILES.items():
            filepath = DATA_FOLDER / filename
            if not filepath.exists():
                print(f"  ⚠️  Not found: {filename}")
                failed.append(filename)
                continue

            try:
                print(f"Loading {filename} → {table_name}...")
                df = pd.read_csv(filepath)
                df.to_sql(
                    table_name,
                    conn,
                    if_exists="replace",
                    index=False,
                    method="multi",      # batches INSERTs — much faster on Postgres
                    chunksize=10_000,    # avoids oversized statements
                )
                total_rows += len(df)
                print(f"  ✅ {len(df):,} rows loaded")
            except Exception as e:
                print(f"  ❌ Failed loading {filename}: {e}")
                failed.append(filename)

    engine.dispose()

    print(f"\n✅ Done. {total_rows:,} total rows across {len(FILES) - len(failed)} tables.")
    if failed:
        print(f"⚠️  {len(failed)} file(s) skipped or failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
