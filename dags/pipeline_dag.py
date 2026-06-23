from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
sys.path.insert(0, '/opt/airflow')

# --- Callbacks ---
def on_failure_alert(context):
    print(f"❌ TASK FAILED: {context['task_instance'].task_id}")
    print(f"   DAG: {context['task_instance'].dag_id}")
    print(f"   Execution time: {context['execution_date']}")
    print(f"   Log URL: {context['task_instance'].log_url}")
    # Phase 6: replace print with Slack/email alert

# --- Default args — this is where self-healing lives ---
default_args = {
    'owner': 'yourname',
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
    'on_failure_callback': on_failure_alert,
    'email_on_failure': False,
}

# --- Task functions ---
def ingest_task(**kwargs):
    from ingestion.ingest_nyc_taxi import ingest
    # Using Olist later — for now test with taxi data
    print("Starting ingestion...")
    # result = ingest(2024, 1)
    # print(f"Ingested: {result}")
    print("Ingestion complete ✅")

def validate_task(**kwargs):
    import sys
    sys.path.insert(0, '/opt/airflow')
    sys.path.insert(0, 'C:\\Users\\nanda\\OneDrive\\Desktop\\projects\\self-healing-data-pipeline')

    from ge.validate_data import run_all_validations_with_results
    from ge.recovery_engine import run_recovery

    print("Running Great Expectations quality gates...")
    results = run_all_validations_with_results()

    failed_checks = [name for name, passed in results if not passed]

    if not failed_checks:
        print("✅ All quality gates passed — pipeline proceeding.")
        return

    print(f"⚠️ {len(failed_checks)} checks failed: {failed_checks}")
    print("🔧 Invoking recovery engine...")

    report = run_recovery(failed_checks)

    if not report['success']:
        raise Exception(f"Recovery engine failed — manual intervention needed. Report: {report}")

    print("🔄 Re-running validation after repair...")
    results2 = run_all_validations_with_results()
    still_failing = [name for name, passed in results2 if not passed]

    if still_failing:
        raise Exception(f"Post-repair validation failed: {still_failing}")

    print("✅ Recovery successful — all checks passing. Pipeline continuing.")
    
def transform_task(**kwargs):
    print("Running dbt models...")
    # dbt comes in Phase 3
    print("Transformation complete ✅")

# --- DAG definition ---
with DAG(
    dag_id='ecommerce_pipeline',
    default_args=default_args,
    description='Self-healing ELT pipeline for e-commerce analytics',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['ecommerce', 'self-healing'],
) as dag:

    ingest = PythonOperator(
        task_id='ingest_raw_data',
        python_callable=ingest_task,
    )

    validate = PythonOperator(
        task_id='validate_data_quality',
        python_callable=validate_task,
    )

    transform = PythonOperator(
        task_id='transform_with_dbt',
        python_callable=transform_task,
    )

    # Task dependencies — the pipeline order
    ingest >> validate >> transform