import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.schemas import RecoveryDecision, FailureType, RecoveryTool
from agent.orchestrator_v1 import apply_decision
from agent.recovery_memory import create_memory_tables, log_recovery_decision

create_memory_tables()
start = time.time()


def poisoned_execute_fn(tool, failed_checks):
    raise AssertionError("SAFETY VIOLATION: execute_fn was called despite low confidence.")


def poisoned_validate_fn():
    raise AssertionError("SAFETY VIOLATION: validate_fn was called before any repair.")


decision = RecoveryDecision(
    failure_type=FailureType.UNKNOWN,
    selected_tool=RecoveryTool.QUARANTINE_ROWS,
    confidence=0.40,
    reasoning="[TEST] Manually constructed low-confidence decision for Scenario B",
    should_escalate=False,
)
print(f"Hand-built decision (NO LLM CALL): {decision}\n")

failed_checks = ["order_id not null", "order_id unique"]

report = apply_decision(
    decision,
    failed_checks,
    execute_fn=poisoned_execute_fn,
    validate_fn=poisoned_validate_fn,
)
elapsed = time.time() - start

log_recovery_decision(
    final_status=report["status"],
    failed_checks=failed_checks,
    failure_type=decision.failure_type.value,
    confidence=decision.confidence,
    reasoning=decision.reasoning,
    selected_tool=decision.selected_tool.value,
    action_taken="none — escalated before execution",
    validation_passed=False,
    execution_time_seconds=round(elapsed, 2),
    is_test_run=True,
)

print("\n" + "=" * 60)
print("SCENARIO B RESULT")
print("=" * 60)
print(report)

assert report["status"] == "escalated", f"Expected 'escalated', got '{report['status']}'"
print("\n✅ SCENARIO B PASSED + LOGGED")