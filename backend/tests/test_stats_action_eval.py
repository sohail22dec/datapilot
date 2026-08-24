import sys
from pathlib import Path
import pytest

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from evals.metrics.stats_action_metrics import StatsActionMetricsCalculator
from evals.run_stats_action_eval import evaluate_single_stats_action_case, load_stats_action_dataset

DATASET = load_stats_action_dataset()


def test_stats_and_actions_overall_benchmark():
    """
    Asserts 100% mathematical determinism and HITL approval compliance
    across all 20 analytics and action test cases.
    """
    results = [evaluate_single_stats_action_case(item) for item in DATASET]
    summary = StatsActionMetricsCalculator.compute_summary(results)

    assert summary.accuracy_pct == 100.0, (
        f"Analytics & Actions failed benchmark ({summary.accuracy_pct:.1f}%): "
        f"{[r.id for r in results if not r.is_passed]}"
    )
    assert summary.math_determinism_pct == 100.0
    assert summary.hitl_compliance_pct == 100.0


@pytest.mark.parametrize(
    "item",
    [item for item in DATASET if item["type"] == "action"],
    ids=[item["id"] for item in DATASET if item["type"] == "action"],
)
def test_action_hitl_approval_invariant(item):
    """Verifies that all action campaign drafts strictly require human review."""
    res = evaluate_single_stats_action_case(item)
    assert res.is_passed is True, f"Action failed HITL test [{res.id}]: {res.diff_reason}"
    assert res.actual_output.get("requires_human_approval") is True
    assert res.actual_output.get("is_approved") is False
