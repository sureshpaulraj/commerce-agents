# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

import pytest

from grocery.api.mock_merchant import MockGroceryMerchant
from merchant_agent import (
    InventoryActionItem,
    ListingFilters,
    MerchantAgentConfig,
    PriceUpdateItem,
)

STORE_NAME = "Riverbend Market"


async def test_snapshot_counts_the_fixture_alerts(merchant, operator_session):
    snapshot = await merchant.get_business_snapshot(operator_session)
    assert snapshot.alerts.low_stock >= 20
    assert snapshot.alerts.slow_movers >= 20
    assert snapshot.alerts.order_issues == 5


async def test_query_metrics_supports_the_prepared_food_segment(merchant, operator_session):
    overall = await merchant.query_metrics(operator_session, "sales", "last_7_days")
    prepared = await merchant.query_metrics(
        operator_session, "sales", "last_7_days", segment="prepared food"
    )
    assert len(overall.points) == 7
    assert len(prepared.points) == 7
    assert 0 < sum(p.value for p in prepared.points) < sum(p.value for p in overall.points)
    assert prepared.segment == "prepared-food"


async def test_weekly_granularity_recomputes_ratio_metrics(merchant, operator_session):
    daily = await merchant.query_metrics(operator_session, "conversion_rate", "last_30_days")
    weekly = await merchant.query_metrics(
        operator_session, "conversion_rate", "last_30_days", granularity="week"
    )
    daily_avg = sum(p.value for p in daily.points) / len(daily.points)
    assert all(p.value < daily_avg * 2 for p in weekly.points)
    weekly_aov = await merchant.query_metrics(
        operator_session, "average_order_value", "last_30_days", granularity="week"
    )
    assert all(40 < p.value < 90 for p in weekly_aov.points)


async def test_alerts_cover_the_demo_listings(merchant, operator_session):
    alerts = await merchant.get_inventory_alerts(operator_session)
    by_id = {alert.listing_id: alert for alert in alerts}
    assert by_id["RB-1002"].kind == "low_stock"
    assert by_id["RB-1111"].kind == "low_stock"
    assert by_id["RB-1016"].kind == "slow_mover"
    assert by_id["RB-1016"].days_of_cover == round(118 / (34 / 30), 1)
    assert by_id["RB-1008"].storefront_visible is False


async def test_storefront_unavailable_products_are_not_active_in_the_portal(
    merchant, operator_session
):
    for product_id, stock in (("RB-1008", 19), ("RB-1106", 14), ("RB-2203", 11)):
        listing = await merchant.get_listing(operator_session, product_id)
        assert listing.status == "out_of_stock"
        assert listing.stock == stock


def test_boot_rejects_an_explicit_catalog_vs_overlay_stock_contradiction(backend):
    broken = MockGroceryMerchant(backend, MerchantAgentConfig(brand_name=STORE_NAME))
    broken._inventory["RB-1008"]["status"] = "active"
    with pytest.raises(ValueError, match="RB-1008"):
        broken._assert_storefront_consistency()


async def test_listing_details_carry_quality_and_review_data(merchant, operator_session):
    listing = await merchant.get_listing(operator_session, "RB-1016")
    assert listing is not None
    assert listing.content_quality == "needs_work"
    assert listing.stock == 118
    assert listing.missing_attributes
    assert listing.sales_last_30d == 34


async def test_order_issues_load_from_the_messages_fixture(merchant, operator_session):
    issues = await merchant.get_order_issues(operator_session)
    kinds = {issue.kind for issue in issues}
    assert kinds == {"delayed", "damaged", "return_spike", "buyer_message"}
    assert any(issue.listing_id == "RB-2206" for issue in issues)


async def test_applied_restock_is_visible_to_the_storefront(merchant, backend, operator_session):
    before = (await merchant.get_listing(operator_session, "RB-1002")).stock
    change = await merchant.stage_inventory_action(
        operator_session, [InventoryActionItem(listing_id="RB-1002", action="restock", quantity=24)]
    )
    assert (await merchant.get_listing(operator_session, "RB-1002")).stock == before

    await merchant.apply_change(operator_session, change.change_id)
    after = await merchant.get_listing(operator_session, "RB-1002")
    assert after.stock == before + 24
    assert backend.products["RB-1002"].in_stock is True
    assert (await merchant.get_business_snapshot(operator_session)).alerts.low_stock >= 1


async def test_applied_price_change_updates_the_shared_catalog(merchant, backend, operator_session):
    pricing = await merchant.get_pricing_context(operator_session, "RB-1002")
    new_price = round(pricing.current_price * 0.95, 2)
    change = await merchant.stage_price_update(
        operator_session, [PriceUpdateItem(listing_id="RB-1002", new_price=new_price)]
    )
    assert change.margin_impact is not None
    assert backend.products["RB-1002"].price == pricing.current_price

    await merchant.apply_change(operator_session, change.change_id)
    assert backend.products["RB-1002"].price == new_price


