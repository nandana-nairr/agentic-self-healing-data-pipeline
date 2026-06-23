"""
agent/memory.py

PostgreSQL-backed memory layer for the recovery agent.
Logs every decision, provides historical metrics, and surfaces
recovery statistics for portfolio demonstration and future
confidence calibration.

Design principle: this module is append-only. It never modifies
or deletes recovery history. Every run — live or test — is recorded
permanently with a full audit trail.
"""
import os
import sys
import uuid
from datetime import datetime

from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/ecommerce_pipeline"


def get_engine():
    return create_engine(DB_URL)


# ─────────────────────────────────────────────────────────
# TABLE CREATION
# ─────────────────────────────────────────────────────────

def create_memory_tables(engine=None):
    """
    Creates agent_recovery_log if it does not already exist.
    Safe to call on every startup — idempotent.
    """
    if engine is None:
        engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS agent_recovery_log (
                id                   SERIAL PRIMARY KEY,
                run_id               TEXT NOT NULL,
                timestamp            TIMESTAMP NOT NULL DEFAULT NOW(),
                failure_type         TEXT,
                failed_checks        TEXT,
                confidence           FLOAT,
                reasoning            TEXT,
                selected_tool        TEXT,
                action_taken         TEXT,
                final_status         TEXT NOT NULL,
                validation_passed    BOOLEAN,
                execution_time_seconds FLOAT,
                is_test_run          BOOLEAN NOT NULL DEFAULT FALSE
            )
        """))

    print("✅ agent_recovery_log table ready.")


# ─────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────

def log_recovery_decision(
    final_status: str,
    failed_checks: list[str] = None,
    failure_type: str = None,
    confidence: float = None,
    reasoning: str = None,
    selected_tool: str = None,
    action_taken: str = None,
    validation_passed: bool = None,
    execution_time_seconds: float = None,
    is_test_run: bool = False,
    engine=None,
) -> str:
    """
    Writes one row to agent_recovery_log.
    Returns the run_id so callers can cross-reference with repair_log.
    """
    if engine is None:
        engine = get_engine()

    run_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO agent_recovery_log (
                run_id, timestamp, failure_type, failed_checks,
                confidence, reasoning, selected_tool, action_taken,
                final_status, validation_passed,
                execution_time_seconds, is_test_run
            ) VALUES (
                :run_id, :timestamp, :failure_type, :failed_checks,
                :confidence, :reasoning, :selected_tool, :action_taken,
                :final_status, :validation_passed,
                :execution_time_seconds, :is_test_run
            )
        """), {
            "run_id": run_id,
            "timestamp": datetime.now(),
            "failure_type": failure_type,
            "failed_checks": ", ".join(failed_checks) if failed_checks else None,
            "confidence": confidence,
            "reasoning": reasoning,
            "selected_tool": selected_tool,
            "action_taken": action_taken,
            "final_status": final_status,
            "validation_passed": validation_passed,
            "execution_time_seconds": execution_time_seconds,
            "is_test_run": is_test_run,
        })

    return run_id


# ─────────────────────────────────────────────────────────
# RETRIEVAL
# ─────────────────────────────────────────────────────────

def get_recent_runs(limit: int = 10, engine=None) -> list[dict]:
    """Returns the most recent N runs, newest first."""
    if engine is None:
        engine = get_engine()

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT run_id, timestamp, failure_type, confidence,
                   selected_tool, final_status, validation_passed,
                   execution_time_seconds, is_test_run
            FROM agent_recovery_log
            ORDER BY timestamp DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()

    return [dict(r._mapping) for r in rows]


def get_agent_metrics(engine=None) -> dict:
    """
    Computes aggregate performance metrics across all logged runs.
    Separates production runs from test runs.
    """
    if engine is None:
        engine = get_engine()

    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT
                COUNT(*)                                            AS total_runs,
                COUNT(*) FILTER (WHERE NOT is_test_run)            AS production_runs,
                COUNT(*) FILTER (WHERE is_test_run)                AS test_runs,
                COUNT(*) FILTER (WHERE final_status = 'repaired')  AS repaired_runs,
                COUNT(*) FILTER (WHERE final_status = 'escalated') AS escalated_runs,
                COUNT(*) FILTER (WHERE final_status = 'repair_failed') AS repair_failed_runs,
                COUNT(*) FILTER (WHERE final_status = 'no_failures')   AS no_failure_runs,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE final_status = 'repaired')
                    / NULLIF(COUNT(*) FILTER (WHERE final_status != 'no_failures'), 0),
                    1
                )                                                   AS repair_success_rate,
                ROUND(AVG(confidence)::numeric, 3)                  AS average_confidence,
                ROUND(AVG(execution_time_seconds)::numeric, 2)      AS avg_execution_seconds
            FROM agent_recovery_log
        """)).fetchone()

    return dict(row._mapping)


def get_failure_statistics(engine=None) -> dict:
    """
    Breaks down failures by type and tool selection frequency.
    Supports root-cause analysis and future confidence calibration.
    """
    if engine is None:
        engine = get_engine()

    with engine.connect() as conn:
        failure_rows = conn.execute(text("""
            SELECT failure_type, COUNT(*) AS count
            FROM agent_recovery_log
            WHERE failure_type IS NOT NULL
            GROUP BY failure_type
            ORDER BY count DESC
        """)).fetchall()

        tool_rows = conn.execute(text("""
            SELECT selected_tool, COUNT(*) AS count
            FROM agent_recovery_log
            WHERE selected_tool IS NOT NULL
            GROUP BY selected_tool
            ORDER BY count DESC
        """)).fetchall()

        confidence_by_type = conn.execute(text("""
            SELECT failure_type,
                   ROUND(AVG(confidence)::numeric, 3) AS avg_confidence,
                   ROUND(
                       100.0 * COUNT(*) FILTER (WHERE final_status = 'repaired')
                       / NULLIF(COUNT(*), 0),
                       1
                   ) AS success_rate_pct
            FROM agent_recovery_log
            WHERE failure_type IS NOT NULL
            GROUP BY failure_type
            ORDER BY failure_type
        """)).fetchall()

    return {
        "failure_type_counts": [dict(r._mapping) for r in failure_rows],
        "tool_usage_counts": [dict(r._mapping) for r in tool_rows],
        "confidence_by_type": [dict(r._mapping) for r in confidence_by_type],
    }


# ─────────────────────────────────────────────────────────
# SELF-TEST
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = get_engine()
    create_memory_tables(engine)
    print("\nTable created. Writing a self-test row...")

    run_id = log_recovery_decision(
        final_status="repaired",
        failed_checks=["order_id not null", "order_id unique"],
        failure_type="duplicate_orders",
        confidence=0.95,
        reasoning="[SELF-TEST] Memory module smoke test",
        selected_tool="repair_duplicate_orders",
        action_taken="repair_orders",
        validation_passed=True,
        execution_time_seconds=1.23,
        is_test_run=True,
        engine=engine,
    )
    print(f"Row written with run_id: {run_id}")

    recent = get_recent_runs(limit=5, engine=engine)
    print(f"\nLast {len(recent)} run(s):")
    for r in recent:
        print(f"  [{r['timestamp']}] {r['final_status']} "
              f"(confidence={r['confidence']}, test={r['is_test_run']})")

    metrics = get_agent_metrics(engine=engine)
    print(f"\nMetrics snapshot: {metrics}")

    print("\n✅ Memory module self-test complete.")