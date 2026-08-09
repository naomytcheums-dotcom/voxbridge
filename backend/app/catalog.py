"""In-memory product catalog.

This is a JSON file for demo purposes. Swap `load_catalog()` for a real
database or vector search and every caller in this module keeps working —
that boundary is deliberate.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_CATALOG_PATH = Path(__file__).resolve().parent / "data" / "products.json"


@lru_cache
def load_catalog() -> list[dict]:
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def search_products(query: str = "", color: str | None = None, max_price: float | None = None) -> list[dict]:
    query_lower = query.lower().strip()
    results = []
    for product in load_catalog():
        if query_lower and query_lower not in product["name"].lower() and query_lower not in product["category"].lower():
            continue
        if color and color.strip().lower() != product["color"].lower():
            continue
        if max_price is not None and product["price"] > max_price:
            continue
        results.append(product)
    return results


def get_product(product_id: str) -> dict | None:
    return next((p for p in load_catalog() if p["id"] == product_id), None)