async def test_listing_update_apply_fixes_content_quality(merchant, backend, operator_session):
    change = await merchant.stage_listing_update(
        operator_session,
        "RB-1016",
        {"short_description": "Prepared pico with use-by window printed on the case label."},
        note="State the use-by window in the prepared pico listing",
    )
    await merchant.apply_change(operator_session, change.change_id)
    listing = await merchant.get_listing(operator_session, "RB-1016")
    assert listing.short_description.startswith("Prepared pico")
    assert listing.content_quality == "good"
    assert backend.products["RB-1016"].short_description.startswith("Prepared pico")


async def test_merchant_context_reports_alert_counts(merchant, operator_session):
    context = await merchant.get_merchant_context(operator_session)
    assert context["store"] == STORE_NAME
    assert context["alerts"]["low_stock"] >= 20


async def test_browse_filters_narrow_the_whole_catalog(merchant, operator_session):
    flagged = await merchant.search_listings(
        operator_session, "", ListingFilters(content_quality="needs_work"), limit=25
    )
    assert {listing.listing_id for listing in flagged} == {
        "RB-1016",
        "RB-1305",
        "RB-1412",
        "RB-1521",
        "RB-2206",
    }
    low_stock = await merchant.search_listings(
        operator_session, "all", ListingFilters(max_stock=15), limit=25
    )
    assert any(listing.listing_id == "RB-1111" for listing in low_stock)


async def test_staged_price_cut_carries_fixture_true_margins(merchant, operator_session):
    change = await merchant.stage_price_update(
        operator_session, [PriceUpdateItem(listing_id="RB-1002", new_price=3.09)]
    )
    assert change.currency == "USD"
    assert change.margin_before_pct == 34.0
    assert change.margin_after_pct == 29.8


async def test_multi_item_price_update_carries_per_item_margin_notes(merchant, operator_session):
    change = await merchant.stage_price_update(
        operator_session,
        [
            PriceUpdateItem(listing_id="RB-1002", new_price=3.09),
            PriceUpdateItem(listing_id="RB-1111", new_price=12.49),
        ],
    )
    assert change.margin_before_pct is None and change.margin_after_pct is None
    assert len([note for note in change.guardrail_notes if "margin" in note]) == 2


def test_kpi_trends_match_the_snapshot_window(merchant):
    trends = merchant.kpi_trends()
    assert set(trends) == {"sales", "orders", "conversion", "average_order_value"}
    for points in trends.values():
        assert len(points) == 7
    day = trends["sales"][0]
    matching = next(p for p in trends["orders"] if p["date"] == day["date"])
    aov = next(p for p in trends["average_order_value"] if p["date"] == day["date"])
    assert aov["value"] == round(day["value"] / matching["value"], 2)


def test_home_insights_are_deterministic_and_fixture_grounded(merchant):
    first = merchant.home_insights()
    assert first == merchant.home_insights()
    assert len(first) <= 3
    for insight in first:
        assert insight["headline"]
        assert insight["prompt"]


async def test_plain_listing_price_and_restock_writes(merchant, backend, operator_session):
    change = await merchant.stage_price_update(
        operator_session, [PriceUpdateItem(listing_id="RB-1501", new_price=1.69)]
    )
    assert [(item.target, item.before, item.after) for item in change.items] == [
        ("RB-1501", 1.79, 1.69)
    ]
    await merchant.apply_change(operator_session, change.change_id)
    assert backend.products["RB-1501"].price == 1.69

    restock = await merchant.stage_inventory_action(
        operator_session, [InventoryActionItem(listing_id="RB-1111", action="restock", quantity=8)]
    )
    await merchant.apply_change(operator_session, restock.change_id)
    listing = await merchant.get_listing(operator_session, "RB-1111")
    assert listing.stock == 15 and listing.status == "active"


async def test_a_promotion_on_plain_listings_updates_each_target(merchant, operator_session):
    from merchant_agent import PromotionDraft

    change = await merchant.stage_promotion(
        operator_session,
        PromotionDraft(
            name="Pantry week",
            listing_ids=["RB-1501", "RB-1516"],
            discount_pct=10,
            starts="2026-09-21",
            ends="2026-09-27",
        ),
    )
    assert [(item.target, item.after) for item in change.items] == [
        ("RB-1501", 1.61),
        ("RB-1516", 2.06),
    ]


async def test_the_store_says_what_it_cannot_supply(merchant, operator_session):
    context = await merchant.get_merchant_context(operator_session)
    assert {entry["source"] for entry in context["limitations"]} == {"campaigns", "orders"}
    campaigns = await merchant.get_campaign_performance(operator_session)
    email = next(c for c in campaigns if c.campaign_id == "C-305")
    assert email.spend == 1250.0 and email.revenue is None


async def test_a_price_below_the_reported_floor_is_refused(merchant, operator_session):
    from merchant_agent import ChangeNotApplicable

    context = await merchant.get_pricing_context(operator_session, "RB-1002")
    assert context.min_price is not None
    with pytest.raises(ChangeNotApplicable, match="below the floor"):
        await merchant.stage_price_update(
            operator_session,
            [PriceUpdateItem(listing_id="RB-1002", new_price=context.min_price - 1)],
        )
