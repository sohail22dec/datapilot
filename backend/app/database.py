import logging
import re
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize SQLAlchemy Engine with tuned persistent connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=15,
    pool_recycle=1800,
    pool_pre_ping=True,
)

# In-memory cache for schema introspection string
_cached_schema: Optional[str] = None
_cached_tables_info: Optional[List[Dict[str, Any]]] = None

# Dangerous SQL keywords that modify schema or data
FORBIDDEN_SQL_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "GRANT", "REVOKE", "EXEC", "EXECUTE", "CREATE", "REPLACE",
    "MERGE", "UPSERT", "LOCK", "CALL"
}

# Supabase internal schemas to ignore
EXCLUDED_SCHEMAS = {
    "auth", "storage", "graphql", "realtime", "vault",
    "pg_catalog", "information_schema", "supabase_functions",
    "pg_toast", "extensions"
}


def warm_database_pool() -> None:
    """Pre-warms the database TCP/SSL connection pool on server boot to avoid cold-start delays."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        logger.info("Supabase database connection pool pre-warmed successfully.")
    except Exception as e:
        logger.warning(f"Database pool pre-warming check failed: {e}")


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

    # Must start with SELECT or WITH
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


def get_database_schema(force_refresh: bool = False) -> str:
    """
    Inspects the Supabase database to fetch table names, column names, data types,
    and foreign key relationships. Returns a formatted schema string for the LLM prompt.
    """
    global _cached_schema, _cached_tables_info

    if _cached_schema and not force_refresh:
        return _cached_schema

    try:
        with engine.connect() as conn:
            # Query all table columns in public schema
            columns_query = text("""
                SELECT 
                    c.table_name,
                    c.column_name,
                    c.data_type
                FROM information_schema.columns c
                JOIN information_schema.tables t 
                    ON c.table_schema = t.table_schema 
                    AND c.table_name = t.table_name
                WHERE c.table_schema = 'public'
                  AND t.table_type = 'BASE TABLE'
                ORDER BY c.table_name, c.ordinal_position;
            """)
            columns_result = conn.execute(columns_query).fetchall()

            # Query foreign key constraints in public schema
            fk_query = text("""
                SELECT
                    tc.table_name AS source_table,
                    kcu.column_name AS source_column,
                    ccu.table_name AS target_table
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public';
            """)
            fk_result = conn.execute(fk_query).fetchall()

            # Map foreign keys
            fk_map: Dict[str, str] = {}
            for row in fk_result:
                key = f"{row.source_table}.{row.source_column}"
                fk_map[key] = f"->{row.target_table}"

            # Group columns by table
            tables: Dict[str, List[str]] = {}
            for row in columns_result:
                tbl = row.table_name
                if tbl in EXCLUDED_SCHEMAS:
                    continue
                if tbl not in tables:
                    tables[tbl] = []
                
                fk_ref = fk_map.get(f"{tbl}.{row.column_name}", "")
                col_def = f"{row.column_name}{fk_ref}"
                tables[tbl].append(col_def)

            if not tables:
                schema_str = "No user tables found in the public database schema."
            else:
                schema_lines = []
                for tbl, cols in tables.items():
                    schema_lines.append(f"{tbl}({', '.join(cols)})")
                schema_str = "\n".join(schema_lines)

            _cached_schema = schema_str
            return schema_str

    except Exception as e:
        logger.error(f"Failed to inspect database schema: {e}")
        return f"Error retrieving schema: {str(e)}"


def get_schema_metadata() -> Dict[str, Any]:
    """Returns structured table and column metadata for introspection endpoints."""
    try:
        schema_text = get_database_schema(force_refresh=True)
        return {
            "status": "connected",
            "schema_text": schema_text,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


def execute_read_only_query(sql_query: str, max_rows: int = 50) -> Dict[str, Any]:
    """
    Executes a read-only SQL query against Supabase inside a protected read-only transaction.
    Returns column names, row dictionaries, row count, and execution time in milliseconds.
    """
    cleaned_sql = validate_read_only_sql(sql_query)

    start_time = time.perf_counter()
    try:
        with engine.connect() as conn:
            # Enforce read-only at session level
            conn.execute(text("SET TRANSACTION READ ONLY;"))
            # Set 4-second query timeout
            conn.execute(text("SET statement_timeout = '4000ms';"))

            result = conn.execute(text(cleaned_sql))
            columns = list(result.keys())
            raw_rows = result.fetchmany(max_rows)
            
            rows = [dict(row._mapping) for row in raw_rows]
            execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "execution_time_ms": execution_time_ms,
                "sql": cleaned_sql,
            }
    except SQLAlchemyError as e:
        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(f"SQL execution error ({execution_time_ms}ms): {e}")
        raise RuntimeError(f"Database query execution failed: {str(e)}") from e
