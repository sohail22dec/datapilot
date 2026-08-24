from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.agent.state import AgentState
from app.tools.schema_tool import get_schema_context

debugger_llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0.0,
)


class CorrectedSQLOutput(BaseModel):
    corrected_sql: str = Field(
        ...,
        description="The fixed PostgreSQL SELECT query resolving the syntax or runtime error."
    )
    explanation: str = Field(
        ...,
        description="Brief explanation of what caused the error and how it was fixed."
    )


structured_debugger = debugger_llm.with_structured_output(CorrectedSQLOutput)

SQL_HEAL_PROMPT = """You are the Senior PostgreSQL Self-Healing Debugger Node in DataPilot.
A generated SQL query failed execution against the PostgreSQL database.
Fix the SQL query so it runs successfully based on the exact error message and schema context.

Database Schema:
{schema_context}

User Question: {user_question}
Failed SQL Query: {failed_sql}
PostgreSQL Error: {error_message}

Debugging Instructions:
1. Carefully diagnose the error (e.g. invalid column name, missing GROUP BY, mismatched types, table not found).
2. Rewrite the query to strictly fix the issue while accurately answering the user's inquiry.
3. Return the corrected PostgreSQL query.
"""


def heal_node(state: AgentState) -> dict:
    """
    Self-Healing Recovery Node:
    Diagnoses SQL failure, rewrites query, increments retry_count,
    and loops back to SQL execution.
    """
    user_q = state.get("user_question", "")
    failed_sql = state.get("sql_query", "")
    error_history = state.get("error_history", [])
    retry_count = state.get("retry_count", 0) + 1
    last_error = error_history[-1] if error_history else "Unknown SQL error"

    schema_context = get_schema_context()

    try:
        correction = structured_debugger.invoke([
            SystemMessage(content=SQL_HEAL_PROMPT.format(
                schema_context=schema_context,
                user_question=user_q,
                failed_sql=failed_sql,
                error_message=last_error,
            )),
            HumanMessage(content="Please provide the corrected PostgreSQL query."),
        ])
        new_sql = correction.corrected_sql.strip()
        explanation = correction.explanation
    except Exception as e:
        new_sql = failed_sql
        explanation = f"Healing prompt failed: {str(e)}"

    trace_msg = f"🩹 [Self-Healing] Attempt {retry_count}/2: Corrected SQL ({explanation})"

    return {
        "sql_query": new_sql,
        "retry_count": retry_count,
        "agent_thought_trace": [trace_msg],
    }
