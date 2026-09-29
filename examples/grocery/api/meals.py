# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""``present_meal_plan``: the meals-to-basket card.

The model composes the meals and says how much of each item one serving takes;
everything numeric is computed here, on the server, from the pack size and price
stored on the product record. Quantities scale to the household's servings, packs
round up, and the subtotal, the cost per serving, the budget headroom, and the
Riverbend Rewards points all follow from that one pass.

The card also owns the deployment's allergen rule, because a shopper acts on it. A
product whose allergen statement is not verified on its record cannot enter a plan at
all, whatever the model believes about it; a product that contains, or may contain, an
allergen the household is avoiding is refused by name. Both refusals are structural:
they hold even if the model never mentions the allergy, and they cannot be talked out
of. What the shopper reads is arithmetic and provenance the deployment owns, not text
the model produced.
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
# plan for the wrong household.
MIN_SERVINGS, MAX_SERVINGS = 1, 60
MIN_BUDGET, MAX_BUDGET = 5.0, 2_000.0

# Riverbend Rewards, as the loyalty policy states it: points earn on the basket, and
# every hundred points is worth ten cents a gallon at a Riverbend Fuel Stop.
POINTS_PER_DOLLAR = 10
FUEL_CENTS_PER_100_POINTS = 10
MAX_FUEL_CENTS_PER_GAL = 100

# The nine allergens the catalog declares, lowercase, as they appear on a record.
KNOWN_ALLERGENS = frozenset(
    {
        "milk",
        "eggs",
        "fish",
        "shellfish",
        "tree nuts",
        "peanuts",
        "wheat",
        "soybeans",
        "sesame",
    }
)

# Weight in ounces, volume in fluid ounces, and count, so a quantity given in one
# measure can be filled from a pack sold in another inside the same family.
_WEIGHT_IN_OZ = {"oz": 1.0, "lb": 16.0}
_VOLUME_IN_FL_OZ = {"fl oz": 1.0, "floz": 1.0, "cup": 8.0, "pt": 16.0, "qt": 32.0, "gal": 128.0}
_COUNT = {"ct": 1.0, "each": 1.0, "ea": 1.0}


class MealItem(BaseModel):
    product_id: str = Field(max_length=64)
    quantity_per_serving: float = Field(gt=0)
    unit: str | None = Field(default=None, max_length=16)
    note: str | None = Field(default=None, max_length=200)


class Meal(BaseModel):
    name: str = Field(max_length=80)
    items: list[MealItem] = Field(min_length=1, max_length=12)
    note: str | None = Field(default=None, max_length=200)


class MealPlanPayload(BaseModel):
    title: str = Field(max_length=80)
    servings: int = Field(gt=0)
    meals: list[Meal] = Field(min_length=1, max_length=7)
    budget: float | None = Field(default=None, gt=0)
    avoid_allergens: list[str] = Field(default_factory=list, max_length=9)
    note: str | None = Field(default=None, max_length=280)


# The JSON schema the model sees; the payload model above is what the executor enforces.
_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "maxLength": 80},
        "servings": {
            "type": "integer",
            "minimum": MIN_SERVINGS,
            "maximum": MAX_SERVINGS,
            "description": "How many servings each meal in the plan is cooked for.",
        },
        "meals": {
            "type": "array",
            "minItems": 1,
            "maxItems": 7,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 80},
                    "items": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 12,
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_id": {"type": "string", "maxLength": 64},
                                "quantity_per_serving": {
                                    "type": "number",
                                    "exclusiveMinimum": 0,
                                    "description": (
                                        "How much of this product one serving takes, in "
                                        "the unit given below. The server multiplies it "
                                        "out across the servings and rounds up to whole "
                                        "packs."
                                    ),
                                },
                                "unit": {
                                    "type": "string",
                                    "maxLength": 16,
                                    "description": (
                                        "The unit the quantity is in: oz, lb, fl oz, cup, "
                                        "pt, qt, gal, or ct. Defaults to the product's "
                                        "own unit_of_measure."
                                    ),
                                },
                                "note": {"type": "string", "maxLength": 200},
                            },
                            "required": ["product_id", "quantity_per_serving"],
                            "additionalProperties": False,
                        },
                    },
                    "note": {"type": "string", "maxLength": 200},
                },
                "required": ["name", "items"],
                "additionalProperties": False,
            },
        },
        "budget": {
            "type": "number",
            "exclusiveMinimum": 0,
            "description": "The shopper's stated budget for the whole plan, if they gave one.",
        },
        "avoid_allergens": {
            "type": "array",
            "maxItems": 9,
            "items": {"type": "string", "maxLength": 20},
            "description": (
                "Allergens the household is avoiding, from: milk, eggs, fish, shellfish, "
                "tree nuts, peanuts, wheat, soybeans, sesame. Pass every one the shopper "
                "has mentioned. The server refuses any product that declares one of them."
            ),
        },
        "note": {"type": "string", "maxLength": 280},
    },
    "required": ["title", "servings", "meals"],
    "additionalProperties": False,
}


