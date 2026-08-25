import json
from typing import Any, Dict, List, Optional
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from app.config import settings
from app.agent.state import AgentState
from app.guardrails import sanitize_and_validate_output


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
1. Provide a direct, professional, executive-level answer to the user's inquiry based strictly on the provided data, metrics, or action draft.
2. Format ALL monetary figures in Indian Rupees (₹) using standard Indian numbering format (e.g. **₹1,25,000**, **₹45,200**, **₹10,00,000**, **₹4.5 Lakhs**). NEVER omit the ₹ symbol for monetary numbers.
3. Highlight all key numbers, counts, percentages, metrics, and top entities in **bold** (e.g. **1,420**, **25.0%**, **₹8,45,000**, **9.0%**).
4. If statistical metrics are present, explicitly state and highlight key insights (e.g., net margins, growth rates, churn percentages, days of stock remaining).
5. If an action draft is present, summarize the campaign title, subject, and key details concisely. DO NOT invent, hallucinate, or fabricate any numbers, order quantities, delivery dates, or metrics not present in the action payload or data.
6. Keep the response concise, strategic, and data-driven (2-4 bullet points max). Do not mention SQL code, query syntax, or database table names.
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

    # Special Case: MoM 2-period comparison is best visualized as a Bar chart
    if len(rows) == 2 and any(k in q_lower for k in ["mom", "month-over-month", "growth rate", "comparison", "compare"]):
        clean_y = y_key.replace("_", " ").title()
        clean_x = x_key.replace("_", " ").title()
        return {"type": "bar", "x_key": x_key, "y_key": y_key, "title": f"{clean_y} by {clean_x}"}

    # Donut / Pie Chart (Part-to-whole categorical breakdowns, e.g. payment methods, reasons, segments, status breakdowns)
    donut_indicators = ["payment_method", "reason", "customer_segment", "segment"]
    donut_keywords = ["breakdown", "distribution", "share", "split", "percentage breakdown", "orders by"]
    if (any(k in x_lower for k in donut_indicators) or any(k in q_lower for k in donut_keywords)) and len(rows) <= 8:
        # If query is explicitly a multi-row aggregation per status with total amounts without "breakdown", prefer Bar
        if not (("per order status" in q_lower or "per status" in q_lower) and "breakdown" not in q_lower):
            title = f"{x_key.replace('_', ' ').title()} Breakdown"
            return {"type": "donut", "x_key": x_key, "y_key": y_key, "title": title}

    # Line / Area Chart (Time-series trends over dates, days, months, quarters, years)
    date_indicators = [
        "date", "month", "day", "week", "year", "quarter", "q1", "q2", "q3", "q4",
        "created_at", "order_date", "signup_date", "payment_date", "signup_quarter",
        "order_month", "payment_day"
    ]
    time_query_indicators = ["trend", "daily", "monthly", "quarterly", "over time", "last 4 quarters", "over the last"]
    if (any(k in x_lower for k in date_indicators) or any(k in q_lower for k in time_query_indicators)) and len(rows) >= 3:
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
    if not rows and not metrics and not action_payload and error_history:
        final_answer = f"I encountered an error executing this request: {error_history[-1]}. Please refine your question."
        return {
            "final_response": final_answer,
            "chart_config": None,
            "agent_thought_trace": ["⚠️ [Synthesis] Error response prepared"],
        }

    # Case 3: Empty dataset (no rows, no computed metrics, no action draft)
    if not rows and not metrics and not action_payload:
        return {
            "final_response": "No matching records were found in the database for your query.",
            "chart_config": None,
            "agent_thought_trace": ["📊 [Synthesis] Empty result set handled"],
        }

    # Case 4: Lean Data Synthesis (Pass max 6 preview rows to prevent context bloat)
    sample_rows = rows[:6] if rows else []
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

    # Apply Layer-3 Output Guardrail (Secret Redaction, Stack Trace Scrubbing, Number Grounding)
    output_guard_outcome = sanitize_and_validate_output(
        text=final_answer,
        rows=rows,
        metrics=metrics,
        has_data=bool(rows) or bool(metrics),
    )
    clean_final_answer = output_guard_outcome.sanitized_output

    return {
        "final_response": clean_final_answer,
        "chart_config": chart_config,
        "agent_thought_trace": [chart_trace],
    }
