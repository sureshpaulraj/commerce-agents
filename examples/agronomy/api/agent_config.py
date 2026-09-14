# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The Heartland Agronomy Supply deployment's two agent configs; the only place this
example reads deployment knobs from the environment."""

from __future__ import annotations

import os

from demo_common import host_approval_default
from merchant_agent import MerchantAgentConfig
from shopping_agent import ShoppingAgentConfig

_SHOPPING_DEFAULTS = ShoppingAgentConfig()
_MERCHANT_DEFAULTS = MerchantAgentConfig()

# Agronomy vocabulary added to the policy-grounding lexicon, so a question about a label
# restriction, a rotation interval, or a licence forces a help-content read first.
_POLICY_TERMS = (
    "label",
    "restricted",
    "restricted-use",
    "licence",
    "license",
    "applicator",
    "certified",
    "rotation",
    "rotational",
    "preharvest",
    "phi",
    "rei",
    "buffer",
    "drift",
    "cleanout",
    "compatible",
    "compatibility",
    "storage",
    "disposal",
    "prepay",
)

# Agronomy vocabulary added to the metrics-grounding lexicon on the merchant side.
_METRICS_TERMS = (
    "acres",
    "acre",
    "prepay",
    "booked",
    "season",
    "program",
    "branch",
    "tote",
    "jug",
)


def build_shopping_config() -> ShoppingAgentConfig:
    return ShoppingAgentConfig(
        brand_name="Heartland Agronomy Supply",
        assistant_name="Heartland Assistant",
        brand_voice="plain-spoken, precise about numbers, and never casual about a label",
        domain_search_notes=(
            "Crop inputs are chosen against an agronomic situation, not a shopper's "
            "taste: when the grower has named a crop, a target weed or pest, or a "
            "timing, pass them as filters.attributes['crop'], "
            "filters.attributes['target'], and filters.attributes['timing'] so the "
            "catalog does the matching. Never state an application rate, a product "
            "volume, a container count, or a preharvest interval from your own "
            "reasoning: the label rate range lives on the product record, and the "
            "arithmetic belongs to present_application_plan, which computes it on the "
            "server and refuses a rate outside that range."
        ),
        policy_intent_terms=_SHOPPING_DEFAULTS.policy_intent_terms + _POLICY_TERMS,
    )


def build_merchant_config(store_name: str) -> MerchantAgentConfig:
    return MerchantAgentConfig(
        brand_name=store_name,
        require_host_approval=host_approval_default(),
        approval_surface="the Approve button on the change preview card",
        metrics_intent_terms=_MERCHANT_DEFAULTS.metrics_intent_terms + _METRICS_TERMS,
        # This deployment runs the run_analysis delegate over MockAgronomyMerchant's
        # read-only SQL view of the fixtures. MERCHANT_ANALYSIS_CODE_EXECUTION=1 adds the
        # code-execution sandbox (first-party API only); MERCHANT_ANALYSIS_MODEL overrides
        # the delegate's model, which otherwise inherits the main one.
        enable_analysis=True,
        analysis_use_code_execution=os.environ.get("MERCHANT_ANALYSIS_CODE_EXECUTION", "0") == "1",
        analysis_model=os.environ.get("MERCHANT_ANALYSIS_MODEL") or None,
    )
