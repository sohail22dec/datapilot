import json
import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database import engine
from app.memory.summarizer import async_compact_conversation, estimate_tokens

logger = logging.getLogger(__name__)

# Watermark compaction thresholds
TOKEN_WATERMARK_LIMIT = 2000
MESSAGE_WATERMARK_LIMIT = 10


class MemoryContext(BaseModel):
    conversation_id: Optional[str] = None
    summary: Optional[str] = None
    recent_messages: List[Dict[str, Any]] = Field(default_factory=list)
    token_count: int = 0
    message_count: int = 0


def get_or_create_conversation(conversation_id: str, title: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves or creates a conversation record in Supabase."""
    clean_title = title or "New Conversation"
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT id, title, summary, token_count, message_count FROM public.conversations WHERE id = :id"),
                {"id": conversation_id}
            ).fetchone()

            if row:
                return {
                    "id": row.id,
                    "title": row.title,
                    "summary": row.summary,
                    "token_count": row.token_count or 0,
                    "message_count": row.message_count or 0,
                }

            conn.execute(
                text("""
                    INSERT INTO public.conversations (id, title, summary, token_count, message_count, created_at, updated_at)
                    VALUES (:id, :title, NULL, 0, 0, NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING
                """),
                {"id": conversation_id, "title": clean_title}
            )

            return {
                "id": conversation_id,
                "title": clean_title,
                "summary": None,
                "token_count": 0,
                "message_count": 0,
            }
    except Exception as e:
        logger.error(f"Error in get_or_create_conversation({conversation_id}): {e}")
        return {
            "id": conversation_id,
            "title": clean_title,
            "summary": None,
            "token_count": 0,
            "message_count": 0,
        }


def get_optimized_context(conversation_id: Optional[str]) -> MemoryContext:
    """
    Builds the optimized memory context for a given conversation.
    - If total tokens < 2,000 and messages < 10: passes all raw history.
    - If total tokens >= 2,000 or messages >= 10: passes compressed summary + last 2 messages (~520 tokens).
    """
    if not conversation_id:
        return MemoryContext()

    try:
        conv = get_or_create_conversation(conversation_id)

        with engine.connect() as conn:
            msg_rows = conn.execute(
                text("""
                    SELECT id, role, content, sql, data_preview, metrics, chart_config, thought_trace, token_count, created_at
                    FROM public.messages
                    WHERE conversation_id = :id
                    ORDER BY created_at ASC
                """),
                {"id": conversation_id}
            ).fetchall()

            messages: List[Dict[str, Any]] = [
                {
                    "id": r.id,
                    "role": r.role,
                    "content": r.content,
                    "sql": r.sql,
                    "data": r.data_preview,
                    "metrics": r.metrics,
                    "chart_config": r.chart_config,
                    "thought_trace": r.thought_trace,
                }
                for r in msg_rows
            ]

            summary = conv.get("summary")
            msg_count = len(messages)

            # Estimate total uncompressed token volume
            raw_tokens = sum(estimate_tokens(m["content"]) for m in messages)
            if summary:
                raw_tokens += estimate_tokens(summary)

            # Check if watermark limit exceeded
            if raw_tokens >= TOKEN_WATERMARK_LIMIT or msg_count >= MESSAGE_WATERMARK_LIMIT:
                # Watermark compaction active: return summary + last 2 messages (1 user + 1 assistant)
                recent_window = messages[-2:] if len(messages) >= 2 else messages
                effective_tokens = estimate_tokens(summary or "") + sum(estimate_tokens(m["content"]) for m in recent_window)
                return MemoryContext(
                    conversation_id=conversation_id,
                    summary=summary,
                    recent_messages=recent_window,
                    token_count=effective_tokens,
                    message_count=msg_count,
                )
            else:
                # Under limit: return full message history
                return MemoryContext(
                    conversation_id=conversation_id,
                    summary=summary,
                    recent_messages=messages,
                    token_count=raw_tokens,
                    message_count=msg_count,
                )

    except Exception as e:
        logger.error(f"Error fetching memory context for conversation {conversation_id}: {e}")
        return MemoryContext(conversation_id=conversation_id)


def save_turn(
    conversation_id: str,
    user_question: str,
    assistant_response: str,
    sql: Optional[str] = None,
    data_preview: Optional[List[Dict[str, Any]]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    chart_config: Optional[Dict[str, Any]] = None,
    thought_trace: Optional[List[str]] = None,
    background_tasks: Optional[Any] = None,
) -> None:
    """
    Persists a complete turn (user + assistant) to Supabase and triggers watermark compaction if needed.
    """
    if not conversation_id:
        return

    user_msg_id = f"msg-u-{int(time.time() * 1000)}"
    asst_msg_id = f"msg-a-{int(time.time() * 1000) + 1}"

    u_tokens = estimate_tokens(user_question)
    a_tokens = estimate_tokens(assistant_response)

    # Clean preview data for JSONB storage (limit preview rows to 10)
    safe_preview = data_preview[:10] if data_preview else None

    try:
        with engine.begin() as conn:
            # Ensure conversation exists
            get_or_create_conversation(conversation_id)

            # Insert user message
            conn.execute(
                text("""
                    INSERT INTO public.messages (id, conversation_id, role, content, token_count, created_at)
                    VALUES (:id, :conv_id, 'user', :content, :tokens, NOW())
                """),
                {
                    "id": user_msg_id,
                    "conv_id": conversation_id,
                    "content": user_question,
                    "tokens": u_tokens,
                }
            )

            # Insert assistant message
            conn.execute(
                text("""
                    INSERT INTO public.messages (
                        id, conversation_id, role, content, sql, data_preview, metrics,
                        chart_config, thought_trace, token_count, created_at
                    )
                    VALUES (
                        :id, :conv_id, 'assistant', :content, :sql, :data_preview, :metrics,
                        :chart_config, :thought_trace, :tokens, NOW()
                    )
                """),
                {
                    "id": asst_msg_id,
                    "conv_id": conversation_id,
                    "content": assistant_response,
                    "sql": sql,
                    "data_preview": json.dumps(safe_preview) if safe_preview else None,
                    "metrics": json.dumps(metrics) if metrics else None,
                    "chart_config": json.dumps(chart_config) if chart_config else None,
                    "thought_trace": json.dumps(thought_trace) if thought_trace else None,
                    "tokens": a_tokens,
                }
            )

            # Update conversation metadata & check if title update is needed
            current_meta = conn.execute(
                text("SELECT title, message_count, token_count FROM public.conversations WHERE id = :id"),
                {"id": conversation_id}
            ).fetchone()

            curr_count = (current_meta.message_count or 0) + 2
            curr_tokens = (current_meta.token_count or 0) + u_tokens + a_tokens

            new_title = current_meta.title
            if new_title == "New Conversation" or not new_title:
                new_title = user_question[:45].strip() + ("..." if len(user_question) > 45 else "")

            conn.execute(
                text("""
                    UPDATE public.conversations
                    SET message_count = :msg_count,
                        token_count = :token_count,
                        title = :title,
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    "msg_count": curr_count,
                    "token_count": curr_tokens,
                    "title": new_title,
                    "id": conversation_id,
                }
            )

        # Check if watermark limit is hit -> schedule non-blocking background summarizer
        if curr_tokens >= TOKEN_WATERMARK_LIMIT or curr_count >= MESSAGE_WATERMARK_LIMIT:
            if background_tasks is not None:
                background_tasks.add_task(async_compact_conversation, conversation_id)
            else:
                # If invoked without FastAPI background_tasks (e.g. sync script), run directly
                try:
                    async_compact_conversation(conversation_id)
                except Exception as e:
                    logger.warning(f"Direct compaction failed: {e}")

    except Exception as e:
        logger.error(f"Error persisting turn to Supabase for conversation '{conversation_id}': {e}")


