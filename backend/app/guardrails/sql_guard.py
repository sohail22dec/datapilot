import re
import time
from typing import List, Optional
from pydantic import BaseModel, Field


class SQLGuardOutcome(BaseModel):
    """
    Validation and sanitization result for an LLM-generated SQL query.
    """
    is_valid: bool = Field(..., description="True if SQL passed all security, schema, and read-only checks.")
    sanitized_sql: str = Field(..., description="Sanitized, validated, and auto-limited SQL ready for database execution.")
    violation_reason: Optional[str] = Field(None, description="Detailed reason if query was blocked.")
    violation_type: Optional[str] = Field(None, description="Violation category code (e.g., MUTATING_KEYWORD, RESTRICTED_SCHEMA).")
    matched_patterns: List[str] = Field(default_factory=list, description="Specific matched violation pattern names.")
    execution_time_ms: float = Field(0.0, description="Latency spent verifying the SQL query in ms.")


# ---------------------------------------------------------------------------
# Forbidden Mutating Tokens & Commands (DDL / DML / Admin)
# ---------------------------------------------------------------------------

FORBIDDEN_MUTATING_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "GRANT", "REVOKE", "EXEC", "EXECUTE", "CREATE", "REPLACE",
    "MERGE", "UPSERT", "LOCK", "CALL", "COPY", "VACUUM",
    "REINDEX", "DISCARD", "INTO OUTFILE", "INTO DUMPFILE",
}

# ---------------------------------------------------------------------------
# Internal / Sensitive Schemas and Tables (Access Control)
# ---------------------------------------------------------------------------

RESTRICTED_SCHEMA_PATTERNS = [
    (
        "AUTH_SCHEMA_RESTRICTED",
        re.compile(r"\bauth\.(users|identities|refresh_tokens|audit_log_entries|sessions|mfa_factors|flow_state|sso_providers)\b", re.IGNORECASE),
        "Access to Supabase internal authentication tables (auth.*) containing user credentials and session data is strictly restricted.",
    ),
    (
        "VAULT_SCHEMA_RESTRICTED",
        re.compile(r"\bvault\.(secrets|decrypted_secrets)\b", re.IGNORECASE),
        "Access to the Supabase Vault (vault.*) containing encrypted private secrets and API keys is strictly prohibited.",
    ),
    (
        "STORAGE_SCHEMA_RESTRICTED",
        re.compile(r"\bstorage\.(objects|buckets|migrations)\b", re.IGNORECASE),
        "Access to raw Supabase storage metadata (storage.*) is restricted.",
    ),
    (
        "POSTGRES_SYSTEM_CATALOG_RESTRICTED",
        re.compile(r"\b(pg_shadow|pg_authid|pg_user|pg_roles|pg_stat_activity|pg_settings)\b|\bpg_catalog\.", re.IGNORECASE),
        "Direct queries accessing PostgreSQL system catalogs, server credentials, and administrative tables are prohibited.",
    ),
    (
        "INFORMATION_SCHEMA_RESTRICTED",
        re.compile(r"\binformation_schema\.(user_mappings|applicable_roles|administrable_role_authorizations)\b", re.IGNORECASE),
        "Queries probing security role authorizations in information_schema are restricted.",
    ),
]


# ---------------------------------------------------------------------------
# Core SQL Sanitization & Validation Engine
# ---------------------------------------------------------------------------

def strip_sql_fences_and_comments(sql_query: str) -> str:
    """
    Strips markdown code fences (```sql ... ```) and SQL line/block comments.
    """
    cleaned = sql_query.strip()

    # Strip markdown code fences (e.g. ```sql ... ``` or ``` ...)
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # Strip SQL line comments (-- comment)
    cleaned = re.sub(r"--.*$", "", cleaned, flags=re.MULTILINE)

    # Strip SQL block comments (/* comment */)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

    return cleaned.strip()


def enforce_query_limit(sql_query: str, default_limit: int = 50, max_limit: int = 100) -> str:
    """
    Enforces a strict LIMIT clause on the SQL query to prevent unbounded data fetching.
    1. If no LIMIT is present -> appends 'LIMIT {default_limit}'.
    2. If a LIMIT is present with a value > max_limit -> clamps it to 'LIMIT {default_limit}'.
    3. Retains any trailing semicolon properly.
    """
    sql = sql_query.rstrip(";").strip()

    # Regex to detect outer/trailing LIMIT clause: LIMIT <number> [OFFSET <number>]
    limit_match = re.search(r"\bLIMIT\s+(\d+)(\s+OFFSET\s+\d+)?\s*$", sql, re.IGNORECASE)

    if limit_match:
        current_limit = int(limit_match.group(1))
        offset_part = limit_match.group(2) or ""

        # If existing limit exceeds max allowed, clamp to default_limit
        if current_limit > max_limit or current_limit <= 0:
            sql = sql[:limit_match.start()] + f"LIMIT {default_limit}{offset_part}"
    else:
        # No outer LIMIT found -> safely append default limit
        sql = f"{sql}\nLIMIT {default_limit}"

    return f"{sql};"


