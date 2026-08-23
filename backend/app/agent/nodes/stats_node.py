from app.agent.state import AgentState
from app.tools.python_tool import execute_python_stats

def stats_node(state: AgentState) -> dict:
    """
    Python Statistics & Analytics Node:
    Takes database query rows and computes deep business metrics:
    Profit Margins, Month-over-Month Growth, Churn Rates, Inventory Burn Rate.
    """
    user_q = state.get("user_question", "").lower()
    rows = state.get("query_results") or []

    if not rows:
        return {
            "computed_metrics": None,
            "agent_thought_trace": ["⚠️ [Stats Engine] No data rows available for statistical computation"],
        }

    # Determine optimal metric calculation
    if any(k in user_q for k in ["margin", "profit", "cogs", "cost", "loss"]):
        metric_name = "profit_margin"
        badge = "Profit Margin & COGS"
    elif any(k in user_q for k in ["growth", "trend", "mom", "month over month", "trajectory"]):
        metric_name = "mom_growth"
        badge = "Month-over-Month Growth Series"
    elif any(k in user_q for k in ["churn", "retention", "inactive", "lapsed", "attrition"]):
        metric_name = "churn_rate"
        badge = "Customer Churn & Retention Rate"
    elif any(k in user_q for k in ["inventory", "stock", "burn rate", "run rate", "depletion", "sku"]):
        metric_name = "inventory_burn_rate"
        badge = "Inventory Run-Rate & Days Remaining"
    else:
        # Default to profit margin or growth based on columns
        cols = [c.lower() for c in (state.get("columns") or [])]
        if any("profit" in c or "cost" in c for c in cols):
            metric_name = "profit_margin"
            badge = "Profit Margin"
        elif any("month" in c or "date" in c for c in cols):
            metric_name = "mom_growth"
            badge = "Growth Trend"
        else:
            metric_name = "profit_margin"
            badge = "Analytical Summary"

    computed = execute_python_stats(metric_name, rows)

    trace_msg = f"🧮 [Stats Engine] Computed {badge} across {len(rows)} data points"

    return {
        "computed_metrics": computed,
        "agent_thought_trace": [trace_msg],
    }
