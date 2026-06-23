import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

DB_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/ecommerce_pipeline"

# Known valid values
VALID_ORDER_STATUSES = {
    "delivered", "shipped", "canceled", "unavailable",
    "invoiced", "processing", "created", "approved"
}
VALID_PAYMENT_TYPES = {
    "credit_card", "boleto", "voucher", "debit_card", "not_defined"
}

# Status normalization map — catches common variants
STATUS_NORMALIZATION = {
    "cancelled": "canceled",
    "cancel": "canceled",
    "complete": "delivered",
    "completed": "delivered",
    "shipped_out": "shipped",
}

PAYMENT_NORMALIZATION = {
    "credit": "credit_card",
    "debit": "debit_card",
    "bank_slip": "boleto",
}


def ensure_quarantine_tables(conn):
    """Create quarantine tables if they don't exist."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS quarantine_orders (
            id SERIAL PRIMARY KEY,
            quarantine_reason TEXT,
            quarantine_time TIMESTAMP DEFAULT NOW(),
            order_id TEXT,
            customer_id TEXT,
            order_status TEXT,
            order_purchase_timestamp TEXT,
            order_approved_at TEXT,
            order_delivered_carrier_date TEXT,
            order_delivered_customer_date TEXT,
            order_estimated_delivery_date TEXT
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS quarantine_payments (
            id SERIAL PRIMARY KEY,
            quarantine_reason TEXT,
            quarantine_time TIMESTAMP DEFAULT NOW(),
            order_id TEXT,
            payment_sequential TEXT,
            payment_type TEXT,
            payment_installments TEXT,
            payment_value TEXT
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS repair_log (
            id SERIAL PRIMARY KEY,
            repair_time TIMESTAMP DEFAULT NOW(),
            table_name TEXT,
            failure_type TEXT,
            rows_repaired INTEGER,
            rows_quarantined INTEGER,
            repair_action TEXT,
            success BOOLEAN
        )
    """))


def log_repair(conn, table_name, failure_type, rows_repaired,
               rows_quarantined, repair_action, success):
    conn.execute(text("""
        INSERT INTO repair_log
            (table_name, failure_type, rows_repaired,
             rows_quarantined, repair_action, success)
        VALUES
            (:table_name, :failure_type, :rows_repaired,
             :rows_quarantined, :repair_action, :success)
    """), {
        "table_name": table_name,
        "failure_type": failure_type,
        "rows_repaired": rows_repaired,
        "rows_quarantined": rows_quarantined,
        "repair_action": repair_action,
        "success": success,
    })


