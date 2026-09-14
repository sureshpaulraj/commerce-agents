# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""Products with options over HTTP: listings, the detail route, and the add button."""

import pytest

from agronomy.api import main
from demo_common.tests.fixtures import session_record


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


def test_listings_carry_the_family_and_none_of_its_variants(client):
    products = client.get("/api/products?category=safety-ppe").json()["products"]
    ids = {product["product_id"] for product in products}
    assert "HA-2202" in ids and not {pid for pid in ids if pid.startswith("HA-2202-")}
    family = next(product for product in products if product["product_id"] == "HA-2202")
    assert family["options"] == {"size": ["M", "L", "XL", "2XL"]}
    assert "variants" not in family


def test_the_detail_route_resolves_a_family_and_a_variant(client):
    family = client.get("/api/products/HA-2202").json()
    assert [v["product_id"] for v in family["variants"]] == [
        "HA-2202-M",
        "HA-2202-L",
        "HA-2202-XL",
        "HA-2202-2XL",
    ]
    assert family["variants"][3]["in_stock"] is False
    variant = client.get("/api/products/HA-2202-2XL").json()
    assert variant["variant_of"] == "HA-2202" and variant["price"] == 30.0
    assert variant["price_intelligence"] and variant["review_aspects"]


def test_the_add_button_on_a_family_is_held_with_the_route_to_a_variant(add):
    response, record = add("HA-2202", "HA-2202")
    assert response.status_code == 400
    assert "options" in response.json()["detail"]
    assert record.pending_app_events == []


def test_the_add_button_on_a_seen_variant_writes_a_line_with_its_choice(add):
    response, record = add("HA-2202-XL", "HA-2202", "HA-2202-XL")
    assert response.status_code == 200
    [line] = response.json()["cart"]["items"]
    assert line["product_id"] == "HA-2202-XL"
    assert line["option_values"] == {"size": "XL"} and line["variant_of"] == "HA-2202"
    assert "HA-2202-XL" in record.pending_app_events[0]


def test_a_sold_out_variant_is_refused_with_its_in_stock_siblings_named(add):
    response, record = add("HA-2202-2XL", "HA-2202", "HA-2202-2XL")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "HA-2202-2XL is out of stock" in detail and "HA-2202-XL" in detail
    assert record.pending_app_events == []
