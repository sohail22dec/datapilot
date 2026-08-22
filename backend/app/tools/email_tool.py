import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def draft_email_action(
    campaign_type: str,
    recipient_count: int,
    sample_recipients: List[Dict[str, Any]],
    context_data: Optional[Dict[str, Any]] = None,
    custom_subject: Optional[str] = None,
    custom_body: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generates a structured email/campaign action draft with Human-in-the-Loop approval required.
    Does NOT send real emails — produces a validated draft payload for user review.
    """
    c_type = campaign_type.lower().strip()
    context_data = context_data or {}
    discount_code = context_data.get("discount_code", "COMEBACK15")
    discount_pct = context_data.get("discount_pct", "15%")

    # Format sample recipient names
    recipient_previews = []
    for r in sample_recipients[:5]:
        name = r.get("customer_name") or f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or r.get("name") or "Valued Customer"
        email = r.get("email") or "customer@example.com"
        spend = r.get("total_spend") or r.get("total_amount") or 0.0
        recipient_previews.append({
            "name": name,
            "email": email,
            "metric": f"Total Spend: ₹{spend:,.2f}" if spend else None,
        })

    if "winback" in c_type or "churn" in c_type or "vip" in c_type:
        subject = custom_subject or f"We miss you! Here is an exclusive {discount_pct} offer just for you"
        body_template = custom_body or (
            "Hi {{name}},\n\n"
            f"We noticed it's been a while since your last order with us. As one of our valued customers, "
            f"we'd love to welcome you back with an exclusive **{discount_pct} discount** on your next purchase.\n\n"
            f"Use code **{discount_code}** at checkout: https://yourstore.com\n\n"
            "Best regards,\nThe DataPilot Team"
        )
        action_title = "VIP Customer Win-Back Campaign"

    elif "restock" in c_type or "supplier" in c_type or "po" in c_type:
        sku_list = context_data.get("sku_list", "Low-stock inventory items")
        subject = custom_subject or "Purchase Order Request - Urgent Stock Replenishment"
        body_template = custom_body or (
            "Hi Supplier Team,\n\n"
            f"Please accept this purchase order request to replenish the following critical SKUs:\n"
            f"- {sku_list}\n\n"
            "Please confirm estimated dispatch timelines and invoice totals at your earliest convenience.\n\n"
            "Best regards,\nOperations & Supply Chain"
        )
        action_title = "Supplier Purchase Order Reorder"

    elif "payment" in c_type or "failed" in c_type:
        subject = custom_subject or "Action Required: Update your payment method for order"
        body_template = custom_body or (
            "Hi {{name}},\n\n"
            "We were unable to process payment for your recent order. Please update your payment details "
            "to avoid any delays in shipping.\n\n"
            "Update payment link: https://yourstore.com/checkout/retry\n\n"
            "Thank you,\nCustomer Support"
        )
        action_title = "Payment Failure Follow-up Notification"

    else:
        subject = custom_subject or "Special Announcement from Our Store"
        body_template = custom_body or (
            "Hi {{name}},\n\n"
            "Thank you for being a valued customer. Check out our latest products and deals!\n\n"
            "Visit: https://yourstore.com\n\n"
            "Warm regards,\nThe Team"
        )
        action_title = "General Customer Announcement"

    return {
        "status": "draft_created",
        "action_title": action_title,
        "campaign_type": c_type,
        "subject": subject,
        "body_template": body_template,
        "total_target_recipients": recipient_count or len(sample_recipients),
        "sample_recipients": recipient_previews,
        "requires_human_approval": True,
        "is_approved": False,
    }
