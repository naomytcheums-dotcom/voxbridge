"""Draft order store.

Orders are created as drafts requiring human confirmation before dispatch —
the agent can promise nothing on its own, matching the review-before-send
pattern used by the other agents in this portfolio.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

_id_counter = itertools.count(1)
_orders: dict[int, "Order"] = {}


@dataclass
class Order:
    id: int
    product_id: str
    quantity: int
    customer_name: str
    customer_phone: str
    status: str = "pending_review"


def create_draft_order(product_id: str, quantity: int, customer_name: str, customer_phone: str) -> Order:
    order = Order(
        id=next(_id_counter),
        product_id=product_id,
        quantity=quantity,
        customer_name=customer_name,
        customer_phone=customer_phone,
    )
    _orders[order.id] = order
    return order


def get_order(order_id: int) -> Order | None:
    return _orders.get(order_id)
