# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""``present_application_plan``: the tank-mix and acreage card.

The model chooses the products and the rate it wants for each; everything numeric is
computed here, on the server, from the rate range stored on the product record. A rate
outside that range is refused rather than rounded, a product this session has not seen
is refused rather than guessed at, and the model never sees an opportunity to do the
arithmetic itself. The card the grower reads is therefore arithmetic the deployment
owns, not text the model produced.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field

from commerce_common.presentation import (
    EnrichmentContext,
    PresentationExtension,
    PresentationRefused,
)
from shopping_agent import ProductDetails, ShoppingSessionState

# Bounds on the inputs the model supplies, so a typo cannot produce a plausible-looking
# plan for the wrong operation.
MIN_ACRES, MAX_ACRES = 0.1, 50_000.0
MIN_CARRIER_GPA, MAX_CARRIER_GPA = 2.0, 60.0
MIN_TANK_GAL, MAX_TANK_GAL = 50.0, 5_000.0
DEFAULT_CARRIER_GPA = 15.0
DEFAULT_TANK_GAL = 1_200.0

# Liquid measures in fluid ounces, and dry measures in ounces, so a rate quoted in one
# unit can be filled from a package sold in another.
_LIQUID_IN_FL_OZ = {"fl oz": 1.0, "floz": 1.0, "pt": 16.0, "qt": 32.0, "gal": 128.0}
_DRY_IN_OZ = {"oz": 1.0, "lb": 16.0}


class PlanRow(BaseModel):
    product_id: str = Field(max_length=64)
    rate_per_acre: float = Field(gt=0)
    note: str | None = Field(default=None, max_length=200)


class ApplicationPlanPayload(BaseModel):
    title: str = Field(max_length=80)
    acres: float = Field(gt=0)
    rows: list[PlanRow] = Field(min_length=1, max_length=6)
    carrier_gpa: float | None = Field(default=None, gt=0)
    tank_capacity_gal: float | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=280)


# The JSON schema the model sees; the payload model above is what the executor enforces.
_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "maxLength": 80},
        "acres": {"type": "number", "exclusiveMinimum": 0},
        "rows": {
            "type": "array",
            "minItems": 1,
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "maxLength": 64},
                    "rate_per_acre": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "description": (
                            "The rate in the product's own rate_unit, which must fall "
                            "inside the rate_min to rate_max range on its record."
                        ),
                    },
                    "note": {"type": "string", "maxLength": 200},
                },
                "required": ["product_id", "rate_per_acre"],
                "additionalProperties": False,
            },
        },
        "carrier_gpa": {
            "type": "number",
            "exclusiveMinimum": 0,
            "description": "Spray carrier volume in gallons per acre; defaults to 15.",
        },
        "tank_capacity_gal": {
            "type": "number",
            "exclusiveMinimum": 0,
            "description": "Sprayer tank capacity in gallons; defaults to 1200.",
        },
        "note": {"type": "string", "maxLength": 280},
    },
    "required": ["title", "acres", "rows"],
    "additionalProperties": False,
}


def _number(text: str | None) -> float | None:
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None


def _rate_basis(rate_unit: str) -> tuple[str, str]:
    """``(numerator unit, basis)`` for a stored rate unit. The basis says what the rate
    is charged against: an acre, a hundred gallons of carrier, the finished spray volume
    as a percentage, or a hundredweight of seed."""
    cleaned = rate_unit.strip().lower()
    if cleaned in {"% v/v", "%v/v", "% vv"}:
        return "fl oz", "percent_vv"
    numerator, _, denominator = cleaned.partition("/")
    numerator, denominator = numerator.strip(), denominator.strip()
    if denominator in {"100 gal", "100gal"}:
        return numerator, "per_100_gal"
    if denominator == "cwt":
        return numerator, "per_cwt"
    return numerator, "per_acre"


def _convert(amount: float, from_unit: str, to_unit: str) -> float | None:
    """``amount`` expressed in ``to_unit``, within the liquid or the dry family."""
    if from_unit == to_unit:
        return amount
    for table in (_LIQUID_IN_FL_OZ, _DRY_IN_OZ):
        if from_unit in table and to_unit in table:
            return amount * table[from_unit] / table[to_unit]
    return None


def _resolve(product_id: str, state: ShoppingSessionState) -> ProductDetails:
    """The product record this session has already seen, or a refusal. A plan is only
    ever built from the catalog; an id from anywhere else would put an unverified rate
    range behind a number the grower is about to pour into a tank."""
    product = state.seen_products.get(product_id)
    if product is None:
        raise PresentationRefused(
            f"{product_id} is not a product from this session's search results or detail "
            "lookups. Search the catalog for it first, then build the plan from the ids "
            "the search returned."
        )
    return product


