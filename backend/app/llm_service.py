import logging

from app.config import settings
from app.cache import query_cache
from app.agents import run_agent_workflow, AgentState
from app.schemas import ChatResponse, ChartConfig

logger = logging.getLogger(__name__)


def process_chat_query(user_question: str) -> ChatResponse:
    """
    Main orchestration entrypoint for DataPilot API.
    1. Checks QueryCache for sub-millisecond repeat query responses.
    2. Invokes compiled LangGraph StateGraph (Router ➔ SQL ➔ Self-Healing ➔ Stats/Email ➔ Synthesis).
    3. Caches and returns rich ChatResponse payload.
    """
    # 1. Check Query Cache for instant repeat responses
    cached_response = query_cache.get(user_question)
    if cached_response:
        logger.info(f"Serving query directly from QueryCache: '{user_question}'")
        return ChatResponse(**cached_response)

    logger.info(f"Executing LangGraph agent workflow for: '{user_question}'")

    # 2. Execute LangGraph Agent State Machine
    try:
        final_state: AgentState = run_agent_workflow(user_question)
    except Exception as e:
        logger.error(f"LangGraph execution exception: {e}", exc_info=True)
        return ChatResponse(
            response=f"I encountered an issue processing your request: {str(e)}",
            model=settings.GEMINI_MODEL,
        )

    # 3. Parse chart configuration if present
    chart_cfg = None
    if final_state.get("chart_config"):
        cfg_dict = final_state["chart_config"]
        chart_cfg = ChartConfig(
            type=cfg_dict.get("type"),
            x_key=cfg_dict.get("x_key"),
            y_key=cfg_dict.get("y_key"),
            title=cfg_dict.get("title"),
        )

    # 4. Build rich ChatResponse
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

    # 5. Cache response
    query_cache.set(user_question, response_payload.model_dump())

    return response_payload
