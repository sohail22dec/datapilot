import re
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.agent.state import AgentState
from app.tools.schema_tool import get_schema_context

debugger_llm = ChatGroq(
    model="openai/gpt-oss-120b",
    groq_api_key=settings.GROQ_API_KEY,
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
1. Carefully diagnose the PostgreSQL error (e.g. column does not exist, relation does not exist, missing column in GROUP BY, invalid type comparison, missing ON join predicate, syntax error).
2. Fix column and table names by mapping them to the real PostgreSQL database schema provided above.
3. For type mismatches (e.g. date vs integer, comparing timestamp to year integer), use proper PostgreSQL functions like EXTRACT(YEAR FROM order_date) = 2024 or '2023-01-01'::date.
4. For missing GROUP BY columns, add all non-aggregated columns from the SELECT projection to the GROUP BY clause.
5. Fix syntax errors like trailing commas, missing ON join predicates, or misplaced WHERE clauses (WHERE must precede GROUP BY).
6. Return strictly the corrected, valid PostgreSQL SELECT query.
"""


def extract_sql_from_text(text: str) -> str:
    """Extracts SQL query from markdown code blocks or raw text."""
    cleaned = text.strip()
    if "```" in cleaned:
        match = re.search(r"```(?:sql)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return cleaned


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

    prompt_content = SQL_HEAL_PROMPT.format(
        schema_context=schema_context,
        user_question=user_q,
        failed_sql=failed_sql,
        error_message=last_error,
    )

    new_sql = failed_sql
    explanation = "SQL repaired"

    try:
        correction = structured_debugger.invoke([
            SystemMessage(content=prompt_content),
            HumanMessage(content="Please provide the corrected PostgreSQL query."),
        ])
        if correction and hasattr(correction, "corrected_sql") and correction.corrected_sql:
            new_sql = extract_sql_from_text(correction.corrected_sql)
            explanation = getattr(correction, "explanation", "Repaired query via structured debugger")
    except Exception as e:
        # Fallback to direct prompt if structured output encounters formatting issue
        try:
            raw_res = debugger_llm.invoke([
                SystemMessage(content=prompt_content + "\nProvide only the corrected SQL inside a ```sql code block with a 1-sentence explanation."),
                HumanMessage(content="Correct the SQL query now."),
            ])
            raw_text = raw_res.content if hasattr(raw_res, "content") else str(raw_res)
            extracted = extract_sql_from_text(raw_text)
            if extracted and extracted != failed_sql:
                new_sql = extracted
                explanation = "Repaired query via direct fallback"
            else:
                new_sql = failed_sql
                explanation = f"Healing prompt failed: {str(e)}"
        except Exception as inner_e:
            new_sql = failed_sql
            explanation = f"Healing fallback failed: {str(inner_e)}"

    trace_msg = f"🩹 [Self-Healing] Attempt {retry_count}/2: Corrected SQL ({explanation})"

    return {
        "sql_query": new_sql,
        "retry_count": retry_count,
        "agent_thought_trace": [trace_msg],
    }