def _row_amounts(
    product: ProductDetails, rate: float, acres: float, carrier_gal: float
) -> dict[str, Any]:
    """One row's arithmetic: the label check, the total product the acres call for, and
    the containers that implies."""
    attributes = product.attributes
    rate_unit = attributes.get("rate_unit")
    rate_min, rate_max = _number(attributes.get("rate_min")), _number(attributes.get("rate_max"))
    if not rate_unit or rate_min is None or rate_max is None:
        raise PresentationRefused(
            f"{product.product_id} ({product.title}) carries no label rate range on its "
            "record, so no rate can be planned for it here. Leave it out of the plan and "
            "point the grower at the product label."
        )
    if not rate_min <= rate <= rate_max:
        raise PresentationRefused(
            f"{rate:g} {rate_unit} is outside the labeled range for {product.product_id} "
            f"({product.title}), which is {rate_min:g} to {rate_max:g} {rate_unit}. Pick a "
            "rate inside that range, or leave the product out; the rate on the label is "
            "not negotiable."
        )

    numerator, basis = _rate_basis(rate_unit)
    row: dict[str, Any] = {
        "product": product.model_dump(exclude_none=True),
        "rate": rate,
        "rate_unit": rate_unit,
        "rate_min": rate_min,
        "rate_max": rate_max,
        "restricted_use": attributes.get("restricted_use") == "yes",
    }

    if basis == "per_acre":
        total = rate * acres
    elif basis == "per_100_gal":
        total = rate * carrier_gal / 100
    elif basis == "percent_vv":
        total = rate / 100 * carrier_gal * 128  # fluid ounces of finished spray
    else:
        row["total_note"] = (
            f"{product.title} is rated per hundredweight of seed, not per acre, so the "
            "amount depends on the seeding rate rather than the acres in this plan."
        )
        return row

    row["total_amount"] = round(total, 2)
    row["total_unit"] = numerator

    per_package = _number(attributes.get("units_per_package"))
    package_unit = (attributes.get("package_unit") or "").strip().lower()
    if per_package and per_package > 0 and package_unit:
        needed = _convert(total, numerator, package_unit)
        if needed is not None:
            containers = math.ceil(needed / per_package)
            row["containers"] = containers
            row["package_size"] = attributes.get("package_size")
            row["line_cost"] = round(containers * product.price, 2)
            row["currency"] = product.currency
    return row


def _build(payload: ApplicationPlanPayload, state: ShoppingSessionState) -> dict[str, Any]:
    acres = payload.acres
    if not MIN_ACRES <= acres <= MAX_ACRES:
        raise PresentationRefused(
            f"{acres:g} acres is outside the range this plan will calculate "
            f"({MIN_ACRES:g} to {MAX_ACRES:g}). Confirm the acres with the grower."
        )
    carrier_gpa = payload.carrier_gpa or DEFAULT_CARRIER_GPA
    if not MIN_CARRIER_GPA <= carrier_gpa <= MAX_CARRIER_GPA:
        raise PresentationRefused(
            f"{carrier_gpa:g} gallons per acre is outside the range this plan will "
            f"calculate ({MIN_CARRIER_GPA:g} to {MAX_CARRIER_GPA:g})."
        )
    tank_gal = payload.tank_capacity_gal or DEFAULT_TANK_GAL
    if not MIN_TANK_GAL <= tank_gal <= MAX_TANK_GAL:
        raise PresentationRefused(
            f"{tank_gal:g} gallons is outside the tank sizes this plan will calculate "
            f"({MIN_TANK_GAL:g} to {MAX_TANK_GAL:g})."
        )

    carrier_gal = acres * carrier_gpa
    rows = [
        _row_amounts(_resolve(row.product_id, state), row.rate_per_acre, acres, carrier_gal)
        | ({"note": row.note} if row.note else {})
        for row in payload.rows
    ]

    plan: dict[str, Any] = {
        "title": payload.title,
        "acres": acres,
        "carrier_gpa": carrier_gpa,
        "tank_capacity_gal": tank_gal,
        "total_carrier_gal": round(carrier_gal, 1),
        "acres_per_load": round(tank_gal / carrier_gpa, 1),
        "tank_loads": math.ceil(carrier_gal / tank_gal),
        "rows": rows,
        "computed_by": "server",
    }
    costed = [row["line_cost"] for row in rows if "line_cost" in row]
    if costed:
        plan["product_cost"] = round(sum(costed), 2)
        plan["cost_per_acre"] = round(sum(costed) / acres, 2)
        plan["currency"] = next(row["currency"] for row in rows if "currency" in row)
    if payload.note:
        plan["note"] = payload.note
    if any(row["restricted_use"] for row in rows):
        plan["restricted_use_present"] = True
    return plan


async def _enrich(payload: ApplicationPlanPayload, context: EnrichmentContext) -> dict[str, Any]:
    plan = _build(payload, context.state)
    context.notes.append(
        "The plan's volumes, container counts, and tank loads were computed on the "
        "server from each product's stored label rate range. Quote them from the card "
        "rather than recalculating them."
    )
    if plan.get("restricted_use_present"):
        context.notes.append(
            "This plan contains a restricted-use product. Say so, and say that the order "
            "cannot be completed until the portal verifies a current applicator licence."
        )
    return plan


def _enrich_partial(data: dict[str, Any], state: ShoppingSessionState) -> dict[str, Any] | None:
    """The streamed prefix of a still-generating call. It shows only the products the
    rows have named so far, and never a number: a partially streamed rate has not been
    checked against the label yet, and a rate that flickers on screen before being
    refused is worse than one that never appears."""
    products = [
        state.seen_products[pid].model_dump(exclude_none=True)
        for row in data.get("rows") or []
        if isinstance(row, dict) and isinstance(pid := row.get("product_id"), str)
        if pid in state.seen_products
    ]
    if not products:
        return None
    return {"title": data.get("title") or "", "pending": True, "products": products}


def build_application_plan_extension() -> PresentationExtension:
    return PresentationExtension(
        name="present_application_plan",
        component="application_plan",
        description=(
            "Show a tank-mix and acreage plan: the products to apply, the rate for each, "
            "and what that works out to across the grower's acres. Use whenever the "
            "grower has named acres and wants to know how much product to buy or load. "
            "Pass product_ids from this session's search results and a rate_per_acre "
            "inside each product's labeled rate_min to rate_max range. The server does "
            "every calculation — total product, containers, cost, and tank loads — and "
            "refuses a rate outside the label, so do not compute or state any of those "
            "numbers yourself."
        ),
        input_schema=_INPUT_SCHEMA,
        payload_model=ApplicationPlanPayload,
        enrich=_enrich,
        enrich_partial=_enrich_partial,
    )
