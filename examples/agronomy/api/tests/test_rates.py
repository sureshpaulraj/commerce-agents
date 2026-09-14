# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""``present_application_plan``: the arithmetic the deployment owns rather than the model.

Each test states a number the card must show, or a refusal the model must be handed
instead of a number. The tool runs through the deployment's own executor, so what these
tests read is what a turn would put on screen.
"""

import pytest

from agronomy.api.rates import build_application_plan_extension

EXTENSION = build_application_plan_extension()
TOOL = "present_application_plan"
# The searches a turn would make before it plans anything, which is what puts the
# products into the session's provenance.
PRIMING_QUERIES = (
    "corn preemergence residual herbicide",
    "adjuvant surfactant water conditioner",
    "seed treatment",
    "insecticide",
    "nitrile gloves",
)


@pytest.fixture
async def primed(executor):
    """The executor with the products these tests plan with in the session's provenance."""
    for query in PRIMING_QUERIES:
        await executor.execute("search_products", {"query": query, "limit": 25})
    return executor


async def card(primed, **payload) -> dict:
    """The payload the turn would stream, or an assertion failure naming the refusal."""
    result = await primed.execute(TOOL, payload)
    assert not result.is_error, result.result_text
    return next(event for event in result.events if event.type == "ui").data["payload"]


async def refusal(primed, **payload) -> str:
    """The text the model is handed when the plan is refused."""
    result = await primed.execute(TOOL, payload)
    assert result.is_error, result.events
    assert not [event for event in result.events if event.type == "ui"]  # nothing rendered
    return result.result_text


# -- the arithmetic --------------------------------------------------------------------


async def test_a_per_acre_rate_becomes_product_containers_and_cost(primed):
    payload = await card(
        primed,
        title="Corn preemergence, north half",
        acres=640,
        carrier_gpa=15,
        tank_capacity_gal=1200,
        rows=[{"product_id": "HA-1001", "rate_per_acre": 1.6}],
    )
    [row] = payload["rows"]
    assert row["total_amount"] == 1024.0 and row["total_unit"] == "pt"  # 1.6 pt x 640 ac
    # A 2.5 gal jug holds 20 pt, so 51.2 jugs rounds up to a whole 52.
    assert row["containers"] == 52
    assert row["line_cost"] == round(52 * 289.0, 2)
    assert payload["product_cost"] == row["line_cost"]
    assert payload["cost_per_acre"] == round(row["line_cost"] / 640, 2)
    assert payload["computed_by"] == "server"


async def test_carrier_volume_sets_the_tank_loads(primed):
    payload = await card(
        primed,
        title="Corn preemergence",
        acres=640,
        carrier_gpa=15,
        tank_capacity_gal=1200,
        rows=[{"product_id": "HA-1001", "rate_per_acre": 1.6}],
    )
    assert payload["total_carrier_gal"] == 9600.0  # 640 ac x 15 GPA
    assert payload["acres_per_load"] == 80.0  # 1200 gal / 15 GPA
    assert payload["tank_loads"] == 8  # 9600 gal / 1200 gal


async def test_the_defaults_are_used_when_the_model_omits_them(primed):
    payload = await card(
        primed,
        title="Corn preemergence",
        acres=100,
        rows=[{"product_id": "HA-1001", "rate_per_acre": 1.6}],
    )
    assert payload["carrier_gpa"] == 15.0 and payload["tank_capacity_gal"] == 1200.0


# -- the rate bases --------------------------------------------------------------------


async def test_a_rate_per_hundred_gallons_is_charged_against_the_carrier(primed):
    payload = await card(
        primed,
        title="Water conditioning",
        acres=640,
        carrier_gpa=15,
        rows=[{"product_id": "HA-1603", "rate_per_acre": 12}],
    )
    [row] = payload["rows"]
    # 12 lb per 100 gal over 9,600 gal of carrier, out of 50 lb bags.
    assert row["total_amount"] == 1152.0 and row["total_unit"] == "lb"
    assert row["containers"] == 24


async def test_a_percent_by_volume_rate_is_charged_against_the_finished_spray(primed):
    payload = await card(
        primed,
        title="Surfactant",
        acres=640,
        carrier_gpa=15,
        rows=[{"product_id": "HA-1601", "rate_per_acre": 0.25}],
    )
    [row] = payload["rows"]
    # 0.25% of 9,600 gal is 24 gal, which is 3,072 fl oz, out of 320 fl oz jugs.
    assert row["total_amount"] == 3072.0 and row["total_unit"] == "fl oz"
    assert row["containers"] == 10


async def test_a_rate_per_hundredweight_of_seed_states_why_it_has_no_volume(primed):
    payload = await card(
        primed,
        title="Seed treatment",
        acres=640,
        rows=[{"product_id": "HA-1801", "rate_per_acre": 4.0}],
    )
    [row] = payload["rows"]
    assert "total_amount" not in row and "containers" not in row
    assert "seeding rate" in row["total_note"]
    assert "product_cost" not in payload  # nothing to cost without a quantity


