import json
from typing import Any, AsyncGenerator, Dict, Optional

from app.config import settings
from app.cache import query_cache
from app.agent.graph import agent_graph, run_agent_workflow
from app.agent.state import AgentState
from app.agent.nodes.synthesis_node import extract_text
from app.schemas import ChatResponse, ChartConfig
from app.memory.manager import get_optimized_context, save_turn


def process_chat_query(
    user_question: str,
    conversation_id: Optional[str] = None,
    background_tasks: Optional[Any] = None,
) -> ChatResponse:
    """
    Synchronous orchestration entrypoint for DataPilot API.
    1. Retrieves optimized conversation memory context (Watermark-compacted if >2,000 tokens).
    2. Invokes compiled LangGraph StateGraph with memory context.
    3. Persists turn and schedules async background compaction if watermark exceeded.
    """
    mem_ctx = get_optimized_context(conversation_id)

    try:
        final_state: AgentState = run_agent_workflow(
            user_question=user_question,
            conversation_id=conversation_id,
            conversation_summary=mem_ctx.summary,
            chat_history=mem_ctx.recent_messages,
        )
    except Exception as e:
        return ChatResponse(
            response=f"I encountered an issue processing your request: {str(e)}",
            model=settings.GEMINI_MODEL,
            conversation_id=conversation_id,
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

    final_resp_text = final_state.get("final_response") or "Analysis completed."
    sql_text = final_state.get("sql_query")
    data_rows = final_state.get("query_results")
    col_names = final_state.get("columns")
    metrics = final_state.get("computed_metrics")
    thought_trace = final_state.get("agent_thought_trace", [])

    response_payload = ChatResponse(
        response=final_resp_text,
        sql=sql_text,
        data=data_rows,
        columns=col_names,
        row_count=final_state.get("row_count", 0),
        execution_time_ms=final_state.get("execution_time_ms", 0.0),
        chart_config=chart_cfg,
        model=settings.GEMINI_MODEL,
        conversation_id=conversation_id,
    )

    if conversation_id:
        save_turn(
            conversation_id=conversation_id,
            user_question=user_question,
            assistant_response=final_resp_text,
            sql=sql_text,
            data_preview=data_rows,
            metrics=metrics,
            chart_config=final_state.get("chart_config"),
            thought_trace=thought_trace,
            background_tasks=background_tasks,
        )

    return response_payload


async def stream_agent_workflow(
    user_question: str,
    conversation_id: Optional[str] = None,
    background_tasks: Optional[Any] = None,
) -> AsyncGenerator[str, None]:
    """
    Native LangGraph Event Streaming Generator (astream_events v2) with Memory Context:
    1. Loads optimized memory context (<520 tokens).
    2. Streams step badges and word-by-word token generation.
    3. Persists turn to Supabase and dispatches non-blocking background compaction.
    """
    mem_ctx = get_optimized_context(conversation_id)

    # Initialize initial state with memory context
    initial_state: AgentState = {
        "messages": [],
        "user_question": user_question,
        "conversation_id": conversation_id,
        "conversation_summary": mem_ctx.summary,
        "chat_history": mem_ctx.recent_messages,
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
        yield f"event: done\ndata: {json.dumps({'response': err_msg, 'sql': None, 'data': None, 'columns': None, 'row_count': 0, 'execution_time_ms': 0.0, 'chart_config': None, 'conversation_id': conversation_id})}\n\n"
        return

    # 4. Emit final completed payload & save turn to Supabase
    if final_state_output:
        res_text = final_state_output.get("final_response") or accumulated_tokens
        sql_text = final_state_output.get("sql_query")
        data_rows = final_state_output.get("query_results")
        col_names = final_state_output.get("columns")
        metrics = final_state_output.get("computed_metrics")
        chart_cfg = final_state_output.get("chart_config")
        thought_trace = final_state_output.get("agent_thought_trace", [])

        done_payload = {
            "response": res_text,
            "sql": sql_text,
            "data": data_rows,
            "columns": col_names,
            "row_count": final_state_output.get("row_count", 0),
            "execution_time_ms": final_state_output.get("execution_time_ms", 0.0),
            "chart_config": chart_cfg,
            "computed_metrics": metrics,
            "action_payload": final_state_output.get("action_payload"),
            "thought_trace": thought_trace,
            "conversation_id": conversation_id,
        }

        if conversation_id:
            save_turn(
                conversation_id=conversation_id,
                user_question=user_question,
                assistant_response=res_text,
                sql=sql_text,
                data_preview=data_rows,
                metrics=metrics,
                chart_config=chart_cfg,
                thought_trace=thought_trace,
                background_tasks=background_tasks,
            )

        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
    else:
        yield f"event: done\ndata: {json.dumps({'response': accumulated_tokens, 'sql': None, 'data': None, 'columns': None, 'row_count': 0, 'execution_time_ms': 0.0, 'chart_config': None, 'conversation_id': conversation_id})}\n\n"

