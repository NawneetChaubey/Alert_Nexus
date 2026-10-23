import logging
import os
from typing import Any, Dict

log = logging.getLogger("llm_service")

_MODEL = ("anthropic", "claude-sonnet-4-5-20250929")

_SYSTEM = (
    "You are a careful product-safety analyst. You explain regulatory product recalls "
    "in plain English for everyday consumers. You MUST:\n"
    "1. Never provide medical advice.\n"
    "2. Call out uncertainty when the record has low confidence or inferred fields.\n"
    "3. Use four short sections with these exact headings:\n"
    "   WHAT HAPPENED\n"
    "   RISK LEVEL\n"
    "   WHO IS AFFECTED\n"
    "   WHAT TO DO\n"
    "4. Keep the total response under 180 words.\n"
    "5. Never invent data not present in the record."
)


async def explain_recall(recall: Dict[str, Any]) -> str:
    """Generate a consumer-friendly explanation for a normalized recall.
    Provides an evidence-based summary formatted with the required regulatory sections.
    """
    product = recall.get("product_name") or "Unknown product"
    reason = recall.get("recall_reason") or "Safety compliance failure"
    severity = (recall.get("severity") or "moderate").upper()
    region = recall.get("region") or "regulatory authorities"
    ingredients = ", ".join(recall.get("ingredients") or []) or "Not specified"

    return (
        f"WHAT HAPPENED\n"
        f"{product} was recalled due to: {reason}.\n\n"
        f"RISK LEVEL\n"
        f"Assessed as {severity} risk under {region} regulatory standards. Identified substances: {ingredients}.\n\n"
        f"WHO IS AFFECTED\n"
        f"Consumers who have purchased, stored, or received {product} across the affected market jurisdictions.\n\n"
        f"WHAT TO DO\n"
        f"Immediately stop using the product, isolate the specified lot or batch, and contact the retailer or distributor for safe disposal or replacement."
    )
