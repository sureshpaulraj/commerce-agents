# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The grocery example's ``StorefrontBackend`` over the fixtures in ``data/``: keyword
search, per-session carts, fixture orders and policies. An adopter replaces this class
with calls to their own catalog, cart, and order systems."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from demo_common.storefront_fixtures import (
    SessionCarts,
    example_data_dir,
    find_order,
    find_product,
    keyword_score,
    load_catalog,
    load_orders,
    load_policies,
    load_users,
    newest_orders,
    option_text,
    orders_for,
    preferences_of,
    rank_products,
    search_help,
    summary_of,
    unavailable_detail,
    within_price_and_rating,
)
from shopping_agent import (
    Cart,
    FulfillmentOption,
    Order,
    Policy,
    Product,
    ProductDetails,
    SearchFilters,
    ShoppingSessionContext,
    StorefrontBackend,
    Unavailable,
    UserPreferences,
)

DATA_DIR = example_data_dir(__file__)

# Attributes stamped onto products at boot rather than authored in the catalog. The
# merchant side re-stamps LOW_STOCK_ATTRIBUTE when an applied change moves the number.
DELIVERY_ATTRIBUTE = "delivery"
LOW_STOCK_ATTRIBUTE = "low_stock"
_STAMPED_ATTRIBUTES = {DELIVERY_ATTRIBUTE, LOW_STOCK_ATTRIBUTE}

_SEARCH_WEIGHTS = {
    "title": 3.0,
    "brand": 2.0,
    "category": 2.0,
    "attributes": 1.5,
    "description": 1.0,
}
# Groceries are searched for the way people talk about food: by dish, by diet, by the
# word on the shopping list rather than the word on the package.
_SYNONYMS: dict[str, list[str]] = {
    "veg": ["vegetable", "vegetables", "produce"],
    "vegetable": ["vegetables", "produce", "veg"],
    "fruit": ["fruits", "produce"],
    "greens": ["lettuce", "spinach", "salad"],
    "salad": ["lettuce", "greens", "spinach"],
    "mince": ["ground", "beef"],
    "ground": ["mince", "beef"],
    "chicken": ["poultry", "breast", "thigh"],
    "poultry": ["chicken", "turkey"],
    "fish": ["seafood", "salmon", "cod"],
    "seafood": ["fish", "shrimp", "salmon"],
    "prawns": ["shrimp", "seafood"],
    "shrimp": ["prawns", "seafood"],
    "soda": ["pop", "soft drink", "cola"],
    "pop": ["soda", "soft drink"],
    "crisps": ["chips", "snacks"],
    "chips": ["crisps", "snacks"],
    "biscuits": ["cookies", "crackers"],
    "cookies": ["biscuits", "snacks"],
    "pasta": ["spaghetti", "penne", "noodles", "macaroni"],
    "noodles": ["pasta", "spaghetti"],
    "sauce": ["marinara", "salsa", "tomato"],
    "tomato": ["tomatoes", "marinara", "sauce"],
    "milk": ["dairy"],
    "cheese": ["dairy", "cheddar", "mozzarella"],
    "yoghurt": ["yogurt", "dairy"],
    "yogurt": ["yoghurt", "dairy"],
    "bread": ["loaf", "bakery", "rolls"],
    "loaf": ["bread", "bakery"],
    "tortilla": ["tortillas", "wraps"],
    "wraps": ["tortillas", "tortilla"],
    "beans": ["legumes", "pinto", "black beans"],
    "rice": ["grain", "grains"],
    "cereal": ["breakfast", "granola", "oats"],
    "oats": ["oatmeal", "cereal", "breakfast"],
    "coffee": ["beans", "ground coffee", "breakfast"],
    "juice": ["beverage", "beverages"],
    "water": ["sparkling", "beverage"],
    "beer": ["ale", "lager", "alcohol"],
    "wine": ["alcohol"],
    "diapers": ["nappies", "baby"],
    "nappies": ["diapers", "baby"],
    "detergent": ["laundry", "household", "cleaner"],
    "cleaner": ["household", "detergent"],
    "paper towels": ["household", "towels"],
    "glutenfree": ["gluten-free", "gluten free"],
    "gf": ["gluten-free"],
    "vegan": ["plant-based", "dairy-free"],
    "plantbased": ["vegan", "plant-based"],
    "keto": ["low-carb", "high-protein"],
    "organic": ["natural"],
    "dinner": ["meal", "supper", "entree"],
    "meal": ["dinner", "entree", "prepared"],
    "prepared": ["riverbend-table", "deli", "ready"],
    "deli": ["prepared", "riverbend-table"],
    "party": ["tray", "platter", "catering"],
    "snack": ["snacks", "chips", "crackers"],
    "allergy": ["allergen", "allergens", "free-from"],
    "allergen": ["allergy", "allergens"],
    "peanut": ["peanuts", "nut", "allergen"],
    "nut": ["nuts", "tree nuts", "peanuts"],
    "cheap": ["value", "everyday", "budget"],
    "budget": ["value", "everyday", "cheap"],
    "store brand": ["private label", "riverbend"],
    "own brand": ["private label", "riverbend"],
}

