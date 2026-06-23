import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.schemas import RecoveryDecision, RecoveryTool
from agent.tool_executor import execute_tool
from ge.validate_data import run_all_validations_with_results

load_dotenv()

CONFIDENCE_THRESHOLD = 0.75
WORKING_MODEL = "cohere/north-mini-code:free"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)


def build_failure_report(failed_checks: list[str]) -> str:
    return "Great Expectations Validation Failure Report:\n" + "\n".join(
        f"- Check: {check}\n  Status: FAILED" for check in failed_checks
    )


def ask_agent(failure_report: str) -> RecoveryDecision:
    """The ONLY function in this file that makes a real LLM call."""
    prompt = f"""You are a DataOps recovery agent. Analyze this Great Expectations
failure report and decide how to respond.

FAILURE REPORT:
{failure_report}

You may ONLY select one of these tools:
repair_duplicate_orders, repair_null_orders, repair_invalid_status,
quarantine_rows, rerun_validation, none

Respond with ONLY valid JSON, no markdown fences, no explanation outside
the JSON, matching exactly this shape:
{{
  "failure_type": "duplicate_orders" | "null_orders" | "invalid_status" | "unknown",
  "selected_tool": "repair_duplicate_orders" | "repair_null_orders" | "repair_invalid_status" | "quarantine_rows" | "rerun_validation" | "none",
  "confidence": <float 0 to 1>,
  "reasoning": "<one sentence>",
  "should_escalate": <true or false>
}}
"""
    response = client.chat.completions.create(
        model=WORKING_MODEL,
        messages=[{"role": "user", "content": prompt}],
        timeout=30,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
    return RecoveryDecision.model_validate_json(raw)


def apply_decision(
    decision: RecoveryDecision,
    failed_checks: list[str],
    execute_fn=execute_tool,
    validate_fn=run_all_validations_with_results,
) -> dict:
    """
    Pure decision-application logic. NO LLM calls happen in here.

    execute_fn / validate_fn are injectable so this exact function can be
    reused for deterministic, zero-cost testing of the escalation and
    repair-failure branches (Scenarios B and C) without touching the
    live LLM or, in some cases, the live database.
    """
    print("=" * 60)
    print("STEP 3 — ESCALATION CHECK")
    print("=" * 60)
    if decision.confidence < CONFIDENCE_THRESHOLD or decision.should_escalate:
        print(f"⚠️  Confidence {decision.confidence} below threshold "
              f"{CONFIDENCE_THRESHOLD} (or agent flagged escalation).")
        print("🚨 ESCALATING TO HUMAN. No automated repair performed.")
        return {
            "status": "escalated",
            "decision": decision.model_dump(),
            "failed_checks": failed_checks,
        }

    print(f"✅ Confidence {decision.confidence} >= {CONFIDENCE_THRESHOLD}. "
          f"Proceeding with auto-repair.\n")

    print("=" * 60)
    print(f"STEP 4 — EXECUTE: Calling tool '{decision.selected_tool.value}'")
    print("=" * 60)
    exec_result = execute_fn(decision.selected_tool, failed_checks)
    print(f"Execution result: {exec_result}\n")

    print("=" * 60)
    print("STEP 5 — VALIDATE: Re-running Great Expectations")
    print("=" * 60)
    results_after = validate_fn()
    still_failing = [name for name, passed in results_after if not passed]

    if still_failing:
        print(f"❌ Repair did NOT fully resolve issues: {still_failing}")
        print("🚨 ESCALATING TO HUMAN.")
        return {
            "status": "repair_failed",
            "decision": decision.model_dump(),
            "execution": exec_result,
            "still_failing": still_failing,
        }

    print("✅ All checks now passing. Pipeline can continue.\n")
    return {
        "status": "repaired",
        "decision": decision.model_dump(),
        "execution": exec_result,
    }


def run_agentic_recovery():
    """Full live pipeline: Observe -> real LLM decision -> apply_decision."""
    import time
    from agent.recovery_memory import create_memory_tables, log_recovery_decision
    create_memory_tables()

    start = time.time()

    print("=" * 60)
    print("STEP 1 — OBSERVE: Running Great Expectations validation")
    print("=" * 60)
    results = run_all_validations_with_results()
    failed_checks = [name for name, passed in results if not passed]

    if not failed_checks:
        print("✅ No failures detected. Nothing for agent to do.")
        elapsed = time.time() - start
        log_recovery_decision(
            final_status="no_failures",
            validation_passed=True,
            execution_time_seconds=round(elapsed, 2),
            is_test_run=False,
        )
        return {"status": "no_failures"}

    print(f"❌ {len(failed_checks)} checks failed: {failed_checks}\n")

    print("=" * 60)
    print("STEP 2 — DIAGNOSE + PLAN: Asking agent for a decision")
    print("=" * 60)
    failure_report = build_failure_report(failed_checks)
    decision = ask_agent(failure_report)
    print(f"Agent decision: {decision}\n")

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
        is_test_run=False,
    )

    print("=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(report)
    return report