def list_conversations(limit: int = 50) -> List[Dict[str, Any]]:
    """Returns list of recent conversations from Supabase."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, title, summary, message_count, token_count, created_at, updated_at
                    FROM public.conversations
                    ORDER BY updated_at DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            ).fetchall()

            return [
                {
                    "id": r.id,
                    "title": r.title,
                    "summary": r.summary,
                    "message_count": r.message_count,
                    "token_count": r.token_count,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        return []


def get_conversation_messages(conversation_id: str) -> List[Dict[str, Any]]:
    """Fetches all message history for a given conversation from Supabase."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, role, content, sql, data_preview, metrics, chart_config, thought_trace, created_at
                    FROM public.messages
                    WHERE conversation_id = :id
                    ORDER BY created_at ASC
                """),
                {"id": conversation_id}
            ).fetchall()

            messages = []
            for r in rows:
                data = json.loads(r.data_preview) if isinstance(r.data_preview, str) else r.data_preview
                metrics = json.loads(r.metrics) if isinstance(r.metrics, str) else r.metrics
                chart = json.loads(r.chart_config) if isinstance(r.chart_config, str) else r.chart_config
                thought = json.loads(r.thought_trace) if isinstance(r.thought_trace, str) else r.thought_trace

                messages.append({
                    "id": r.id,
                    "role": r.role,
                    "content": r.content,
                    "sql": r.sql,
                    "data": data,
                    "metrics": metrics,
                    "chart_config": chart,
                    "thought_trace": thought,
                    "timestamp": r.created_at.strftime("%I:%M %p") if r.created_at else "",
                })
            return messages
    except Exception as e:
        logger.error(f"Error getting messages for conversation {conversation_id}: {e}")
        return []


def delete_conversation(conversation_id: str) -> bool:
    """Deletes a conversation and its cascaded messages from Supabase."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.conversations WHERE id = :id"),
                {"id": conversation_id}
            )
        return True
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {e}")
        return False