def repair_orders(engine):
    """
    Attempt to repair raw_orders.
    Returns: (success: bool, actions_taken: list[str])
    """
    actions = []

    with engine.begin() as conn:
        ensure_quarantine_tables(conn)
        df = pd.read_sql("SELECT * FROM raw_orders", conn)
        original_count = len(df)

        # --- Repair 1: Quarantine null order_id rows ---
        null_order_ids = df["order_id"].isna()
        if null_order_ids.sum() > 0:
            bad = df[null_order_ids].copy()
            bad["quarantine_reason"] = "null order_id"
            bad["quarantine_time"] = datetime.now()
            bad.to_sql("quarantine_orders", conn,
                       if_exists="append", index=False)
            df = df[~null_order_ids]
            msg = f"Quarantined {null_order_ids.sum()} rows with null order_id"
            actions.append(msg)
            print(f"  🔧 {msg}")
            log_repair(conn, "raw_orders", "null_order_id",
                       0, int(null_order_ids.sum()),
                       "quarantine null order_id rows", True)

        # --- Repair 2: Deduplicate order_id ---
        dupes = df.duplicated(subset=["order_id"], keep=False)
        if dupes.sum() > 0:
            before = len(df)
            df = df.sort_values("order_purchase_timestamp",
                                ascending=False, na_position="last")
            df = df.drop_duplicates(subset=["order_id"], keep="first")
            removed = before - len(df)
            msg = f"Deduplicated {removed} duplicate order_id rows"
            actions.append(msg)
            print(f"  🔧 {msg}")
            log_repair(conn, "raw_orders", "duplicate_order_id",
                       int(removed), 0,
                       "keep latest by purchase_timestamp", True)

        # --- Repair 3: Quarantine null customer_id ---
        null_customer = df["customer_id"].isna()
        if null_customer.sum() > 0:
            bad = df[null_customer].copy()
            bad["quarantine_reason"] = "null customer_id"
            bad["quarantine_time"] = datetime.now()
            bad.to_sql("quarantine_orders", conn,
                       if_exists="append", index=False)
            df = df[~null_customer]
            msg = f"Quarantined {null_customer.sum()} rows with null customer_id"
            actions.append(msg)
            print(f"  🔧 {msg}")
            log_repair(conn, "raw_orders", "null_customer_id",
                       0, int(null_customer.sum()),
                       "quarantine null customer_id rows", True)

        # --- Repair 4: Normalize + quarantine invalid order_status ---
        df["order_status"] = df["order_status"].str.strip().str.lower()
        df["order_status"] = df["order_status"].replace(STATUS_NORMALIZATION)
        invalid_status = ~df["order_status"].isin(VALID_ORDER_STATUSES)
        if invalid_status.sum() > 0:
            bad = df[invalid_status].copy()
            bad["quarantine_reason"] = "invalid order_status: " + \
                bad["order_status"].astype(str)
            bad["quarantine_time"] = datetime.now()
            bad.to_sql("quarantine_orders", conn,
                       if_exists="append", index=False)
            df = df[~invalid_status]
            msg = f"Quarantined {invalid_status.sum()} rows with invalid order_status"
            actions.append(msg)
            print(f"  🔧 {msg}")
            log_repair(conn, "raw_orders", "invalid_order_status",
                       0, int(invalid_status.sum()),
                       "normalize known variants, quarantine unknown", True)

        # --- Write repaired data back ---
        if len(actions) > 0:
            conn.execute(text("DELETE FROM raw_orders"))
            df.to_sql("raw_orders", conn,
                      if_exists="append", index=False)
            print(f"  ✅ raw_orders repaired: "
                  f"{original_count} → {len(df)} rows "
                  f"({original_count - len(df)} removed)")

    return True, actions


def repair_payments(engine):
    """
    Attempt to repair raw_payments.
    Returns: (success: bool, actions_taken: list[str])
    """
    actions = []

    with engine.begin() as conn:
        ensure_quarantine_tables(conn)
        df = pd.read_sql("SELECT * FROM raw_payments", conn)
        original_count = len(df)

        # --- Repair 1: Quarantine null order_id ---
        null_order = df["order_id"].isna()
        if null_order.sum() > 0:
            bad = df[null_order].copy()
            bad["quarantine_reason"] = "null order_id"
            bad["quarantine_time"] = datetime.now()
            bad.to_sql("quarantine_payments", conn,
                       if_exists="append", index=False)
            df = df[~null_order]
            msg = f"Quarantined {null_order.sum()} payment rows with null order_id"
            actions.append(msg)
            print(f"  🔧 {msg}")
            log_repair(conn, "raw_payments", "null_order_id",
                       0, int(null_order.sum()),
                       "quarantine null order_id rows", True)

        # --- Repair 2: Quarantine zero/negative payment_value ---
        invalid_value = df["payment_value"] <= 0
        if invalid_value.sum() > 0:
            bad = df[invalid_value].copy()
            bad["quarantine_reason"] = "payment_value <= 0: " + \
                bad["payment_value"].astype(str)
            bad["quarantine_time"] = datetime.now()
            bad.to_sql("quarantine_payments", conn,
                       if_exists="append", index=False)
            df = df[~invalid_value]
            msg = f"Quarantined {invalid_value.sum()} rows with invalid payment_value"
            actions.append(msg)
            print(f"  🔧 {msg}")
            log_repair(conn, "raw_payments", "invalid_payment_value",
                       0, int(invalid_value.sum()),
                       "quarantine zero/negative payment values", True)

        # --- Repair 3: Normalize + quarantine invalid payment_type ---
        df["payment_type"] = df["payment_type"].str.strip().str.lower()
        df["payment_type"] = df["payment_type"].replace(PAYMENT_NORMALIZATION)
        invalid_type = ~df["payment_type"].isin(VALID_PAYMENT_TYPES)
        if invalid_type.sum() > 0:
            bad = df[invalid_type].copy()
            bad["quarantine_reason"] = "invalid payment_type: " + \
                bad["payment_type"].astype(str)
            bad["quarantine_time"] = datetime.now()
            bad.to_sql("quarantine_payments", conn,
                       if_exists="append", index=False)
            df = df[~invalid_type]
            msg = f"Quarantined {invalid_type.sum()} rows with invalid payment_type"
            actions.append(msg)
            print(f"  🔧 {msg}")
            log_repair(conn, "raw_payments", "invalid_payment_type",
                       0, int(invalid_type.sum()),
                       "normalize known variants, quarantine unknown", True)

        # --- Write repaired data back ---
        if len(actions) > 0:
            conn.execute(text("DELETE FROM raw_payments"))
            df.to_sql("raw_payments", conn,
                      if_exists="append", index=False)
            print(f"  ✅ raw_payments repaired: "
                  f"{original_count} → {len(df)} rows "
                  f"({original_count - len(df)} removed)")

    return True, actions


