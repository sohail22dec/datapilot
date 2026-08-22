from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.agents.state import AgentState
from app.tools.schema_tool import get_schema_context

# Initialize structured LLM for routing & single-hop SQL generation
fused_entry_llm = ChatGroq(
    model="openai/gpt-oss-120b",
    groq_api_key=settings.GROQ_API_KEY,
    temperature=0.0,
)


class FusedEntryOutput(BaseModel):
    intent: Literal["data_query", "statistical_analysis", "email_action", "general_chat"] = Field(
        ...,
        description="Operational intent: business data query, statistical analysis, email/action drafting, or general chat."
    )
    thought_process: str = Field(
        ...,
        description="Concise 1-sentence reasoning."
    )
    sql_query: Optional[str] = Field(
        None,
        description="Valid PostgreSQL SELECT query with LIMIT 50 when querying data. None for general_chat."
    )
    tables_used: List[str] = Field(
        default_factory=list,
        description="List of queried table names."
    )
    direct_response: Optional[str] = Field(
        None,
        description="Direct conversational answer when intent is general_chat."
    )


structured_fused_entry = fused_entry_llm.with_structured_output(FusedEntryOutput)

ENTRY_SYSTEM_PROMPT = """You are DataPilot AI, an elite Business Intelligence Architect for PostgreSQL.
Analyze the user inquiry against the database schema:
{schema_context}

Rules:
1. GREETING / IDENTITY / GENERAL CHAT: Set intent='general_chat', provide direct_response, sql_query=null.
2. BUSINESS DATA QUERY: Set intent='data_query', generate valid PostgreSQL SELECT with LIMIT 50.
3. STATISTICAL ANALYSIS (margins, growth, churn, burn rate): Set intent='statistical_analysis', select raw columns.
4. ACTION / EMAIL (winback, purchase order): Set intent='email_action', select recipient and item details.
5. SAFETY: Read-only SELECT queries only. Only query existing tables and columns. Use LOWER()/ILIKE for text filters.
"""


def router_node(state: AgentState) -> dict:
    """
    Supervisor Router Node:
    Single-hop intent classification and SQL generation via LLM.
    """
    raw_q = state.get("user_question", "").strip()
    schema_context = get_schema_context()

    try:
        decision = structured_fused_entry.invoke([
            SystemMessage(content=ENTRY_SYSTEM_PROMPT.format(schema_context=schema_context)),
            HumanMessage(content=f"Inquiry: {raw_q}"),
        ])
        intent = decision.intent
        thought = decision.thought_process
        direct_resp = decision.direct_response
        current_sql = decision.sql_query.strip() if decision.sql_query else None
        tables_used = decision.tables_used

    except Exception as e:
        intent = "general_chat"
        thought = f"Fallback due to router exception: {str(e)}"
        direct_resp = (
            "I am DataPilot AI, your database analyst. I can assist with querying sales, customers, and revenue metrics. "
            "How can I assist you with your business data today?"
        )
        current_sql = None
        tables_used = []

    # Conversational or no SQL generated -> route to direct response
    if intent == "general_chat" or not current_sql:
        return {
            "intent": "general_chat",
            "thought_process": thought,
            "direct_response": direct_resp or "I am DataPilot AI. How can I assist you with your business data today?",
            "sql_query": None,
            "tables_used": [],
            "query_results": None,
            "columns": None,
            "row_count": 0,
            "execution_time_ms": 0.0,
            "retry_count": 0,
            "error_history": [],
            "agent_thought_trace": [f"💬 [Router] {thought}"],
        }

    # Data query -> prepare for sql_node execution
    trace_badge = {
        "data_query": "🔍 [Router] Data Query",
        "statistical_analysis": "📈 [Router] Statistical Analysis",
        "email_action": "✉️ [Router] Action Drafting",
    }.get(intent, "🔍 [Router] SQL Generated")

    return {
        "intent": intent,
        "thought_process": thought,
        "direct_response": None,
        "sql_query": current_sql,
        "tables_used": tables_used,
        "agent_thought_trace": [f"{trace_badge}: {thought}"],
    }
