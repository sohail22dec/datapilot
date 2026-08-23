import json
from typing import Any, AsyncGenerator, Dict, Optional

from app.config import settings
from app.cache import query_cache
from app.agent.graph import agent_graph, run_agent_workflow
from app.agent.state import AgentState
from app.agent.nodes.synthesis_node import extract_text
from app.schemas import ChatResponse, ChartConfig


def process_chat_query(user_question: str) -> ChatResponse:
    """
    Synchronous orchestration entrypoint for DataPilot API.
    1. Checks QueryCache for sub-millisecond repeat query responses.
    2. Invokes compiled LangGraph StateGraph (Router ➔ SQL ➔ Self-Healing ➔ Stats/Email ➔ Synthesis).
    3. Caches and returns rich ChatResponse payload.
    """
    cached_response = query_cache.get(user_question)
    if cached_response:
        return ChatResponse(**cached_response)

    try:
        final_state: AgentState = run_agent_workflow(user_question)
    except Exception as e:
        return ChatResponse(
            response=f"I encountered an issue processing your request: {str(e)}",
            model=settings.GEMINI_MODEL,
        )

    chart_cfg = None
    if final_state.get("chart_config"):
        cfg_dict = final_state["chart_config"]
        chart_cfg = ChartConfig(
            type=cfg_dict.get("type"),
            x_key=cfg_dict.get("x_key"),
            y_key=cfg_dict.get("y_key"),
            title=cfg_dict.get("title"),
        )

    response_payload = ChatResponse(
        response=final_state.get("final_response") or "Analysis completed.",
        sql=final_state.get("sql_query"),
        data=final_state.get("query_results"),
        columns=final_state.get("columns"),
        row_count=final_state.get("row_count", 0),
        execution_time_ms=final_state.get("execution_time_ms", 0.0),
        chart_config=chart_cfg,
        model=settings.GEMINI_MODEL,
    )

    query_cache.set(user_question, response_payload.model_dump())
    return response_payload


async def stream_agent_workflow(user_question: str) -> AsyncGenerator[str, None]:
    """
    Native LangGraph Event Streaming Generator (astream_events v2):
    1. Runs the compiled LangGraph StateGraph natively so LangSmith records the full node tree.
    2. Streams 'step' events as nodes transition (router_node ➔ sql_node ➔ synthesis_node).
    3. Streams 'token' events word-by-word as synthesis_node generates text in <300ms perceived time.
    4. Yields 'done' event with final data table, row count, execution time, and chart config.
    """
    # 0. Check QueryCache for instant 0ms cached stream
    cached_data = query_cache.get(user_question)
    if cached_data:
        yield f"event: step\ndata: {json.dumps({'step': 'Serving from QueryCache', 'badge': '⚡ Cache Hit'})}\n\n"
        yield f"event: token\ndata: {json.dumps({'delta': cached_data.get('response', '')})}\n\n"
        yield f"event: done\ndata: {json.dumps(cached_data)}\n\n"
        return

    # Initialize initial state
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

    final_state_output: Optional[Dict[str, Any]] = None
    accumulated_tokens = ""

    node_badges = {
        "router_node": "🔍 Analyzing Inquiry & Schema",
        "sql_node": "⚡ Querying Supabase Database",
        "heal_node": "🩹 Self-Healing SQL",
        "stats_node": "🧮 Computing Statistical Metrics",
        "email_node": "✉️ Drafting Action Campaign",
        "synthesis_node": "📊 Synthesizing Insights",
    }

    try:
        # Native LangGraph astream_events v2
        async for event in agent_graph.astream_events(initial_state, version="v2"):
            kind = event["event"]
            name = event.get("name", "")

            # 1. Node Start: Stream animated status badge
            if kind == "on_chain_start" and name in node_badges:
                badge_text = node_badges[name]
                yield f"event: step\ndata: {json.dumps({'step': badge_text, 'badge': badge_text})}\n\n"

            # 2. Token Stream: Stream tokens word-by-word from synthesis_node
            elif kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk:
                    delta = extract_text(getattr(chunk, "content", ""))
                    if delta:
                        accumulated_tokens += delta
                        yield f"event: token\ndata: {json.dumps({'delta': delta})}\n\n"

            # 3. Graph Finished: Capture final state
            elif kind == "on_chain_end" and name == "LangGraph":
                final_state_output = event["data"].get("output")

    except Exception as e:
        err_msg = f"I encountered an error executing this request: {str(e)}"
        yield f"event: token\ndata: {json.dumps({'delta': err_msg})}\n\n"
        yield f"event: done\ndata: {json.dumps({'response': err_msg, 'sql': None, 'data': None, 'columns': None, 'row_count': 0, 'execution_time_ms': 0.0, 'chart_config': None})}\n\n"
        return

    # 4. Emit final completed payload
    if final_state_output:
        res_text = final_state_output.get("final_response") or accumulated_tokens
        done_payload = {
            "response": res_text,
            "sql": final_state_output.get("sql_query"),
            "data": final_state_output.get("query_results"),
            "columns": final_state_output.get("columns"),
            "row_count": final_state_output.get("row_count", 0),
            "execution_time_ms": final_state_output.get("execution_time_ms", 0.0),
            "chart_config": final_state_output.get("chart_config"),
            "computed_metrics": final_state_output.get("computed_metrics"),
            "action_payload": final_state_output.get("action_payload"),
            "thought_trace": final_state_output.get("agent_thought_trace", []),
        }
        query_cache.set(user_question, done_payload)
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
    else:
        yield f"event: done\ndata: {json.dumps({'response': accumulated_tokens, 'sql': None, 'data': None, 'columns': None, 'row_count': 0, 'execution_time_ms': 0.0, 'chart_config': None})}\n\n"
