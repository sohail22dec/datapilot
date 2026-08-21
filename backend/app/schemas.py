from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="The natural language question from the user.")


class GeneratedSQL(BaseModel):
    sql_query: str = Field(
        ...,
        description="The valid, optimized PostgreSQL SELECT query to answer the user request."
    )
    thought_process: str = Field(
        ...,
        description="Brief reasoning for how the SQL was constructed based on tables and columns."
    )
    tables_used: List[str] = Field(
        default_factory=list,
        description="List of table names accessed in the SQL query."
    )


class ChartConfig(BaseModel):
    type: Optional[Literal["bar", "line", "area", "donut"]] = Field(
        None, description="Recommended chart type: bar, line, area, or donut."
    )
    x_key: Optional[str] = Field(
        None, description="Key/column name for the x-axis or category slice."
    )
    y_key: Optional[str] = Field(
        None, description="Key/column name for the numeric y-axis or metric value."
    )
    title: Optional[str] = Field(
        None, description="Concise descriptive title for the chart visualization."
    )


class ChatResponse(BaseModel):
    response: str = Field(..., description="The executive natural-language answer with bold metrics.")
    sql: Optional[str] = Field(None, description="The executed PostgreSQL query.")
    data: Optional[List[Dict[str, Any]]] = Field(None, description="Row objects returned by Supabase.")
    columns: Optional[List[str]] = Field(None, description="Column names returned in the query result.")
    row_count: Optional[int] = Field(None, description="Number of rows returned.")
    execution_time_ms: Optional[float] = Field(None, description="SQL query execution time in milliseconds.")
    chart_config: Optional[ChartConfig] = Field(None, description="Visual chart configuration if applicable.")
    model: Optional[str] = Field(None, description="AI model name used.")


class DatabaseHealthResponse(BaseModel):
    status: str = Field(..., description="Connection status: 'healthy', 'connected', or 'error'.")
    schema_text: Optional[str] = Field(None, description="Detected tables and column definitions.")
    error: Optional[str] = Field(None, description="Error message if connection failed.")
