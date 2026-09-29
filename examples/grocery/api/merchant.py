# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The Riverbend Market merchant router: the shared portal routes over
``MockGroceryMerchant``, plus the KPI trends and insight cards the portal's home page
shows."""

from __future__ import annotations

from fastapi import APIRouter

from commerce_common.memory import MemoryStore
from demo_common import REPO_ROOT, MerchantIdentity, build_merchant_router, demo_model_client
from merchant_agent_runtime import MerchantAgent

from .agent_config import build_merchant_config
from .mock_grocery import MockGrocery
from .mock_merchant import MockGroceryMerchant

IDENTITY = MerchantIdentity(merchant_id="riverbend-market", operator="Dana")


def create_merchant_router(storefront: MockGrocery, memory_store: MemoryStore) -> APIRouter:
    config = build_merchant_config(storefront.store_name)
    merchant = MockGroceryMerchant(storefront, config, merchant_id=IDENTITY.merchant_id)
    agent = MerchantAgent(
        backend=merchant,
        skills_dir=REPO_ROOT / "merchant-agent" / "skills",
        config=config,
        memory_store=memory_store,
        client=demo_model_client(),
    )
    return build_merchant_router(
        storefront=storefront,
        backend=merchant,
        agent=agent,
        identity=IDENTITY,
        example_dir="grocery",
        overview_extras=lambda: {
            "trends": merchant.kpi_trends(),
            "trends_prior": merchant.kpi_trends(periods_back=1),
            "insights": merchant.home_insights(),
        },
    )
