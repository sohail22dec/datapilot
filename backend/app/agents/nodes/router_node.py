import logging
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.agents.state import AgentState
from app.tools.schema_tool import get_schema_context

logger = logging.getLogger(__name__)

# Initialize structured LLM for routing & single-hop SQL generation
fused_entry_llm = ChatGroq(
    model="openai/gpt-oss-120b",
    groq_api_key=settings.GROQ_API_KEY,
    temperature=0.0,
)


class FusedEntryOutput(BaseModel):
    is_data_query: bool = Field(
        ...,
        description="True for database business queries (sales, revenue, orders, customers, stats). False for general chat/help."
    )
    intent: Literal["data_query", "statistical_analysis", "email_action", "general_chat"] = Field(
        ...,
        description="Operational intent."
    )
    direct_response: Optional[str] = Field(
        None,
        description="Natural conversational response when is_data_query is False."
    )
    sql_query: Optional[str] = Field(
        None,
        description="PostgreSQL SELECT query when is_data_query is True. None otherwise."
    )
    tables_used: List[str] = Field(
        default_factory=list,
        description="List of queried table names."
    )
    thought_process: str = Field(
        ...,
        description="Concise 1-sentence reasoning."
    )


structured_fused_entry = fused_entry_llm.with_structured_output(FusedEntryOutput)

# Streamlined, compact system prompt for maximum speed & zero hallucinations
COMPACT_ENTRY_SYSTEM_PROMPT = """DataPilot PostgreSQL BI Architect.
Analyze inquiry against schema:
{schema_context}

Rules:
1. If greeting/identity/help: is_data_query=false, intent='general_chat', return executive direct_response.
2. If data query: is_data_query=true, intent='data_query', generate valid PostgreSQL SELECT with LIMIT 50.
3. If statistical analysis (margins, growth, churn, inventory): is_data_query=true, intent='statistical_analysis', select raw columns (e.g. products, prices, costs, dates) for the stats engine.
4. If email/PO action (winback, restock): is_data_query=true, intent='email_action', select recipient/item details.
5. Read-only queries only. Only use tables/columns in the schema. Use LOWER()/ILIKE for text filters.
"""


def router_node(state: AgentState) -> dict:
    """
    Supervisor Router Node (Pure AI Intent & SQL Generation):
    1. Instant 0ms response for greetings and capability questions (0 tokens, 0 DB calls).
    2. Single-hop Intent & SQL generation via LLM.
    3. Delegates database execution to dedicated sql_node for clean observability.
    """
    raw_q = state.get("user_question", "").strip()
    user_q = raw_q.lower()

    # -------------------------------------------------------------
    # ⚡ 1. PLAIN-CODE FAST PATH: Instant Greetings (< 0.001s, 0 Tokens)
    # -------------------------------------------------------------
    greetings = ["hi", "hello", "hey", "yo", "greetings", "good morning", "good evening", "good afternoon", "namaste"]
    if user_q in greetings or (len(user_q.split()) <= 2 and any(user_q.startswith(g) for g in ["hi", "hello", "hey"])):
        return {
            "intent": "general_chat",
            "thought_process": "Instant greeting fast-path filter",
            "direct_response": (
                "Hello! I am **DataPilot AI**, your autonomous business intelligence analyst. "
                "How can I help you explore your sales, revenue, top customers, or profit margins today?"
            ),
            "sql_query": None,
            "tables_used": [],
            "query_results": None,
            "columns": None,
            "row_count": 0,
            "execution_time_ms": 0.0,
            "retry_count": 0,
            "error_history": [],
            "agent_thought_trace": ["💬 [Router] Handled greeting instantly (0ms)"],
        }

    # -------------------------------------------------------------
    # ⚡ 2. PLAIN-CODE FAST PATH: Identity & Capabilities (< 0.001s, 0 Tokens)
    # -------------------------------------------------------------
    identity_triggers = [
        "who are you", "what is your name", "what can you do", "what do you do",
        "how does this work", "help", "what tables exist", "what can i ask"
    ]
    if any(trigger in user_q for trigger in identity_triggers) and len(user_q.split()) <= 10:
        return {
            "intent": "general_chat",
            "thought_process": "Instant capabilities inquiry fast-path",
            "direct_response": (
                "I am **DataPilot AI**, your executive business intelligence data analyst! Here is how I can help:\n\n"
                "• 📊 **Data Queries:** Instant answers on sales, top customers, return reasons, and orders.\n"
                "• 📈 **Statistical Analysis:** Profit margins & COGS, MoM growth rates, customer churn, inventory burn rates.\n"
                "• ✉️ **Action Engine:** Drafting VIP customer win-back emails and supplier purchase orders.\n\n"
                "💡 **Try asking:** *'What are our top 5 products by total revenue?'* or *'Calculate our overall profit margins'*."
            ),
            "sql_query": None,
            "tables_used": [],
            "query_results": None,
            "columns": None,
            "row_count": 0,
            "execution_time_ms": 0.0,
            "retry_count": 0,
            "error_history": [],
            "agent_thought_trace": ["💬 [Router] Handled capabilities inquiry instantly (0ms)"],
        }

    # -------------------------------------------------------------
    # ⚡ 3. MINIFIED SCHEMA INTENT & SQL GENERATION
    # -------------------------------------------------------------
    schema_context = get_schema_context()

    try:
        decision = structured_fused_entry.invoke([
            SystemMessage(content=COMPACT_ENTRY_SYSTEM_PROMPT.format(schema_context=schema_context)),
            HumanMessage(content=f"Inquiry: {raw_q}"),
        ])
        is_data_query = decision.is_data_query
        intent = decision.intent
        thought = decision.thought_process
        direct_resp = decision.direct_response
        current_sql = decision.sql_query.strip() if decision.sql_query else None
        tables_used = decision.tables_used

    except Exception as e:
        logger.error(f"Router LLM invocation error: {e}")
        is_data_query = False
        intent = "general_chat"
        thought = f"Fallback due to router exception: {str(e)}"
        direct_resp = (
            "I am DataPilot AI, your database analyst. I can assist with querying sales, customers, and revenue metrics. "
            "Please ask a business data question!"
        )
        current_sql = None
        tables_used = []

    # Conversational / Out-of-Scope fallback
    if not is_data_query or not current_sql:
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
            "agent_thought_trace": [f"💬 [Router] Handled inquiry: {thought}"],
        }

    # Trace badge based on intent
    trace_badge = {
        "data_query": "🔍 [Router] Classified as Data Query & Generated SQL",
        "statistical_analysis": "📈 [Router] Classified as Statistical Analysis & Generated SQL",
        "email_action": "✉️ [Router] Classified as Action Drafting & Generated SQL",
    }.get(intent, "🔍 [Router] Generated SQL")

    # Return pure AI state to let sql_node execute query cleanly
    return {
        "intent": intent,
        "thought_process": thought,
        "direct_response": None,
        "sql_query": current_sql,
        "tables_used": tables_used,
        "agent_thought_trace": [f"{trace_badge}: {thought}"],
    }
