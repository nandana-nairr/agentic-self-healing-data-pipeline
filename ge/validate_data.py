import great_expectations as ge
import pandas as pd
from sqlalchemy import create_engine

DB_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/ecommerce_pipeline"

def validate_orders():
    print("Running Great Expectations validation on raw_orders...")
    
    engine = create_engine(DB_URL)
    df = pd.read_sql_query(
    "SELECT * FROM raw_orders",
    engine
)
    
    # Convert to GE dataframe
    gdf = ge.from_pandas(df)
    
    results = []
    
    # Check 1: order_id is never null
    r1 = gdf.expect_column_values_to_not_be_null("order_id")
    results.append(("order_id not null", r1["success"]))
    
    # Check 2: order_id is unique
    r2 = gdf.expect_column_values_to_be_unique("order_id")
    results.append(("order_id unique", r2["success"]))
    
    # Check 3: customer_id is never null
    r3 = gdf.expect_column_values_to_not_be_null("customer_id")
    results.append(("customer_id not null", r3["success"]))
    
    # Check 4: order_status only contains known values
    r4 = gdf.expect_column_values_to_be_in_set(
        "order_status",
        ["delivered", "shipped", "canceled", "unavailable",
         "invoiced", "processing", "created", "approved"]
    )
    results.append(("order_status valid values", r4["success"]))
    
    # Check 5: dataset is not empty
    r5 = gdf.expect_table_row_count_to_be_between(min_value=1, max_value=None)
    results.append(("table not empty", r5["success"]))
    
    return results

def validate_payments():
    print("Running Great Expectations validation on raw_payments...")
    
    engine = create_engine(DB_URL)
    df = pd.read_sql_query(
    "SELECT * FROM raw_payments",
    engine
    )
    gdf = ge.from_pandas(df)
    
    results = []
    
    # Check 1: order_id not null
    r1 = gdf.expect_column_values_to_not_be_null("order_id")
    results.append(("payment order_id not null", r1["success"]))
    
    # Check 2: payment_value is positive
    r2 = gdf.expect_column_values_to_be_between(
        "payment_value", min_value=0.01, max_value=None
    )
    results.append(("payment_value positive", r2["success"]))
    
    # Check 3: payment_type is valid
    r3 = gdf.expect_column_values_to_be_in_set(
        "payment_type",
        ["credit_card", "boleto", "voucher", "debit_card", "not_defined"]
    )
    results.append(("payment_type valid", r3["success"]))
    
    return results

def run_all_validations():
    print("\n" + "="*50)
    print("GREAT EXPECTATIONS — DATA QUALITY GATES")
    print("="*50 + "\n")
    
    all_results = []
    all_results.extend(validate_orders())
    all_results.extend(validate_payments())
    
    print("\n" + "-"*50)
    print("VALIDATION RESULTS:")
    print("-"*50)
    
    passed = 0
    failed = 0
    
    for check_name, success in all_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}  {check_name}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print("-"*50)
    print(f"  Total: {passed} passed, {failed} failed")
    print("="*50 + "\n")
    
    if failed > 0:
        raise Exception(f"Data quality gate FAILED — {failed} checks failed. Pipeline blocked.")
    else:
        print("✅ All quality gates passed — pipeline can proceed.")
    
    return failed == 0

def run_all_validations_with_results():
    """Returns list of (check_name, passed) tuples instead of raising."""
    engine = create_engine(DB_URL)
    df_orders = pd.read_sql("SELECT * FROM raw_orders", engine)
    df_payments = pd.read_sql("SELECT * FROM raw_payments", engine)

    gdf_orders = ge.from_pandas(df_orders)
    gdf_payments = ge.from_pandas(df_payments)

    results = []
    results.append(("order_id not null", gdf_orders.expect_column_values_to_not_be_null("order_id")["success"]))
    results.append(("order_id unique", gdf_orders.expect_column_values_to_be_unique("order_id")["success"]))
    results.append(("customer_id not null", gdf_orders.expect_column_values_to_not_be_null("customer_id")["success"]))
    results.append(("order_status valid values", gdf_orders.expect_column_values_to_be_in_set("order_status", ["delivered","shipped","canceled","unavailable","invoiced","processing","created","approved"])["success"]))
    results.append(("table not empty", gdf_orders.expect_table_row_count_to_be_between(min_value=1, max_value=None)["success"]))
    results.append(("payment order_id not null", gdf_payments.expect_column_values_to_not_be_null("order_id")["success"]))
    results.append(("payment_value positive", gdf_payments.expect_column_values_to_be_between("payment_value", min_value=0.01, max_value=None)["success"]))
    results.append(("payment_type valid", gdf_payments.expect_column_values_to_be_in_set("payment_type", ["credit_card","boleto","voucher","debit_card","not_defined"])["success"]))

    return results

if __name__ == "__main__":
    run_all_validations()