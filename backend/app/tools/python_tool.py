import logging
import math
import statistics
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Safe environment for custom sandbox execution
SAFE_GLOBALS = {
    "__builtins__": {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "len": len,
        "float": float,
        "int": int,
        "str": str,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "enumerate": enumerate,
        "zip": zip,
        "sorted": sorted,
        "range": range,
    },
    "math": math,
    "statistics": statistics,
}


def calculate_profit_margins(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates overall and itemized profit margins from transaction/order rows."""
    if not rows:
        return {"error": "No rows provided for profit margin calculation."}

    total_revenue = 0.0
    total_cost = 0.0
    item_breakdown = []

    for r in rows:
        rev = float(r.get("total_price") or r.get("revenue") or r.get("sales") or r.get("total_spend") or 0.0)
        cost = float(r.get("cost_price") or r.get("cost") or r.get("cogs") or 0.0)
        
        # If cost not provided, check for profit or assume estimated margin if needed
        profit = float(r.get("profit") or (rev - cost))
        margin = round((profit / rev * 100), 2) if rev > 0 else 0.0

        total_revenue += rev
        total_cost += cost
        item_name = r.get("product_name") or r.get("title") or r.get("name") or r.get("category")
        if item_name:
            item_breakdown.append({
                "item": str(item_name),
                "revenue": rev,
                "profit": profit,
                "margin_pct": margin,
            })

    net_profit = total_revenue - total_cost
    net_margin_pct = round((net_profit / total_revenue * 100), 2) if total_revenue > 0 else 0.0

    return {
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
        "net_profit": round(net_profit, 2),
        "net_margin_pct": net_margin_pct,
        "item_breakdown": item_breakdown[:10],
    }


def calculate_mom_growth(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates Month-over-Month (MoM) growth series from aggregated chronological rows."""
    if len(rows) < 2:
        return {"error": "At least 2 periods required to calculate MoM growth."}

    periods = []
    for r in rows:
        # Find period label
        period_key = next((k for k in r if any(p in k.lower() for p in ["month", "date", "period", "year"])), None)
        val_key = next((k for k in r if isinstance(r[k], (int, float)) and not k.endswith("_id")), None)
        
        if period_key and val_key:
            periods.append({
                "period": str(r[period_key]),
                "value": float(r[val_key]),
            })

    if len(periods) < 2:
        return {"error": "Could not identify period and metric columns for MoM growth."}

    growth_series = []
    for i in range(1, len(periods)):
        prev_val = periods[i - 1]["value"]
        curr_val = periods[i]["value"]
        growth_pct = round(((curr_val - prev_val) / prev_val * 100), 2) if prev_val > 0 else 0.0
        growth_series.append({
            "period": periods[i]["period"],
            "current_value": curr_val,
            "previous_value": prev_val,
            "growth_pct": growth_pct,
        })

    avg_growth = round(statistics.mean([g["growth_pct"] for g in growth_series]), 2) if growth_series else 0.0

    return {
        "growth_series": growth_series,
        "average_mom_growth_pct": avg_growth,
        "latest_growth_pct": growth_series[-1]["growth_pct"] if growth_series else 0.0,
    }


def calculate_churn_rate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates customer churn rate and active segment proportions."""
    if not rows:
        return {"error": "No rows provided for churn calculation."}

    total_customers = len(rows)
    churned = 0
    active = 0

    for r in rows:
        status = str(r.get("status") or r.get("customer_segment") or "").lower()
        if any(w in status for w in ["churn", "inactive", "lapsed", "cancelled"]):
            churned += 1
        elif any(w in status for w in ["active", "vip", "regular", "completed"]):
            active += 1

    # If status columns not found, check for last order date
    if churned == 0 and active == 0:
        churn_rate = 0.0
    else:
        churn_rate = round((churned / total_customers * 100), 2) if total_customers > 0 else 0.0

    return {
        "total_customers": total_customers,
        "churned_customers": churned,
        "active_customers": active,
        "churn_rate_pct": churn_rate,
    }


def calculate_inventory_burn_rate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates stock run-rate and estimated days of inventory remaining."""
    if not rows:
        return {"error": "No inventory rows provided."}

    sku_analysis = []
    for r in rows:
        sku = r.get("product_name") or r.get("sku") or r.get("name") or "Item"
        stock = float(r.get("stock_quantity") or r.get("quantity") or r.get("units_in_stock") or 0.0)
        daily_velocity = float(r.get("daily_sales") or r.get("units_sold_daily") or r.get("velocity") or 1.0)

        days_remaining = round(stock / daily_velocity, 1) if daily_velocity > 0 else 999.0
        sku_analysis.append({
            "item": str(sku),
            "current_stock": stock,
            "daily_velocity": daily_velocity,
            "days_remaining": days_remaining,
            "status": "CRITICAL" if days_remaining < 7 else ("LOW" if days_remaining < 15 else "HEALTHY"),
        })

    return {
        "sku_analysis": sku_analysis[:10],
        "critical_skus_count": sum(1 for item in sku_analysis if item["status"] == "CRITICAL"),
    }


def execute_python_stats(
    metric_name: str,
    data_rows: List[Dict[str, Any]],
    custom_script: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes sandboxed Python calculations on structured data rows.
    Supports prebuilt business metrics: 'profit_margin', 'mom_growth', 'churn_rate', 'inventory_burn_rate'.
    """
    norm_metric = metric_name.lower().strip()

    if norm_metric in ["profit_margin", "profit", "margin"]:
        return calculate_profit_margins(data_rows)
    elif norm_metric in ["mom_growth", "growth", "trend"]:
        return calculate_mom_growth(data_rows)
    elif norm_metric in ["churn_rate", "churn"]:
        return calculate_churn_rate(data_rows)
    elif norm_metric in ["inventory_burn_rate", "burn_rate", "inventory"]:
        return calculate_inventory_burn_rate(data_rows)
    elif custom_script:
        # Sandboxed execution
        try:
            local_scope = {"data": data_rows, "result": {}}
            exec(custom_script, SAFE_GLOBALS, local_scope)
            return local_scope.get("result", {})
        except Exception as e:
            logger.error(f"Custom sandboxed Python execution error: {e}")
            return {"error": f"Python script execution failed: {str(e)}"}
    else:
        return {"error": f"Unsupported metric calculation: '{metric_name}'"}
