import sys
from pathlib import Path
import pytest

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from evals.metrics.healing_metrics import HealingMetricsCalculator
from evals.run_healing_eval import evaluate_single_healing_case, load_healing_golden_dataset

DATASET = load_healing_golden_dataset()


def test_self_healing_overall_recovery_rate():
    """
    Asserts that the Self-Healing Node achieves >= 80% Recovery Rate
    across the 20 fault-injected benchmark scenarios.
    """
    results = [evaluate_single_healing_case(item) for item in DATASET]
    summary = HealingMetricsCalculator.compute_summary(results)

    # Print summary in test log
    print("\n" + HealingMetricsCalculator.render_error_type_report(summary))

    assert summary.recovery_rate_pct >= 80.0, (
        f"Self-Healing Recovery Rate ({summary.recovery_rate_pct:.1f}%) is below 80% target threshold! "
        f"Unrecovered cases: {[r.id for r in results if not r.is_recovered]}"
    )
    assert summary.one_shot_pct >= 50.0, (
        f"1-Shot Recovery Rate ({summary.one_shot_pct:.1f}%) is below 50% threshold!"
    )


@pytest.mark.parametrize(
    "item",
    [item for item in DATASET if item["error_type"] == "column_hallucination"],
    ids=[item["id"] for item in DATASET if item["error_type"] == "column_hallucination"],
)
def test_healing_column_hallucinations(item):
    """Verifies that column typos and hallucinations (e.g. customer_name) are successfully diagnosed and healed."""
    res = evaluate_single_healing_case(item)
    assert res.is_recovered is True, f"Failed to heal column hallucination in [{res.id}]: {res.diff_reason}"


@pytest.mark.parametrize(
    "item",
    [item for item in DATASET if item["error_type"] == "table_hallucination"],
    ids=[item["id"] for item in DATASET if item["error_type"] == "table_hallucination"],
)
def test_healing_table_hallucinations(item):
    """Verifies that non-existent table references (e.g. users -> customers) are mapped and healed."""
    res = evaluate_single_healing_case(item)
    assert res.is_recovered is True, f"Failed to heal table hallucination in [{res.id}]: {res.diff_reason}"


@pytest.mark.parametrize(
    "item",
    [item for item in DATASET if item["error_type"] == "missing_group_by"],
    ids=[item["id"] for item in DATASET if item["error_type"] == "missing_group_by"],
)
def test_healing_missing_group_by(item):
    """Verifies that non-aggregated column errors in GROUP BY are diagnosed and fixed."""
    res = evaluate_single_healing_case(item)
    assert res.is_recovered is True, f"Failed to heal missing GROUP BY in [{res.id}]: {res.diff_reason}"
