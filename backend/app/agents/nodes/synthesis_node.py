import json
from typing import Any, Dict, List, Optional
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from app.config import settings
from app.agents.state import AgentState


synthesis_llm = ChatGroq(
    model="openai/gpt-oss-120b",
    groq_api_key=settings.GROQ_API_KEY,
    temperature=0.0,
)

LEAN_SYNTHESIS_PROMPT = """You are DataPilot AI, an elite executive business intelligence consultant.

User Question: {user_question}
Query Results Preview (Top {sample_count} of {total_count} rows):
{result_rows_summary}

Statistical Metrics (if computed):
{computed_metrics}

Action Draft (if any):
{action_payload}

Instructions:
1. Provide a direct, professional, executive-level answer to the user's inquiry based on the data.
2. Format all monetary figures in Indian Rupees (₹) with comma separators (e.g. **₹1,24,500**, **₹45,200**).
3. Highlight all key numbers, counts, percentages, and top entities in **bold**.
4. If statistical metrics are present, highlight key insights (e.g., net margins, growth rates, churn percentages).
5. If an action draft is present, summarize the campaign highlights concisely.
6. Keep the response concise, strategic, and data-driven (2-4 bullet points max). Do not mention SQL code or table names.
"""


def extract_text(content: Any) -> str:
    """Safely extracts a clean string from LangChain response content."""
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


def determine_chart_config(
    user_question: str,
    rows: Optional[List[Dict[str, Any]]],
    columns: Optional[List[str]]
) -> Optional[Dict[str, Any]]:
    """
    Intelligently determines whether a query's result warrants a chart visualization
    and chooses the optimal chart type (bar, line, area, or donut) with x/y keys.
    """
    if not rows or len(rows) < 2 or not columns or len(columns) < 2:
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

    if "customer_name" in first_row and "customer_name" not in categorical_cols:
        categorical_cols.insert(0, "customer_name")

    if not numeric_cols:
        return None

    y_key = numeric_cols[0]
    x_key = categorical_cols[0] if categorical_cols else columns[0]

    q_lower = user_question.lower()
    x_lower = x_key.lower()

    # Donut / Pie Chart
    donut_indicators = [
        "payment_method", "method", "status", "segment", "customer_segment",
        "share", "distribution", "breakdown", "split", "reason"
    ]
    if any(k in x_lower or k in q_lower for k in donut_indicators) and len(rows) <= 8:
        title = f"{x_key.replace('_', ' ').title()} Breakdown"
        return {"type": "donut", "x_key": x_key, "y_key": y_key, "title": title}

    # Line / Area Chart
    date_indicators = [
        "date", "month", "day", "week", "year", "created_at", "order_date",
        "signup_date", "payment_date"
    ]
    time_query_indicators = ["trend", "daily", "monthly", "over time", "growth"]
    if any(k in x_lower for k in date_indicators) or any(k in q_lower for k in time_query_indicators):
        title = f"{y_key.replace('_', ' ').title()} Trend"
        return {"type": "area", "x_key": x_key, "y_key": y_key, "title": title}

    # Default: Bar Chart
    clean_y_label = y_key.replace("_", " ").title()
    clean_x_label = x_key.replace("_", " ").title()
    title = f"{clean_y_label} by {clean_x_label}"

    return {"type": "bar", "x_key": x_key, "y_key": y_key, "title": title}


def synthesis_node(state: AgentState) -> dict:
    """
    Lean Executive Synthesis Node:
    Prunes input rows to < 150 tokens to eliminate generation latency,
    synthesizes INR formatting, and detects visual chart configuration.
    """
    intent = state.get("intent", "data_query")
    user_q = state.get("user_question", "")
    direct_resp = state.get("direct_response")
    rows = state.get("query_results") or []
    columns = state.get("columns")
    metrics = state.get("computed_metrics")
    action_payload = state.get("action_payload")
    error_history = state.get("error_history", [])

    # Case 1: General Chat / Policy Violation (Instant 0ms, 0 tokens)
    if intent in ("general_chat", "policy_violation"):
        fallback = (
            "For security and compliance reasons, this inquiry cannot be processed."
            if intent == "policy_violation"
            else "Hello! I am DataPilot, your AI data analyst. How can I help you explore your business metrics today?"
        )
        final_answer = direct_resp or fallback
        trace_msg = (
            "🛡️ [Synthesis] Safety & policy rejection prepared"
            if intent == "policy_violation"
            else "📊 [Synthesis] Conversational answer prepared"
        )
        return {
            "final_response": final_answer,
            "chart_config": None,
            "agent_thought_trace": [trace_msg],
        }

    # Case 2: Query Failed after retries
    if not rows and error_history:
        final_answer = f"I encountered an error executing this request: {error_history[-1]}. Please refine your question."
        return {
            "final_response": final_answer,
            "chart_config": None,
            "agent_thought_trace": ["⚠️ [Synthesis] Error response prepared"],
        }

    # Case 3: Empty dataset
    if not rows:
        return {
            "final_response": "No matching records were found in the database for your query.",
            "chart_config": None,
            "agent_thought_trace": ["📊 [Synthesis] Empty result set handled"],
        }

    # Case 4: Lean Data Synthesis (Pass max 6 preview rows to prevent context bloat)
    sample_rows = rows[:6]
    compact_summary = json.dumps(sample_rows, default=str)

    try:
        prompt = LEAN_SYNTHESIS_PROMPT.format(
            user_question=user_q,
            sample_count=len(sample_rows),
            total_count=len(rows),
            result_rows_summary=compact_summary,
            computed_metrics=json.dumps(metrics, default=str) if metrics else "None",
            action_payload=json.dumps(action_payload, default=str) if action_payload else "None",
        )
        response = synthesis_llm.invoke([HumanMessage(content=prompt)])
        final_answer = extract_text(response.content)
    except Exception as e:
        final_answer = f"Retrieved {len(rows)} records successfully from your database."

    # Determine Chart Configuration
    chart_config = determine_chart_config(
        user_question=user_q,
        rows=rows,
        columns=columns,
    )

    chart_trace = f"📈 [Synthesis] Configured {chart_config['type']} chart ({chart_config['title']})" if chart_config else "📊 [Synthesis] Formatted executive summary"

    return {
        "final_response": final_answer,
        "chart_config": chart_config,
        "agent_thought_trace": [chart_trace],
    }
