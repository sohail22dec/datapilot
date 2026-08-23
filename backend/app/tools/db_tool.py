import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine
from app.guardrails.sql_guard import validate_and_sanitize_sql



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


def validate_read_only_sql(sql_query: str, default_limit: int = 50, max_limit: int = 100) -> str:
    """
    Validates, sanitizes, and auto-limits a SQL query via the centralized SQL Guardrail.
    Raises ValueError if unsafe mutating statements or unauthorized schemas are detected.
    """
    outcome = validate_and_sanitize_sql(sql_query, default_limit=default_limit, max_limit=max_limit)
    if not outcome.is_valid:
        raise ValueError(outcome.violation_reason)
    return outcome.sanitized_sql


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
        raise RuntimeError(f"Database query execution failed: {error_msg}") from e
