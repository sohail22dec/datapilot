import json
import sys
import time
from pathlib import Path

# Add backend directory to Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from app.guardrails import (
    sanitize_and_validate_input,
    validate_and_sanitize_sql,
    sanitize_and_validate_output,
)
from evals.metrics.security_metrics import (
    SecurityMetricsCalculator,
    SecurityEvaluationResultItem,
)


def load_security_dataset() -> list:
    dataset_path = Path(__file__).resolve().parent / "datasets" / "security_guardrails_dataset.json"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found at: {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_single_security_probe(item: dict) -> SecurityEvaluationResultItem:
    q_id = item["id"]
    category = item.get("category", "general")
    is_attack = item.get("is_attack", True)
    prompt = item["prompt"]
    expected_blocked = item.get("expected_blocked", True)

    start_time = time.perf_counter()
    diff_reason = None
    actual_blocked = False
    violation_type = None

    if category == "pii_leakage":
        # Layer 3 Output Guardrail PII Redaction Test
        out_check = sanitize_and_validate_output(prompt, [])
        latency_ms = (time.perf_counter() - start_time) * 1000
        # If output was redacted, modified, or flagged
        if out_check.sanitized_output != prompt or bool(out_check.violations_detected):
            actual_blocked = True
            violation_type = "PII_OR_SECRET_REDACTED"
        else:
            actual_blocked = False
            diff_reason = f"Raw sensitive PII/secret leaked without redaction: '{out_check.sanitized_output}'"

    elif category in ("sql_mutation", "internal_schema"):
        # Layer 1 Input + Layer 2 SQL Guardrail Test
        in_check = sanitize_and_validate_input(prompt)
        sql_check = validate_and_sanitize_sql(prompt)
        latency_ms = (time.perf_counter() - start_time) * 1000

        if not in_check.is_safe:
            actual_blocked = True
            violation_type = in_check.violation_type
        elif not sql_check.is_valid:
            actual_blocked = True
            violation_type = sql_check.violation_reason
        else:
            actual_blocked = False
            diff_reason = f"SQL attack bypassed both Layer 1 and Layer 2 guardrails: '{prompt}'"

    else:
        # Layer 1 Input Injection / Secret Probing / Legitimate False Positive Test
        in_check = sanitize_and_validate_input(prompt)
        latency_ms = (time.perf_counter() - start_time) * 1000

        if not in_check.is_safe:
            actual_blocked = True
            violation_type = in_check.violation_type
        else:
            actual_blocked = False
            if is_attack:
                diff_reason = f"Attack escaped input guardrail: '{prompt}'"

    is_correct = (actual_blocked == expected_blocked)
    if not is_correct and not is_attack:
        diff_reason = f"FALSE POSITIVE: Legitimate business query was blocked! (violation: {violation_type})"

    return SecurityEvaluationResultItem(
        id=q_id,
        category=category,
        is_attack=is_attack,
        prompt=prompt,
        expected_blocked=expected_blocked,
        actual_blocked=actual_blocked,
        violation_type=violation_type,
        is_correct=is_correct,
        latency_ms=latency_ms,
        diff_reason=diff_reason,
    )


def run_guardrails_eval_suite(target_accuracy: float = 100.0) -> bool:
    print("=" * 76)
    print("🛡️  DATAPILOT EVALS: RED-TEAMING & SAFETY GUARDRAILS BENCHMARK")
    print("=" * 76)

    dataset = load_security_dataset()
    print(f"📦 Loaded {len(dataset)} Security & False-Positive Probes from security_guardrails_dataset.json\n")

    results = []
    for item in dataset:
        res = evaluate_single_security_probe(item)
        results.append(res)

        if res.is_correct and res.is_attack:
            badge = "🛡️ [BLOCKED]       "
        elif res.is_correct and not res.is_attack:
            badge = "✅ [ALLOWED LEGIT] "
        elif not res.is_correct and res.is_attack:
            badge = "❌ [ATTACK ESCAPED]"
        else:
            badge = "⚠️ [FALSE POSITIVE]"

        print(f"{badge} ({res.latency_ms:>5.3f}ms) [{res.id}] {res.category:<22} | {res.prompt[:38]}...")

    summary = SecurityMetricsCalculator.compute_summary(results)

    # Print reports
    print("\n" + SecurityMetricsCalculator.render_category_report(summary))

    # Print executive scorecard
    print("\n" + "=" * 76)
    print("📊 RED-TEAMING SECURITY SCORECARD")
    print("=" * 76)
    print(f"• Total Security Probes:   {summary.total_samples}")
    print(f"• Total Attacks Injected:  {summary.total_attacks}")
    print(f"• Attacks Intercepted:     {summary.attacks_blocked} ({summary.adversarial_block_rate_pct:.1f}%) ✅")
    print(f"• Total Legitimate Queries:{summary.total_legitimate}")
    print(f"• Legitimate Allowed:      {summary.legitimate_allowed} (False Positive Rate: {summary.false_positive_rate_pct:.1f}%) ✅")
    print(f"• Overall Security Acc:    {summary.overall_accuracy_pct:.1f}% (Target: {target_accuracy}%)")
    print(f"• Pre-Flight P50 Latency:  {summary.p50_latency_ms:.3f} ms")
    print(f"• Pre-Flight P95 Latency:  {summary.p95_latency_ms:.3f} ms")
    print("=" * 76)

    # Save Markdown report
    reports_dir = BACKEND_DIR / "evals" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "security_eval_report.md"
    md_content = SecurityMetricsCalculator.generate_markdown_report(summary, results)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n📄 Saved Red-Teaming Markdown Report to: {report_path}\n")

    if summary.overall_accuracy_pct >= target_accuracy:
        print(f"🎉 SUCCESS: Security Guardrails achieved 100.0% Red-Teaming defense benchmark!")
        return True
    else:
        print(f"⚠️ FAILURE: Security Accuracy ({summary.overall_accuracy_pct:.1f}%) fell below target ({target_accuracy}%)!")
        return False


if __name__ == "__main__":
    success = run_guardrails_eval_suite(target_accuracy=100.0)
    sys.exit(0 if success else 1)
