import time
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.guardrails.sql_guard import (
    validate_and_sanitize_sql,
    enforce_query_limit,
    strip_sql_fences_and_comments,
)


def test_valid_read_only_queries():
    """
    Ensures that standard read-only SQL queries with SELECT, CTEs (WITH),
    JOINs, GROUP BY, and aggregations pass with high speed.
    """
    valid_queries = [
        "SELECT id, name, email FROM customers LIMIT 10;",
        "SELECT country, SUM(total_amount) as rev FROM orders GROUP BY country ORDER BY rev DESC LIMIT 5;",
        """
        WITH monthly_metrics AS (
            SELECT DATE_TRUNC('month', created_at) as month, SUM(total_amount) as sales
            FROM orders
            GROUP BY 1
        )
        SELECT month, sales FROM monthly_metrics ORDER BY month ASC LIMIT 12;
        """,
        "SELECT p.category, COUNT(oi.id) FROM products p JOIN order_items oi ON p.id = oi.product_id GROUP BY p.category LIMIT 20;",
    ]

    print("\n--- 1. Testing Legitimate Read-Only SQL Queries ---")
    for q in valid_queries:
        outcome = validate_and_sanitize_sql(q)
        print(f"[PASS] Safe SQL validated ({outcome.execution_time_ms:.3f}ms) -> {outcome.sanitized_sql[:50]}...")
        assert outcome.is_valid is True, f"Failed on valid SQL: {q}"
        assert outcome.violation_type is None
        assert "LIMIT" in outcome.sanitized_sql


def test_auto_limit_injection_and_clamping():
    """
    Tests that:
    1. Queries missing LIMIT get 'LIMIT 50' auto-injected.
    2. Queries with excessive LIMIT (e.g. LIMIT 5000) get clamped to 'LIMIT 50'.
    3. Queries with safe LIMIT (e.g. LIMIT 10) retain their limit.
    """
    print("\n--- 2. Testing Unbounded Query Protection & Auto-Limiting ---")

    # Case 1: Missing LIMIT
    q_no_limit = "SELECT id, name, country FROM customers"
    res1 = validate_and_sanitize_sql(q_no_limit, default_limit=50)
    assert res1.is_valid is True
    assert "LIMIT 50" in res1.sanitized_sql
    print(f"[AUTO-INJECT] Added missing LIMIT 50 -> {res1.sanitized_sql.strip()}")

    # Case 2: Excessive LIMIT (50,000 rows)
    q_huge_limit = "SELECT * FROM order_items LIMIT 50000;"
    res2 = validate_and_sanitize_sql(q_huge_limit, default_limit=50, max_limit=100)
    assert res2.is_valid is True
    assert "LIMIT 50" in res2.sanitized_sql
    assert "50000" not in res2.sanitized_sql
    print(f"[CLAMPED] Clamped 50,000 to LIMIT 50 -> {res2.sanitized_sql.strip()}")

    # Case 3: Safe small LIMIT (retained)
    q_safe_limit = "SELECT id, name FROM products LIMIT 5;"
    res3 = validate_and_sanitize_sql(q_safe_limit, default_limit=50, max_limit=100)
    assert res3.is_valid is True
    assert "LIMIT 5" in res3.sanitized_sql
    print(f"[RETAINED] Kept user LIMIT 5 -> {res3.sanitized_sql.strip()}")


def test_mutating_sql_blocking():
    """
    Ensures that all DDL/DML mutation commands are strictly blocked.
    """
    mutating_queries = [
        "DROP TABLE customers;",
        "DELETE FROM orders WHERE total_amount < 100;",
        "UPDATE customers SET email = 'hacker@evil.com' WHERE id = 1;",
        "INSERT INTO products (name, price) VALUES ('Backdoor', 0.0);",
        "TRUNCATE TABLE order_items;",
        "ALTER TABLE users ADD COLUMN is_admin BOOLEAN;",
        "GRANT ALL PRIVILEGES ON ALL TABLES TO public;",
        "REVOKE SELECT ON customers FROM app_user;",
        "EXEC xp_cmdshell('whoami');",
        "CALL drop_all_data();",
        "COPY customers TO '/tmp/data.csv';",
    ]

    print("\n--- 3. Testing Mutating & Destructive SQL Rejection ---")
    for q in mutating_queries:
        outcome = validate_and_sanitize_sql(q)
        print(f"[BLOCKED] '{q[:40]}' -> type={outcome.violation_type} ({outcome.execution_time_ms:.3f}ms)")
        assert outcome.is_valid is False, f"Failed to block mutating SQL: {q}"
        assert outcome.violation_type in ("MUTATING_KEYWORD_DETECTED", "NON_READ_ONLY_STATEMENT")


