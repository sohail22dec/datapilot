from fastapi import APIRouter
from app.schemas import ChatRequest
from app.llm_service import generate_chat_response

router = APIRouter()


@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.post("/api/chat")
def chat(request: ChatRequest):
    """Chatbot endpoint powered by Gemini Flash & LangChain."""
    return generate_chat_response(request.message)
