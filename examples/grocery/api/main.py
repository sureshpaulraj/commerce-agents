# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""Riverbend Market example API: the mock grocery retailer behind the shared storefront
routes, the merchant router under /api/merchant, and the grocery-only routes below.

    uvicorn grocery.api.main:app --app-dir examples --reload --port 8005

The one thing this deployment adds to the shopping agent's tool surface is
``present_meal_plan`` (``meals.py``): the servings arithmetic runs on the server against
each product's stored pack size, so the model composes the meals but never produces the
numbers, and the same call refuses any item whose allergen statement is unverified.

Memory here is file-backed (``data/.memory-store.json``, gitignored) and seeded once per
user, so what a shopper asks the store to remember, or to forget, survives a restart.
"""

from __future__ import annotations

from fastapi.staticfiles import StaticFiles

from commerce_common.memory import InMemoryMemoryStore, JsonFileMemoryStore
from demo_common import (
    REPO_ROOT,
    CartAddRequest,
    MemorySeeder,
    build_storefront_host,
    demo_model_client,
    load_demo_env,
)
from shopping_agent import ProductDetails
from shopping_agent_runtime import ShoppingAgent

from .agent_config import build_shopping_config
from .meals import build_meal_plan_extension
from .merchant import create_merchant_router
from .mock_grocery import DATA_DIR, MockGrocery

load_demo_env(DATA_DIR.parent)
PRODUCT_IMAGES = DATA_DIR.parent / "storefront-web" / "public" / "products"

backend = MockGrocery()
agent = ShoppingAgent(
    backend=backend,
    skills_dir=REPO_ROOT / "shopping-agent" / "skills",
    config=build_shopping_config(),
    memory_store=JsonFileMemoryStore(DATA_DIR / ".memory-store.json"),
    extra_presentation_tools=[build_meal_plan_extension()],
    client=demo_model_client(),
)


def product_detail(product: ProductDetails) -> dict:
    # Detail-panel enrichment only; the agent's tool results never carry it.
    return product.model_dump() | {
        "price_intelligence": backend.price_intelligence(product.product_id),
        "review_aspects": backend.review_aspects(product.product_id),
        "substitutes": backend.substitutes_for(product.product_id),
    }


host = build_storefront_host(
    title="Riverbend Market demo API",
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
        note=(
            "Shopper tapped the add-to-cart button on {title} ({product_id}), quantity {quantity}."
        ),
    )
