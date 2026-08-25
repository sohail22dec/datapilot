import json
import sys
import time
from pathlib import Path

# Add backend directory to Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from app.agent.nodes.synthesis_node import synthesis_node
from app.agent.state import AgentState
from evals.metrics.synthesis_deepeval_metrics import (
    SynthesisJudgeEvaluator,
    SynthesisEvaluationResultItem,
)


def load_synthesis_dataset() -> list:
    dataset_path = Path(__file__).resolve().parent / "datasets" / "synthesis_golden_dataset.json"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found at: {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_single_synthesis_case(item: dict, evaluator: SynthesisJudgeEvaluator) -> SynthesisEvaluationResultItem:
    q_id = item["id"]
    category = item.get("category", "general")
    user_q = item["user_question"]
    query_results = item.get("query_results", [])
    columns = item.get("columns", [])
    metrics = item.get("computed_metrics")
    action_payload = item.get("action_payload")
    expected_chart_type = item.get("expected_chart_type")

    # Run Synthesis Node
    state: AgentState = {
        "messages": [],
        "user_question": user_q,
        "intent": "data_query" if query_results else ("statistical_analysis" if metrics else "general_chat"),
        "thought_process": "",
        "direct_response": None,
        "tables_used": [],
        "sql_query": None,
        "query_results": query_results,
        "columns": columns,
        "row_count": len(query_results),
        "execution_time_ms": 10.0,
        "error_history": [],
        "retry_count": 0,
        "computed_metrics": metrics,
        "action_type": None,
        "action_payload": action_payload,
        "requires_human_approval": False,
        "is_approved": False,
        "chart_config": None,
        "final_response": "",
        "agent_thought_trace": [],
    }

    start_time = time.perf_counter()
    synth_output = synthesis_node(state)
    latency_ms = (time.perf_counter() - start_time) * 1000

    final_response = synth_output.get("final_response", "")
    chart_config = synth_output.get("chart_config")

    # Unified LLM-as-a-Judge Evaluation (Faithfulness, Relevancy, Formatting in 1 call)
    judge_out = evaluator.evaluate_response(user_q, query_results, metrics, final_response)

    # Deterministic Chart Validator
    chart_valid, chart_reason = evaluator.validate_chart_config(chart_config, expected_chart_type, columns)

    diff_reason = None
    if not judge_out.is_faithful:
        diff_reason = f"Hallucination: {judge_out.hallucinated_facts} ({judge_out.critique})"
    elif not chart_valid:
        diff_reason = chart_reason

    return SynthesisEvaluationResultItem(
        id=q_id,
        category=category,
        user_question=user_q,
        final_response=final_response,
        chart_config=chart_config,
        expected_chart_type=expected_chart_type,
        is_faithful=judge_out.is_faithful,
        faithfulness_score=judge_out.faithfulness_score,
        is_relevant=judge_out.is_relevant,
        relevancy_score=judge_out.relevancy_score,
        inr_formatted=judge_out.inr_currency_used,
        bold_highlights=judge_out.bold_highlights_used,
        chart_valid=chart_valid,
        latency_ms=latency_ms,
        diff_reason=diff_reason,
    )


def run_synthesis_eval_suite(target_faithfulness: float = 90.0) -> bool:
    print("=" * 76)
    print("📊 DATAPILOT EVALS: EXECUTIVE SYNTHESIS & LLM-AS-A-JUDGE BENCHMARK")
    print("=" * 76)

    evaluator = SynthesisJudgeEvaluator(model_provider="groq")
    print(f"🤖 Configured LLM Judge: {evaluator.model_name}")

    dataset = load_synthesis_dataset()
    print(f"📦 Loaded {len(dataset)} Synthesis Test Scenarios\n")

    results = []
    for idx, item in enumerate(dataset):
        res = evaluate_single_synthesis_case(item, evaluator)
        results.append(res)

        if res.is_faithful and res.chart_valid:
            badge = "✅ [FAITHFUL + CHART OK]"
        elif not res.is_faithful:
            badge = "❌ [HALLUCINATION]     "
        else:
            badge = "⚠️ [CHART MISMATCH]    "

        chart_label = f"({res.chart_config.get('type')})" if res.chart_config else "(no chart)"
        print(f"{badge} ({res.latency_ms:>6.1f}ms) [{res.id}] {chart_label:<10} | {res.user_question[:38]}...")

        # Pace calls (1.0s sleep) to respect 30 requests/minute Groq rate limit
        if idx < len(dataset) - 1:
            time.sleep(1.0)

    summary = SynthesisJudgeEvaluator.compute_summary(results)

    # Print executive scorecard
    print("\n" + "=" * 76)
    print("📊 SYNTHESIS & LLM JUDGE SCORECARD")
    print("=" * 76)
    print(f"• Total Test Cases:        {summary.total_samples}")
    print(f"• Passed Cases:            {summary.passed_count} ✅")
    print(f"• Failed Cases:            {summary.failed_count} ❌")
    print(f"• Data Faithfulness (No Hallucination): {summary.mean_faithfulness_pct:.1f}% (Target: >={target_faithfulness}%)")
    print(f"• Answer Relevancy:        {summary.mean_relevancy_pct:.1f}%")
    print(f"• ChartConfig Accuracy:    {summary.chart_accuracy_pct:.1f}%")
    print(f"• INR Currency (₹) Rate:   {summary.inr_compliance_pct:.1f}%")
    print(f"• Overall Quality Index:   {summary.overall_quality_pct:.1f}%")
    print(f"• Median (P50) Latency:    {summary.p50_latency_ms:.1f} ms")
    print(f"• P95 Latency:             {summary.p95_latency_ms:.1f} ms")
    print("=" * 76)

    # Save Markdown report
    reports_dir = BACKEND_DIR / "evals" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "synthesis_eval_report.md"
    md_content = SynthesisJudgeEvaluator.generate_markdown_report(summary, results)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n📄 Saved Synthesis Markdown Report to: {report_path}\n")

    if summary.mean_faithfulness_pct >= target_faithfulness:
        print(f"🎉 SUCCESS: Executive Synthesis achieved {summary.mean_faithfulness_pct:.1f}% Faithfulness benchmark!")
        return True
    else:
        print(f"⚠️ FAILURE: Faithfulness ({summary.mean_faithfulness_pct:.1f}%) fell below target ({target_faithfulness}%)!")
        return False


if __name__ == "__main__":
    success = run_synthesis_eval_suite(target_faithfulness=90.0)
    sys.exit(0 if success else 1)