def _number(text: str | None) -> float | None:
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None


def _allergen_set(raw: str | None) -> set[str]:
    """The allergens named on a record, lowercase. ``none`` and blanks are empty."""
    if not raw:
        return set()
    cleaned = raw.strip().lower()
    if cleaned in {"none", "n/a", "-"}:
        return set()
    return {part.strip() for part in cleaned.split(",") if part.strip()}


def _convert(amount: float, from_unit: str, to_unit: str) -> float | None:
    """``amount`` expressed in ``to_unit``, within the weight, volume, or count family."""
    if from_unit == to_unit:
        return amount
    for table in (_WEIGHT_IN_OZ, _VOLUME_IN_FL_OZ, _COUNT):
        if from_unit in table and to_unit in table:
            return amount * table[from_unit] / table[to_unit]
    return None


def _resolve(product_id: str, state: ShoppingSessionState) -> ProductDetails:
    """The product record this session has already seen, or a refusal. A plan is only
    ever built from the catalog; an id from anywhere else would put an unverified
    allergen statement behind food a household is about to eat."""
    product = state.seen_products.get(product_id)
    if product is None:
        raise PresentationRefused(
            f"{product_id} is not a product from this session's search results or detail "
            "lookups. Search the catalog for it first, then build the plan from the ids "
            "the search returned."
        )
    return product


def _check_allergens(product: ProductDetails, avoid: set[str]) -> dict[str, Any]:
    """The provenance gate. Refuses a product whose allergen statement is not verified,
    and a product that declares an allergen the household is avoiding. Returns what the
    card should show about the ones that pass."""
    attributes = product.attributes
    status = (attributes.get("allergen_status") or "").strip().lower()
    if status != "verified":
        raise PresentationRefused(
            f"{product.product_id} ({product.title}) has no verified allergen statement on "
            "its record, so this plan will not carry it. Tell the shopper the allergen "
            "information for that item is not confirmed in our system and that we will not "
            "put it in a plan on that basis, then offer an item whose statement is "
            "verified. Do not describe the item as safe, and do not reason about its "
            "ingredients yourself."
        )

    contains = _allergen_set(attributes.get("allergens"))
    may_contain = _allergen_set(attributes.get("may_contain"))
    hit = sorted(contains & avoid)
    if hit:
        raise PresentationRefused(
            f"{product.product_id} ({product.title}) contains {', '.join(hit)}, which this "
            "household is avoiding. Leave it out and pick something else; say plainly why "
            "it was left out."
        )
    shared = sorted(may_contain & avoid)
    if shared:
        raise PresentationRefused(
            f"{product.product_id} ({product.title}) is made on equipment that also handles "
            f"{', '.join(shared)}, which this household is avoiding. Leave it out and pick "
            "something else; say that it was the shared-equipment statement, not an "
            "ingredient, that ruled it out."
        )

    return {
        "allergens": sorted(contains),
        "may_contain": sorted(may_contain),
        "allergen_status": "verified",
        "allergen_source": attributes.get("allergen_source"),
    }


