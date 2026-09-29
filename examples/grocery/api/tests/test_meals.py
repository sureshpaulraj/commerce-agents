# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""``present_meal_plan``: grocery meal arithmetic the deployment owns."""

import pytest

from commerce_common.presentation import enrich_partial, partial_ui_tool_names
from grocery.api.meals import build_meal_plan_extension

EXTENSION = build_meal_plan_extension()
TOOL = "present_meal_plan"


@pytest.fixture
def remember(backend, state):
    """Returns ``remember(*ids)`` for products that the session has seen."""

    def _remember(*product_ids: str) -> None:
        products = []
        for product_id in product_ids:
            product = backend.product(product_id)
            assert product is not None, product_id
            products.append(product)
        state.remember_products(products)

    return _remember


async def card(executor, **payload) -> dict:
    """The payload the turn would stream, or an assertion failure naming the refusal."""
    result = await executor.execute(TOOL, payload)
    assert not result.is_error, result.result_text
    return next(event for event in result.events if event.type == "ui").data["payload"]


async def refusal(executor, **payload) -> str:
    """The text the model is handed when the plan is refused."""
    result = await executor.execute(TOOL, payload)
    assert result.is_error, result.events
    assert not [event for event in result.events if event.type == "ui"]
    return result.result_text


def meal(product_id: str, quantity: float, unit: str | None = None) -> dict:
    row: dict = {"product_id": product_id, "quantity_per_serving": quantity}
    if unit is not None:
        row["unit"] = unit
    return row


def line_by_id(rows: list[dict], product_id: str) -> dict:
    return next(row for row in rows if row["product"]["product_id"] == product_id)


# -- the arithmetic --------------------------------------------------------------------


async def test_meal_plan_quantities_basket_totals_rewards_and_budget(executor, remember):
    remember("RB-1501", "RB-1516", "RB-1504")
    payload = await card(
        executor,
        title="Two simple dinners",
        servings=4,
        budget=10,
        meals=[
            {
                "name": "Pasta night",
                "items": [meal("RB-1501", 3, "oz"), meal("RB-1516", 3, "oz")],
            },
            {
                "name": "Rice bowls",
                "items": [meal("RB-1501", 2, "oz"), meal("RB-1504", 0.25, "lb")],
            },
        ],
    )

    first_pasta = line_by_id(payload["meals"][0]["items"], "RB-1501")
    assert first_pasta["total_needed"] == 12.0
    assert first_pasta["packs"] == 1
    assert first_pasta["line_cost"] == 1.79

    second_pasta = line_by_id(payload["meals"][1]["items"], "RB-1501")
    assert second_pasta["total_needed"] == 8.0
    assert second_pasta["packs"] == 1
    assert second_pasta["line_cost"] == 1.79

    basket = {row["product"]["product_id"]: row for row in payload["basket"]}
    assert set(basket) == {"RB-1501", "RB-1516", "RB-1504"}
    assert basket["RB-1501"]["total_needed"] == 20.0
    assert basket["RB-1501"]["packs"] == 2
    assert basket["RB-1501"]["line_cost"] == 3.58

    assert payload["subtotal"] == sum(row["line_cost"] for row in payload["basket"]) == 8.36
    assert payload["cost_per_serving"] == 1.04
    assert payload["rewards_points"] == 83
    assert payload["fuel_cents_per_gal"] == 0
    assert payload["budget"] == 10
    assert payload["budget_headroom"] == 1.64
    assert payload["over_budget"] is False
    assert payload["computed_by"] == "server"


async def test_rewards_fuel_cap_budget_overage_and_age_restriction(executor, remember):
    remember("RB-1612")
    payload = await card(
        executor,
        title="Tailgate drinks",
        servings=60,
        budget=100,
        meals=[{"name": "Beverages", "items": [meal("RB-1612", 2, "ct")]}],
    )
    [row] = payload["basket"]
    assert row["packs"] == 20
    assert row["line_cost"] == 199.8
    assert payload["subtotal"] == 199.8
    assert payload["rewards_points"] == 1998
    assert payload["fuel_cents_per_gal"] == 100
    assert payload["budget_headroom"] == -99.8
    assert payload["over_budget"] is True
    assert payload["age_restricted_present"] is True


# -- allergen and provenance gates -----------------------------------------------------


async def test_unverified_allergen_statement_is_refused(executor, backend, remember):
    unverified = [
        product
        for product in backend.products.values()
        if product.attributes.get("allergen_status") != "verified"
    ]
    assert len(unverified) == 10
    product = unverified[0]
    remember(product.product_id)

    text = await refusal(
        executor,
        title="Dinner",
        servings=2,
        meals=[{"name": "Meal", "items": [meal(product.product_id, 1)]}],
    )
    assert "no verified allergen statement" in text


