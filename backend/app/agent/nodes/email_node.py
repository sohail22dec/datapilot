from app.agent.state import AgentState
from app.tools.email_tool import draft_email_action


def email_node(state: AgentState) -> dict:
    """
    Action Engine Node:
    Drafts structured email, SMS, or supplier purchase order campaigns with
    Human-in-the-Loop (HITL) approval flags.
    """
    user_q = state.get("user_question", "").lower()
    rows = state.get("query_results") or []

    # Identify campaign intent type
    if any(k in user_q for k in ["winback", "churn", "vip", "inactive", "discount", "re-engage", "offer"]):
        campaign_type = "vip_winback"
        action_title = "VIP Re-engagement Campaign"
    elif any(k in user_q for k in ["restock", "supplier", "purchase order", "po", "order stock"]):
        campaign_type = "restock_po"
        action_title = "Supplier Purchase Order"
    elif any(k in user_q for k in ["payment", "failed", "card", "declined"]):
        campaign_type = "payment_reminder"
        action_title = "Payment Failure Follow-up"
    else:
        campaign_type = "general_announcement"
        action_title = "Customer Announcement"

    payload = draft_email_action(
        campaign_type=campaign_type,
        recipient_count=len(rows),
        sample_recipients=rows[:5],
        context_data={"discount_code": "PILOT20", "discount_pct": "20%"},
    )

    trace_msg = f"✉️ [Action Engine] Generated '{action_title}' draft payload for {payload['total_target_recipients']} recipients (Requires User Review & Approval)"

    return {
        "action_type": campaign_type,
        "action_payload": payload,
        "requires_human_approval": True,
        "is_approved": False,
        "agent_thought_trace": [trace_msg],
    }
