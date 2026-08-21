import logging
import re
from decimal import Decimal
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.database import get_database_schema, execute_read_only_query
from app.schemas import GeneratedSQL, ChatResponse, ChartConfig

logger = logging.getLogger(__name__)

# Initialize LangChain Gemini model
llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
)

# Structured output generator for SQL & Intent Classification
structured_sql_llm = llm.with_structured_output(GeneratedSQL)


SQL_GENERATION_SYSTEM_PROMPT = """You are DataPilot AI, an expert PostgreSQL business intelligence data analyst and database architect.
Your task is to analyze the user's inquiry and either query the database or provide a direct conversational response.

Database Schema:
{schema_context}

Intent Classification Instructions:
1. DATA QUERY:
   - If the user asks for business numbers, sales, revenue, metrics, customers, orders, products, returns, statistics, filtering, or aggregations based on the database schema:
     -> Set `is_data_query = true`
     -> Generate a valid, optimized PostgreSQL SELECT query in `sql_query`.
     -> Populate `tables_used` with the exact tables queried.
     -> Set `direct_response = null`.

2. GENERAL CONVERSATION / GREETINGS:
   - If the user sends greetings ("hi", "hello", "hey"), identity questions ("who are you", "what is your name"), pleasantries ("how are you", "thank you"), or asks general questions ("how do I use this", "what tables exist"):
     -> Set `is_data_query = false`
     -> Set `sql_query = null` and `tables_used = []`.
     -> Provide a helpful, professional, friendly response in `direct_response` (introducing yourself as DataPilot and explaining how you can help query and visualize their database).
     -> NEVER generate dummy SQL like `SELECT 'hello' AS response` for conversational queries.

Rules for SQL generation (when is_data_query is true):
1. Generate standard, read-only PostgreSQL queries (SELECT or WITH statements).
2. Only query tables and columns that exist in the provided schema. Do not hallucinate columns.
3. When joining tables, always use explicit table aliases and qualify column references (e.g. `c.first_name`, `o.order_id`).
4. Always provide clear, clean column aliases for aggregations (e.g. `SUM(oi.quantity * oi.unit_price) AS total_spend`, `COUNT(o.order_id) AS order_count`).
5. For date filtering, use standard PostgreSQL functions (e.g. `DATE_TRUNC('month', order_date)`, `NOW() - INTERVAL '30 days'`).
6. Apply `LIMIT 100` if the query could return an unbound list of rows.
7. Always use `LOWER()` or `ILIKE` when filtering text/status/segment columns (e.g. `LOWER(c.customer_segment) = 'vip'`, `LOWER(o.status) = 'completed'`, `LOWER(p.payment_status) = 'successful'`) to avoid case-mismatch issues.
8. Return ONLY the structured output.
"""

SQL_HEALING_SYSTEM_PROMPT = """You are a senior PostgreSQL database debugger.
A previously generated SQL query failed execution against the database.
Fix the SQL query so it runs successfully on PostgreSQL based on the schema and error message.

Database Schema:
{schema_context}

User Question: {user_question}
Failed SQL Query: {failed_sql}
PostgreSQL Error: {error_message}

Instructions:
1. Analyze the exact error message (e.g. column does not exist, type mismatch, group by requirement).
2. Rewrite the query to fix the error while accurately answering the user's question.
3. Return the corrected structured output.
"""

ANSWER_SYNTHESIS_PROMPT = """You are DataPilot AI, an executive business intelligence data analyst.

User Question: {user_question}
Executed SQL Query: {sql_query}
Query Result Rows:
{result_rows}

Instructions:
1. Provide a direct, professional, executive-level answer to the user's question based on the query results.
2. Format all monetary values in Indian Rupees (₹) with proper comma separators, and metrics, percentages, counts, and top entities in **bold** (e.g. **₹45,200**, **₹1,24,500**, **18.5%**, **3,420 orders**).
3. If multiple rows exist, summarize the key findings or top performers clearly, using concise bullet points if helpful.
4. If no rows were returned, politely mention that no matching records were found in the database.
5. Keep the tone concise, helpful, and analytical. Do not explain the SQL code itself in this summary.
"""


