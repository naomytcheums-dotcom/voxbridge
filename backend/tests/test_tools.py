from app.call_log import CallLog
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


def test_start_order_creates_a_pending_draft_not_a_confirmed_sale(tmp_path):
    call_log = CallLog(str(tmp_path / "calls.db"))
    call_id = call_log.start_call("+237600000000")

    result = dispatch("start_order", {
        "product_id": "bag-001",
        "quantity": 2,
        "customer_name": "Test Caller",
        "customer_phone": "+237600000000",
    }, context={"call_log": call_log, "call_id": call_id})

    assert result["status"] == "pending_review"

    orders = call_log.list_orders()
    assert len(orders) == 1
    assert orders[0]["product_id"] == "bag-001"
    assert orders[0]["quantity"] == 2
    assert orders[0]["status"] == "pending_review"
    assert orders[0]["call_id"] == call_id


def test_escalate_to_human_passes_through_reason():
    result = dispatch("escalate_to_human", {"reason": "angry caller"})
    assert result == {"escalated": True, "reason": "angry caller"}


def test_unknown_tool_name_returns_error_instead_of_raising():
    result = dispatch("not_a_real_tool", {})
    assert "error" in result
