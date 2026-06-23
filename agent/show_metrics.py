"""
agent/show_metrics.py

Reporting script for the agent recovery memory layer.
Run at any time to see historical performance metrics.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.recovery_memory import (
    get_agent_metrics,
    get_recent_runs,
    get_failure_statistics,
)


def fmt(val):
    """Format Decimal/None values cleanly for display."""
    if val is None:
        return "N/A"
    try:
        return str(float(val))
    except (TypeError, ValueError):
        return str(val)


def show_metrics():
    metrics = get_agent_metrics()
    stats = get_failure_statistics()
    recent = get_recent_runs(limit=10)

    print("\n" + "=" * 56)
    print("  AGENTIC SELF-HEALING PIPELINE — RECOVERY METRICS")
    print("=" * 56)

    print(f"\n{'Total Runs:':<30} {metrics['total_runs']}")
    print(f"{'Production Runs:':<30} {metrics['production_runs']}")
    print(f"{'Test Runs:':<30} {metrics['test_runs']}")

    print(f"\n{'Repaired:':<30} {metrics['repaired_runs']}")
    print(f"{'Escalated:':<30} {metrics['escalated_runs']}")
    print(f"{'Repair Failed:':<30} {metrics['repair_failed_runs']}")
    print(f"{'No Failures (clean runs):':<30} {metrics['no_failure_runs']}")

    print(f"\n{'Repair Success Rate:':<30} {fmt(metrics['repair_success_rate'])}%")
    print(f"{'Average Confidence:':<30} {fmt(metrics['average_confidence'])}")
    print(f"{'Avg Execution Time (s):':<30} {fmt(metrics['avg_execution_seconds'])}")

    if stats["failure_type_counts"]:
        top = stats["failure_type_counts"][0]
        print(f"\n{'Most Common Failure:':<30} {top['failure_type']} ({top['count']} times)")

    if stats["tool_usage_counts"]:
        top = stats["tool_usage_counts"][0]
        print(f"{'Most Used Tool:':<30} {top['selected_tool']} ({top['count']} times)")

    print("\n" + "-" * 56)
    print("  CONFIDENCE + SUCCESS RATE BY FAILURE TYPE")
    print("-" * 56)
    if stats["confidence_by_type"]:
        for row in stats["confidence_by_type"]:
            print(f"  {row['failure_type']:<24} "
                  f"avg_conf={fmt(row['avg_confidence'])}  "
                  f"success={fmt(row['success_rate_pct'])}%")
    else:
        print("  No failure type data yet.")

    print("\n" + "-" * 56)
    print("  LAST 10 RUNS")
    print("-" * 56)
    for r in recent:
        tag = "[TEST]" if r["is_test_run"] else "[LIVE]"
        conf = f"conf={fmt(r['confidence'])}" if r["confidence"] else "conf=N/A"
        print(f"  {tag} {str(r['timestamp'])[:19]}  "
              f"{r['final_status']:<14} {conf}  "
              f"tool={r['selected_tool'] or 'N/A'}")

    print("\n" + "=" * 56)


if __name__ == "__main__":
    show_metrics()