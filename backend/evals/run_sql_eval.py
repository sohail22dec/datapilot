import json
import sys
import time
from pathlib import Path
from typing import List

# Add backend directory to Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from app.agent.nodes.router_node import router_node
from app.agent.state import AgentState
from app.tools.db_tool import execute_db_query
from app.tools.schema_tool import get_available_tables
from evals.metrics.sql_metrics import (
    SQLMetricsCalculator,
    SQLEvaluationResultItem,
)


def load_sql_golden_dataset() -> list:
    dataset_path = Path(__file__).resolve().parent / "datasets" / "sql_golden_dataset.json"
    if not dataset_path.exists():
        raise FileNotFoundError(f"SQL golden dataset not found at: {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_single_sql_case(item: dict, valid_tables: List[str]) -> SQLEvaluationResultItem:
    """
    Executes a single benchmark question:
    1. Generates SQL via router_node
    2. Runs Ground Truth SQL on PostgreSQL
    3. Runs Generated SQL on PostgreSQL
    4. Evaluates Execution Match (EM) and DataFrame equivalence
    """
    q_id = item["id"]
    difficulty = item.get("difficulty", "medium")
    category = item.get("category", "general")
    question = item["question"]
    ground_truth_sql = item["ground_truth_sql"]

    # 1. Execute Ground Truth SQL on DB
    expected_rows = None
    expected_row_count = 0
    gt_error = None
    try:
        gt_result = execute_db_query(ground_truth_sql)
        expected_rows = gt_result.get("rows", [])
        expected_row_count = len(expected_rows)
    except Exception as e:
        gt_error = f"Ground Truth execution failed: {str(e)}"

    # 2. Generate SQL via Agent
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
    gen_outcome = {}
    gen_error = None
    try:
        gen_outcome = router_node(initial_state)
    except Exception as e:
        gen_error = str(e)

    generated_sql = gen_outcome.get("sql_query")
    tables_used = gen_outcome.get("tables_used", [])

    # 3. Execute Generated SQL on DB
    actual_rows = None
    actual_row_count = 0
    is_syntax_valid = False
    exec_error = None

    if generated_sql:
        try:
            exec_result = execute_db_query(generated_sql)
            actual_rows = exec_result.get("rows", [])
            actual_row_count = len(actual_rows)
            is_syntax_valid = True
        except Exception as e:
            is_syntax_valid = False
            exec_error = str(e)
    else:
        exec_error = gen_error or "Router did not generate a SQL query"

    latency_ms = (time.perf_counter() - start_time) * 1000

    # 4. Compare Results
    if not is_syntax_valid:
        is_em = False
        rc_match = False
        diff_reason = f"Syntax/Execution Error: {exec_error}"
    elif gt_error:
        is_em = False
        rc_match = False
        diff_reason = gt_error
    else:
        is_em, rc_match, diff_reason = SQLMetricsCalculator.compare_row_sets(actual_rows, expected_rows)

    # 5. Schema Adherence
    schema_adherent = True
    for tbl in tables_used:
        if tbl.lower() not in [vt.lower() for vt in valid_tables]:
            schema_adherent = False
            break

    return SQLEvaluationResultItem(
        id=q_id,
        difficulty=difficulty,
        category=category,
        question=question,
        ground_truth_sql=ground_truth_sql,
        generated_sql=generated_sql,
        is_syntax_valid=is_syntax_valid,
        is_execution_match=is_em,
        row_count_match=rc_match,
        expected_row_count=expected_row_count,
        actual_row_count=actual_row_count,
        schema_adherent=schema_adherent,
        tables_used=tables_used,
        latency_ms=latency_ms,
        error_message=exec_error or gt_error,
        diff_reason=diff_reason,
        expected_rows_sample=expected_rows[:2] if expected_rows else None,
        actual_rows_sample=actual_rows[:2] if actual_rows else None,
    )


def run_sql_eval_suite(target_em_pct: float = 80.0, target_syntax_pct: float = 95.0) -> bool:
    print("=" * 76)
    print("🗄️  DATAPILOT EVALS: TEXT-TO-SQL EXECUTION MATCH (EM) BENCHMARK")
    print("=" * 76)

    dataset = load_sql_golden_dataset()
    valid_tables = get_available_tables()
    print(f"📦 Loaded {len(dataset)} Benchmark Questions across {len(valid_tables)} Schema Tables: {valid_tables}\n")

    results = []
    for item in dataset:
        res = evaluate_single_sql_case(item, valid_tables)
        results.append(res)

        if res.is_execution_match:
            status_badge = "✅ [MATCH]     "
        elif res.is_syntax_valid:
            status_badge = "⚠️ [VALUE DIFF]"
        else:
            status_badge = "❌ [SYNTAX ERR]"

        rows_info = f"({res.actual_row_count}/{res.expected_row_count} rows)"
        print(f"{status_badge} ({res.latency_ms:>6.1f}ms) [{res.id}] {res.difficulty.capitalize():<8} {rows_info:<12} | {res.question[:42]}...")

    # Calculate metrics
    summary = SQLMetricsCalculator.compute_summary(results)

    # Print reports
    print("\n" + SQLMetricsCalculator.render_difficulty_report(summary))

    # Print executive scorecard
    print("\n" + "=" * 76)
    print("📊 TEXT-TO-SQL EXECUTIVE SCORECARD")
    print("=" * 76)
    print(f"• Total Benchmark Queries: {summary.total_samples}")
    print(f"• Execution Matches (EM):  {summary.execution_match_count} ✅")
    print(f"• Syntax Valid Queries:    {summary.syntax_valid_count} ✅")
    print(f"• Execution Match (EM) %:  {summary.execution_match_pct:.1f}% (Benchmark Target: >={target_em_pct}%)")
    print(f"• Syntax Validity Rate %:  {summary.syntax_validity_pct:.1f}% (Target: >={target_syntax_pct}%)")
    print(f"• Row Count Match Rate %:  {summary.row_count_match_pct:.1f}%")
    print(f"• Schema Adherence Rate %: {summary.schema_adherence_pct:.1f}%")
    print(f"• Median (P50) Latency:    {summary.p50_latency_ms:.1f} ms")
    print(f"• P95 Latency:             {summary.p95_latency_ms:.1f} ms")
    print("=" * 76)

    # Save Markdown report
    reports_dir = BACKEND_DIR / "evals" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "sql_eval_report.md"
    md_content = SQLMetricsCalculator.generate_markdown_report(summary, results)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n📄 Saved SQL Markdown Evaluation Report to: {report_path}\n")

    # Pass/Fail determination
    if summary.execution_match_pct >= target_em_pct and summary.syntax_validity_pct >= target_syntax_pct:
        print(f"🎉 SUCCESS: Text-to-SQL Execution Match ({summary.execution_match_pct:.1f}%) meets benchmark target ({target_em_pct}%)!")
        return True
    else:
        print(f"⚠️ FAILURE: Text-to-SQL Execution Match ({summary.execution_match_pct:.1f}%) fell below target ({target_em_pct}%)!")
        return False


if __name__ == "__main__":
    success = run_sql_eval_suite(target_em_pct=80.0, target_syntax_pct=95.0)
    sys.exit(0 if success else 1)