def test_restricted_schema_access_control():
    """
    Ensures that queries attempting to access internal Supabase auth, vault,
    storage, or PostgreSQL system catalog tables are rejected.
    """
    restricted_queries = [
        "SELECT * FROM auth.users LIMIT 10;",
        "SELECT email, encrypted_password FROM auth.users;",
        "SELECT * FROM auth.identities;",
        "SELECT * FROM vault.secrets;",
        "SELECT * FROM vault.decrypted_secrets;",
        "SELECT * FROM storage.objects;",
        "SELECT * FROM pg_shadow;",
        "SELECT * FROM pg_authid;",
        "SELECT * FROM pg_catalog.pg_user;",
        "SELECT * FROM information_schema.user_mappings;",
    ]

    print("\n--- 4. Testing Schema Access Control (Blocking auth/vault/pg_shadow) ---")
    for q in restricted_queries:
        outcome = validate_and_sanitize_sql(q)
        print(f"[BLOCKED] '{q[:40]}' -> type={outcome.violation_type} ({outcome.execution_time_ms:.3f}ms)")
        assert outcome.is_valid is False, f"Failed to block restricted schema query: {q}"
        assert outcome.violation_type in (
            "AUTH_SCHEMA_RESTRICTED",
            "VAULT_SCHEMA_RESTRICTED",
            "STORAGE_SCHEMA_RESTRICTED",
            "POSTGRES_SYSTEM_CATALOG_RESTRICTED",
            "INFORMATION_SCHEMA_RESTRICTED",
        )


def test_multi_statement_chaining_blocking():
    """
    Ensures multiple statements chained with semicolons are rejected.
    """
    chained_queries = [
        "SELECT * FROM products; DROP TABLE customers;",
        "SELECT 1; SELECT 2; SELECT 3;",
        "SELECT * FROM orders; DELETE FROM order_items WHERE id > 0;",
    ]

    print("\n--- 5. Testing Multi-Statement Semicolon Chaining Blocking ---")
    for q in chained_queries:
        outcome = validate_and_sanitize_sql(q)
        print(f"[BLOCKED] '{q[:40]}' -> type={outcome.violation_type} ({outcome.execution_time_ms:.3f}ms)")
        assert outcome.is_valid is False
        assert outcome.violation_type == "MULTI_STATEMENT_PROHIBITED"


def test_code_fence_and_comment_stripping():
    """
    Tests that markdown code fences and SQL comments are cleanly stripped.
    """
    print("\n--- 6. Testing Markdown Code Fence & Comment Stripping ---")

    raw_fenced = "```sql\n-- Retrieve top 5 sales\nSELECT * FROM orders /* inline comment */ LIMIT 5;\n```"
    cleaned = strip_sql_fences_and_comments(raw_fenced)
    assert not cleaned.startswith("```")
    assert "--" not in cleaned
    assert "/*" not in cleaned
    assert "SELECT * FROM orders" in cleaned
    print(f"[CLEANED] Markdown fences & comments stripped -> '{cleaned}'")


def test_sql_guard_latency_benchmark():
    """
    Benchmarks 1,000 iterations to verify performance is strictly sub-millisecond (<0.1ms average).
    """
    print("\n--- 7. Benchmarking SQL Guardrail Latency (1,000 iterations) ---")
    sample_queries = [
        "SELECT id, name, email FROM customers LIMIT 10;",
        "SELECT * FROM orders WHERE status = 'delivered'",
        "SELECT * FROM auth.users",
        "DROP TABLE products;",
        "WITH monthly AS (SELECT * FROM orders) SELECT * FROM monthly LIMIT 5;",
    ]

    total_runs = 1000
    start = time.perf_counter()
    for i in range(total_runs):
        q = sample_queries[i % len(sample_queries)]
        validate_and_sanitize_sql(q)
    total_elapsed_ms = (time.perf_counter() - start) * 1000
    avg_latency_ms = total_elapsed_ms / total_runs

    print(f"Total time for {total_runs} validations: {total_elapsed_ms:.2f}ms")
    print(f"Average latency per query: {avg_latency_ms:.4f}ms (Goal: < 0.1ms)")
    assert avg_latency_ms < 0.1, f"SQL Guardrail latency exceeded threshold: {avg_latency_ms}ms"


if __name__ == "__main__":
    print("===============================================================")
    print("🛡️  DATAPILOT SQL & TOOL GUARDRAILS TEST SUITE")
    print("===============================================================")
    test_valid_read_only_queries()
    test_auto_limit_injection_and_clamping()
    test_mutating_sql_blocking()
    test_restricted_schema_access_control()
    test_multi_statement_chaining_blocking()
    test_code_fence_and_comment_stripping()
    test_sql_guard_latency_benchmark()
    print("\n===============================================================")
    print("✅ ALL SQL GUARDRAIL TESTS PASSED SUCCESSFULLY!")
    print("===============================================================")
