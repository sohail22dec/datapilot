import time
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.guardrails.output_guard import (
    sanitize_and_validate_output,
    verify_number_grounding,
    build_ground_truth_numbers,
    extract_numbers_from_text,
    redact_secrets,
    scrub_stack_traces,
)


def test_clean_executive_summary_preservation():
    """
    Ensures that legitimate, well-formatted executive summaries
    (with bold metrics, INR formatting, bullet points) are preserved cleanly.
    """
    clean_texts = [
        "- Total revenue for last month was **₹1,24,500** across **45 orders**.\n- Top region was **India** with **₹85,000** in sales.",
        "Based on the analysis, **Jennifer Phillips** is the top customer with **23 total purchases**.",
        "- Net profit margin increased by **14.5%** quarter-over-quarter.\n- Return rate remained low at **1.2%**.",
    ]

    print("\n--- 1. Testing Legitimate Executive Summaries (Clean Preservation) ---")
    for text in clean_texts:
        outcome = sanitize_and_validate_output(text, has_data=True)
        print(f"[PASS] Text preserved cleanly ({outcome.latency_ms:.3f}ms) -> '{outcome.sanitized_output[:50]}...'")
        assert outcome.is_safe is True
        assert "₹" in outcome.sanitized_output or "**" in outcome.sanitized_output


def test_number_grounding_and_hallucination_detection():
    """
    Tests that numbers matching real DB rows & metrics pass grounding,
    and fabricated numbers are properly caught.
    """
    print("\n--- 2. Testing Mathematical Number Grounding ---")

    sample_rows = [
        {"customer_name": "Jennifer Phillips", "total_spend": 32400.0, "orders_count": 23},
        {"customer_name": "Michael Smith", "total_spend": 18200.0, "orders_count": 12},
    ]
    sample_metrics = {"net_margin_pct": 14.5, "total_revenue": 50600.0}

    # Case A: 100% Grounded Summary (all numbers exist in DB rows/metrics/sums)
    grounded_summary = (
        "- **Jennifer Phillips** is our top customer with **₹32,400** across **23 orders**.\n"
        "- Total revenue across both customers reached **₹50,600** with a net margin of **14.5%**."
    )
    outcome_grounded = sanitize_and_validate_output(grounded_summary, rows=sample_rows, metrics=sample_metrics)
    print(f"[GROUNDED PASS] is_grounded={outcome_grounded.is_grounded}, verified={outcome_grounded.grounded_numbers}")
    assert outcome_grounded.is_grounded is True
    assert 32400.0 in outcome_grounded.grounded_numbers
    assert 23.0 in outcome_grounded.grounded_numbers
    assert 50600.0 in outcome_grounded.grounded_numbers
    assert 14.5 in outcome_grounded.grounded_numbers
    assert len(outcome_grounded.unverified_numbers) == 0

    # Case B: Hallucinated Summary (contains fabricated numbers like ₹999,000 and 88.5%)
    hallucinated_summary = (
        "- **Jennifer Phillips** spent **₹999,000** on **88 orders**.\n"
        "- Net margin was an astronomical **88.5%**."
    )
    outcome_hallucinated = sanitize_and_validate_output(hallucinated_summary, rows=sample_rows, metrics=sample_metrics)
    print(f"[HALLUCINATION CAUGHT] is_grounded={outcome_hallucinated.is_grounded}, unverified={outcome_hallucinated.unverified_numbers}")
    assert outcome_hallucinated.is_grounded is False
    assert 999000.0 in outcome_hallucinated.unverified_numbers
    assert "UNGROUNDED_NUMBER_DETECTED" in outcome_hallucinated.violations_detected


def test_api_key_and_secret_redaction():
    """
    Ensures that leaked Groq keys, Gemini keys, PostgreSQL URIs, Bearer tokens,
    and env assignments are scrubbed.
    """
    print("\n--- 3. Testing API Key & Secret Redaction ---")

    # 1. Groq Key
    groq_leak = "Summary completed using key gsk_abcdef1234567890abcdef123456 for authorization."
    res_groq = sanitize_and_validate_output(groq_leak)
    print(f"[REDACTED GROQ] -> {res_groq.sanitized_output}")
    assert "gsk_" not in res_groq.sanitized_output
    assert "[REDACTED_API_KEY]" in res_groq.sanitized_output
    assert "GROQ_API_KEY_LEAK" in res_groq.violations_detected

    # 2. Gemini Key
    gemini_leak = "Connected with AIza_SAMPLE_TEST_KEY_FOR_VALIDATION_123 to generate response."
    res_gem = sanitize_and_validate_output(gemini_leak)
    print(f"[REDACTED GEMINI] -> {res_gem.sanitized_output}")
    assert "AIza_" not in res_gem.sanitized_output
    assert "[REDACTED_API_KEY]" in res_gem.sanitized_output
    assert "GEMINI_API_KEY_LEAK" in res_gem.violations_detected

    # 3. Database URI
    db_leak = "Queried database at postgresql://postgres:SecretPassword123@aws-0-pooler.supabase.com:6543/postgres directly."
    res_db = sanitize_and_validate_output(db_leak)
    print(f"[REDACTED DB URI] -> {res_db.sanitized_output}")
    assert "SecretPassword123" not in res_db.sanitized_output
    assert "[REDACTED_DATABASE_URI]" in res_db.sanitized_output
    assert "DATABASE_URI_LEAK" in res_db.violations_detected

    # 4. Bearer Token
    token_leak = "Authorization header used: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sampletoken."
    res_tok = sanitize_and_validate_output(token_leak)
    print(f"[REDACTED TOKEN] -> {res_tok.sanitized_output}")
    assert "eyJhbGci" not in res_tok.sanitized_output
    assert "Bearer [REDACTED_TOKEN]" in res_tok.sanitized_output
    assert "BEARER_TOKEN_LEAK" in res_tok.violations_detected

    # 5. Env variable
    env_leak = "Configurations: GEMINI_API_KEY=AIza_SECRET_TEST_KEY and DATABASE_URL=postgresql://secret"
    res_env = sanitize_and_validate_output(env_leak)
    print(f"[REDACTED ENV] -> {res_env.sanitized_output}")
    assert "AIza_SECRET_TEST_KEY" not in res_env.sanitized_output
    assert "GEMINI_API_KEY=[REDACTED]" in res_env.sanitized_output


