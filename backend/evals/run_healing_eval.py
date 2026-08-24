import json
import sys
import time
from pathlib import Path
from typing import List, Optional

# Add backend directory to Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from app.agent.nodes.heal_node import heal_node
from app.agent.state import AgentState
from app.tools.db_tool import execute_db_query
from evals.metrics.sql_metrics import SQLMetricsCalculator
from evals.metrics.healing_metrics import (
    HealingMetricsCalculator,
    HealingEvaluationResultItem,
    HealingAttemptLog,
)


def load_healing_golden_dataset() -> list:
    dataset_path = Path(__file__).resolve().parent / "datasets" / "healing_golden_dataset.json"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Healing dataset not found at: {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_single_healing_case(item: dict) -> HealingEvaluationResultItem:
    """
    Executes a fault-injected self-healing test case:
    1. Injects broken SQL and initial error
    2. Runs heal_node (Attempt 1) and tests DB execution
    3. If failed, runs heal_node (Attempt 2) and tests DB execution
    4. Compares post-heal result set against Ground Truth SQL
    """
    q_id = item["id"]
    error_type = item.get("error_type", "general")
    question = item["question"]
    broken_sql = item["broken_sql"]
    initial_error = item.get("simulated_error", "SQL error")
    ground_truth_sql = item.get("ground_truth_sql", "")

    # Execute Ground Truth for baseline comparison
    expected_rows = None
    try:
        if ground_truth_sql:
            gt_result = execute_db_query(ground_truth_sql)
            expected_rows = gt_result.get("rows", [])
    except Exception:
        expected_rows = None

    state: AgentState = {
        "messages": [],
        "user_question": question,
        "intent": "data_query",
        "thought_process": "",
        "direct_response": None,
        "tables_used": [],
        "sql_query": broken_sql,
        "query_results": None,
        "columns": None,
        "row_count": 0,
        "execution_time_ms": 0.0,
        "error_history": [initial_error],
        "retry_count": 0,
        "computed_metrics": None,
        "action_type": None,
        "action_payload": None,
        "requires_human_approval": False,
        "is_approved": False,
        "chart_config": None,
        "final_response": "",
        "agent_thought_trace": [],
    }

    attempts_history: List[HealingAttemptLog] = []
    is_recovered = False
    attempts_needed = 0
    final_sql = broken_sql
    diff_reason = None
    actual_rows = None
    total_diag_latency = 0.0

    # Self-Healing Retry Loop (up to 2 attempts)
    for attempt in range(1, 3):
        t_start = time.perf_counter()
        heal_result = heal_node(state)
        diag_latency = (time.perf_counter() - t_start) * 1000
        total_diag_latency += diag_latency

        rewritten_sql = heal_result.get("sql_query", "").strip()
        state["sql_query"] = rewritten_sql
        state["retry_count"] = attempt
        final_sql = rewritten_sql

        # Test execution on DB
        try:
            exec_res = execute_db_query(rewritten_sql)
            actual_rows = exec_res.get("rows", [])
            attempts_history.append(HealingAttemptLog(
                attempt_number=attempt,
                rewritten_sql=rewritten_sql,
                is_syntax_valid=True,
                error_message=None,
                latency_ms=diag_latency,
            ))
            is_recovered = True
            attempts_needed = attempt
            break
        except Exception as e:
            err_msg = str(e)
            attempts_history.append(HealingAttemptLog(
                attempt_number=attempt,
                rewritten_sql=rewritten_sql,
                is_syntax_valid=False,
                error_message=err_msg,
                latency_ms=diag_latency,
            ))
            state["error_history"].append(err_msg)
            diff_reason = err_msg

    # Post-Heal Execution Match against Ground Truth
    is_execution_match = False
    if is_recovered and expected_rows is not None:
        is_execution_match, _, match_reason = SQLMetricsCalculator.compare_row_sets(actual_rows, expected_rows)
        if not is_execution_match:
            diff_reason = f"Execution diff post-heal: {match_reason}"
    elif is_recovered:
        is_execution_match = True

    return HealingEvaluationResultItem(
        id=q_id,
        error_type=error_type,
        question=question,
        broken_sql=broken_sql,
        initial_error=initial_error,
        final_sql=final_sql,
        is_recovered=is_recovered,
        attempts_needed=attempts_needed,
        is_one_shot=(attempts_needed == 1),
        is_two_shot=(attempts_needed == 2),
        is_execution_match=is_execution_match,
        attempts_history=attempts_history,
        total_diagnostic_latency_ms=total_diag_latency,
        ground_truth_sql=ground_truth_sql,
        diff_reason=diff_reason,
    )


def run_healing_eval_suite(target_recovery_pct: float = 80.0) -> bool:
    print("=" * 76)
    print("🩹 DATAPILOT EVALS: SELF-HEALING & RESILIENCE BENCHMARK")
    print("=" * 76)

    dataset = load_healing_golden_dataset()
    print(f"📦 Loaded {len(dataset)} Fault Injection Cases from healing_golden_dataset.json\n")

    results = []
    for item in dataset:
        res = evaluate_single_healing_case(item)
        results.append(res)

        if res.is_one_shot:
            badge = "✅ [1-SHOT RECOVERED]"
        elif res.is_two_shot:
            badge = "🩹 [2-SHOT RECOVERED]"
        else:
            badge = "❌ [HEALING FAILED]  "

        print(f"{badge} ({res.total_diagnostic_latency_ms:>6.1f}ms) [{res.id}] {res.error_type:<22} | {res.question[:38]}...")

    # Calculate metrics
    summary = HealingMetricsCalculator.compute_summary(results)

    # Print reports
    print("\n" + HealingMetricsCalculator.render_error_type_report(summary))

    # Print executive scorecard
    print("\n" + "=" * 76)
    print("📊 SELF-HEALING RESILIENCE SCORECARD")
    print("=" * 76)
    print(f"• Total Fault Injections:  {summary.total_samples}")
    print(f"• Successfully Recovered:  {summary.recovered_count} ✅")
    print(f"• 1-Shot Recoveries:       {summary.one_shot_count} ({summary.one_shot_pct:.1f}%)")
    print(f"• 2-Shot Recoveries:       {summary.two_shot_count} ({summary.two_shot_pct:.1f}%)")
    print(f"• Unrecovered Failures:    {summary.failed_count} ❌")
    print(f"• Overall Recovery Rate:   {summary.recovery_rate_pct:.1f}% (Benchmark Target: >={target_recovery_pct}%)")
    print(f"• Post-Heal Exec Match:    {summary.post_heal_em_pct:.1f}%")
    print(f"• Median Diagnostic Time:  {summary.p50_latency_ms:.1f} ms")
    print(f"• P95 Diagnostic Time:     {summary.p95_latency_ms:.1f} ms")
    print("=" * 76)

    # Save Markdown report
    reports_dir = BACKEND_DIR / "evals" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "healing_eval_report.md"
    md_content = HealingMetricsCalculator.generate_markdown_report(summary, results)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n📄 Saved Self-Healing Markdown Evaluation Report to: {report_path}\n")

    # Pass/Fail determination
    if summary.recovery_rate_pct >= target_recovery_pct:
        print(f"🎉 SUCCESS: Self-Healing Recovery Rate ({summary.recovery_rate_pct:.1f}%) meets benchmark target ({target_recovery_pct}%)!")
        return True
    else:
        print(f"⚠️ FAILURE: Self-Healing Recovery Rate ({summary.recovery_rate_pct:.1f}%) fell below target ({target_recovery_pct}%)!")
        return False


if __name__ == "__main__":
    success = run_healing_eval_suite(target_recovery_pct=80.0)
    sys.exit(0 if success else 1)
