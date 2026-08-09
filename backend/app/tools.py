"""Tools the voice agent can call mid-conversation, plus the dispatcher
that executes them.

Defined once in a provider-neutral shape (name, description, JSON-schema
parameters); each LLM provider adapts this into its own function-calling
wire format — see `_to_openai_tool` / `_to_anthropic_tool` in `llm.py`.
"""
from __future__ import annotations

from typing import Any

from . import catalog, orders

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_products",
        "description": (
            "Search the store catalog by keyword, color, and/or maximum price. "
            "Use this whenever the caller mentions a product, even vaguely."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text term, e.g. product name or category"},
                "color": {"type": "string", "description": "Filter by color, if the caller mentioned one"},
                "max_price": {"type": "number", "description": "Filter by maximum price, if the caller mentioned a budget"},
            },
            "required": [],
        },
    },
    {
        "name": "check_stock",
        "description": "Check exact remaining stock for one specific product by its id.",
        "parameters": {
            "type": "object",
            "properties": {"product_id": {"type": "string"}},
            "required": ["product_id"],
        },
    },
    {
        "name": "start_order",
        "description": (
            "Create a draft order once the caller has confirmed the product and quantity "
            "they want, and given their name and phone number. This does NOT charge or ship "
            "anything — it creates a pending order that a human confirms afterwards."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "quantity": {"type": "integer"},
                "customer_name": {"type": "string"},
                "customer_phone": {"type": "string"},
            },
            "required": ["product_id", "quantity", "customer_name", "customer_phone"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Use this if the caller is frustrated, asks for something outside the catalog, or explicitly asks for a human.",
        "parameters": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
]


def dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "search_products":
        results = catalog.search_products(
            query=arguments.get("query", ""),
            color=arguments.get("color"),
            max_price=arguments.get("max_price"),
        )
        return {"results": results}

    if name == "check_stock":
        product = catalog.get_product(arguments["product_id"])
        if not product:
            return {"error": "unknown product_id"}
        return {"product_id": product["id"], "stock": product["stock"]}

    if name == "start_order":
        order = orders.create_draft_order(
            product_id=arguments["product_id"],
            quantity=arguments["quantity"],
            customer_name=arguments["customer_name"],
            customer_phone=arguments["customer_phone"],
        )
        return {"order_id": order.id, "status": order.status}

    if name == "escalate_to_human":
        return {"escalated": True, "reason": arguments.get("reason", "")}

    return {"error": f"unknown tool '{name}'"}
