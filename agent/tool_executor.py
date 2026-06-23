import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.schemas import RecoveryTool
from ge.recovery_engine import repair_orders, repair_payments
from sqlalchemy import create_engine

DB_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/ecommerce_pipeline"

ORDERS_CHECKS = {
    "order_id not null", "order_id unique",
    "customer_id not null", "order_status valid values",
    "table not empty"
}
PAYMENTS_CHECKS = {
    "payment order_id not null",
    "payment_value positive",
    "payment_type valid"
}


def execute_tool(tool: RecoveryTool, failed_checks: list[str], engine=None) -> dict:
    """
    The LLM decides WHETHER to act (via confidence/escalation) and picks
    a tool name for logging/explanation purposes. The ACTUAL table routing
    is deterministic, based on which GE checks failed — same classification
    logic as recovery_engine.run_recovery(). This prevents an imprecise or
    vague LLM tool choice from misrouting a repair to the wrong table.
    """
    if engine is None:
        engine = create_engine(DB_URL)

    if tool == RecoveryTool.NONE:
        return {"executed": False, "tool": tool.value, "reason": "Agent decided no action needed"}

    if tool == RecoveryTool.RERUN_VALIDATION:
        from ge.validate_data import run_all_validations_with_results
        results = run_all_validations_with_results()
        failed = [name for name, passed in results if not passed]
        return {"executed": True, "tool": tool.value, "success": len(failed) == 0, "failed_checks": failed}

    failed_set = set(failed_checks)
    all_actions = []
    tables_touched = []

    if failed_set & ORDERS_CHECKS:
        success, actions = repair_orders(engine)
        all_actions.extend(actions)
        tables_touched.append("raw_orders")

    if failed_set & PAYMENTS_CHECKS:
        success, actions = repair_payments(engine)
        all_actions.extend(actions)
        tables_touched.append("raw_payments")

    if not tables_touched:
        return {
            "executed": False,
            "tool": tool.value,
            "reason": f"No known table mapping for failed checks: {failed_checks}",
        }

    return {
        "executed": True,
        "tool": tool.value,
        "success": True,
        "tables_touched": tables_touched,
        "actions": all_actions,
    }


if __name__ == "__main__":
    # Manual test — same failed checks the agent would have seen
    test_checks = ["order_id not null", "order_id unique", "order_status valid values"]
    result = execute_tool(RecoveryTool.QUARANTINE_ROWS, test_checks)
    print("EXECUTION RESULT:")
    print(result)