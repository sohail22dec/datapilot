from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings

# Initialize LangChain Gemini model
llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0.2,
)

SYSTEM_INSTRUCTION = "You are DataPilot AI, an expert AI assistant."


def generate_chat_response(prompt: str) -> dict:
    """Send user prompt to Gemini via LangChain and return the response."""
    messages = [
        SystemMessage(content=SYSTEM_INSTRUCTION),
        HumanMessage(content=prompt),
    ]
    response = llm.invoke(messages)

    return {
        "response": response.content or "",
        "model": settings.GEMINI_MODEL,
    }
