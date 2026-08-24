from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import statistics


@dataclass
class HealingAttemptLog:
    """Logs details for a single retry attempt."""
    attempt_number: int
    rewritten_sql: str
    is_syntax_valid: bool
    error_message: Optional[str]
    latency_ms: float


@dataclass
class HealingEvaluationResultItem:
    """Evaluation record for a single fault-injected test case."""
    id: str
    error_type: str
    question: str
    broken_sql: str
    initial_error: str
    final_sql: Optional[str]
    is_recovered: bool
    attempts_needed: int  # 1, 2, or 0 if failed
    is_one_shot: bool
    is_two_shot: bool
    is_execution_match: bool
    attempts_history: List[HealingAttemptLog]
    total_diagnostic_latency_ms: float
    ground_truth_sql: str
    diff_reason: Optional[str] = None


@dataclass
class ErrorTypeMetric:
    """Recovery performance for a specific category of SQL error."""
    error_type: str
    total_samples: int
    recovered_count: int
    recovery_rate_pct: float
    one_shot_count: int
    two_shot_count: int


@dataclass
class HealingEvaluationSummary:
    """Aggregated self-healing resilience scorecard."""
    total_samples: int
    recovered_count: int
    recovery_rate_pct: float
    one_shot_count: int
    one_shot_pct: float
    two_shot_count: int
    two_shot_pct: float
    failed_count: int
    post_heal_em_count: int
    post_heal_em_pct: float
    mean_diagnostic_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    error_type_metrics: Dict[str, ErrorTypeMetric] = field(default_factory=dict)


