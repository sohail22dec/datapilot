from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import (
    ChatRequest,
    ChatResponse,
    DatabaseHealthResponse,
    ConversationListResponse,
    ConversationDetailResponse,
    ConversationItem,
    ConversationMessageItem,
)
from app.llm_service import process_chat_query, stream_agent_workflow
from app.database import get_schema_metadata
from app.guardrails import verify_rate_limit
from app.memory.manager import (
    list_conversations,
    get_conversation_messages,
    get_or_create_conversation,
    delete_conversation,
)

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


@router.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(verify_rate_limit)])
def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """Synchronous text-to-SQL data analyst chat endpoint with memory & rate limiting."""
    return process_chat_query(
        user_question=request.message,
        conversation_id=request.conversation_id,
        background_tasks=background_tasks,
    )


@router.post("/api/chat/stream", dependencies=[Depends(verify_rate_limit)])
def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Real-time Server-Sent Events (SSE) streaming endpoint.
    Emits live step badges, token-by-token text generation (<300ms), and final chart data.
    """
    return StreamingResponse(
        stream_agent_workflow(
            user_question=request.message,
            conversation_id=request.conversation_id,
            background_tasks=background_tasks,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/conversations", response_model=ConversationListResponse)
def get_conversations():
    """List recent persistent conversations stored in Supabase."""
    convs = list_conversations(limit=50)
    items = [ConversationItem(**c) for c in convs]
    return ConversationListResponse(conversations=items)


@router.get("/api/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation_detail(conversation_id: str):
    """Fetch complete historical messages and summary for a conversation."""
    conv = get_or_create_conversation(conversation_id)
    raw_msgs = get_conversation_messages(conversation_id)
    messages = [ConversationMessageItem(**m) for m in raw_msgs]
    return ConversationDetailResponse(
        id=conv["id"],
        title=conv["title"],
        summary=conv.get("summary"),
        messages=messages,
    )


@router.delete("/api/conversations/{conversation_id}")
def remove_conversation(conversation_id: str):
    """Delete a conversation thread and its messages from Supabase."""
    success = delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete conversation from database.")
    return {"status": "success", "deleted_id": conversation_id}

