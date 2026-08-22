from langgraph.graph import StateGraph, START, END

from app.agents.state import AgentState
from app.agents.nodes import (
    router_node,
    sql_node,
    heal_node,
    stats_node,
    email_node,
    synthesis_node,
)


# ---------------------------------------------------------
# Conditional Edge Routers
# ---------------------------------------------------------

def route_after_entry(state: AgentState) -> str:
    """
    Evaluates outcome of the Router Node:
    1. General chat / Identity ➔ synthesis_node (instant return)
    2. Business data query / Statistical analysis / Email action ➔ sql_node (for pure DB execution)
    """
    intent = state.get("intent", "data_query")

    if intent == "general_chat":
        return "synthesis_node"

    return "sql_node"


def route_after_sql(state: AgentState) -> str:
    """
    Evaluates outcome of database execution in sql_node:
    1. Failed query and retries < 2 ➔ heal_node (Self-Healing Loop)
    2. Failed query and retries >= 2 ➔ synthesis_node (Error fallback)
    3. Statistical analysis intent ➔ stats_node
    4. Email action intent ➔ email_node
    5. Standard data query ➔ synthesis_node
    """
    rows = state.get("query_results")
    retry_count = state.get("retry_count", 0)

    # Failed query branch
    if rows is None:
        if retry_count < 2:
            return "heal_node"
        return "synthesis_node"

    # Successful branch
    intent = state.get("intent", "data_query")
    if intent == "statistical_analysis":
        return "stats_node"
    elif intent == "email_action":
        return "email_node"
    return "synthesis_node"


# ---------------------------------------------------------
# Graph Construction
# ---------------------------------------------------------

def create_agent_graph() -> StateGraph:
    """
    Assembles the Decoupled High-Performance DataPilot LangGraph:
    START ➔ router_node ──(general_chat)──────────────▶ synthesis_node ➔ END
                       └──(data/stats/email)──▶ sql_node
                                                  │──(success: data) ────────▶ synthesis_node
                                                  │──(success: stats) ───────▶ stats_node ──▶ synthesis_node
                                                  │──(success: email) ───────▶ email_node ──▶ synthesis_node
                                                  └──(error) ──▶ heal_node ──▶ sql_node
    """
    workflow = StateGraph(AgentState)

    # 1. Register all specialized nodes
    workflow.add_node("router_node", router_node)
    workflow.add_node("sql_node", sql_node)
    workflow.add_node("heal_node", heal_node)
    workflow.add_node("stats_node", stats_node)
    workflow.add_node("email_node", email_node)
    workflow.add_node("synthesis_node", synthesis_node)

    # 2. Entry point into Router Node
    workflow.add_edge(START, "router_node")

    # 3. Conditional routing from Router Node
    workflow.add_conditional_edges(
        "router_node",
        route_after_entry,
        {
            "sql_node": "sql_node",
            "synthesis_node": "synthesis_node",
        },
    )

    # 4. Conditional routing after SQL execution
    workflow.add_conditional_edges(
        "sql_node",
        route_after_sql,
        {
            "heal_node": "heal_node",
            "stats_node": "stats_node",
            "email_node": "email_node",
            "synthesis_node": "synthesis_node",
        },
    )

    # 5. Self-healing loop: heal_node ➔ sql_node
    workflow.add_edge("heal_node", "sql_node")

    # 6. Feature nodes route to synthesis
    workflow.add_edge("stats_node", "synthesis_node")
    workflow.add_edge("email_node", "synthesis_node")

    # 7. Terminal edge
    workflow.add_edge("synthesis_node", END)

    return workflow


# Compiled Singleton Graph Instance
agent_graph = create_agent_graph().compile()


def run_agent_workflow(user_question: str) -> AgentState:
    """
    Synchronously executes the decoupled LangGraph agent workflow.
    Returns populated final AgentState with sub-2s latency.
    """
    initial_state: AgentState = {
        "messages": [],
        "user_question": user_question,
        "intent": "data_query",
        "thought_process": "",
        "direct_response": None,
        "tables_used": [],
        "sql_query": None,
        "query_results": None,
        "columns": None,
        "row_count": 0,
        "execution_time_ms": 0.0,
        "error_history": [],
        "retry_count": 0,
        "computed_metrics": None,
        "action_type": None,
        "action_payload": None,
        "requires_human_approval": False,
        "is_approved": False,
        "chart_config": None,
        "final_response": "",
        "agent_thought_trace": [],
    }

    final_state = agent_graph.invoke(initial_state)
    return final_state
