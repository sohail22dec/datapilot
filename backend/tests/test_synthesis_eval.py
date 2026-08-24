import sys
from pathlib import Path
import pytest

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from evals.metrics.synthesis_deepeval_metrics import (
    SynthesisJudgeEvaluator,
)
from evals.run_synthesis_eval import (
    evaluate_single_synthesis_case,
    load_synthesis_dataset,
)

DATASET = load_synthesis_dataset()
EVALUATOR = SynthesisJudgeEvaluator(model_provider="groq")


def test_synthesis_faithfulness_and_hallucination_benchmark():
    """
    Asserts >= 90% Data Faithfulness (zero hallucinated figures) and
    >= 90% ChartConfig accuracy across the 25 Synthesis benchmark cases.
    """
    results = [evaluate_single_synthesis_case(item, EVALUATOR) for item in DATASET]
    summary = SynthesisJudgeEvaluator.compute_summary(results)

    assert summary.mean_faithfulness_pct >= 90.0, (
        f"Data Faithfulness ({summary.mean_faithfulness_pct:.1f}%) is below 90% target threshold! "
        f"Unfaithful responses: {[r.id for r in results if not r.is_faithful]}"
    )
    assert summary.chart_accuracy_pct >= 90.0, (
        f"ChartConfig accuracy ({summary.chart_accuracy_pct:.1f}%) is below 90%!"
    )


@pytest.mark.parametrize(
    "item",
    [item for item in DATASET if item["category"] == "empty_dataset"],
    ids=[item["id"] for item in DATASET if item["category"] == "empty_dataset"],
)
def test_synthesis_empty_dataset_fallbacks(item):
    """Verifies that queries returning 0 rows produce graceful messages with no broken charts."""
    res = evaluate_single_synthesis_case(item, EVALUATOR)
    assert res.chart_config is None, f"Expected no chart for empty dataset [{res.id}], but got: {res.chart_config}"
    assert "no matching records" in res.final_response.lower() or "not found" in res.final_response.lower()


@pytest.mark.parametrize(
    "item",
    [item for item in DATASET if item["id"] in ("syn_01", "syn_02", "syn_03", "syn_05", "syn_07")],
    ids=["syn_01", "syn_02", "syn_03", "syn_05", "syn_07"],
)
def test_synthesis_core_visualizations(item):
    """Fast sanity check for essential multi-row, time-series, and action synthesis cases."""
    res = evaluate_single_synthesis_case(item, EVALUATOR)
    assert res.is_faithful is True, f"Hallucination in [{res.id}]: {res.diff_reason}"
    assert res.chart_valid is True, f"Invalid chart in [{res.id}]: {res.diff_reason}"