def extract_text(content: Any) -> str:
    """Safely extracts a clean string from LangChain response content (string or block list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                text_parts.append(item["text"])
            elif hasattr(item, "text"):
                text_parts.append(str(item.text))
        return "\n".join(text_parts).strip()
    return str(content or "")


def sanitize_row_values(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Converts Decimals, dates, and non-JSON-serializable objects into clean Python types."""
    sanitized = []
    for row in rows:
        clean_row = {}
        for k, v in row.items():
            if isinstance(v, Decimal):
                clean_row[k] = float(v)
            elif isinstance(v, (datetime, date)):
                clean_row[k] = v.isoformat()
            else:
                clean_row[k] = v
        
        # Combine customer first_name and last_name for chart labels if available
        if "first_name" in clean_row and "last_name" in clean_row and "name" not in clean_row:
            clean_row["customer_name"] = f"{clean_row['first_name']} {clean_row['last_name']}"

        sanitized.append(clean_row)
    return sanitized


def determine_chart_config(
    user_question: str,
    sql_query: str,
    rows: List[Dict[str, Any]],
    columns: List[str]
) -> Optional[ChartConfig]:
    """
    Intelligently determines whether a query's result warrants a chart visualization
    and chooses the optimal chart type (bar, line, area, or donut) with x/y keys.
    """
    if len(rows) < 2 or not columns or len(columns) < 2:
        return None

    first_row = rows[0]
    
    # Identify numeric candidate columns
    numeric_cols = [
        col for col in columns
        if isinstance(first_row.get(col), (int, float)) and not col.endswith("_id")
    ]
    # Identify categorical / label candidate columns
    categorical_cols = [
        col for col in columns
        if col not in numeric_cols and not col.endswith("_id")
    ]

    # If first_name + last_name were combined into customer_name
    if "customer_name" in first_row and "customer_name" not in categorical_cols:
        categorical_cols.insert(0, "customer_name")

    if not numeric_cols:
        return None

    y_key = numeric_cols[0]
    x_key = categorical_cols[0] if categorical_cols else columns[0]

    q_lower = user_question.lower()
    x_lower = x_key.lower()

    # Donut / Pie Chart: distribution / shares with 8 or fewer slices
    donut_indicators = [
        "payment_method", "method", "status", "segment", "customer_segment",
        "share", "distribution", "breakdown", "split", "reason"
    ]
    if any(k in x_lower or k in q_lower for k in donut_indicators) and len(rows) <= 8:
        title = f"{x_key.replace('_', ' ').title()} Breakdown"
        return ChartConfig(type="donut", x_key=x_key, y_key=y_key, title=title)

    # Line / Area Chart: date / time-series trends
    date_indicators = [
        "date", "month", "day", "week", "year", "created_at", "order_date",
        "signup_date", "payment_date"
    ]
    time_query_indicators = ["trend", "daily", "monthly", "over time", "growth"]
    if any(k in x_lower for k in date_indicators) or any(k in q_lower for k in time_query_indicators):
        title = f"{y_key.replace('_', ' ').title()} Trend"
        return ChartConfig(type="area", x_key=x_key, y_key=y_key, title=title)

    # Default: Bar Chart for rankings, categories, products, top spenders, cities
    clean_y_label = y_key.replace("_", " ").title()
    clean_x_label = x_key.replace("_", " ").title()
    title = f"{clean_y_label} by {clean_x_label}"

    return ChartConfig(type="bar", x_key=x_key, y_key=y_key, title=title)


def generate_sql(user_question: str, schema_context: str) -> GeneratedSQL:
    """Generates structured PostgreSQL query using Gemini Flash."""
    system_msg = SystemMessage(content=SQL_GENERATION_SYSTEM_PROMPT.format(schema_context=schema_context))
    user_msg = HumanMessage(content=f"User Question: {user_question}")
    
    result = structured_sql_llm.invoke([system_msg, user_msg])
    return result


def heal_sql_query(
    user_question: str,
    failed_sql: str,
    error_message: str,
    schema_context: str
) -> GeneratedSQL:
    """Prompts Gemini to self-heal/correct a failed SQL query."""
    system_msg = SystemMessage(
        content=SQL_HEALING_SYSTEM_PROMPT.format(
            schema_context=schema_context,
            user_question=user_question,
            failed_sql=failed_sql,
            error_message=error_message,
        )
    )
    user_msg = HumanMessage(content="Please provide the corrected PostgreSQL query.")
    
    result = structured_sql_llm.invoke([system_msg, user_msg])
    return result


