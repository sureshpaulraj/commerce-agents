# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The Riverbend Market deployment's two agent configs; the only place this example
reads deployment knobs from the environment."""

from __future__ import annotations

import os

from demo_common import host_approval_default
from merchant_agent import MerchantAgentConfig
from shopping_agent import ShoppingAgentConfig

_SHOPPING_DEFAULTS = ShoppingAgentConfig()
_MERCHANT_DEFAULTS = MerchantAgentConfig()

# Grocery vocabulary added to the policy-grounding lexicon, so a question about an
# allergen, a substitution, a pickup slot, or the pharmacy forces a help-content read
# first. An allergen question answered from the model's own memory of a brand is the
# failure this deployment most wants to make impossible.
_POLICY_TERMS = (
    "allergen",
    "allergens",
    "allergy",
    "allergic",
    "gluten",
    "dairy-free",
    "nut-free",
    "substitution",
    "substitute",
    "substitutes",
    "pickup",
    "curbside",
    "slot",
    "window",
    "rewards",
    "points",
    "fuel",
    "snap",
    "ebt",
    "wic",
    "recall",
    "recalled",
    "freshness",
    "guarantee",
    "pharmacy",
    "prescription",
    "alcohol",
    "age-restricted",
    "coupon",
    "weekly ad",
    "expiration",
    "sell by",
    "best by",
)

# Grocery vocabulary added to the metrics-grounding lexicon on the merchant side.
_METRICS_TERMS = (
    "shrink",
    "markdown",
    "markdowns",
    "basket",
    "trips",
    "department",
    "departments",
    "perishable",
    "waste",
    "substitution",
    "accept rate",
    "end cap",
    "facing",
    "banner",
    "loyalty",
    "private label",
    "store brand",
)


def build_shopping_config() -> ShoppingAgentConfig:
    return ShoppingAgentConfig(
        brand_name="Riverbend Market",
        assistant_name="Riverbend Assistant",
        brand_voice=(
            "warm, practical about a household's week, and never casual about an allergen"
        ),
        domain_search_notes=(
            "Groceries are chosen against a household rather than a taste: when the "
            "shopper has named a diet, an allergy, a department, or a brand preference, "
            "pass them as filters.attributes['dietary'], "
            "filters.attributes['allergens'], filters.attributes['department'], and "
            "filters.attributes['private_label'] so the catalog does the matching. Never "
            "state that a product is free of an allergen from your own knowledge of the "
            "brand: the allergen statement lives on the product record, it carries a "
            "verified or unverified status, and an unverified one means the store will "
            "not make the claim at all. Never state a quantity, a pack count, a "
            "subtotal, a cost per serving, or a rewards total from your own reasoning: "
            "that arithmetic belongs to present_meal_plan, which computes it on the "
            "server and refuses any item whose allergen statement is unverified."
        ),
        policy_intent_terms=_SHOPPING_DEFAULTS.policy_intent_terms + _POLICY_TERMS,
    )


def build_merchant_config(store_name: str) -> MerchantAgentConfig:
    return MerchantAgentConfig(
        brand_name=store_name,
        require_host_approval=host_approval_default(),
        approval_surface="the Approve button on the change preview card",
        metrics_intent_terms=_MERCHANT_DEFAULTS.metrics_intent_terms + _METRICS_TERMS,
        # This deployment runs the run_analysis delegate over MockGroceryMerchant's
        # read-only SQL view of the fixtures. MERCHANT_ANALYSIS_CODE_EXECUTION=1 adds the
        # code-execution sandbox (first-party API only); MERCHANT_ANALYSIS_MODEL overrides
        # the delegate's model, which otherwise inherits the main one.
        enable_analysis=True,
        analysis_use_code_execution=os.environ.get("MERCHANT_ANALYSIS_CODE_EXECUTION", "0") == "1",
        analysis_model=os.environ.get("MERCHANT_ANALYSIS_MODEL") or None,
    )
