# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime

from agronomy.api.mock_agronomy import (
    DATA_DIR,
    FREE_SHIPPING_OVER,
    FREIGHT_SHIPPING,
    STANDARD_SHIPPING,
    MockAgronomy,
)
from commerce_common.types import MemoryCategory, MemoryFact
from demo_common.storefront_fixtures import load_json
from shopping_agent import SearchFilters


def test_catalog_loads_and_validates(backend):
    assert len(backend.products) >= 25
    assert backend.store_name == "Heartland Agronomy Supply"
    sample = backend.products["HA-1001"]
    assert sample.brand == "Heartland Crop Protection"
    assert sample.long_description  # hero products carry a long description


def test_every_chemical_product_states_a_machine_readable_label_rate(backend):
    """The application-plan calculator reads these, so a missing one is a fixture bug."""
    rated = {"herbicides", "fungicides", "insecticides", "adjuvants", "micronutrients"}
    for product in backend.products.values():
        if product.category not in rated:
            continue
        attributes = product.attributes
        assert attributes.get("rate_unit"), product.product_id
        low, high = float(attributes["rate_min"]), float(attributes["rate_max"])
        assert 0 < low <= high, product.product_id
        assert float(attributes["units_per_package"]) > 0, product.product_id
        assert attributes["package_unit"], product.product_id


async def test_search_relevance(backend, session):
    residual = await backend.search_products(session, "corn preemergence residual for waterhemp")
    assert residual and residual[0].product_id in {"HA-1001", "HA-1002"}

    fungicide = await backend.search_products(session, "tar spot fungicide for corn")
    assert fungicide and fungicide[0].product_id in {"HA-1203", "HA-1201"}

    gloves = await backend.search_products(session, "chemical resistant gloves")
    assert any(p.product_id == "HA-2202" for p in gloves[:3])

    nothing = await backend.search_products(session, "zzzqqq")
    assert nothing == []


async def test_out_of_stock_items_are_searchable(backend, session):
    hits = await backend.search_products(session, "tar spot fungicide")
    assert any(p.product_id == "HA-1203" and p.in_stock is False for p in hits)


async def test_delivery_promises_stamped(backend):
    for product in backend.products.values():
        promise = product.attributes.get("delivery")
        if product.in_stock:
            assert promise is not None and promise.startswith("Get it by ")
        else:
            assert promise is None

    # The promise is kept out of search scoring.
    sample = next(p for p in backend.products.values() if p.in_stock)
    assert "Get it by" not in backend._searchable_text(sample)["attributes"]


def test_memory_seed_is_schema_valid():
    seed = load_json(DATA_DIR, "memory-seed.json")
    assert "demo-user" in seed
    for facts in seed.values():
        for raw in facts:
            fact = MemoryFact(
                key=raw["key"], value=raw["value"], category=MemoryCategory(raw["category"])
            )
            assert fact.key and fact.value


async def test_search_filters_and_sort(backend, session):
    cheap = await backend.search_products(session, "fungicide", SearchFilters(max_price=300))
    assert all(p.price <= 300 for p in cheap)
    assert all(p.product_id != "HA-1203" for p in cheap)

    adjuvants_only = await backend.search_products(
        session, "surfactant oil conditioner", SearchFilters(category="adjuvants"), limit=20
    )
    assert adjuvants_only and all(p.category == "adjuvants" for p in adjuvants_only)

    by_price = await backend.search_products(
        session, "herbicide", SearchFilters(sort="price_asc"), limit=20
    )
    prices = [p.price for p in by_price]
    assert prices == sorted(prices)


async def test_policy_search(backend, session):
    returns = await backend.search_policies(session, "how do returns and refunds work")
    assert returns and returns[0].policy_id == "returns"

    restricted = await backend.search_policies(
        session, "restricted use applicator licence requirement"
    )
    assert any(p.policy_id == "restricted-use" for p in restricted)


async def test_fulfillment_options_follow_the_delivery_policy(backend, session):
    options = await backend.get_fulfillment_options(session, ["HA-1601"])
    assert [o.method for o in options] == ["delivery", "delivery", "pickup"]
    standard, express, pickup = options
    assert backend.products["HA-1601"].price < FREE_SHIPPING_OVER
    assert standard.fee == STANDARD_SHIPPING.fee
    assert pickup.location.startswith("Heartland ")

    (free, *_rest) = await backend.get_fulfillment_options(session, ["HA-1201", "HA-1202"])
    assert (
        backend.products["HA-1201"].price + backend.products["HA-1202"].price > FREE_SHIPPING_OVER
    )
    assert free.fee == 0.0

    freight = await backend.get_fulfillment_options(session, ["HA-1201"])
    assert freight[-1] == FREIGHT_SHIPPING

    delivery = next(p for p in backend._policies if p.policy_id == "delivery").content
    for term in (
        f"free over ${FREE_SHIPPING_OVER}",
        "two to four business days",
        "five business days",
        "freight",
        "Pickup at the Heartland branch",
    ):
        assert term in delivery, term


def test_pickup_eta_stays_inside_branch_hours():
    eta = MockAgronomy._pickup_eta
    # Two hours of picking, rounded up to the hour.
    assert eta(datetime(2026, 9, 14, 13, 0)) == "today by 3 PM"
    assert eta(datetime(2026, 9, 14, 13, 20)) == "today by 4 PM"
    # Before opening, the two hours count from the 7 AM open.
    assert eta(datetime(2026, 9, 14, 5, 30)) == "today by 9 AM"
    # 16:00 plus two hours lands on the 6 PM close.
    assert eta(datetime(2026, 9, 14, 16, 0)) == "today by 6 PM"
    assert eta(datetime(2026, 9, 14, 16, 30)) == "tomorrow morning"
    assert eta(datetime(2026, 9, 14, 23, 0)) == "tomorrow morning"


async def test_a_family_is_found_by_its_option_values_and_its_variants_stay_out_of_listings(
    backend, session
):
    assert "HA-2202" in backend.products and "HA-2202-L" not in backend.products
    assert backend.variants["HA-2202-L"].variant_of == "HA-2202"
    hits = await backend.search_products(session, "nitrile gloves")
    assert hits and hits[0].product_id == "HA-2202"
    assert hits[0].options == {"size": ["M", "L", "XL", "2XL"]}
    assert all(hit.variant_of is None for hit in hits)


async def test_details_resolve_a_family_and_a_variant(backend, session):
    family = await backend.get_product_details(session, "HA-2201")
    assert family is not None and set(family.options) == {"orifice"}
    assert len(family.variants) == 4
    assert all(set(v.option_values) == {"orifice"} for v in family.variants)
    variant = await backend.get_product_details(session, "ha-2201-05")
    assert variant is not None and variant.variant_of == "HA-2201"
    assert variant.in_stock is False and variant.price == 114.0
    assert backend.listing_of("HA-2201-05") is family


async def test_an_order_line_for_a_variant_names_its_choice(backend, session):
    orders = await backend.get_orders(session)
    lines = [item for order in orders for item in order.items if item.variant_of]
    assert [(i.product_id, i.option_values, i.variant_of) for i in lines] == [
        ("HA-2202-L", {"size": "L"}, "HA-2202")
    ]
