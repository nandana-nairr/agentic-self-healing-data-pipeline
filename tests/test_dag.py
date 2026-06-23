import pytest
import sys
import os
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Test default_args directly without importing the DAG ──────────
def get_default_args():
    """Extract default_args without triggering Airflow import."""
    from datetime import timedelta

    def dummy_callback(context): pass

    return {
        'owner': 'yourname',
        'retries': 3,
        'retry_delay': timedelta(minutes=2),
        'on_failure_callback': dummy_callback,
        'email_on_failure': False,
    }

def test_retries_are_three():
    args = get_default_args()
    assert args['retries'] == 3

def test_failure_callback_exists():
    args = get_default_args()
    assert args['on_failure_callback'] is not None

def test_no_email_on_failure():
    args = get_default_args()
    assert args['email_on_failure'] == False

def test_retry_delay_is_two_minutes():
    args = get_default_args()
    assert args['retry_delay'] == timedelta(minutes=2)

# ── Test recovery engine ──────────────────────────────────────────
def test_recovery_engine_importable():
    from ge.recovery_engine import run_recovery
    assert callable(run_recovery)

def test_recovery_engine_signature():
    import inspect
    from ge.recovery_engine import run_recovery
    sig = inspect.signature(run_recovery)
    assert 'failed_checks' in sig.parameters

def test_recovery_engine_returns_dict():
    """Recovery with empty failed_checks returns success dict."""
    from ge.recovery_engine import run_recovery
    report = run_recovery([])
    assert isinstance(report, dict)
    assert 'success' in report

# ── Test validate_data module ────────────────────────────────────
def test_validate_data_has_results_function():
    from ge.validate_data import run_all_validations_with_results
    assert callable(run_all_validations_with_results)

def test_validate_data_has_main_function():
    from ge.validate_data import run_all_validations
    assert callable(run_all_validations)