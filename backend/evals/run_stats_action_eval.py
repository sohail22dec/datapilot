import json
import sys
import time
from pathlib import Path

# Add backend directory to Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from app.tools.python_tool import execute_python_stats
from app.tools.email_tool import draft_email_action
from evals.metrics.stats_action_metrics import (
    StatsActionMetricsCalculator,
    StatsEvaluationResultItem,
)


def load_stats_action_dataset() -> list:
    dataset_path = Path(__file__).resolve().parent / "datasets" / "stats_action_golden_dataset.json"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found at: {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_single_stats_action_case(item: dict) -> StatsEvaluationResultItem:
    q_id = item["id"]
    item_type = item.get("type", "analytics")
    metric_or_campaign = item.get("metric") or item.get("campaign_type") or "unknown"
    desc = item.get("description", "")
    expected_error = item.get("expected_error", False)

    start_time = time.perf_counter()
    diff_reason = None
    math_match = True
    hitl_enforced = True
    error_handled = True
    actual_output = {}

    if item_type == "analytics":
        input_rows = item.get("input_rows", [])
        actual_output = execute_python_stats(metric_or_campaign, input_rows)
        latency_ms = (time.perf_counter() - start_time) * 1000

        if expected_error:
            if "error" not in actual_output:
                error_handled = False
                diff_reason = f"Expected graceful error on edge case, but got: {actual_output}"
        else:
            expected_metrics = item.get("expected_metrics", {})
            math_match = StatsActionMetricsCalculator.compare_metrics(actual_output, expected_metrics)
            if not math_match:
                diff_reason = f"Math output mismatch (Expected: {expected_metrics}, Got: {actual_output})"

    else:  # "action"
        sample_recipients = item.get("sample_recipients", [])
        actual_output = draft_email_action(
            campaign_type=metric_or_campaign,
            recipient_count=len(sample_recipients),
            sample_recipients=sample_recipients,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000

        # HITL Safety Invariant Verification
        if actual_output.get("requires_human_approval") is not True or actual_output.get("is_approved") is not False:
            hitl_enforced = False
            diff_reason = "CRITICAL: Action draft failed HITL safety check (requires_human_approval != True or is_approved != False)"

        expected_action = item.get("expected_action", {})
        for k, v in expected_action.items():
            if actual_output.get(k) != v:
                math_match = False
                diff_reason = f"Action draft mismatch on '{k}' (Expected: {v}, Got: {actual_output.get(k)})"
                break

    is_passed = (math_match and hitl_enforced and error_handled)

    return StatsEvaluationResultItem(
        id=q_id,
        type=item_type,
        metric_or_campaign=metric_or_campaign,
        description=desc,
        is_passed=is_passed,
        actual_output=actual_output,
        expected_output=item.get("expected_metrics") or item.get("expected_action"),
        math_match=math_match,
        error_handled_correctly=error_handled,
        hitl_enforced=hitl_enforced,
        latency_ms=latency_ms,
        diff_reason=diff_reason,
    )


def run_stats_action_eval_suite(target_accuracy: float = 100.0) -> bool:
    print("=" * 76)
    print("🧮 DATAPILOT EVALS: PYTHON ANALYTICS & BUSINESS ACTION BENCHMARK")
    print("=" * 76)

    dataset = load_stats_action_dataset()
    print(f"📦 Loaded {len(dataset)} Test Cases from stats_action_golden_dataset.json\n")

    results = []
    for item in dataset:
        res = evaluate_single_stats_action_case(item)
        results.append(res)

        badge = "✅ [PASS]" if res.is_passed else "❌ [FAIL]"
        print(f"{badge} ({res.latency_ms:>5.3f}ms) [{res.id}] {res.metric_or_campaign:<20} | {res.description[:42]}...")

    summary = StatsActionMetricsCalculator.compute_summary(results)

    # Print executive scorecard
    print("\n" + "=" * 76)
    print("📊 ANALYTICS & ACTIONS SCORECARD")
    print("=" * 76)
    print(f"• Total Test Cases:        {summary.total_samples}")
    print(f"• Passed Cases:            {summary.passed_count} ✅")
    print(f"• Failed Cases:            {summary.failed_count} ❌")
    print(f"• Overall Tool Accuracy:   {summary.accuracy_pct:.1f}% (Target: >={target_accuracy}%)")
    print(f"• Math Determinism:        {summary.math_determinism_pct:.1f}%")
    print(f"• HITL Approval Invariant: {summary.hitl_compliance_pct:.1f}%")
    print(f"• Edge Case Resilience:    {summary.edge_case_resilience_pct:.1f}%")
    print(f"• Median (P50) Latency:    {summary.p50_latency_ms:.3f} ms")
    print(f"• P95 Latency:             {summary.p95_latency_ms:.3f} ms")
    print("=" * 76)

    # Save Markdown report
    reports_dir = BACKEND_DIR / "evals" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "stats_action_eval_report.md"
    md_content = StatsActionMetricsCalculator.generate_markdown_report(summary, results)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n📄 Saved Markdown Evaluation Report to: {report_path}\n")

    if summary.accuracy_pct >= target_accuracy:
        print(f"🎉 SUCCESS: Analytics & Action Tools meet 100% benchmark target!")
        return True
    else:
        print(f"⚠️ FAILURE: Accuracy ({summary.accuracy_pct:.1f}%) fell below target ({target_accuracy}%)!")
        return False


if __name__ == "__main__":
    success = run_stats_action_eval_suite(target_accuracy=100.0)
    sys.exit(0 if success else 1)
