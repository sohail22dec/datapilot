import json
import sys
import time
from pathlib import Path

# Add backend directory to Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from app.agent.nodes.router_node import router_node
from app.agent.state import AgentState
from evals.metrics.classification_metrics import (
    ClassificationMetricsCalculator,
    EvaluationResultItem,
)


def load_golden_dataset() -> list:
    dataset_path = Path(__file__).resolve().parent / "datasets" / "router_golden_dataset.json"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Golden dataset not found at: {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_single_case(item: dict) -> EvaluationResultItem:
    """Executes router_node on a single test prompt and validates state contract."""
    q_id = item["id"]
    category = item.get("category", "unknown")
    question = item["question"]
    expected_intent = item["expected_intent"]

    initial_state: AgentState = {
        "messages": [],
        "user_question": question,
        "intent": "data_query",
        "thought_process": "",
        "direct_response": None,
        "tables_used": [],
        "sql_query": None,
        "query_results": None,
        "columns": None,
        "row_count": 0,
        "execution_time_ms": 0.0,
        "error_history": [],
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

    start_time = time.perf_counter()
    error_msg = None
    try:
        outcome = router_node(initial_state)
        predicted_intent = outcome.get("intent", "unknown")
        sql_query = outcome.get("sql_query")
        direct_resp = outcome.get("direct_response")
    except Exception as e:
        predicted_intent = "error"
        sql_query = None
        direct_resp = None
        error_msg = str(e)

    latency = (time.perf_counter() - start_time) * 1000

    # 1. Intent Match
    is_intent_correct = (predicted_intent == expected_intent)

    # 2. State Contract Validation
    contract_valid = True
    contract_reason = "OK"

    if predicted_intent in ("data_query", "statistical_analysis", "email_action"):
        if not sql_query:
            contract_valid = False
            contract_reason = "Missing SQL for data/stats/email intent"
        elif direct_resp is not None:
            contract_valid = False
            contract_reason = "Unexpected direct_response on SQL intent"
    elif predicted_intent in ("general_chat", "policy_violation"):
        if sql_query is not None:
            contract_valid = False
            contract_reason = "Unexpected SQL generated for chat/policy intent"
        elif not direct_resp:
            contract_valid = False
            contract_reason = "Missing direct_response for chat/policy intent"

    return EvaluationResultItem(
        id=q_id,
        category=category,
        question=question,
        expected_intent=expected_intent,
        predicted_intent=predicted_intent,
        is_intent_correct=is_intent_correct,
        sql_generated=bool(sql_query),
        sql_query=sql_query,
        direct_response=direct_resp,
        contract_valid=contract_valid,
        contract_reason=contract_reason,
        latency_ms=latency,
        error=error_msg,
    )


def run_router_eval_suite(target_accuracy: float = 90.0) -> bool:
    print("=" * 72)
    print("🚀 DATAPILOT EVALS: ROUTER INTENT CLASSIFICATION BENCHMARK")
    print("=" * 72)

    dataset = load_golden_dataset()
    print(f"📦 Loaded {len(dataset)} Golden Test Cases from router_golden_dataset.json\n")

    results = []
    for i, item in enumerate(dataset, start=1):
        res = evaluate_single_case(item)
        results.append(res)

        status_badge = "✅ PASS" if (res.is_intent_correct and res.contract_valid) else "❌ FAIL"
        intent_diff = (
            f"[{res.predicted_intent}]"
            if res.is_intent_correct
            else f"[{res.predicted_intent} != expected:{res.expected_intent}]"
        )
        print(f"{status_badge} ({res.latency_ms:>6.1f}ms) [{res.id}] {intent_diff:<40} | {res.question[:45]}...")

    # Calculate metrics
    summary = ClassificationMetricsCalculator.compute_summary(results)

    # Print reports
    print("\n" + ClassificationMetricsCalculator.render_classification_report(summary))
    print("\n" + ClassificationMetricsCalculator.render_confusion_matrix(summary))

    # Print executive scorecard
    print("\n" + "=" * 72)
    print("📊 EXECUTIVE SCORECARD")
    print("=" * 72)
    print(f"• Total Test Cases:        {summary.total_samples}")
    print(f"• Passed (Intent+Contract):{summary.passed_count} ✅")
    print(f"• Failed:                  {summary.failed_count} ❌")
    print(f"• Intent Accuracy:         {summary.accuracy_pct:.1f}% (Target: >={target_accuracy}%)")
    print(f"• Contract Integrity:      {summary.contract_compliance_pct:.1f}%")
    print(f"• Median (P50) Latency:    {summary.p50_latency_ms:.1f} ms")
    print(f"• P95 Latency:             {summary.p95_latency_ms:.1f} ms")
    print("=" * 72)

    # Save Markdown report
    reports_dir = BACKEND_DIR / "evals" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "router_eval_report.md"
    md_content = ClassificationMetricsCalculator.generate_markdown_report(summary, results)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n📄 Saved Markdown Evaluation Report to: {report_path}\n")

    # Pass/Fail determination
    if summary.accuracy_pct >= target_accuracy and summary.contract_compliance_pct >= 90.0:
        print(f"🎉 SUCCESS: Router Accuracy ({summary.accuracy_pct:.1f}%) meets benchmark target ({target_accuracy}%)!")
        return True
    else:
        print(f"⚠️ FAILURE: Router Accuracy ({summary.accuracy_pct:.1f}%) fell below target ({target_accuracy}%)!")
        return False


if __name__ == "__main__":
    success = run_router_eval_suite(target_accuracy=90.0)
    sys.exit(0 if success else 1)
