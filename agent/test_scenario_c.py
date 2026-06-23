import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.schemas import RecoveryDecision, FailureType, RecoveryTool
from agent.orchestrator_v1 import apply_decision
from agent.recovery_memory import create_memory_tables, log_recovery_decision
from agent.tool_executor import execute_tool

create_memory_tables()
start = time.time()


def validate_fn_still_failing():
    return [
        ("order_id not null", True),
        ("order_id unique", True),
        ("order_status valid values", True),
        ("table not empty", False),
    ]


decision = RecoveryDecision(
    failure_type=FailureType.UNKNOWN,
    selected_tool=RecoveryTool.QUARANTINE_ROWS,
    confidence=0.90,
    reasoning="[TEST] High-confidence — repair runs but simulated failure remains",
    should_escalate=False,
)
print(f"Hand-built decision (NO LLM CALL): {decision}\n")

failed_checks = ["order_id not null", "order_id unique", "order_status valid values"]

report = apply_decision(
    decision,
    failed_checks,
    execute_fn=execute_tool,
    validate_fn=validate_fn_still_failing,
)
elapsed = time.time() - start

log_recovery_decision(
    final_status=report["status"],
    failed_checks=failed_checks,
    failure_type=decision.failure_type.value,
    confidence=decision.confidence,
    reasoning=decision.reasoning,
    selected_tool=decision.selected_tool.value,
    action_taken=str(report.get("execution", {}).get("actions", [])),
    validation_passed=False,
    execution_time_seconds=round(elapsed, 2),
    is_test_run=True,
)

print("\n" + "=" * 60)
print("SCENARIO C RESULT")
print("=" * 60)
print(report)

assert report["status"] == "repair_failed"
assert "table not empty" in report["still_failing"]
print("\n✅ SCENARIO C PASSED + LOGGED")