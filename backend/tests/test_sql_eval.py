import sys
from pathlib import Path
import pytest

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from app.tools.schema_tool import get_available_tables
from evals.metrics.sql_metrics import SQLMetricsCalculator
from evals.run_sql_eval import evaluate_single_sql_case, load_sql_golden_dataset

DATASET = load_sql_golden_dataset()
VALID_TABLES = get_available_tables()


def test_sql_benchmark_overall_execution_match():
    """
    Asserts that the Text-to-SQL generation achieves >= 80% Execution Match (EM)
    and >= 95% Syntax Validity across the 30-query Benchmark Dataset.
    """
    results = [evaluate_single_sql_case(item, VALID_TABLES) for item in DATASET]
    summary = SQLMetricsCalculator.compute_summary(results)

    # Print summary in test log
    print("\n" + SQLMetricsCalculator.render_difficulty_report(summary))

    assert summary.syntax_validity_pct >= 95.0, (
        f"SQL Syntax Validity Rate ({summary.syntax_validity_pct:.1f}%) is below 95% target threshold! "
        f"Syntax failures: {[r.id for r in results if not r.is_syntax_valid]}"
    )
    assert summary.execution_match_pct >= 80.0, (
        f"SQL Execution Match ({summary.execution_match_pct:.1f}%) is below 80% benchmark target! "
        f"Mismatches: {[r.id for r in results if not r.is_execution_match]}"
    )


@pytest.mark.parametrize(
    "item",
    [item for item in DATASET if item["difficulty"] == "simple"],
    ids=[item["id"] for item in DATASET if item["difficulty"] == "simple"],
)
def test_sql_simple_queries_match(item):
    """Verifies that single-table filters, counts, and sorts execute with exact matches."""
    res = evaluate_single_sql_case(item, VALID_TABLES)
    assert res.is_syntax_valid is True, f"Syntax error in simple query [{res.id}]: {res.error_message}"
    assert res.is_execution_match is True, f"Execution mismatch in [{res.id}]: {res.diff_reason}"


@pytest.mark.parametrize(
    "item",
    [item for item in DATASET if item["difficulty"] == "medium"],
    ids=[item["id"] for item in DATASET if item["difficulty"] == "medium"],
)
def test_sql_medium_join_queries_syntax(item):
    """Verifies that multi-table relational JOIN queries compile and execute without syntax errors."""
    res = evaluate_single_sql_case(item, VALID_TABLES)
    assert res.is_syntax_valid is True, f"Syntax/JOIN error in medium query [{res.id}]: {res.error_message}"
    assert res.schema_adherent is True, f"Non-existent tables used in [{res.id}]: {res.tables_used}"
