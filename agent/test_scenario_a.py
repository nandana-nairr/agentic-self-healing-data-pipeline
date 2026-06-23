import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.schemas import RecoveryDecision, FailureType, RecoveryTool
from agent.orchestrator_v1 import apply_decision
from agent.recovery_memory import create_memory_tables, log_recovery_decision
from ge.validate_data import run_all_validations_with_results

create_memory_tables()
start = time.time()

results = run_all_validations_with_results()
failed_checks = [name for name, passed in results if not passed]
print(f"Failed checks before repair: {failed_checks}")

if not failed_checks:
    print("No failing checks found. Run agent/inject_test_failure.py first.")
    sys.exit(0)

decision = RecoveryDecision(
    failure_type=FailureType.UNKNOWN,
    selected_tool=RecoveryTool.QUARANTINE_ROWS,
    confidence=0.95,
    reasoning="[TEST] Manually constructed high-confidence decision for Scenario A",
    should_escalate=False,
)
print(f"\nHand-built decision (NO LLM CALL): {decision}\n")

report = apply_decision(decision, failed_checks)
elapsed = time.time() - start

log_recovery_decision(
    final_status=report["status"],
    failed_checks=failed_checks,
    failure_type=decision.failure_type.value,
    confidence=decision.confidence,
    reasoning=decision.reasoning,
    selected_tool=decision.selected_tool.value,
    action_taken=str(report.get("execution", {}).get("actions", [])),
    validation_passed=(report["status"] == "repaired"),
    execution_time_seconds=round(elapsed, 2),
    is_test_run=True,
)

print("\n" + "=" * 60)
print("SCENARIO A RESULT")
print("=" * 60)
print(report)

assert report["status"] == "repaired", f"Expected 'repaired', got '{report['status']}'"
print("\n✅ SCENARIO A PASSED + LOGGED")