def test_stack_trace_and_driver_error_scrubbing():
    """
    Ensures raw Python tracebacks or database driver exceptions are replaced with
    polite executive fallbacks.
    """
    print("\n--- 4. Testing Stack Trace & Driver Error Scrubbing ---")

    traceback_dump = """
    Traceback (most recent call last):
      File "/app/tools/db_tool.py", line 101, in execute_db_query
        result = conn.execute(text(sql))
      psycopg2.OperationalError: server closed the connection unexpectedly
    """
    res_trace = sanitize_and_validate_output(traceback_dump)
    print(f"[SCRUBBED TRACEBACK] -> {res_trace.sanitized_output}")
    assert "Traceback" not in res_trace.sanitized_output
    assert "psycopg2" not in res_trace.sanitized_output
    assert "operational issue" in res_trace.sanitized_output
    assert "RAW_STACK_TRACE_SCRUBBED" in res_trace.violations_detected


def test_empty_output_fallback():
    """
    Ensures empty or whitespace outputs are handled cleanly.
    """
    print("\n--- 5. Testing Empty Output Fallback ---")

    res_empty_with_data = sanitize_and_validate_output("   \n\t  ", has_data=True)
    print(f"[EMPTY WITH DATA] -> '{res_empty_with_data.sanitized_output}'")
    assert res_empty_with_data.sanitized_output == "Analysis completed based on the retrieved data records."
    assert "EMPTY_OUTPUT_FALLBACK" in res_empty_with_data.violations_detected

    res_empty_no_data = sanitize_and_validate_output("", has_data=False)
    print(f"[EMPTY NO DATA] -> '{res_empty_no_data.sanitized_output}'")
    assert res_empty_no_data.sanitized_output == "No matching records were found in the database for your inquiry."


def test_output_guard_latency_benchmark():
    """
    Benchmarks 1,000 iterations to verify performance is strictly sub-millisecond (<0.05ms average).
    """
    print("\n--- 6. Benchmarking Output Guardrail Latency (1,000 iterations) ---")
    sample_rows = [{"spend": 124500.0, "orders": 45}]
    sample_outputs = [
        "- Total revenue was **₹1,24,500** across **45 orders**.",
        "Connected with gsk_abcdef1234567890abcdef123456 to query database.",
        "Traceback (most recent call last): psycopg2.OperationalError",
        "Top customer segment is VIP with 32% share.",
        "   \n\t   ",
    ]

    total_runs = 1000
    start = time.perf_counter()
    for i in range(total_runs):
        text = sample_outputs[i % len(sample_outputs)]
        sanitize_and_validate_output(text, rows=sample_rows, has_data=True)
    total_elapsed_ms = (time.perf_counter() - start) * 1000
    avg_latency_ms = total_elapsed_ms / total_runs

    print(f"Total time for {total_runs} validations: {total_elapsed_ms:.2f}ms")
    print(f"Average latency per output: {avg_latency_ms:.4f}ms (Goal: < 0.05ms)")
    assert avg_latency_ms < 0.05, f"Output Guardrail latency exceeded threshold: {avg_latency_ms}ms"


if __name__ == "__main__":
    print("===============================================================")
    print("🛡️  DATAPILOT OUTPUT GUARDRAILS & NUMBER GROUNDING TEST SUITE")
    print("===============================================================")
    test_clean_executive_summary_preservation()
    test_number_grounding_and_hallucination_detection()
    test_api_key_and_secret_redaction()
    test_stack_trace_and_driver_error_scrubbing()
    test_empty_output_fallback()
    test_output_guard_latency_benchmark()
    print("\n===============================================================")
    print("✅ ALL OUTPUT GUARDRAIL & GROUNDING TESTS PASSED SUCCESSFULLY!")
    print("===============================================================")
