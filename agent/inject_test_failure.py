from sqlalchemy import create_engine, text

DB_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/ecommerce_pipeline"


def inject_bad_data():
    engine = create_engine(DB_URL)

    with engine.begin() as conn:
        # Null order_id
        conn.execute(text("""
            INSERT INTO raw_orders
            (order_id, customer_id, order_status, order_purchase_timestamp)
            VALUES (NULL, 'test-customer-001', 'delivered', NOW())
        """))

        # Duplicate order_id
        conn.execute(text("""
            INSERT INTO raw_orders
            (order_id, customer_id, order_status, order_purchase_timestamp)
            VALUES
            ('FAKE-DUPE-001', 'test-customer-002', 'delivered', NOW()),
            ('FAKE-DUPE-001', 'test-customer-003', 'delivered', NOW())
        """))

        # Invalid status
        conn.execute(text("""
            INSERT INTO raw_orders
            (order_id, customer_id, order_status, order_purchase_timestamp)
            VALUES ('FAKE-BAD-STATUS-001', 'test-customer-004', 'unknown_status', NOW())
        """))

    print("✅ Bad data injected — NOT repaired. Ready for agent to diagnose.")


if __name__ == "__main__":
    inject_bad_data()