async def test_a_whole_tank_mix_costs_out_row_by_row(primed):
    payload = await card(
        primed,
        title="Corn preemergence tank mix",
        acres=640,
        carrier_gpa=15,
        tank_capacity_gal=1200,
        rows=[
            {"product_id": "HA-1001", "rate_per_acre": 1.6},
            {"product_id": "HA-1603", "rate_per_acre": 12, "note": "Goes in the tank first."},
            {"product_id": "HA-1601", "rate_per_acre": 0.25},
        ],
    )
    assert [row["containers"] for row in payload["rows"]] == [52, 24, 10]
    assert payload["product_cost"] == round(52 * 289.0 + 24 * 42.0 + 10 * 78.0, 2)
    assert payload["rows"][1]["note"] == "Goes in the tank first."


# -- the refusals ----------------------------------------------------------------------


async def test_a_rate_above_the_label_is_refused_and_the_range_is_named(primed):
    text = await refusal(
        primed,
        title="Corn preemergence",
        acres=640,
        rows=[{"product_id": "HA-1001", "rate_per_acre": 3.0}],
    )
    assert "1.2 to 2 pt/acre" in text


async def test_a_rate_below_the_label_is_refused_too(primed):
    text = await refusal(
        primed,
        title="Corn preemergence",
        acres=640,
        rows=[{"product_id": "HA-1001", "rate_per_acre": 0.4}],
    )
    assert "outside the labeled range" in text


async def test_a_product_this_session_has_not_seen_is_refused_not_dropped(primed):
    """Silently dropping a row would hand the grower an incomplete tank mix."""
    text = await refusal(
        primed,
        title="Corn preemergence",
        acres=640,
        rows=[
            {"product_id": "HA-1001", "rate_per_acre": 1.6},
            {"product_id": "HA-9999", "rate_per_acre": 1.0},
        ],
    )
    assert "not a product from this session" in text


async def test_a_product_with_no_stored_rate_range_is_refused(primed):
    text = await refusal(
        primed,
        title="Gloves",
        acres=640,
        rows=[{"product_id": "HA-2202", "rate_per_acre": 1.0}],
    )
    assert "no label rate range" in text


@pytest.mark.parametrize(
    ("field", "value"),
    [("acres", 90_000), ("carrier_gpa", 200), ("tank_capacity_gal", 40)],
)
async def test_an_out_of_range_operation_figure_is_refused(primed, field, value):
    payload = {
        "title": "Corn preemergence",
        "acres": 640,
        "rows": [{"product_id": "HA-1001", "rate_per_acre": 1.6}],
        field: value,
    }
    assert "outside the" in await refusal(primed, **payload)


async def test_an_invalid_payload_is_a_soft_error(primed):
    from commerce_common.presentation import invalid_payload_prefix

    result = await primed.execute(TOOL, {"title": "x" * 200, "acres": 10, "rows": []})
    assert result.is_error
    assert result.result_text.startswith(invalid_payload_prefix(TOOL))


# -- what the model is told ------------------------------------------------------------


async def test_the_model_is_told_to_quote_the_card_rather_than_recalculate(primed):
    result = await primed.execute(
        TOOL,
        {
            "title": "Corn preemergence",
            "acres": 640,
            "rows": [{"product_id": "HA-1001", "rate_per_acre": 1.6}],
        },
    )
    assert "computed on the " in result.result_text and "server" in result.result_text


async def test_a_restricted_use_row_is_flagged_and_the_licence_note_is_queued(primed):
    result = await primed.execute(
        TOOL,
        {
            "title": "Postemergence insecticide",
            "acres": 320,
            "rows": [{"product_id": "HA-1403", "rate_per_acre": 4.8}],
        },
    )
    assert not result.is_error, result.result_text
    payload = next(event for event in result.events if event.type == "ui").data["payload"]
    assert payload["restricted_use_present"] is True
    assert payload["rows"][0]["restricted_use"] is True
    assert "applicator licence" in result.result_text


async def test_a_plan_with_no_restricted_product_carries_no_flag(primed):
    payload = await card(
        primed,
        title="Corn preemergence",
        acres=640,
        rows=[{"product_id": "HA-1001", "rate_per_acre": 1.6}],
    )
    assert "restricted_use_present" not in payload


# -- the streamed prefix ---------------------------------------------------------------


async def test_the_streamed_prefix_shows_products_and_never_a_number(primed, state):
    from commerce_common.presentation import enrich_partial, partial_ui_tool_names

    assert TOOL in partial_ui_tool_names({}, [EXTENSION])
    streamed = enrich_partial(
        EXTENSION,
        {
            "title": "Corn preemergence",
            "acres": 640,
            "rows": [{"product_id": "HA-1001", "rate_per_acre": 9.9}],
        },
        state,
    )
    assert streamed is not None
    component, payload, _signature = streamed
    assert component == "application_plan"
    assert payload["pending"] is True
    assert [p["product_id"] for p in payload["products"]] == ["HA-1001"]
    # An unchecked rate must not reach the screen, even for the moment before it is refused.
    assert "9.9" not in str(payload) and "640" not in str(payload)


async def test_the_streamed_prefix_is_held_back_until_a_product_is_named(primed, state):
    from commerce_common.presentation import enrich_partial

    assert enrich_partial(EXTENSION, {"title": "Corn preem"}, state) is None
    assert enrich_partial(EXTENSION, {"rows": [{"product_id": "HA-9999"}]}, state) is None
