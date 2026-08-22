import logging
import re
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine

logger = logging.getLogger(__name__)

# Dangerous keywords that modify schema or data
FORBIDDEN_SQL_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "GRANT", "REVOKE", "EXEC", "EXECUTE", "CREATE", "REPLACE",
    "MERGE", "UPSERT", "LOCK", "CALL"
}


def sanitize_row_values(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Converts Decimals, dates, UUIDs, and non-JSON-serializable objects into clean Python types."""
    sanitized = []
    for row in rows:
        clean_row = {}
        for k, v in row.items():
            if isinstance(v, Decimal):
                clean_row[k] = float(v)
            elif isinstance(v, (datetime, date)):
                clean_row[k] = v.isoformat()
            elif isinstance(v, UUID):
                clean_row[k] = str(v)
            elif isinstance(v, bytes):
                clean_row[k] = v.decode("utf-8", errors="replace")
            else:
                clean_row[k] = v

        # Combine customer first_name and last_name for chart labels if available
        if "first_name" in clean_row and "last_name" in clean_row and "customer_name" not in clean_row:
            clean_row["customer_name"] = f"{clean_row['first_name']} {clean_row['last_name']}".strip()

        sanitized.append(clean_row)
    return sanitized


def validate_read_only_sql(sql_query: str) -> str:
    """
    Validates that a SQL query is strictly a read-only SELECT or WITH statement.
    Removes markdown code fences and returns the clean SQL string.
    Raises ValueError if unsafe statements are detected.
    """
    cleaned_sql = sql_query.strip()

    # Strip markdown code fences if present (e.g. ```sql ... ```)
    if cleaned_sql.startswith("```"):
        cleaned_sql = re.sub(r"^```(?:sql)?\s*", "", cleaned_sql, flags=re.IGNORECASE)
        cleaned_sql = re.sub(r"\s*```$", "", cleaned_sql)
        cleaned_sql = cleaned_sql.strip()

    # Remove SQL comments for security analysis
    sql_no_comments = re.sub(r"--.*$", "", cleaned_sql, flags=re.MULTILINE)
    sql_no_comments = re.sub(r"/\*.*?\*/", "", sql_no_comments, flags=re.DOTALL).strip()

    if not sql_no_comments:
        raise ValueError("SQL query cannot be empty.")

    upper_sql = sql_no_comments.upper()
    if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
        raise ValueError("Only SELECT or WITH (CTE) read-only queries are permitted.")

    # Reject forbidden mutating keywords as standalone tokens
    for keyword in FORBIDDEN_SQL_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper_sql):
            raise ValueError(f"Forbidden statement keyword detected: '{keyword}'. Only read-only queries are allowed.")

    # Reject multiple query chaining via semicolon
    statements = [stmt.strip() for stmt in sql_no_comments.split(";") if stmt.strip()]
    if len(statements) > 1:
        raise ValueError("Multiple SQL statements chained with semicolons are not permitted.")

    return cleaned_sql


def execute_db_query(sql_query: str, max_rows: int = 100) -> Dict[str, Any]:
    """
    Executes a read-only SQL query against the database inside a protected transaction.
    Returns sanitized rows, columns, row count, execution time in ms, and sanitized query.
    """
    cleaned_sql = validate_read_only_sql(sql_query)

    start_time = time.perf_counter()
    try:
        with engine.connect() as conn:
            # Enforce read-only at session level
            conn.execute(text("SET TRANSACTION READ ONLY;"))
            # Set 5-second query timeout
            conn.execute(text("SET statement_timeout = '5000ms';"))

            result = conn.execute(text(cleaned_sql))
            columns = list(result.keys())
            raw_rows = result.fetchmany(max_rows)

            raw_dict_rows = [dict(row._mapping) for row in raw_rows]
            sanitized_rows = sanitize_row_values(raw_dict_rows)
            execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

            return {
                "columns": columns,
                "rows": sanitized_rows,
                "row_count": len(sanitized_rows),
                "execution_time_ms": execution_time_ms,
                "sql": cleaned_sql,
                "error": None,
            }
    except SQLAlchemyError as e:
        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        error_msg = str(e)
        logger.error(f"SQL execution error ({execution_time_ms}ms): {error_msg}")
        raise RuntimeError(f"Database query execution failed: {error_msg}") from e
