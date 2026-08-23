from app.agent.state import AgentState
from app.tools.db_tool import execute_db_query


def sql_node(state: AgentState) -> dict:
    """
    Dedicated Database Execution Node:
    1. Receives SQL query from router_node or heal_node.
    2. Safely executes read-only query against Supabase PostgreSQL.
    3. Populates query_results, columns, row_count, execution_time_ms.
    4. Captures errors cleanly for self-healing routing.
    """
    current_sql = state.get("sql_query")
    
    if not current_sql:
        return {
            "query_results": None,
            "columns": None,
            "row_count": 0,
            "execution_time_ms": 0.0,
            "error_history": ["No SQL query provided for execution."],
            "agent_thought_trace": ["⚠️ [SQL Node] No SQL query present to execute"],
        }

    try:
        query_result = execute_db_query(current_sql, max_rows=50)
        rows = query_result["rows"]
        cols = query_result["columns"]
        row_count = query_result["row_count"]
        latency = query_result["execution_time_ms"]

        db_trace = f"⚡ [DB Execution] Executed query in {latency}ms ({row_count} rows retrieved)"
        return {
            "query_results": rows,
            "columns": cols,
            "row_count": row_count,
            "execution_time_ms": latency,
            "retry_count": 0,
            "agent_thought_trace": [db_trace],
        }

    except Exception as e:
        error_msg = str(e)
        return {
            "query_results": None,
            "columns": None,
            "row_count": 0,
            "execution_time_ms": 0.0,
            "error_history": [error_msg],
            "agent_thought_trace": [f"⚠️ [DB Execution] Query failed: {error_msg}"],
        }
