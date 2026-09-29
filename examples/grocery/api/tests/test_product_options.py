# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""Plain grocery listings over HTTP: listings, the detail route, and the add button."""

import pytest

from demo_common.tests.fixtures import session_record
from grocery.api import main


@pytest.fixture
def add(client, shopper):
    """Returns ``add(product_id, *seen) -> (response, session record)``."""

    def _add(product_id: str, *seen: str):
        headers = shopper(*seen)
        body = {"product_id": product_id, "quantity": 1}
        return client.post("/api/cart/add", json=body, headers=headers), session_record(
            main, headers
        )

    return _add


def test_listings_are_plain_products_without_option_families(client):
    products = client.get("/api/products?category=pantry").json()["products"]
    assert products
    assert all(not product.get("options") for product in products)
    assert all("variants" not in product for product in products)


def test_the_detail_route_resolves_a_plain_product(client):
    product = client.get("/api/products/RB-1501").json()
    assert product["product_id"] == "RB-1501"
    assert not product.get("variants")
    assert product["price_intelligence"] and product["review_aspects"]


def test_the_add_button_requires_the_product_to_be_seen(add):
    response, record = add("RB-1501")
    assert response.status_code == 400
    assert "not in this session's results" in response.json()["detail"]
    assert record.pending_app_events == []


def test_the_add_button_on_a_seen_product_writes_a_line(add):
    response, record = add("RB-1501", "RB-1501")
    assert response.status_code == 200
    [line] = response.json()["cart"]["items"]
    assert line["product_id"] == "RB-1501"
    assert not line.get("option_values") and line.get("variant_of") is None
    assert "RB-1501" in record.pending_app_events[0]


def test_an_unavailable_seen_product_is_refused(add):
    response, record = add("RB-1008", "RB-1008")
    assert response.status_code == 400
    assert "RB-1008 is out of stock" in response.json()["detail"]
    assert record.pending_app_events == []
