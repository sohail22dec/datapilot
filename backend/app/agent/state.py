import operator
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """
    Core state contract passed across nodes in the LangGraph state machine.
    Preserves context, SQL execution logs, analytical metrics, action payloads, and UI reasoning traces.
    """
    # Conversation history & Input
    messages: Annotated[List[BaseMessage], operator.add]
    user_question: str
    conversation_id: Optional[str]
    conversation_summary: Optional[str]
    chat_history: Optional[List[Dict[str, Any]]]

    # Intent Classification & Reasoning
    intent: str  # "data_query" | "statistical_analysis" | "email_action" | "general_chat"
    thought_process: str
    direct_response: Optional[str]

    # Database Context
    tables_used: List[str]
    sql_query: Optional[str]
    query_results: Optional[List[Dict[str, Any]]]
    columns: Optional[List[str]]
    row_count: int
    execution_time_ms: float

    # Self-Healing & Error Handling
    error_history: List[str]
    retry_count: int

    # Statistical Analytics Context
    computed_metrics: Optional[Dict[str, Any]]

    # Business Action Engine (Email / Campaign / Restock)
    action_type: Optional[str]
    action_payload: Optional[Dict[str, Any]]
    requires_human_approval: bool
    is_approved: bool

    # UI Presentation & Visualization
    chart_config: Optional[Dict[str, Any]]
    final_response: str
    agent_thought_trace: Annotated[List[str], operator.add]