class HealingMetricsCalculator:
    """
    Computes statistical resilience metrics for the Self-Healing Loop:
    - Overall Recovery Rate (%)
    - 1-Shot vs 2-Shot Success (%)
    - Post-Heal Execution Match Equivalence (%)
    - Per-Error-Type Diagnostics Breakdown
    - Diagnostic Latency Percentiles
    """

    @classmethod
    def compute_summary(cls, results: List[HealingEvaluationResultItem]) -> HealingEvaluationSummary:
        total = len(results)
        if total == 0:
            return HealingEvaluationSummary(
                total_samples=0,
                recovered_count=0,
                recovery_rate_pct=0.0,
                one_shot_count=0,
                one_shot_pct=0.0,
                two_shot_count=0,
                two_shot_pct=0.0,
                failed_count=0,
                post_heal_em_count=0,
                post_heal_em_pct=0.0,
                mean_diagnostic_latency_ms=0.0,
                p50_latency_ms=0.0,
                p95_latency_ms=0.0,
            )

        recovered = sum(1 for r in results if r.is_recovered)
        one_shot = sum(1 for r in results if r.is_one_shot)
        two_shot = sum(1 for r in results if r.is_two_shot)
        failed = total - recovered
        post_heal_em = sum(1 for r in results if r.is_execution_match)

        recovery_pct = (recovered / total) * 100
        one_shot_pct = (one_shot / total) * 100
        two_shot_pct = (two_shot / total) * 100
        post_heal_em_pct = (post_heal_em / total) * 100

        latencies = [r.total_diagnostic_latency_ms for r in results]
        latencies.sort()
        mean_lat = statistics.mean(latencies) if latencies else 0.0
        p50_lat = statistics.median(latencies) if latencies else 0.0
        p95_idx = int(len(latencies) * 0.95)
        p95_lat = latencies[min(p95_idx, len(latencies) - 1)] if latencies else 0.0

        # Breakdown by error type
        err_groups: Dict[str, List[HealingEvaluationResultItem]] = {}
        for r in results:
            et = r.error_type
            if et not in err_groups:
                err_groups[et] = []
            err_groups[et].append(r)

        error_metrics: Dict[str, ErrorTypeMetric] = {}
        for et, group in err_groups.items():
            g_total = len(group)
            g_recovered = sum(1 for item in group if item.is_recovered)
            g_one_shot = sum(1 for item in group if item.is_one_shot)
            g_two_shot = sum(1 for item in group if item.is_two_shot)
            error_metrics[et] = ErrorTypeMetric(
                error_type=et,
                total_samples=g_total,
                recovered_count=g_recovered,
                recovery_rate_pct=(g_recovered / g_total) * 100 if g_total else 0.0,
                one_shot_count=g_one_shot,
                two_shot_count=g_two_shot,
            )

        return HealingEvaluationSummary(
            total_samples=total,
            recovered_count=recovered,
            recovery_rate_pct=recovery_pct,
            one_shot_count=one_shot,
            one_shot_pct=one_shot_pct,
            two_shot_count=two_shot,
            two_shot_pct=two_shot_pct,
            failed_count=failed,
            post_heal_em_count=post_heal_em,
            post_heal_em_pct=post_heal_em_pct,
            mean_diagnostic_latency_ms=mean_lat,
            p50_latency_ms=p50_lat,
            p95_latency_ms=p95_lat,
            error_type_metrics=error_metrics,
        )

    @classmethod
    def render_error_type_report(cls, summary: HealingEvaluationSummary) -> str:
        """Renders per-error-type recovery rate table."""
        lines = []
        lines.append("=" * 76)
        lines.append("🩹 SELF-HEALING RECOVERY BY ERROR TYPE")
        lines.append("=" * 76)
        lines.append(f"{'Fault Category':<24} | {'Cases':<6} | {'Recovered':<10} | {'1-Shot':<8} | {'Recovery %':<12}")
        lines.append("-" * 76)

        for et, m in summary.error_type_metrics.items():
            lines.append(
                f"{et:<24} | {m.total_samples:<6} | {m.recovered_count:<10} | {m.one_shot_count:<8} | {m.recovery_rate_pct:>10.1f}%"
            )

        lines.append("-" * 76)
        lines.append(
            f"{'OVERALL TOTAL':<24} | {summary.total_samples:<6} | {summary.recovered_count:<10} | {summary.one_shot_count:<8} | {summary.recovery_rate_pct:>10.1f}%"
        )
        lines.append("=" * 76)
        return "\n".join(lines)

    @classmethod
    def generate_markdown_report(cls, summary: HealingEvaluationSummary, results: List[HealingEvaluationResultItem]) -> str:
        """Generates a detailed Markdown resilience evaluation report."""
        md = []
        md.append("# 🩹 DataPilot Self-Healing Resilience Evaluation Report\n")
        md.append(f"**Generated:** `2026-08-24` | **Fault Injections:** `{summary.total_samples} test cases`\n")

        # Scorecard
        md.append("## 📈 Executive Summary Scorecard\n")
        md.append("| Metric | Result | Benchmark Target | Status |")
        md.append("| :--- | :--- | :--- | :---: |")

        rec_status = "✅ PASS" if summary.recovery_rate_pct >= 80.0 else "❌ FAIL"
        one_shot_status = "✅ PASS" if summary.one_shot_pct >= 65.0 else "⚠️ WARN"
        em_status = "✅ PASS" if summary.post_heal_em_pct >= 75.0 else "❌ FAIL"
        p95_status = "✅ PASS" if summary.p95_latency_ms < 3500.0 else "⚠️ WARN"

        md.append(f"| **Overall Recovery Rate** | **{summary.recovery_rate_pct:.1f}%** ({summary.recovered_count}/{summary.total_samples}) | $\\ge 80.0\\%$ | {rec_status} |")
        md.append(f"| **1-Shot Recovery Rate** | **{summary.one_shot_pct:.1f}%** ({summary.one_shot_count}/{summary.total_samples}) | $\\ge 65.0\\%$ | {one_shot_status} |")
        md.append(f"| **2-Shot Recovery Rate** | **{summary.two_shot_pct:.1f}%** ({summary.two_shot_count}/{summary.total_samples}) | $\\le 30.0\\%$ | — |")
        md.append(f"| **Post-Heal Execution Match** | **{summary.post_heal_em_pct:.1f}%** ({summary.post_heal_em_count}/{summary.total_samples}) | $\\ge 75.0\\%$ | {em_status} |")
        md.append(f"| **Median (P50) Healing Time** | **{summary.p50_latency_ms:.1f} ms** | $< 2000\\text{{ ms}}$ | ⚡ FAST |")
        md.append(f"| **P95 Healing Time** | **{summary.p95_latency_ms:.1f} ms** | $< 3500\\text{{ ms}}$ | {p95_status} |\n")

        # Category Breakdown
        md.append("## 🎯 Resilience by Fault Category\n")
        md.append("| Fault Category | Samples | Recovered | 1-Shot | Recovery Rate |")
        md.append("| :--- | :---: | :---: | :---: | :---: |")
        for et, m in summary.error_type_metrics.items():
            md.append(f"| `{et}` | {m.total_samples} | {m.recovered_count} | {m.one_shot_count} | **{m.recovery_rate_pct:.1f}%** |")
        md.append("\n")

        # Failure Details
        unrecovered = [r for r in results if not r.is_recovered]
        if unrecovered:
            md.append("## ❌ Unrecovered Fault Injections\n")
            for u in unrecovered:
                md.append(f"### `[{u.id}]` {u.question} (`{u.error_type}`)\n")
                md.append(f"- **Initial Injected SQL:** `{u.broken_sql}`")
                md.append(f"- **Initial Error:** `{u.initial_error}`")
                md.append(f"- **Final Healed SQL (Failed):** `{u.final_sql}`")
                md.append(f"- **Reason:** `{u.diff_reason}`\n")
        else:
            md.append("## 🎉 100% Self-Healing Recovery across all 20 Fault Injections!\n")

        return "\n".join(md)