def _item_amounts(
    product: ProductDetails, quantity_per_serving: float, servings: int, unit: str | None
) -> dict[str, Any]:
    """One line's arithmetic: what the servings need, and the whole packs that takes."""
    attributes = product.attributes
    pack_unit = (unit or attributes.get("unit_of_measure") or "").strip().lower()
    unit_count = _number(attributes.get("unit_count"))
    stored_unit = (attributes.get("unit_of_measure") or "").strip().lower()
    if not stored_unit or unit_count is None or unit_count <= 0:
        raise PresentationRefused(
            f"{product.product_id} ({product.title}) carries no pack size on its record, so "
            "the amount a plan needs cannot be worked out here. Leave it out of the plan."
        )

    needed = _convert(quantity_per_serving * servings, pack_unit or stored_unit, stored_unit)
    if needed is None:
        raise PresentationRefused(
            f"A quantity in {pack_unit} cannot be filled from {product.product_id} "
            f"({product.title}), which is sold by {stored_unit}. Give the quantity in "
            f"{stored_unit}, or a unit in the same family."
        )

    packs = math.ceil(needed / unit_count)
    line_cost = round(packs * product.price, 2)
    return {
        "product": product.model_dump(exclude_none=True),
        "quantity_per_serving": quantity_per_serving,
        "quantity_unit": pack_unit or stored_unit,
        "total_needed": round(needed, 2),
        "total_unit": stored_unit,
        "pack_size": attributes.get("pack_size"),
        "packs": packs,
        "line_cost": line_cost,
        "currency": product.currency,
        "leftover": round(packs * unit_count - needed, 2),
        "department": attributes.get("department"),
        "private_label": attributes.get("private_label") == "yes",
        "age_restricted": attributes.get("age_restricted") == "yes",
        "snap_eligible": attributes.get("snap_eligible") == "yes",
    }


def _build(payload: MealPlanPayload, state: ShoppingSessionState) -> dict[str, Any]:
    servings = payload.servings
    if not MIN_SERVINGS <= servings <= MAX_SERVINGS:
        raise PresentationRefused(
            f"{servings} servings is outside the range this plan will calculate "
            f"({MIN_SERVINGS} to {MAX_SERVINGS}). Confirm the household size with the shopper."
        )
    budget = payload.budget
    if budget is not None and not MIN_BUDGET <= budget <= MAX_BUDGET:
        raise PresentationRefused(
            f"A budget of {budget:g} is outside the range this plan will calculate "
            f"({MIN_BUDGET:g} to {MAX_BUDGET:g}). Confirm the budget with the shopper."
        )

    avoid = {a.strip().lower() for a in payload.avoid_allergens if a.strip()}
    unknown = sorted(avoid - KNOWN_ALLERGENS)
    if unknown:
        raise PresentationRefused(
            f"{', '.join(unknown)} is not an allergen the catalog declares, so this plan "
            "cannot screen for it. The declared allergens are "
            f"{', '.join(sorted(KNOWN_ALLERGENS))}. Tell the shopper we cannot screen for "
            "it here and suggest they read the package label."
        )

    meals: list[dict[str, Any]] = []
    # One product can appear in several meals; the basket buys it once.
    totals: dict[str, dict[str, Any]] = {}
    for meal in payload.meals:
        lines: list[dict[str, Any]] = []
        for item in meal.items:
            product = _resolve(item.product_id, state)
            allergen_note = _check_allergens(product, avoid)
            line = _item_amounts(product, item.quantity_per_serving, servings, item.unit)
            line |= allergen_note
            if item.note:
                line["note"] = item.note
            lines.append(line)

            entry = totals.setdefault(
                product.product_id,
                {"product": line["product"], "needed": 0.0, "unit": line["total_unit"]},
            )
            entry["needed"] += line["total_needed"]
        meals.append(
            {"name": meal.name, "servings": servings, "items": lines}
            | ({"note": meal.note} if meal.note else {})
        )

    basket: list[dict[str, Any]] = []
    for product_id, entry in totals.items():
        product = state.seen_products[product_id]
        unit_count = _number(product.attributes.get("unit_count")) or 1.0
        packs = math.ceil(entry["needed"] / unit_count)
        basket.append(
            {
                "product": entry["product"],
                "total_needed": round(entry["needed"], 2),
                "total_unit": entry["unit"],
                "packs": packs,
                "line_cost": round(packs * product.price, 2),
                "currency": product.currency,
            }
        )
    basket.sort(key=lambda row: row["line_cost"], reverse=True)

    subtotal = round(sum(row["line_cost"] for row in basket), 2)
    points = int(subtotal * POINTS_PER_DOLLAR)
    plan: dict[str, Any] = {
        "title": payload.title,
        "servings": servings,
        "meals": meals,
        "basket": basket,
        "item_count": len(basket),
        "pack_count": sum(row["packs"] for row in basket),
        "subtotal": subtotal,
        "cost_per_serving": round(subtotal / (servings * len(meals)), 2),
        "currency": basket[0]["currency"] if basket else "USD",
        "rewards_points": points,
        "fuel_cents_per_gal": min(
            points // 100 * FUEL_CENTS_PER_100_POINTS, MAX_FUEL_CENTS_PER_GAL
        ),
        "computed_by": "server",
    }
    if avoid:
        plan["avoided_allergens"] = sorted(avoid)
    if budget is not None:
        plan["budget"] = budget
        plan["budget_headroom"] = round(budget - subtotal, 2)
        plan["over_budget"] = subtotal > budget
    if payload.note:
        plan["note"] = payload.note
    if any(row.get("age_restricted") for meal in meals for row in meal["items"]):
        plan["age_restricted_present"] = True
    return plan


