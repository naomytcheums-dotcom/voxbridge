from app.catalog import get_product, search_products


def test_search_by_keyword_matches_category():
    results = search_products(query="bag")
    assert len(results) == 4
    assert all(p["category"] == "bags" for p in results)


def test_search_by_color_filters_correctly():
    results = search_products(query="bag", color="red")
    assert {p["id"] for p in results} == {"bag-001", "bag-003"}


def test_search_by_max_price_excludes_expensive_items():
    results = search_products(query="bag", max_price=15000)
    ids = {p["id"] for p in results}
    assert "bag-001" not in ids  # 25000, over budget
    assert "bag-004" in ids  # 12000, within budget


def test_search_with_no_filters_returns_full_catalog():
    assert len(search_products()) == 8


def test_get_product_returns_none_for_unknown_id():
    assert get_product("does-not-exist") is None


def test_get_product_returns_matching_item():
    product = get_product("shoe-002")
    assert product["name"] == "Classic Sneakers"
    assert product["color"] == "black"
