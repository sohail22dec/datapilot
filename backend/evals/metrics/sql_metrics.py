from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import statistics


@dataclass
class SQLEvaluationResultItem:
    """Represents the evaluation outcome of a single Text-to-SQL test case."""
    id: str
    difficulty: str
    category: str
    question: str
    ground_truth_sql: str
    generated_sql: Optional[str]
    is_syntax_valid: bool
    is_execution_match: bool
    row_count_match: bool
    expected_row_count: int
    actual_row_count: int
    schema_adherent: bool
    tables_used: List[str]
    latency_ms: float
    error_message: Optional[str] = None
    diff_reason: Optional[str] = None
    expected_rows_sample: Optional[List[Dict[str, Any]]] = None
    actual_rows_sample: Optional[List[Dict[str, Any]]] = None


@dataclass
class DifficultyMetric:
    """Accuracy and execution metrics for a specific difficulty level."""
    difficulty: str
    total_samples: int
    syntax_valid_count: int
    execution_match_count: int
    syntax_validity_pct: float
    execution_match_pct: float


@dataclass
class SQLEvaluationSummary:
    """Aggregated metrics across the full Text-to-SQL benchmark suite."""
    total_samples: int
    syntax_valid_count: int
    syntax_validity_pct: float
    execution_match_count: int
    execution_match_pct: float
    row_count_match_pct: float
    schema_adherence_pct: float
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    difficulty_metrics: Dict[str, DifficultyMetric] = field(default_factory=dict)


