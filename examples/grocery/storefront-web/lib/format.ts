// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

/** Image-less products get a tile color and glyph from id and category. */

const TILE_CLASSES = [
  "bg-amber-100 text-amber-900",
  "bg-emerald-100 text-emerald-900",
  "bg-sky-100 text-sky-900",
  "bg-rose-100 text-rose-900",
  "bg-violet-100 text-violet-900",
  "bg-lime-100 text-lime-900",
  "bg-orange-100 text-orange-900",
  "bg-cyan-100 text-cyan-900",
];

function hash(text: string): number {
  let value = 0;
  for (let i = 0; i < text.length; i++) {
    value = (value * 31 + text.charCodeAt(i)) >>> 0;
  }
  return value;
}

/** First match wins; order runs specific to general. */
const KEYWORD_GLYPHS: [string, string][] = [
  ["apple", "🍎"], ["berry", "🫐"], ["banana", "🍌"], ["salad", "🥗"],
  ["tomato", "🍅"], ["vegetable", "🥦"], ["produce", "🥬"],
  ["chicken", "🍗"], ["turkey", "🍗"], ["beef", "🥩"], ["meatball", "🍝"],
  ["milk", "🥛"], ["cheese", "🧀"], ["yogurt", "🥛"], ["egg", "🥚"],
  ["bread", "🍞"], ["tortilla", "🌯"], ["pasta", "🍝"], ["rice", "🍚"],
  ["bean", "🫘"], ["sauce", "🥫"], ["soup", "🥣"], ["cereal", "🥣"],
  ["coffee", "☕"], ["juice", "🧃"], ["sparkling", "🫧"], ["water", "💧"],
  ["meal", "🍽️"], ["dinner", "🍽️"], ["pizza", "🍕"], ["sandwich", "🥪"],
  ["paper", "🧻"], ["towel", "🧻"], ["soap", "🧼"], ["detergent", "🧺"],
  ["pharmacy", "💊"], ["fuel", "⛽"],
];

/** Rotated by product id so a same-category row varies. */
const CATEGORY_GLYPHS: Record<string, string[]> = {
  produce: ["🥬", "🍎", "🥦", "🍅"],
  meat: ["🥩", "🍗", "🥓", "🌭"],
  seafood: ["🐟", "🍤", "🦀", "🥫"],
  dairy: ["🥛", "🧀", "🧈", "🥚"],
  bakery: ["🍞", "🥖", "🥯", "🥐"],
  pantry: ["🥫", "🍝", "🍚", "🫘"],
  frozen: ["🧊", "🍕", "🥘", "🍦"],
  beverages: ["🧃", "☕", "💧", "🫖"],
  "prepared-foods": ["🍽️", "🥗", "🥪", "🍲"],
  household: ["🧻", "🧼", "🧺", "🧽"],
  pharmacy: ["💊", "🩹", "🧴", "🌡️"],
};

export function productGlyph(product: { title?: string; category?: string | null; product_id?: string }): string {
  const title = (product.title ?? "").toLowerCase();
  for (const [keyword, glyph] of KEYWORD_GLYPHS) {
    if (title.includes(keyword)) return glyph;
  }
  const pool = CATEGORY_GLYPHS[product.category ?? ""] ?? ["🛒"];
  return pool[hash(product.product_id ?? title) % pool.length];
}

export function productTileClass(productId: string): string {
  return TILE_CLASSES[hash(productId) % TILE_CLASSES.length];
}

/** These have their own renderers or are operational data, not shopper chips. */
const STAMPED_ATTRIBUTES = new Set([
  "allergen_source",
  "allergen_status",
  "delivery",
  "low_stock",
  "unit_count",
  "unit_of_measure",
]);

function humanizeUnit(value: string): string {
  return value
    .replace(/\bfl oz\b/gi, "fl oz")
    .replace(/\boz\b/gi, "oz")
    .replace(/\blb\b/gi, "lb")
    .replace(/\bct\b/gi, "ct")
    .replace(/\bqt\b/gi, "qt")
    .replace(/\bgal\b/gi, "gal");
}

export function attributeChips(product: { attributes?: Record<string, string> }): string[] {
  return Object.entries(product.attributes ?? {})
    .filter(([key]) => !STAMPED_ATTRIBUTES.has(key))
    .map(([key, value]) => {
      if (/^(yes|true)$/i.test(value)) return key.replaceAll("_", " ");
      if (/^(no|false)$/i.test(value)) return null;
      if (/^(none|n\/a|-)$/i.test(value)) return null;
      return humanizeUnit(value);
    })
    .filter((chip): chip is string => Boolean(chip))
    .slice(0, 3);
}