def synthesize_data_response(
    user_question: str,
    sql_query: str,
    rows: List[Dict[str, Any]]
) -> str:
    """Synthesizes executive natural language answer from database query results in INR (₹)."""
    display_rows = rows[:50]
    prompt = ANSWER_SYNTHESIS_PROMPT.format(
        user_question=user_question,
        sql_query=sql_query,
        result_rows=display_rows,
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    return extract_text(response.content)


def process_chat_query(user_question: str) -> ChatResponse:
    """
    Main orchestration pipeline:
    1. Schema Introspection
    2. Text-to-SQL Generation
    3. Safe Read-Only Execution with Self-Healing
    4. Answer Synthesis & Intelligent Chart Detection
    5. Return Rich Payload with ChartConfig
    """
    # 1. Fetch live or cached schema
    schema_context = get_database_schema()
    
    if "No user tables found" in schema_context or "Error retrieving schema" in schema_context:
        fallback_prompt = f"You are DataPilot AI. The database currently has no user tables or is unreachable. Schema status: {schema_context}. User Question: {user_question}. Answer gracefully."
        resp = llm.invoke([HumanMessage(content=fallback_prompt)])
        return ChatResponse(
            response=extract_text(resp.content) or "Database connection is active, but no public business tables were found.",
            model=settings.GEMINI_MODEL,
        )

    # 2. Generate SQL or Conversational Response
    try:
        sql_plan = generate_sql(user_question, schema_context)
    except Exception as e:
        logger.error(f"Intent / SQL generation failed: {e}")
        return ChatResponse(
            response=f"I couldn't process your question. Error: {str(e)}",
            model=settings.GEMINI_MODEL,
        )

    # Route General Conversation / Greetings (no SQL or table needed)
    if not sql_plan.is_data_query or not sql_plan.sql_query or not sql_plan.sql_query.strip():
        response_text = sql_plan.direct_response or "Hello! I am DataPilot, your AI data analyst. How can I help you explore your database today?"
        return ChatResponse(
            response=response_text,
            model=settings.GEMINI_MODEL,
        )

    current_sql = sql_plan.sql_query.strip()

    # Safety catch: If model generated a literal constant SELECT without any tables (e.g. SELECT 'message' AS response)
    if not sql_plan.tables_used and re.match(r"^SELECT\s+['\"].*?['\"]\s*(AS\s+\w+)?\s*;?$", current_sql, flags=re.IGNORECASE):
        extracted = re.search(r"^SELECT\s+['\"](.*?)['\"]", current_sql, flags=re.IGNORECASE)
        response_text = extracted.group(1).replace("''", "'") if extracted else (sql_plan.direct_response or "Hello! How can I assist you with your database today?")
        return ChatResponse(
            response=response_text,
            model=settings.GEMINI_MODEL,
        )

    query_result: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None

    # 3. Safe Execution with up to 2 self-healing retry attempts
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            query_result = execute_read_only_query(current_sql)
            break  # Execution succeeded!
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Query attempt {attempt + 1} failed: {last_error}")
            
            if attempt < max_retries:
                logger.info(f"Attempting self-healing query correction (retry {attempt + 1})...")
                try:
                    healed_plan = heal_sql_query(
                        user_question=user_question,
                        failed_sql=current_sql,
                        error_message=last_error,
                        schema_context=schema_context,
                    )
                    if healed_plan.sql_query:
                        current_sql = healed_plan.sql_query.strip()
                    else:
                        break
                except Exception as heal_err:
                    logger.error(f"Self-healing prompt failed: {heal_err}")
                    break

    # If all execution attempts failed
    if not query_result:
        return ChatResponse(
            response=f"I attempted to query your database, but encountered an error: {last_error}",
            sql=current_sql,
            model=settings.GEMINI_MODEL,
        )

    # Sanitize rows for clean JSON serialization
    sanitized_rows = sanitize_row_values(query_result["rows"])

    # 4. Synthesize natural language answer
    try:
        summary_text = synthesize_data_response(
            user_question=user_question,
            sql_query=query_result["sql"],
            rows=sanitized_rows,
        )
    except Exception as e:
        logger.error(f"Answer synthesis failed: {e}")
        summary_text = f"Retrieved {query_result['row_count']} rows successfully from database."

    # 5. Determine chart visualization configuration
    chart_config = determine_chart_config(
        user_question=user_question,
        sql_query=query_result["sql"],
        rows=sanitized_rows,
        columns=query_result["columns"],
    )

    # 6. Return complete rich payload
    return ChatResponse(
        response=summary_text,
        sql=query_result["sql"],
        data=sanitized_rows,
        columns=query_result["columns"],
        row_count=query_result["row_count"],
        execution_time_ms=query_result["execution_time_ms"],
        chart_config=chart_config,
        model=settings.GEMINI_MODEL,
    )