async def _enrich(payload: MealPlanPayload, context: EnrichmentContext) -> dict[str, Any]:
    plan = _build(payload, context.state)
    context.notes.append(
        "The plan's quantities, pack counts, subtotal, cost per serving, and Riverbend "
        "Rewards points were computed on the server from each product's stored pack size "
        "and price. Quote them from the card rather than recalculating them."
    )
    if plan.get("avoided_allergens"):
        context.notes.append(
            "Every item in this plan has a verified allergen statement on its record and "
            "declares none of the allergens being avoided. Say that the check was against "
            "our stored statements, and that the printed package label is what governs."
        )
    if plan.get("over_budget"):
        context.notes.append(
            "This plan is over the shopper's stated budget. Say so plainly, and offer to "
            "swap the costliest lines for store-brand equivalents."
        )
    if plan.get("age_restricted_present"):
        context.notes.append(
            "This plan contains an age-restricted item. Say so, and say that it needs ID "
            "at handoff and cannot be left unattended in a curbside or delivery order."
        )
    return plan


def _enrich_partial(data: dict[str, Any], state: ShoppingSessionState) -> dict[str, Any] | None:
    """The streamed prefix of a still-generating call. It shows only the meals and the
    products named so far, and never a number: a partially streamed line has not been
    through the allergen gate yet, and an item that flickers on screen before being
    refused is worse than one that never appears."""
    meals: list[dict[str, Any]] = []
    for meal in data.get("meals") or []:
        if not isinstance(meal, dict):
            continue
        products = [
            _partial_product(state.seen_products[pid])
            for item in meal.get("items") or []
            if isinstance(item, dict) and isinstance(pid := item.get("product_id"), str)
            if pid in state.seen_products
        ]
        if products:
            meals.append({"name": meal.get("name") or "", "products": products})
    if not meals:
        return None
    return {"title": data.get("title") or "", "pending": True, "meals": meals}


def _partial_product(product: ProductDetails) -> dict[str, Any]:
    """A non-numeric product identity for a streamed meal-plan prefix."""
    return {
        key: value
        for key, value in product.model_dump(exclude_none=True).items()
        if key
        in {
            "product_id",
            "title",
            "brand",
            "category",
            "image_url",
            "short_description",
        }
    }


def build_meal_plan_extension() -> PresentationExtension:
    return PresentationExtension(
        name="present_meal_plan",
        component="meal_plan",
        description=(
            "Show a week of meals and the basket that fills them: the meals, what each "
            "one takes per serving, and what that works out to across the household. Use "
            "whenever the shopper has asked for meals, a week of dinners, or a plan for a "
            "number of people. Pass product_ids from this session's search results and "
            "how much of each one serving takes. The server does every calculation — "
            "quantities, whole packs, subtotal, cost per serving, budget headroom, and "
            "Riverbend Rewards points — so do not compute or state any of those numbers "
            "yourself. It also refuses any item whose allergen statement is not verified "
            "on its record, and any item declaring an allergen passed in avoid_allergens, "
            "so pass every allergy the shopper has mentioned."
        ),
        input_schema=_INPUT_SCHEMA,
        payload_model=MealPlanPayload,
        enrich=_enrich,
        enrich_partial=_enrich_partial,
    )
