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

# Supabase internal schemas and internal memory tables to ignore in business text-to-SQL schema prompt
EXCLUDED_SCHEMAS = {
    "auth", "storage", "graphql", "realtime", "vault",
    "pg_catalog", "information_schema", "supabase_functions",
    "pg_toast", "extensions"
}
EXCLUDED_TABLES = {"conversations", "messages", "conversation_memories"}


def init_memory_tables() -> None:
    """Auto-creates persistent Long-Term Memory (LTM) tables in Supabase PostgreSQL."""
    create_conversations_sql = """
    CREATE TABLE IF NOT EXISTS public.conversations (
        id VARCHAR(64) PRIMARY KEY,
        title VARCHAR(255) NOT NULL DEFAULT 'New Conversation',
        summary TEXT DEFAULT NULL,
        token_count INT DEFAULT 0,
        message_count INT DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """
    create_messages_sql = """
    CREATE TABLE IF NOT EXISTS public.messages (
        id VARCHAR(64) PRIMARY KEY,
        conversation_id VARCHAR(64) NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
        role VARCHAR(16) NOT NULL,
        content TEXT NOT NULL,
        sql TEXT DEFAULT NULL,
        data_preview JSONB DEFAULT NULL,
        metrics JSONB DEFAULT NULL,
        chart_config JSONB DEFAULT NULL,
        thought_trace JSONB DEFAULT NULL,
        token_count INT DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """
    create_index_sql = "CREATE INDEX IF NOT EXISTS idx_messages_conv_id ON public.messages(conversation_id, created_at ASC);"

    try:
        with engine.begin() as conn:
            conn.execute(text(create_conversations_sql))
            conn.execute(text(create_messages_sql))
            conn.execute(text(create_index_sql))
        logger.info("Supabase Long-Term Memory tables verified/initialized.")
    except Exception as e:
        logger.warning(f"Could not auto-initialize memory tables in Supabase: {e}")


def warm_database_pool() -> None:
    """Pre-warms the database TCP/SSL connection pool and initializes memory tables on server boot."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        logger.info("Supabase database connection pool pre-warmed successfully.")
        init_memory_tables()
    except Exception as e:
        logger.warning(f"Database pool pre-warming check failed: {e}")



def validate_read_only_sql(sql_query: str) -> str:
    """
    Validates that a SQL query is strictly read-only and safe via the centralized SQL Guardrail.
    Raises ValueError if unsafe statements or unauthorized schemas are detected.
    """
    from app.guardrails.sql_guard import validate_and_sanitize_sql
    
    outcome = validate_and_sanitize_sql(sql_query)
    if not outcome.is_valid:
        raise ValueError(outcome.violation_reason)
    return outcome.sanitized_sql


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
                if tbl in EXCLUDED_SCHEMAS or tbl in EXCLUDED_TABLES:
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
