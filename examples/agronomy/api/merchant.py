# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The Heartland Agronomy Supply merchant router: the shared portal routes over
``MockAgronomyMerchant``, plus the KPI trends and insight cards the portal's home page
shows."""

from __future__ import annotations

from fastapi import APIRouter

from commerce_common.memory import MemoryStore
from demo_common import REPO_ROOT, MerchantIdentity, build_merchant_router
from merchant_agent_runtime import MerchantAgent

from .agent_config import build_merchant_config
from .mock_agronomy import MockAgronomy
from .mock_merchant import MockAgronomyMerchant

IDENTITY = MerchantIdentity(merchant_id="heartland-agronomy", operator="Avery")


def create_merchant_router(storefront: MockAgronomy, memory_store: MemoryStore) -> APIRouter:
    config = build_merchant_config(storefront.store_name)
    merchant = MockAgronomyMerchant(storefront, config, merchant_id=IDENTITY.merchant_id)
    agent = MerchantAgent(
        backend=merchant,
        skills_dir=REPO_ROOT / "merchant-agent" / "skills",
        config=config,
        memory_store=memory_store,
    )
    return build_merchant_router(
        storefront=storefront,
        backend=merchant,
        agent=agent,
        identity=IDENTITY,
        example_dir="agronomy",
        overview_extras=lambda: {
            "trends": merchant.kpi_trends(),
            "trends_prior": merchant.kpi_trends(periods_back=1),
            "insights": merchant.home_insights(),
        },
    )
