from app.orders import get_order
from app.tools import dispatch


def test_search_products_dispatch_matches_direct_call():
    result = dispatch("search_products", {"query": "sneakers", "color": "black"})
    assert result["results"][0]["id"] == "shoe-002"


def test_check_stock_known_product():
    result = dispatch("check_stock", {"product_id": "bag-003"})
    assert result == {"product_id": "bag-003", "stock": 0}


def test_check_stock_unknown_product_returns_error():
    result = dispatch("check_stock", {"product_id": "does-not-exist"})
    assert "error" in result


def test_start_order_creates_a_pending_draft_not_a_confirmed_sale():
    result = dispatch("start_order", {
        "product_id": "bag-001",
        "quantity": 2,
        "customer_name": "Test Caller",
        "customer_phone": "+237600000000",
    })
    assert result["status"] == "pending_review"

    order = get_order(result["order_id"])
    assert order.product_id == "bag-001"
    assert order.quantity == 2
    assert order.status == "pending_review"


def test_escalate_to_human_passes_through_reason():
    result = dispatch("escalate_to_human", {"reason": "angry caller"})
    assert result == {"escalated": True, "reason": "angry caller"}


def test_unknown_tool_name_returns_error_instead_of_raising():
    result = dispatch("not_a_real_tool", {})
    assert "error" in result