def validate_and_sanitize_sql(
    sql_query: str,
    default_limit: int = 50,
    max_limit: int = 100,
) -> SQLGuardOutcome:
    """
    Executes comprehensive Layer-2 SQL execution guardrail checks:
    1. Strips markdown fences & comments.
    2. Enforces single-statement execution (prohibiting semicolon chaining).
    3. Validates strictly read-only statements (must start with SELECT or WITH CTE).
    4. Blocks mutating DDL/DML tokens (DROP, DELETE, UPDATE, INSERT, ALTER, etc.).
    5. Enforces schema access control (blocks auth.users, vault.secrets, pg_shadow).
    6. Auto-injects and clamps LIMIT clause (default 50, max 100).
    """
    start_time = time.perf_counter()

    if not isinstance(sql_query, str):
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
        return SQLGuardOutcome(
            is_valid=False,
            sanitized_sql="",
            violation_reason="Invalid SQL query type. Expected string.",
            violation_type="INVALID_TYPE",
            matched_patterns=["NON_STRING_SQL"],
            execution_time_ms=elapsed_ms,
        )

    # 1. Clean code fences and comments
    cleaned_sql = strip_sql_fences_and_comments(sql_query)

    if not cleaned_sql:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
        return SQLGuardOutcome(
            is_valid=False,
            sanitized_sql="",
            violation_reason="SQL query cannot be empty.",
            violation_type="EMPTY_SQL",
            matched_patterns=["EMPTY_STRING"],
            execution_time_ms=elapsed_ms,
        )

    # 2. Check for multi-statement chaining via semicolon
    # Semicolons inside strings are rare in analytical queries, split by non-quoted semicolons
    statements = [s.strip() for s in cleaned_sql.split(";") if s.strip()]
    if len(statements) > 1:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
        return SQLGuardOutcome(
            is_valid=False,
            sanitized_sql=cleaned_sql,
            violation_reason="Multiple chained SQL statements with semicolons are prohibited for database security.",
            violation_type="MULTI_STATEMENT_PROHIBITED",
            matched_patterns=["SEMICOLON_CHAINING"],
            execution_time_ms=elapsed_ms,
        )

    single_sql = statements[0]
    upper_sql = single_sql.upper()

    # 3. Read-Only Query Start Verification (must start with SELECT or WITH)
    if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
        return SQLGuardOutcome(
            is_valid=False,
            sanitized_sql=cleaned_sql,
            violation_reason="Only read-only SELECT or WITH (Common Table Expression) queries are permitted.",
            violation_type="NON_READ_ONLY_STATEMENT",
            matched_patterns=["NON_SELECT_START"],
            execution_time_ms=elapsed_ms,
        )

    # 4. Check for forbidden mutating keywords
    for keyword in FORBIDDEN_MUTATING_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper_sql):
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
            return SQLGuardOutcome(
                is_valid=False,
                sanitized_sql=cleaned_sql,
                violation_reason=f"Forbidden mutating keyword detected: '{keyword}'. Only read-only analytical operations are allowed.",
                violation_type="MUTATING_KEYWORD_DETECTED",
                matched_patterns=[f"KEYWORD_{keyword}"],
                execution_time_ms=elapsed_ms,
            )

    # 5. Check for Restricted Schema Access (auth.*, vault.*, pg_shadow, etc.)
    for rule_id, pattern, reason in RESTRICTED_SCHEMA_PATTERNS:
        if pattern.search(single_sql):
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
            return SQLGuardOutcome(
                is_valid=False,
                sanitized_sql=cleaned_sql,
                violation_reason=reason,
                violation_type=rule_id,
                matched_patterns=[rule_id],
                execution_time_ms=elapsed_ms,
            )

    # 6. Enforce Unbounded Query Protection (Auto-inject / Clamp LIMIT)
    safe_sql = enforce_query_limit(single_sql, default_limit=default_limit, max_limit=max_limit)

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
    return SQLGuardOutcome(
        is_valid=True,
        sanitized_sql=safe_sql,
        violation_reason=None,
        violation_type=None,
        matched_patterns=[],
        execution_time_ms=elapsed_ms,
    )
