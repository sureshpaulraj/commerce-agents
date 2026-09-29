# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime

from commerce_common.types import MemoryCategory, MemoryFact
from demo_common.storefront_fixtures import load_json
from grocery.api.mock_grocery import (
    DATA_DIR,
    DELIVERY_FEE,
    EXPRESS_DELIVERY_FEE,
    FREE_DELIVERY_OVER,
    PARCEL_SHIPPING,
    PICKUP_MINIMUM,
    MockGrocery,
)
from shopping_agent import SearchFilters


def test_catalog_loads_and_validates(backend):
    assert len(backend.products) == 180
    assert backend.store_name == "Riverbend Market"
    sample = backend.products["RB-1001"]
    assert sample.brand == "Northfield Farms"
    assert sample.long_description


def test_every_product_states_pack_size_and_allergen_provenance(backend):
    """The meal-plan calculator reads these, so a missing value is a fixture bug."""
    for product in backend.products.values():
        attributes = product.attributes
        assert attributes.get("pack_size"), product.product_id
        assert float(attributes["unit_count"]) > 0, product.product_id
        assert attributes.get("unit_of_measure"), product.product_id
        assert attributes.get("allergen_status"), product.product_id
        if attributes.get("allergen_status") == "verified":
            assert attributes.get("allergen_source"), product.product_id


async def test_search_relevance_and_synonyms(backend, session):
    pasta = await backend.search_products(session, "pasta marinara tomato sauce")
    assert pasta and pasta[0].product_id == "RB-1516"

    shrimp = await backend.search_products(session, "seafood prawns")
    assert shrimp and shrimp[0].product_id == "RB-1113"

    milk = await backend.search_products(session, "dairy free vegan milk")
    assert milk and milk[0].product_id == "RB-1216"

    diapers = await backend.search_products(session, "size 3 diapers nappies")
    assert diapers and diapers[0].product_id == "RB-2001"

    nothing = await backend.search_products(session, "zzzqqq")
    assert nothing == []


async def test_out_of_stock_items_are_searchable(backend, session):
    hits = await backend.search_products(session, "baby spinach")
    assert any(p.product_id == "RB-1008" and p.in_stock is False for p in hits)


async def test_delivery_promises_stamped(backend):
    for product in backend.products.values():
        promise = product.attributes.get("delivery")
        if product.in_stock:
            assert promise is not None and promise.startswith("Ready by ")
        else:
            assert promise is None

    sample = next(p for p in backend.products.values() if p.in_stock)
    assert "Ready by" not in backend._searchable_text(sample)["attributes"]


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
    cheap = await backend.search_products(session, "milk", SearchFilters(max_price=3.50))
    assert cheap
    assert all(p.price <= 3.50 for p in cheap)
    assert all(p.product_id != "RB-1201" for p in cheap)

    pantry_only = await backend.search_products(
        session, "pasta sauce rice", SearchFilters(category="pantry"), limit=20
    )
    assert pantry_only and all(p.category == "pantry" for p in pantry_only)

    by_price = await backend.search_products(
        session, "pasta sauce", SearchFilters(sort="price_asc"), limit=20
    )
    prices = [p.price for p in by_price]
    assert prices == sorted(prices)


async def test_policy_search(backend, session):
    returns = await backend.search_policies(session, "how do returns and refunds work")
    assert returns and returns[0].policy_id == "returns-refunds"

    restricted = await backend.search_policies(session, "age restricted items id handoff")
    assert any(p.policy_id == "age-restricted-items" for p in restricted)


async def test_fulfillment_options_follow_the_delivery_policy(backend, session):
    options = await backend.get_fulfillment_options(session, ["RB-1501"])
    assert [o.method for o in options] == ["pickup", "delivery", "delivery", "shipping"]
    pickup, delivery, express, parcel = options
    assert backend.products["RB-1501"].price < FREE_DELIVERY_OVER
    assert pickup.fee == 0.0
    assert pickup.location.startswith("Riverbend Market ")
    assert delivery.fee == DELIVERY_FEE
    assert express.fee == EXPRESS_DELIVERY_FEE
    assert parcel == PARCEL_SHIPPING

    free, *_rest = await backend.get_fulfillment_options(
        session, ["RB-2003", "RB-1907", "RB-1613", "RB-1612", "RB-2210", "RB-1111"]
    )
    assert free.method == "pickup"
    delivery = _rest[0]
    assert (
        sum(
            backend.products[pid].price
            for pid in ["RB-2003", "RB-1907", "RB-1613", "RB-1612", "RB-2210", "RB-1111"]
        )
        > FREE_DELIVERY_OVER
    )
    assert delivery.fee == 0.0

    no_parcel = await backend.get_fulfillment_options(session, ["RB-1111"])
    assert PARCEL_SHIPPING not in no_parcel

    delivery_policy = next(
        p for p in backend._policies if p.policy_id == "pickup-delivery-windows-fees"
    ).content
    for term in (
        f"${PICKUP_MINIMUM} or more",
        f"${DELIVERY_FEE:.2f} delivery fee",
        f"${PICKUP_MINIMUM} order minimum",
        f"${EXPRESS_DELIVERY_FEE:.2f} express delivery fee",
        "Curbside pickup",
        "two-hour blocks",
    ):
        assert term in delivery_policy, term


def test_pickup_eta_stays_inside_store_hours():
    eta = MockGrocery._pickup_eta
    assert eta(datetime(2026, 9, 14, 13, 0)) == "ready today by 3 PM"
    assert eta(datetime(2026, 9, 14, 13, 20)) == "ready today by 4 PM"
    assert eta(datetime(2026, 9, 14, 5, 30)) == "ready today by 9 AM"
    assert eta(datetime(2026, 9, 14, 19, 0)) == "ready today by 9 PM"
    assert eta(datetime(2026, 9, 14, 19, 30)) == "ready tomorrow from 7 AM"
    assert eta(datetime(2026, 9, 14, 23, 0)) == "ready tomorrow from 7 AM"


async def test_details_resolve_plain_products(backend, session):
    product = await backend.get_product_details(session, "rb-1501")
    assert product is not None
    assert product.product_id == "RB-1501"
    assert product.variants == []
    assert backend.listing_of("RB-1501") is product


async def test_cart_lines_belong_to_the_session(backend, session, other_session):
    await backend.add_to_cart(session, "RB-1501", 1)
    assert (await backend.add_to_cart(session, "RB-1501", 2)).item_count == 3
    assert (await backend.get_cart(other_session)).item_count == 0
    assert (await backend.update_cart_item(session, "RB-1501", 1)).item_count == 1
    assert (await backend.remove_from_cart(session, "RB-1501")).items == []


async def test_orders_are_newest_first_and_case_insensitive(backend, session, other_session):
    orders = await backend.get_orders(session)
    assert orders and [order.placed_at for order in orders] == sorted(
        (order.placed_at for order in orders), reverse=True
    )
    found = await backend.get_order(session, orders[0].order_id.lower())
    assert found is not None and found.order_id == orders[0].order_id
    assert await backend.get_order(other_session, orders[0].order_id) is None