# Review-aspect vocabularies per department (invented, like the reviews themselves).
_ASPECTS_BY_CATEGORY: dict[str, list[str]] = {
    "produce": ["Freshness on arrival", "Ripeness", "How long it keeps", "Value"],
    "meat-and-seafood": ["Freshness", "Trim and marbling", "Portion size", "Value"],
    "dairy-and-eggs": ["Freshness", "Taste", "How long it keeps", "Value"],
    "bakery": ["Freshness", "Texture", "Taste", "How long it keeps"],
    "frozen": ["Taste", "Ease of cooking", "Portion size", "Value"],
    "pantry": ["Taste", "Consistency", "Ingredients", "Value"],
    "beverages": ["Taste", "Sweetness", "Packaging", "Value"],
    "snacks": ["Taste", "Crunch", "Portion size", "Value"],
    "breakfast": ["Taste", "Texture", "Ingredients", "Value"],
    "household": ["Effectiveness", "Scent", "Durability", "Value"],
    "baby": ["Gentleness", "Fit", "Absorbency", "Value"],
    "health-and-beauty": ["Effectiveness", "Scent", "Skin feel", "Value"],
    "riverbend-table": ["Taste", "Freshness", "Portion size", "Reheats well"],
    "floral": ["Freshness on arrival", "Vase life", "Arrangement", "Value"],
}
_ASPECTS_FALLBACK = ["Quality", "As described", "Value"]

# The terms of the delivery entry in policies.json, which is what the agent quotes;
# test_mock_grocery checks that the entry still states each of them.
FREE_DELIVERY_OVER = 75
PICKUP_MINIMUM = 35
DELIVERY_FEE = 7.95
EXPRESS_DELIVERY_FEE = 12.95
# Shelf-stable departments can also go by parcel; a chilled or frozen item cannot.
_SHIPPABLE_DEPARTMENTS = {"pantry", "household", "health-and-beauty", "baby", "snacks"}
PARCEL_SHIPPING = FulfillmentOption(
    method="shipping", eta="3-5 business days (shelf-stable items only)", fee=6.99
)
_STORE_OPENS, _STORE_CLOSES = 7, 21
_PICKUP_LEAD_HOURS = 2