def run_recovery(failed_checks: list[str], engine=None) -> dict:
    """
    Main entry point. Called by the Airflow DAG when GE fails.
    failed_checks: list of check names that failed
    Returns: recovery report dict
    """
    if engine is None:
        engine = create_engine(DB_URL)

    print("\n" + "="*50)
    print("RECOVERY ENGINE — STARTING REPAIR")
    print("="*50)

    report = {
        "attempted": True,
        "orders_repaired": False,
        "payments_repaired": False,
        "actions": [],
        "success": False,
    }

    orders_checks = {
        "order_id not null", "order_id unique",
        "customer_id not null", "order_status valid values",
        "table not empty"
    }
    payments_checks = {
        "payment order_id not null",
        "payment_value positive",
        "payment_type valid"
    }

    failed_set = set(failed_checks)

    if failed_set & orders_checks:
        print("\n🔍 Orders failures detected — attempting repair...")
        success, actions = repair_orders(engine)
        report["orders_repaired"] = success
        report["actions"].extend(actions)

    if failed_set & payments_checks:
        print("\n🔍 Payments failures detected — attempting repair...")
        success, actions = repair_payments(engine)
        report["payments_repaired"] = success
        report["actions"].extend(actions)

    report["success"] = True
    print("\n" + "="*50)
    print(f"RECOVERY ENGINE — COMPLETE")
    print(f"Actions taken: {len(report['actions'])}")
    for a in report["actions"]:
        print(f"  • {a}")
    print("="*50 + "\n")

    return report


if __name__ == "__main__":
    engine = create_engine(DB_URL)

    print("Injecting bad data for testing...")

    with engine.begin() as conn:

        # Null order_id
        conn.execute(text("""
            INSERT INTO raw_orders
            (order_id, customer_id, order_status,
             order_purchase_timestamp)
            VALUES
            (NULL, 'test-customer-001',
             'delivered', NOW())
        """))

        # Duplicate order_id
        conn.execute(text("""
            INSERT INTO raw_orders
            (order_id, customer_id, order_status,
             order_purchase_timestamp)
            VALUES
            ('FAKE-DUPE-001',
             'test-customer-002',
             'delivered', NOW()),
            ('FAKE-DUPE-001',
             'test-customer-003',
             'delivered', NOW())
        """))

        # Invalid status
        conn.execute(text("""
            INSERT INTO raw_orders
            (order_id, customer_id, order_status,
             order_purchase_timestamp)
            VALUES
            ('FAKE-BAD-STATUS-001',
             'test-customer-004',
             'unknown_status',
             NOW())
        """))

    print("✅ Bad data injected")

    failed = [
        "order_id not null",
        "order_id unique",
        "order_status valid values"
    ]

    report = run_recovery(failed, engine)

    print("\nRecovery report:")
    print(report)