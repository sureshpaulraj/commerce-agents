# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""Heartland Agronomy Supply example API: the mock crop-input retailer behind the shared
storefront routes, the merchant router under /api/merchant, and the agronomy-only routes
below.

    uvicorn agronomy.api.main:app --app-dir examples --reload --port 8004

The one thing this deployment adds to the shopping agent's tool surface is
``present_application_plan`` (``rates.py``): the acreage and tank-mix arithmetic runs on
the server against each product's stored label rate range, so the model chooses products
and rates but never produces the numbers.

Memory here is file-backed (``data/.memory-store.json``, gitignored) and seeded once per
user, so what a grower asks the store to remember, or to forget, survives a restart.
"""

from __future__ import annotations

from fastapi.staticfiles import StaticFiles

from commerce_common.memory import InMemoryMemoryStore, JsonFileMemoryStore
from demo_common import (
    REPO_ROOT,
    CartAddRequest,
    MemorySeeder,
    build_storefront_host,
    load_demo_env,
)
from shopping_agent import ProductDetails
from shopping_agent_runtime import ShoppingAgent

from .agent_config import build_shopping_config
from .merchant import create_merchant_router
from .mock_agronomy import DATA_DIR, MockAgronomy
from .rates import build_application_plan_extension

load_demo_env(DATA_DIR.parent)
PRODUCT_IMAGES = DATA_DIR.parent / "storefront-web" / "public" / "products"

backend = MockAgronomy()
agent = ShoppingAgent(
    backend=backend,
    skills_dir=REPO_ROOT / "shopping-agent" / "skills",
    config=build_shopping_config(),
    memory_store=JsonFileMemoryStore(DATA_DIR / ".memory-store.json"),
    extra_presentation_tools=[build_application_plan_extension()],
)


def product_detail(product: ProductDetails) -> dict:
    # Detail-panel enrichment only; the agent's tool results never carry it.
    return product.model_dump() | {
        "price_intelligence": backend.price_intelligence(product.product_id),
        "review_aspects": backend.review_aspects(product.product_id),
    }


host = build_storefront_host(
    title="Heartland Agronomy Supply demo API",
    example_root=DATA_DIR.parent,
    backend=backend,
    agent=agent,
    memory_seeder=MemorySeeder(
        DATA_DIR / "memory-seed.json", marker=DATA_DIR / ".memory-seeded.json"
    ),
    product_detail=product_detail,
)
app = host.app
app.include_router(create_merchant_router(backend, InMemoryMemoryStore()), prefix="/api/merchant")
# The merchant portal shows the storefront's listing photos, so the API serves them to both apps.
app.mount("/products", StaticFiles(directory=PRODUCT_IMAGES, check_dir=False), name="products")


@app.post("/api/cart/add")
async def cart_add(request: CartAddRequest, record: host.CurrentSession) -> dict:
    return await host.direct_add(
        record,
        request,
        note="Grower tapped the add-to-cart button on {title} ({product_id}), quantity {quantity}.",
    )
