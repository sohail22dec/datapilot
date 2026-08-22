from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest, ChatResponse, DatabaseHealthResponse
from app.llm_service import process_chat_query, stream_agent_workflow
from app.database import get_schema_metadata

router = APIRouter()


@router.get("/health")
def health_check():
    """Basic service health check endpoint."""
    return {"status": "healthy"}


@router.get("/api/database/health", response_model=DatabaseHealthResponse)
def database_health():
    """Inspect Supabase database connection and detected public schema."""
    info = get_schema_metadata()
    return DatabaseHealthResponse(
        status=info["status"],
        schema_text=info.get("schema_text"),
        error=info.get("error"),
    )


@router.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Synchronous text-to-SQL data analyst chat endpoint."""
    return process_chat_query(request.message)


@router.post("/api/chat/stream")
def chat_stream(request: ChatRequest):
    """
    Real-time Server-Sent Events (SSE) streaming endpoint.
    Emits live step badges, token-by-token text generation (<300ms), and final chart data.
    """
    return StreamingResponse(
        stream_agent_workflow(request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
