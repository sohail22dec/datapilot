import logging
from typing import Optional
from sqlalchemy import text
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.database import engine

logger = logging.getLogger(__name__)

# Fast, lean model for non-blocking background summarization
summarizer_llm = ChatGroq(
    model="openai/gpt-oss-120b",
    groq_api_key=settings.GROQ_API_KEY,
    temperature=0.0,
)

SUMMARIZER_PROMPT = """You are a background conversation memory compressor for DataPilot, an executive BI system.
Your task is to compress the conversation history into a dense, bulleted long-term context summary (<100 tokens).

Existing Summary (if any):
{existing_summary}

Older Messages to Compress:
{messages_text}

Instructions:
1. Capture only essential business context:
   - Primary user analytical objectives and goals.
   - Specific SQL filters, table entities, timeframes, or customer segments analyzed.
   - Key numeric metrics discovered (e.g. Total Revenue ₹45.2L, 14.5% churn, Top VIPs).
2. Output EXACTLY 2-4 concise bullet points.
3. DO NOT include pleasantries, greetings, or raw SQL syntax.
4. Keep the total output under 100 tokens.
"""


def estimate_tokens(text_content: str) -> int:
    """Estimates token count (~4 characters per token)."""
    if not text_content:
        return 0
    return max(1, len(text_content) // 4)


def async_compact_conversation(conversation_id: str) -> Optional[str]:
    """
    Asynchronously compresses older conversation turns into a persistent summary in Supabase.
    Runs non-blocking in background tasks after response streaming finishes.
    """
    if not conversation_id:
        return None

    try:
        with engine.connect() as conn:
            # 1. Fetch current conversation metadata
            conv_row = conn.execute(
                text("SELECT id, summary FROM public.conversations WHERE id = :id"),
                {"id": conversation_id}
            ).fetchone()

            if not conv_row:
                return None

            existing_summary = conv_row.summary or "None"

            # 2. Fetch all messages ordered by creation time
            msg_rows = conn.execute(
                text("""
                    SELECT role, content, sql
                    FROM public.messages
                    WHERE conversation_id = :id
                    ORDER BY created_at ASC
                """),
                {"id": conversation_id}
            ).fetchall()

            if len(msg_rows) < 4:
                return None

            # Keep the last 2 messages uncompressed for immediate conversational flow
            older_msgs = msg_rows[:-2]
            recent_msgs = msg_rows[-2:]

            messages_text_parts = []
            for m in older_msgs:
                role_label = "User" if m.role == "user" else "Assistant"
                sql_note = f" (Executed SQL: {m.sql})" if m.sql else ""
                messages_text_parts.append(f"{role_label}: {m.content}{sql_note}")

            messages_text = "\n".join(messages_text_parts)

            # 3. Call LLM to summarize older turns
            response = summarizer_llm.invoke([
                SystemMessage(content="You are DataPilot AI's background conversation memory summarizer."),
                HumanMessage(content=SUMMARIZER_PROMPT.format(
                    existing_summary=existing_summary,
                    messages_text=messages_text
                ))
            ])

            new_summary = response.content.strip() if hasattr(response, "content") else str(response).strip()

            # 4. Calculate new working window token count (summary + recent 2 messages)
            recent_text = " ".join([m.content for m in recent_msgs])
            new_working_tokens = estimate_tokens(new_summary) + estimate_tokens(recent_text)

            # 5. Update Supabase record
            with engine.begin() as update_conn:
                update_conn.execute(
                    text("""
                        UPDATE public.conversations
                        SET summary = :summary,
                            token_count = :tokens,
                            updated_at = NOW()
                        WHERE id = :id
                    """),
                    {
                        "summary": new_summary,
                        "tokens": new_working_tokens,
                        "id": conversation_id
                    }
                )

            logger.info(f"Memory compaction completed for conversation '{conversation_id}': new token footprint = {new_working_tokens}")
            return new_summary

    except Exception as e:
        logger.error(f"Error during async memory compaction for conversation '{conversation_id}': {e}")
        return None
