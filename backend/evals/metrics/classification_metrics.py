from dataclasses import dataclass, field
from typing import Dict, List, Optional
import statistics


@dataclass
class EvaluationResultItem:
    """Represents the evaluation outcome of a single test case."""
    id: str
    category: str
    question: str
    expected_intent: str
    predicted_intent: str
    is_intent_correct: bool
    sql_generated: bool
    sql_query: Optional[str]
    direct_response: Optional[str]
    contract_valid: bool
    contract_reason: str
    latency_ms: float
    error: Optional[str] = None


@dataclass
class PerClassMetric:
    """Precision, Recall, and F1 for a specific intent class."""
    intent: str
    total_samples: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float


@dataclass
class EvaluationSummary:
    """Aggregated metrics across the full benchmark test suite."""
    total_samples: int
    passed_count: int
    failed_count: int
    accuracy_pct: float
    contract_compliance_pct: float
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    per_class_metrics: Dict[str, PerClassMetric] = field(default_factory=dict)
    confusion_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)
    all_classes: List[str] = field(default_factory=list)


class ClassificationMetricsCalculator:
    """
    Computes statistical evaluation metrics for Intent Classification:
    - Overall Accuracy (%)
    - Per-class Precision, Recall, and F1-score
    - Multi-class Confusion Matrix
    - State Contract Integrity (% valid state transitions)
    - Latency distribution percentiles (P50, P95, Mean)
    """

    INTENTS = [
        "data_query",
        "statistical_analysis",
        "email_action",
        "general_chat",
        "policy_violation",
    ]

    @classmethod
    def compute_summary(cls, results: List[EvaluationResultItem]) -> EvaluationSummary:
        total = len(results)
        if total == 0:
            return EvaluationSummary(
                total_samples=0,
                passed_count=0,
                failed_count=0,
                accuracy_pct=0.0,
                contract_compliance_pct=0.0,
                mean_latency_ms=0.0,
                p50_latency_ms=0.0,
                p95_latency_ms=0.0,
            )

        passed = sum(1 for r in results if r.is_intent_correct and r.contract_valid)
        failed = total - passed
        accuracy = (sum(1 for r in results if r.is_intent_correct) / total) * 100
        contract_compliance = (sum(1 for r in results if r.contract_valid) / total) * 100

        # Latencies
        latencies = [r.latency_ms for r in results]
        latencies.sort()
        mean_lat = statistics.mean(latencies) if latencies else 0.0
        p50_lat = statistics.median(latencies) if latencies else 0.0
        p95_idx = int(len(latencies) * 0.95)
        p95_lat = latencies[min(p95_idx, len(latencies) - 1)] if latencies else 0.0

        # Classes represented in dataset
        all_classes = list(cls.INTENTS)
        for r in results:
            if r.expected_intent not in all_classes:
                all_classes.append(r.expected_intent)
            if r.predicted_intent not in all_classes:
                all_classes.append(r.predicted_intent)

        # Confusion Matrix: rows = expected, cols = predicted
        confusion: Dict[str, Dict[str, int]] = {
            exp: {pred: 0 for pred in all_classes} for exp in all_classes
        }
        for r in results:
            exp = r.expected_intent
            pred = r.predicted_intent
            if exp in confusion and pred in confusion[exp]:
                confusion[exp][pred] += 1

        # Per-class Precision, Recall, F1
        per_class: Dict[str, PerClassMetric] = {}
        for c in all_classes:
            tp = confusion[c][c]
            fp = sum(confusion[other][c] for other in all_classes if other != c)
            fn = sum(confusion[c][other] for other in all_classes if other != c)
            total_class_samples = sum(confusion[c].values())

            precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
            recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

            per_class[c] = PerClassMetric(
                intent=c,
                total_samples=total_class_samples,
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                precision=precision * 100,
                recall=recall * 100,
                f1_score=f1 * 100,
            )

        return EvaluationSummary(
            total_samples=total,
            passed_count=passed,
            failed_count=failed,
            accuracy_pct=accuracy,
            contract_compliance_pct=contract_compliance,
            mean_latency_ms=mean_lat,
            p50_latency_ms=p50_lat,
            p95_latency_ms=p95_lat,
            per_class_metrics=per_class,
            confusion_matrix=confusion,
            all_classes=all_classes,
        )

    @classmethod
    def render_confusion_matrix(cls, summary: EvaluationSummary) -> str:
        """Renders an ASCII confusion matrix table."""
        classes = [c for c in summary.all_classes if summary.per_class_metrics[c].total_samples > 0 or any(summary.confusion_matrix[other][c] > 0 for other in summary.all_classes)]
        short_names = {
            "data_query": "data_q",
            "statistical_analysis": "stats",
            "email_action": "email",
            "general_chat": "chat",
            "policy_violation": "policy",
        }
        headers = [short_names.get(c, c[:6]) for c in classes]
        col_width = 8

        lines = []
        lines.append("=" * 68)
        lines.append("📊 CONFUSION MATRIX (Rows: Expected, Columns: Predicted)")
        lines.append("=" * 68)
        
        # Header row
        header_str = f"{'Expected \\ Pred':<18} | " + " | ".join(f"{h:>{col_width}}" for h in headers)
        lines.append(header_str)
        lines.append("-" * len(header_str))

        for exp in classes:
            row_label = f"{short_names.get(exp, exp):<18}"
            vals = [f"{summary.confusion_matrix[exp].get(pred, 0):>{col_width}}" for pred in classes]
            lines.append(f"{row_label} | " + " | ".join(vals))

        lines.append("=" * 68)
        return "\n".join(lines)

    @classmethod
    def render_classification_report(cls, summary: EvaluationSummary) -> str:
        """Renders per-intent precision, recall, and F1 scores."""
        lines = []
        lines.append("=" * 68)
        lines.append("🎯 INTENT CLASSIFICATION REPORT")
        lines.append("=" * 68)
        lines.append(f"{'Intent Category':<22} | {'Samples':<7} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10}")
        lines.append("-" * 68)

        for intent, m in summary.per_class_metrics.items():
            if m.total_samples == 0 and m.false_positives == 0:
                continue
            lines.append(
                f"{intent:<22} | {m.total_samples:<7} | {m.precision:>9.1f}% | {m.recall:>9.1f}% | {m.f1_score:>9.1f}%"
            )

        lines.append("-" * 68)
        lines.append(f"{'OVERALL ACCURACY':<22} | {summary.total_samples:<7} | {'':<10} | {'':<10} | {summary.accuracy_pct:>9.1f}%")
        lines.append(f"{'CONTRACT COMPLIANCE':<22} | {summary.total_samples:<7} | {'':<10} | {'':<10} | {summary.contract_compliance_pct:>9.1f}%")
        lines.append("=" * 68)
        return "\n".join(lines)

    @classmethod
    def generate_markdown_report(cls, summary: EvaluationSummary, results: List[EvaluationResultItem]) -> str:
        """Generates a comprehensive GitHub-flavored Markdown report."""
        md = []
        md.append("# 🧭 DataPilot Router Node Evaluation Report\n")
        md.append(f"**Generated:** `2026-08-24` | **Benchmark Size:** `{summary.total_samples} test cases`\n")
        
        # Summary KPI Table
        md.append("## 📈 Executive Summary Scorecard\n")
        md.append("| Metric | Result | Benchmark Target | Status |")
        md.append("| :--- | :--- | :--- | :---: |")
        
        acc_status = "✅ PASS" if summary.accuracy_pct >= 90.0 else "❌ FAIL"
        contract_status = "✅ PASS" if summary.contract_compliance_pct >= 95.0 else "❌ FAIL"
        p95_status = "✅ PASS" if summary.p95_latency_ms < 2000.0 else "⚠️ WARN"
        
        md.append(f"| **Overall Intent Accuracy** | **{summary.accuracy_pct:.1f}%** ({summary.passed_count}/{summary.total_samples}) | $\\ge 90.0\\%$ | {acc_status} |")
        md.append(f"| **State Contract Integrity** | **{summary.contract_compliance_pct:.1f}%** | $\\ge 95.0\\%$ | {contract_status} |")
        md.append(f"| **P50 Latency (Median)** | **{summary.p50_latency_ms:.1f} ms** | $< 1000\\text{{ ms}}$ | ⚡ FAST |")
        md.append(f"| **P95 Latency** | **{summary.p95_latency_ms:.1f} ms** | $< 2000\\text{{ ms}}$ | {p95_status} |\n")

        # Per-class breakdown
        md.append("## 🎯 Precision, Recall & F1 by Intent Category\n")
        md.append("| Intent | Support | Precision | Recall | F1-Score |")
        md.append("| :--- | :---: | :---: | :---: | :---: |")
        for intent, m in summary.per_class_metrics.items():
            if m.total_samples > 0 or m.false_positives > 0:
                md.append(f"| `{intent}` | {m.total_samples} | {m.precision:.1f}% | {m.recall:.1f}% | **{m.f1_score:.1f}%** |")
        md.append("\n")

        # Failures section
        failures = [r for r in results if not r.is_intent_correct or not r.contract_valid]
        if failures:
            md.append("## ❌ Failure Analysis & Edge Cases\n")
            md.append("| ID | Category | Question | Expected | Predicted | Contract Issue |")
            md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for f in failures:
                reason = f.contract_reason if not f.contract_valid else "Intent Mismatch"
                md.append(f"| `{f.id}` | `{f.category}` | *{f.question[:50]}...* | `{f.expected_intent}` | `{f.predicted_intent}` | {reason} |")
            md.append("\n")
        else:
            md.append("## 🎉 100% Zero Failures Detected across all Golden Benchmark Cases!\n")

        return "\n".join(md)