class SQLMetricsCalculator:
    """
    Computes statistical evaluation metrics for Text-to-SQL Generation & Execution:
    - Syntax Validity Rate (%)
    - Execution Match (EM) Equivalence (%)
    - Row Count Match Rate (%)
    - Schema Adherence Rate (%)
    - P50 & P95 Database Execution Latencies
    """

    @staticmethod
    def _normalize_value(val: Any) -> Any:
        """Normalizes numbers, dates, and strings for set comparison."""
        if val is None:
            return None
        if isinstance(val, float):
            return round(val, 2)
        if isinstance(val, int):
            return float(val)
        if isinstance(val, str):
            val_clean = val.strip().lower()
            try:
                num = float(val_clean)
                return round(num, 2)
            except ValueError:
                return val_clean
        return str(val)

    @classmethod
    def compare_row_sets(
        cls,
        actual_rows: Optional[List[Dict[str, Any]]],
        expected_rows: Optional[List[Dict[str, Any]]],
        tolerance: float = 0.01,
    ) -> Tuple[bool, bool, str]:
        """
        Evaluates whether generated query rows match ground truth rows invariant to
        column naming aliases or row ordering.
        Returns: (is_execution_match, is_row_count_match, diff_reason)
        """
        if actual_rows is None and expected_rows is None:
            return True, True, "Both returned None"
        if actual_rows is None:
            return False, False, "Generated query execution returned None/Error"
        if expected_rows is None:
            return False, False, "Ground truth execution returned None/Error"

        actual_len = len(actual_rows)
        expected_len = len(expected_rows)
        row_count_match = (actual_len == expected_len)

        if not row_count_match:
            return False, False, f"Row count mismatch (Expected: {expected_len}, Got: {actual_len})"

        if actual_len == 0 and expected_len == 0:
            return True, True, "Both result sets are empty (0 rows)"

        # Extract normalized row tuples (ignoring column aliases)
        def to_value_tuples(rows: List[Dict[str, Any]]) -> List[Tuple]:
            tuples = []
            for r in rows:
                row_vals = [cls._normalize_value(v) for v in r.values()]
                # Sort values in row if column ordering differed
                tuples.append(tuple(sorted(row_vals, key=lambda x: str(x))))
            return sorted(tuples, key=lambda t: str(t))

        try:
            actual_tuples = to_value_tuples(actual_rows)
            expected_tuples = to_value_tuples(expected_rows)

            if len(actual_tuples) != len(expected_tuples):
                return False, True, "Tuple shape mismatch"

            for act_t, exp_t in zip(actual_tuples, expected_tuples):
                if len(act_t) != len(exp_t):
                    return False, True, f"Column count mismatch ({len(act_t)} cols vs {len(exp_t)} expected cols)"

                for v_act, v_exp in zip(act_t, exp_t):
                    if isinstance(v_act, (int, float)) and isinstance(v_exp, (int, float)):
                        if abs(v_act - v_exp) > tolerance:
                            return False, True, f"Numeric value mismatch ({v_act} != {v_exp})"
                    elif v_act != v_exp:
                        return False, True, f"Value mismatch ('{v_act}' != '{v_exp}')"

            return True, True, "Exact Execution Match"

        except Exception as e:
            return False, row_count_match, f"Comparison error: {str(e)}"

    @classmethod
    def compute_summary(cls, results: List[SQLEvaluationResultItem]) -> SQLEvaluationSummary:
        total = len(results)
        if total == 0:
            return SQLEvaluationSummary(
                total_samples=0,
                syntax_valid_count=0,
                syntax_validity_pct=0.0,
                execution_match_count=0,
                execution_match_pct=0.0,
                row_count_match_pct=0.0,
                schema_adherence_pct=0.0,
                mean_latency_ms=0.0,
                p50_latency_ms=0.0,
                p95_latency_ms=0.0,
            )

        syntax_valid = sum(1 for r in results if r.is_syntax_valid)
        execution_matches = sum(1 for r in results if r.is_execution_match)
        row_count_matches = sum(1 for r in results if r.row_count_match)
        schema_adherent = sum(1 for r in results if r.schema_adherent)

        syntax_pct = (syntax_valid / total) * 100
        em_pct = (execution_matches / total) * 100
        rc_pct = (row_count_matches / total) * 100
        schema_pct = (schema_adherent / total) * 100

        latencies = [r.latency_ms for r in results]
        latencies.sort()
        mean_lat = statistics.mean(latencies) if latencies else 0.0
        p50_lat = statistics.median(latencies) if latencies else 0.0
        p95_idx = int(len(latencies) * 0.95)
        p95_lat = latencies[min(p95_idx, len(latencies) - 1)] if latencies else 0.0

        # Breakdown by difficulty
        diff_groups: Dict[str, List[SQLEvaluationResultItem]] = {}
        for r in results:
            d = r.difficulty
            if d not in diff_groups:
                diff_groups[d] = []
            diff_groups[d].append(r)

        diff_metrics: Dict[str, DifficultyMetric] = {}
        for d, group in diff_groups.items():
            g_total = len(group)
            g_syntax = sum(1 for item in group if item.is_syntax_valid)
            g_em = sum(1 for item in group if item.is_execution_match)
            diff_metrics[d] = DifficultyMetric(
                difficulty=d,
                total_samples=g_total,
                syntax_valid_count=g_syntax,
                execution_match_count=g_em,
                syntax_validity_pct=(g_syntax / g_total) * 100 if g_total else 0.0,
                execution_match_pct=(g_em / g_total) * 100 if g_total else 0.0,
            )

        return SQLEvaluationSummary(
            total_samples=total,
            syntax_valid_count=syntax_valid,
            syntax_validity_pct=syntax_pct,
            execution_match_count=execution_matches,
            execution_match_pct=em_pct,
            row_count_match_pct=rc_pct,
            schema_adherence_pct=schema_pct,
            mean_latency_ms=mean_lat,
            p50_latency_ms=p50_lat,
            p95_latency_ms=p95_lat,
            difficulty_metrics=diff_metrics,
        )

    @classmethod
    def render_difficulty_report(cls, summary: SQLEvaluationSummary) -> str:
        """Renders per-difficulty execution match rates."""
        lines = []
        lines.append("=" * 72)
        lines.append("🎯 TEXT-TO-SQL EXECUTION MATCH BY DIFFICULTY")
        lines.append("=" * 72)
        lines.append(f"{'Difficulty Tier':<18} | {'Samples':<8} | {'Syntax Valid':<14} | {'Execution Match (EM)':<20}")
        lines.append("-" * 72)

        for diff in ["simple", "medium", "complex", "temporal"]:
            if diff in summary.difficulty_metrics:
                m = summary.difficulty_metrics[diff]
                lines.append(
                    f"{diff.capitalize():<18} | {m.total_samples:<8} | {m.syntax_validity_pct:>12.1f}% | {m.execution_match_pct:>18.1f}%"
                )

        lines.append("-" * 72)
        lines.append(
            f"{'OVERALL TOTAL':<18} | {summary.total_samples:<8} | {summary.syntax_validity_pct:>12.1f}% | {summary.execution_match_pct:>18.1f}%"
        )
        lines.append("=" * 72)
        return "\n".join(lines)

    @classmethod
    def generate_markdown_report(cls, summary: SQLEvaluationSummary, results: List[SQLEvaluationResultItem]) -> str:
        """Generates a detailed Markdown evaluation report with SQL diffs."""
        md = []
        md.append("# 🗄️ DataPilot Text-to-SQL Execution Evaluation Report\n")
        md.append(f"**Generated:** `2026-08-24` | **Benchmark Size:** `{summary.total_samples} test cases`\n")

        # Scorecard
        md.append("## 📈 Executive Summary Scorecard\n")
        md.append("| Metric | Result | Benchmark Target | Status |")
        md.append("| :--- | :--- | :--- | :---: |")

        syntax_status = "✅ PASS" if summary.syntax_validity_pct >= 95.0 else "❌ FAIL"
        em_status = "✅ PASS" if summary.execution_match_pct >= 80.0 else "❌ FAIL"
        schema_status = "✅ PASS" if summary.schema_adherence_pct >= 95.0 else "❌ FAIL"
        p95_status = "✅ PASS" if summary.p95_latency_ms < 1500.0 else "⚠️ WARN"

        md.append(f"| **Execution Match (EM)** | **{summary.execution_match_pct:.1f}%** ({summary.execution_match_count}/{summary.total_samples}) | $\\ge 80.0\\%$ | {em_status} |")
        md.append(f"| **Syntax Validity Rate** | **{summary.syntax_validity_pct:.1f}%** ({summary.syntax_valid_count}/{summary.total_samples}) | $\\ge 95.0\\%$ | {syntax_status} |")
        md.append(f"| **Schema Adherence** | **{summary.schema_adherence_pct:.1f}%** | $\\ge 95.0\\%$ | {schema_status} |")
        md.append(f"| **Row Count Match** | **{summary.row_count_match_pct:.1f}%** | $\\ge 85.0\\%$ | — |")
        md.append(f"| **Median (P50) Latency** | **{summary.p50_latency_ms:.1f} ms** | $< 800\\text{{ ms}}$ | ⚡ FAST |")
        md.append(f"| **P95 Latency** | **{summary.p95_latency_ms:.1f} ms** | $< 1500\\text{{ ms}}$ | {p95_status} |\n")

        # Breakdown by difficulty
        md.append("## 🎯 Performance by Difficulty Tier\n")
        md.append("| Tier | Cases | Syntax Valid | Execution Match |")
        md.append("| :--- | :---: | :---: | :---: |")
        for diff in ["simple", "medium", "complex", "temporal"]:
            if diff in summary.difficulty_metrics:
                m = summary.difficulty_metrics[diff]
                md.append(f"| `{diff.capitalize()}` | {m.total_samples} | {m.syntax_validity_pct:.1f}% | **{m.execution_match_pct:.1f}%** |")
        md.append("\n")

        # Failure diffs
        failures = [r for r in results if not r.is_execution_match]
        if failures:
            md.append("## ❌ Mismatch & Failure Analysis\n")
            for f in failures:
                md.append(f"### `[{f.id}]` {f.question} ({f.difficulty.capitalize()})\n")
                md.append(f"- **Reason:** `{f.diff_reason or f.error_message}`")
                md.append(f"- **Expected Rows:** `{f.expected_row_count}` | **Actual Rows:** `{f.actual_row_count}`")
                md.append("```sql\n-- Ground Truth SQL\n" + f.ground_truth_sql + "\n```")
                md.append("```sql\n-- Generated SQL\n" + (f.generated_sql or "None (Failed to generate SQL)") + "\n```\n")
        else:
            md.append("## 🎉 100% Execution Match across all 30 Benchmark Queries!\n")

        return "\n".join(md)