async def test_declared_allergen_is_refused(executor, remember):
    remember("RB-1521")
    text = await refusal(
        executor,
        title="Snack",
        servings=2,
        avoid_allergens=["peanuts"],
        meals=[{"name": "Snack", "items": [meal("RB-1521", 1, "oz")]}],
    )
    assert "contains peanuts" in text


async def test_shared_equipment_allergen_is_refused(executor, remember):
    remember("RB-1216")
    text = await refusal(
        executor,
        title="Breakfast",
        servings=2,
        avoid_allergens=["tree nuts"],
        meals=[{"name": "Breakfast", "items": [meal("RB-1216", 1, "cup")]}],
    )
    assert "equipment" in text and "tree nuts" in text


async def test_unknown_allergen_name_is_refused(executor, remember):
    remember("RB-1501")
    text = await refusal(
        executor,
        title="Dinner",
        servings=2,
        avoid_allergens=["mustard"],
        meals=[{"name": "Dinner", "items": [meal("RB-1501", 2, "oz")]}],
    )
    assert "not an allergen the catalog declares" in text


async def test_unseen_product_id_is_refused(executor):
    text = await refusal(
        executor,
        title="Dinner",
        servings=2,
        meals=[{"name": "Dinner", "items": [meal("RB-1501", 2, "oz")]}],
    )
    assert "not a product from this session" in text


@pytest.mark.parametrize(
    ("field", "value"),
    [("servings", 61), ("budget", 4.99), ("budget", 2000.01)],
)
async def test_bounds_are_refused(executor, remember, field, value):
    remember("RB-1501")
    payload = {
        "title": "Dinner",
        "servings": 2,
        "budget": 25,
        "meals": [{"name": "Dinner", "items": [meal("RB-1501", 2, "oz")]}],
        field: value,
    }
    assert "outside the range" in await refusal(executor, **payload)


# -- units -----------------------------------------------------------------------------


async def test_unit_conversion_across_weight_volume_and_count_families(executor, remember):
    remember("RB-1504", "RB-1201", "RB-1204")
    payload = await card(
        executor,
        title="Breakfast prep",
        servings=4,
        meals=[
            {
                "name": "Prep",
                "items": [
                    meal("RB-1504", 8, "oz"),
                    meal("RB-1201", 1, "cup"),
                    meal("RB-1204", 1, "each"),
                ],
            }
        ],
    )
    lines = {row["product"]["product_id"]: row for row in payload["meals"][0]["items"]}
    assert lines["RB-1504"]["total_needed"] == 2.0
    assert lines["RB-1504"]["total_unit"] == "lb"
    assert lines["RB-1201"]["total_needed"] == 32.0
    assert lines["RB-1201"]["total_unit"] == "fl oz"
    assert lines["RB-1204"]["total_needed"] == 4.0
    assert lines["RB-1204"]["total_unit"] == "ct"
    assert all(line["packs"] == 1 for line in lines.values())


async def test_cross_family_unit_conversion_is_refused(executor, remember):
    remember("RB-1504")
    text = await refusal(
        executor,
        title="Rice bowls",
        servings=4,
        meals=[{"name": "Rice", "items": [meal("RB-1504", 1, "cup")]}],
    )
    assert "cannot be filled" in text


# -- the streamed prefix ---------------------------------------------------------------


def _has_number(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int | float):
        return True
    if isinstance(value, dict):
        return any(_has_number(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_number(item) for item in value)
    return False


async def test_the_streamed_prefix_shows_only_meals_and_products_without_numbers(remember, state):
    remember("RB-1501")

    assert TOOL in partial_ui_tool_names({}, [EXTENSION])
    streamed = enrich_partial(
        EXTENSION,
        {
            "title": "Pasta week",
            "servings": 4,
            "budget": 25,
            "meals": [
                {
                    "name": "Dinner",
                    "items": [{"product_id": "RB-1501", "quantity_per_serving": 99}],
                }
            ],
        },
        state,
    )
    assert streamed is not None
    component, payload, _signature = streamed
    assert component == "meal_plan"
    assert set(payload) == {"title", "pending", "meals"}
    assert payload["pending"] is True
    assert set(payload["meals"][0]) == {"name", "products"}
    assert [p["product_id"] for p in payload["meals"][0]["products"]] == ["RB-1501"]
    assert not _has_number(payload)


async def test_the_streamed_prefix_is_held_back_until_a_product_resolves(state):
    assert enrich_partial(EXTENSION, {"title": "Dinner"}, state) is None
    assert (
        enrich_partial(
            EXTENSION,
            {"meals": [{"name": "Dinner", "items": [{"product_id": "RB-9999"}]}]},
            state,
        )
        is None
    )
