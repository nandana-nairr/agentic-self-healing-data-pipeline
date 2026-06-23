print("Step 1: importing...")
from sqlalchemy import create_engine, text
print("Step 2: sqlalchemy imported")

engine = create_engine('postgresql+psycopg2://postgres:postgres@localhost:5432/ecommerce_pipeline')
print("Step 3: engine created")

with engine.begin() as conn:
    conn.execute(text("INSERT INTO raw_orders (order_id, customer_id, order_status, order_purchase_timestamp) VALUES (NULL, 'test-001', 'delivered', NOW())"))
print("Step 4: bad data inserted")

from ge.recovery_engine import ensure_quarantine_tables, repair_orders
print("Step 5: recovery engine imported")

with engine.begin() as conn:
    ensure_quarantine_tables(conn)
print("Step 6: quarantine tables created")

success, actions = repair_orders(engine)
print("Step 7: repair complete")
print("Actions:", actions)