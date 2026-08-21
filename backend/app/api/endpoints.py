from fastapi import APIRouter
from app.schemas import ChatRequest, ChatResponse, DatabaseHealthResponse
from app.llm_service import process_chat_query
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
    """Text-to-SQL data analyst chat endpoint powered by Gemini 2.5 Flash & Supabase."""
    return process_chat_query(request.message)
