import time
import pytest
from app.database import init_memory_tables
from app.memory.manager import (
    estimate_tokens,
    get_or_create_conversation,
    get_optimized_context,
    save_turn,
    list_conversations,
    get_conversation_messages,
    delete_conversation,
    TOKEN_WATERMARK_LIMIT,
    MESSAGE_WATERMARK_LIMIT,
)


@pytest.fixture(autouse=True)
def setup_tables():
    init_memory_tables()



def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world") >= 1
    # 400 characters is ~100 tokens
    long_text = "a" * 400
    assert estimate_tokens(long_text) == 100


def test_conversation_lifecycle_and_watermark_compaction():
    conv_id = f"test-conv-{int(time.time() * 1000)}"

    # 1. Create conversation
    conv = get_or_create_conversation(conv_id, title="Test Analytics Thread")
    assert conv["id"] == conv_id
    assert conv["title"] == "Test Analytics Thread"

    # 2. Add turns under watermark threshold (<10 messages, <2000 tokens)
    save_turn(
        conversation_id=conv_id,
        user_question="Show top 5 customers by revenue",
        assistant_response="Top customers generated.",
        sql="SELECT * FROM customers LIMIT 5;",
    )
    save_turn(
        conversation_id=conv_id,
        user_question="Filter those from Bangalore",
        assistant_response="Filtered for Bangalore region.",
        sql="SELECT * FROM customers WHERE city = 'Bangalore' LIMIT 5;",
    )

    # 3. Verify optimized context returns full history when under watermark
    ctx = get_optimized_context(conv_id)
    assert ctx.conversation_id == conv_id
    assert len(ctx.recent_messages) == 4  # 2 turns = 4 messages
    assert ctx.message_count == 4

    # 4. Add more turns to exceed the 10-message watermark limit
    for i in range(4):
        save_turn(
            conversation_id=conv_id,
            user_question=f"Follow up query {i+1}",
            assistant_response=f"Answer for query {i+1}",
            sql=f"SELECT {i+1};",
        )

    # 5. Verify watermark compaction kicks in (message count = 12 >= 10)
    compact_ctx = get_optimized_context(conv_id)
    assert compact_ctx.message_count == 12
    # When watermark is active, context is compacted to only the last 2 messages (1 turn)
    assert len(compact_ctx.recent_messages) == 2

    # 6. Verify listing and detail retrieval
    conv_list = list_conversations(limit=20)
    matching = [c for c in conv_list if c["id"] == conv_id]
    assert len(matching) == 1

    messages = get_conversation_messages(conv_id)
    assert len(messages) == 12

    # 7. Cleanup & delete
    deleted = delete_conversation(conv_id)
    assert deleted is True
    assert len(get_conversation_messages(conv_id)) == 0