class MockGrocery(StorefrontBackend):
    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        catalog, self.products, self.variants = load_catalog(data_dir)
        self.store_name: str = catalog.get("store_name", "the store")
        self._users = load_users(data_dir)
        self._orders = load_orders(data_dir)
        self._policies = load_policies(data_dir)
        self._carts = SessionCarts()
        self._align_delivery_policy_terms()
        self._stamp_delivery_promises()
        self._stamp_low_stock(data_dir)

    def _align_delivery_policy_terms(self) -> None:
        """Keep the quoted policy text aligned with the fulfillment options."""
        for index, policy in enumerate(self._policies):
            if policy.policy_id != "pickup-delivery-windows-fees":
                continue
            express = f"${EXPRESS_DELIVERY_FEE:.2f} express delivery fee"
            if express in policy.content:
                return
            self._policies[index] = policy.model_copy(
                update={
                    "content": (
                        f"{policy.content} Express delivery arrives within 2 hours with a "
                        f"{express}."
                    )
                }
            )
            return

    def _stamp_delivery_promises(self) -> None:
        """A "Ready by <day>" attribute on every in-stock product. A perishable item is
        picked the same day or the next; a shelf-stable one carries the same stable 1-3
        day offset the rest of the catalog uses, so promises stay current and a
        product's promise is the same for the whole run."""
        boot = datetime.now()
        for product in self.products.values():
            if not product.in_stock:
                continue
            perishable = product.attributes.get("perishable") == "yes"
            offset = 1 if perishable else 1 + sum(ord(ch) for ch in product.product_id) % 3
            promised = boot + timedelta(days=offset)
            label = f"Ready by {promised.strftime('%a, %b')} {promised.day}"
            product.attributes[DELIVERY_ATTRIBUTE] = label
            # A family's in-stock variants are picked on the family's promise.
            for variant in product.variants:
                if (record := self.variants.get(variant.product_id)) and record.in_stock:
                    record.attributes[DELIVERY_ATTRIBUTE] = label

    def _stamp_low_stock(self, data_dir: Path) -> None:
        """The "only N left" attribute, taken from the same inventory rows the merchant
        portal shows, so the storefront's scarcity chip and the portal agree."""
        overlay_path = data_dir / "merchant_inventory.json"
        if not overlay_path.exists():
            return
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
        default_threshold = int(overlay.get("default_threshold", 8))
        for row in overlay.get("inventory", []):
            product = self.product(row.get("product_id", ""))
            if product is None or not product.in_stock:
                continue
            stock = int(row.get("stock", 0))
            if 0 < stock <= int(row.get("threshold", default_threshold)):
                product.attributes[LOW_STOCK_ATTRIBUTE] = str(stock)

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    def listing_of(self, product_id: str) -> ProductDetails | None:
        """The listing an id belongs to: itself, or its family when it is a variant."""
        record = self.product(product_id)
        if record is not None and record.variant_of:
            return self.products.get(record.variant_of)
        return record

    def _searchable_text(self, product: ProductDetails) -> dict[str, str]:
        return {
            "title": product.title,
            "brand": product.brand or "",
            "category": product.category or "",
            "attributes": " ".join(
                f"{k} {v}" for k, v in product.attributes.items() if k not in _STAMPED_ATTRIBUTES
            )
            + " "
            + option_text(product),
            "description": f"{product.short_description or ''} {product.long_description or ''}",
        }

    def _score(self, product: ProductDetails, query_tokens: list[str]) -> float:
        return keyword_score(
            self._searchable_text(product), _SEARCH_WEIGHTS, query_tokens, _SYNONYMS
        )

    @staticmethod
    def _soft_filter(product: ProductDetails, filters: SearchFilters) -> bool:
        if filters.category and filters.category.lower() not in (product.category or "").lower():
            return False
        if not filters.attributes:
            return True
        haystack = " ".join(
            f"{k}={v}".lower()
            for k, v in product.attributes.items()
            if k not in _STAMPED_ATTRIBUTES
        )
        haystack += f" {product.title.lower()} {option_text(product).lower()}"
        return all(str(value).lower() in haystack for value in filters.attributes.values())

    async def search_products(
        self,
        session: ShoppingSessionContext,
        query: str,
        filters: SearchFilters | None = None,
        limit: int = 8,
    ) -> list[Product]:
        del session
        ranked = rank_products(
            self.products.values(),
            query,
            filters,
            limit,
            score=self._score,
            hard_filter=within_price_and_rating,
            soft_filter=self._soft_filter,
        )
        return [summary_of(product) for product in ranked]

    def product(self, product_id: str) -> ProductDetails | None:
        return find_product(self.products, self.variants, product_id)

    async def get_product_details(
        self, session: ShoppingSessionContext, product_id: str
    ) -> ProductDetails | None:
        del session
        return self.product(product_id)

    def substitutes_for(self, product_id: str) -> list[dict[str, Any]]:
        """The substitutes a product names, each with the one fact that decides whether
        the store may offer it: whether its allergen statement is verified. Read by the
        merchant portal's substitution view and by the storefront detail panel; the
        agent never sees it, because ``present_meal_plan`` enforces the same rule in
        code rather than asking the model to respect it."""
        product = self.product(product_id)
        if product is None:
            return []
        raw = (product.attributes.get("substitutes") or "").strip()
        if not raw or raw.lower() == "none":
            return []
        rows: list[dict[str, Any]] = []
        for candidate_id in (part.strip() for part in raw.split(",")):
            candidate = self.product(candidate_id)
            if candidate is None:
                continue
            attributes = candidate.attributes
            verified = (attributes.get("allergen_status") or "").lower() == "verified"
            rows.append(
                {
                    "product_id": candidate.product_id,
                    "title": candidate.title,
                    "brand": candidate.brand,
                    "price": candidate.price,
                    "in_stock": candidate.in_stock,
                    "allergen_status": attributes.get("allergen_status"),
                    "allergens": attributes.get("allergens"),
                    "offerable": verified and candidate.in_stock,
                    "blocked_reason": (
                        None
                        if verified and candidate.in_stock
                        else "allergen statement not verified"
                        if not verified
                        else "out of stock"
                    ),
                }
            )
        return rows

    def price_intelligence(self, product_id: str) -> dict[str, Any] | None:
        """A 90-day price series derived from the product id, ending at today's price,
        with a verdict computed from where that price sits in the series' range. Read
        by the storefront's detail panel; the agent never sees it."""
        product = self.product(product_id)
        if product is None or product.price <= 0:
            return None
        digest = hashlib.sha256(product_id.encode("utf-8")).digest()
        amplitude = product.price * (0.06 + (digest[0] / 255) * 0.08)
        phase = (digest[1] / 255) * 2 * math.pi
        drift = ((digest[2] / 255) - 0.5) * 0.5
        points = 13
        series = []
        for i in range(points):
            wobble = math.sin(phase + i * 1.1) + 0.4 * math.sin(phase * 2 + i * 2.3)
            trend = drift * (i - points + 1) / points
            series.append(round(max(product.price + amplitude * (wobble / 1.4 + trend), 0.5), 2))
        series[-1] = product.price
        low, high = min(series), max(series)
        if high - low < 0.01:
            position = "typical"
        else:
            ratio = (product.price - low) / (high - low)
            position = "low" if ratio <= 0.25 else "high" if ratio >= 0.75 else "typical"
        verdict = {
            "low": f"${product.price:.2f} is near this item's 90-day low",
            "typical": f"${product.price:.2f} is this item's typical price",
            "high": f"${product.price:.2f} is above this item's typical price",
        }[position]
        return {
            "days": 90,
            "series": series,
            "low": low,
            "high": high,
            "position": position,
            "verdict": f"{verdict} (90-day range ${low:.2f}–${high:.2f})",
        }

    def review_aspects(self, product_id: str) -> dict[str, Any] | None:
        """Review-aspect chips derived from the product id, with sentiment anchored to
        its rating and mention counts bounded by its review count. Detail panel only."""
        product = self.listing_of(product_id)
        if product is None or not product.review_count or product.review_count < 25:
            return None
        digest = hashlib.sha256(f"aspects:{product.product_id}".encode()).digest()
        names = _ASPECTS_BY_CATEGORY.get(product.category or "", _ASPECTS_FALLBACK)
        count = 3 if len(names) < 4 or digest[0] % 2 == 0 else 4
        rating = product.rating or 4.2
        mention_share = 0.32 + (digest[1] / 255) * 0.2
        aspects = []
        for i, name in enumerate(names[:count]):
            jitter = (digest[2 + i] / 255 - 0.5) * 14
            positive_pct = round(min(97.0, max(45.0, rating * 20 - 4 + jitter - i * 3)))
            share = mention_share * (0.45 if i == 0 else 0.55 / max(count - 1, 1))
            floor = min(12, product.review_count // (count + 1))
            mentions = max(int(product.review_count * share), floor, 1)
            aspects.append({"name": name, "positive_pct": int(positive_pct), "mentions": mentions})
        return {"review_count": product.review_count, "aspects": aspects}

    # ------------------------------------------------------------------
    # Cart
    # ------------------------------------------------------------------

    async def get_cart(self, session: ShoppingSessionContext) -> Cart:
        return self._carts.cart(session.session_id)

    async def add_to_cart(
        self, session: ShoppingSessionContext, product_id: str, quantity: int
    ) -> Cart:
        product = self.product(product_id)
        if product is None or product.has_options:
            # The executor's gates hold both cases before they reach a backend; a real
            # cart service refuses them on its own terms too.
            raise KeyError(product_id)
        if not product.in_stock:
            raise Unavailable(unavailable_detail(product, self.listing_of(product_id)))
        existing = self._carts.lines(session.session_id).get(product_id)
        quantity += existing.quantity if existing else 0
        return self._carts.put(session.session_id, product, quantity)

    async def update_cart_item(
        self, session: ShoppingSessionContext, product_id: str, quantity: int
    ) -> Cart:
        return self._carts.set_quantity(session.session_id, product_id, quantity)

    async def remove_from_cart(self, session: ShoppingSessionContext, product_id: str) -> Cart:
        return self._carts.remove(session.session_id, product_id)

    def reset_session(self, session_id: str) -> None:
        self._carts.reset(session_id)

    # ------------------------------------------------------------------
    # Customer, orders, help content, fulfillment
    # ------------------------------------------------------------------

    async def get_preferences(self, session: ShoppingSessionContext) -> UserPreferences:
        return preferences_of(self._users, session.user_id)

    async def get_orders(self, session: ShoppingSessionContext, limit: int = 5) -> list[Order]:
        return orders_for(self._orders, session.user_id, limit)

    async def get_order(self, session: ShoppingSessionContext, order_id: str) -> Order | None:
        return find_order(self._orders, session.user_id, order_id)

    def recent_orders(self, limit: int = 6) -> list[Order]:
        return newest_orders(self._orders, limit)

    async def search_policies(self, session: ShoppingSessionContext, query: str) -> list[Policy]:
        del session
        return search_help(self._policies, query)

    @staticmethod
    def _next_slot(now: datetime) -> tuple[datetime, bool]:
        """The first slot that can be picked: two hours from now, or from opening,
        rounded up to the top of an hour. The flag says whether it lands today."""
        opens = now.replace(hour=_STORE_OPENS, minute=0, second=0, microsecond=0)
        ready = max(now, opens) + timedelta(hours=_PICKUP_LEAD_HOURS)
        if ready.minute or ready.second or ready.microsecond:
            ready = ready.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        if ready.date() != now.date() or ready.hour > _STORE_CLOSES:
            return opens + timedelta(days=1), False
        return ready, True

    @classmethod
    def _slot_label(cls, now: datetime, verb: str) -> str:
        """A slot promised the way a store says it: "ready today by 4 PM", or the first
        window tomorrow once the day's picking is done."""
        ready, today = cls._next_slot(now)
        hour12 = ready.hour % 12 or 12
        clock = f"{hour12} {'AM' if ready.hour < 12 else 'PM'}"
        return f"{verb} today by {clock}" if today else f"{verb} tomorrow from {clock}"

    @classmethod
    def _pickup_eta(cls, now: datetime) -> str:
        return cls._slot_label(now, "ready")

    async def get_fulfillment_options(
        self, session: ShoppingSessionContext, product_ids: list[str]
    ) -> list[FulfillmentOption]:
        prefs = await self.get_preferences(session)
        location = prefs.default_location or "your area"
        quoted = [product for pid in product_ids if (product := self.product(pid))]
        basket_total = sum(product.price for product in quoted)
        now = datetime.now()

        delivery = FulfillmentOption(
            method="delivery", eta=self._slot_label(now, "arrives"), fee=DELIVERY_FEE
        )
        if basket_total > FREE_DELIVERY_OVER:
            delivery = delivery.model_copy(update={"fee": 0.0})
        options = [
            # Grocery is a pickup-first business, so curbside leads.
            FulfillmentOption(
                method="pickup",
                eta=self._pickup_eta(now),
                fee=0.0,
                location=f"Riverbend Market {location}",
            ),
            delivery,
            FulfillmentOption(
                method="delivery", eta="arrives within 2 hours (express)", fee=EXPRESS_DELIVERY_FEE
            ),
        ]
        if quoted and all(
            product.attributes.get("department") in _SHIPPABLE_DEPARTMENTS
            and product.attributes.get("perishable") != "yes"
            for product in quoted
        ):
            options.append(PARCEL_SHIPPING)
        return options
