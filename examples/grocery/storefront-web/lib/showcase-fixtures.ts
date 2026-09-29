// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

/** Products are invented Riverbend Market grocery records. */

import type {
  CartPayload,
  CheckoutPayload,
  ComparisonPayload,
  GuidePayload,
  MealPlanItem,
  MealPlanPayload,
  OrderStatusPayload,
  PlanPayload,
  Product,
  ProductsPayload,
} from "./types";

const PENNE: Product = {
  product_id: "RB-1001",
  title: "Riverbend Everyday Penne Pasta",
  brand: "Riverbend Everyday",
  price: 1.79,
  currency: "USD",
  rating: 4.6,
  review_count: 428,
  category: "pantry",
  labels: ["bestseller"],
  attributes: {
    department: "Pantry",
    pack_size: "16 oz box",
    unit_count: "16",
    unit_of_measure: "oz",
    allergens: "wheat",
    may_contain: "none",
    allergen_status: "verified",
    allergen_source: "Riverbend supplier record",
    private_label: "yes",
    age_restricted: "no",
    snap_eligible: "yes",
    delivery: "Pickup today",
  },
  in_stock: true,
  short_description: "Everyday pasta for quick weeknight dinners.",
};

const SAUCE: Product = {
  product_id: "RB-1002",
  title: "Riverbend Selects Tomato Basil Pasta Sauce",
  brand: "Riverbend Selects",
  price: 3.49,
  currency: "USD",
  rating: 4.7,
  review_count: 319,
  category: "pantry",
  labels: [],
  attributes: {
    department: "Pantry",
    pack_size: "24 fl oz jar",
    unit_count: "24",
    unit_of_measure: "fl oz",
    allergens: "none",
    may_contain: "none",
    allergen_status: "verified",
    allergen_source: "Riverbend supplier record",
    private_label: "yes",
    age_restricted: "no",
    snap_eligible: "yes",
    delivery: "Pickup today",
  },
  in_stock: true,
  short_description: "Tomato sauce with basil for pasta, meatballs, and pantry meals.",
};

const MEATBALLS: Product = {
  product_id: "RB-1003",
  title: "Northfield Farms Turkey Meatballs",
  brand: "Northfield Farms",
  price: 6.99,
  currency: "USD",
  rating: 4.4,
  review_count: 206,
  category: "meat",
  labels: ["new"],
  attributes: {
    department: "Meat",
    pack_size: "20 oz tray",
    unit_count: "20",
    unit_of_measure: "oz",
    allergens: "wheat",
    may_contain: "milk",
    allergen_status: "verified",
    allergen_source: "Northfield Farms item sheet",
    private_label: "no",
    age_restricted: "no",
    snap_eligible: "yes",
    delivery: "Pickup today",
  },
  in_stock: true,
  short_description: "Fully cooked turkey meatballs for pasta night or sandwiches.",
};

const SALAD: Product = {
  product_id: "RB-1004",
  title: "Harvest Hollow Garden Salad Kit",
  brand: "Harvest Hollow",
  price: 4.49,
  currency: "USD",
  rating: 4.5,
  review_count: 184,
  category: "produce",
  labels: ["bestseller"],
  attributes: {
    department: "Produce",
    pack_size: "12 oz bag",
    unit_count: "12",
    unit_of_measure: "oz",
    allergens: "none",
    may_contain: "tree nuts",
    allergen_status: "verified",
    allergen_source: "Harvest Hollow pack statement",
    private_label: "no",
    age_restricted: "no",
    snap_eligible: "yes",
    delivery: "Pickup today",
    low_stock: "7",
  },
  in_stock: true,
  short_description: "Washed greens and vegetables for a fast dinner side.",
};

const CHICKEN: Product = {
  product_id: "RB-1005",
  title: "Northfield Farms Chicken Breast Family Pack",
  brand: "Northfield Farms",
  price: 13.99,
  currency: "USD",
  rating: 4.6,
  review_count: 512,
  category: "meat",
  labels: ["bestseller"],
  attributes: {
    department: "Meat",
    pack_size: "48 oz pack",
    unit_count: "48",
    unit_of_measure: "oz",
    allergens: "none",
    may_contain: "none",
    allergen_status: "verified",
    allergen_source: "Northfield Farms item sheet",
    private_label: "no",
    age_restricted: "no",
    snap_eligible: "yes",
    delivery: "Pickup today",
  },
  in_stock: true,
  short_description: "Family-size pack for tacos, bowls, and easy dinners.",
};

const TORTILLAS: Product = {
  product_id: "RB-1006",
  title: "Mill & Meadow Flour Tortillas",
  brand: "Mill & Meadow",
  price: 2.99,
  currency: "USD",
  rating: 4.5,
  review_count: 271,
  category: "bakery",
  labels: [],
  attributes: {
    department: "Bakery",
    pack_size: "10 ct pack",
    unit_count: "10",
    unit_of_measure: "ct",
    allergens: "wheat",
    may_contain: "soybeans",
    allergen_status: "verified",
    allergen_source: "Mill & Meadow pack statement",
    private_label: "no",
    age_restricted: "no",
    snap_eligible: "yes",
    delivery: "Pickup today",
  },
  in_stock: true,
  short_description: "Soft tortillas sized for tacos, wraps, and quesadillas.",
};

const CHEDDAR: Product = {
  product_id: "RB-1007",
  title: "Cedar Creek Dairy Shredded Cheddar",
  brand: "Cedar Creek Dairy",
  price: 3.29,
  currency: "USD",
  rating: 4.8,
  review_count: 362,
  category: "dairy",
  labels: ["bestseller"],
  attributes: {
    department: "Dairy",
    pack_size: "8 oz bag",
    unit_count: "8",
    unit_of_measure: "oz",
    allergens: "milk",
    may_contain: "none",
    allergen_status: "verified",
    allergen_source: "Cedar Creek Dairy pack statement",
    private_label: "no",
    age_restricted: "no",
    snap_eligible: "yes",
    delivery: "Pickup today",
  },
  in_stock: true,
  short_description: "Shredded cheddar for tacos, bowls, and casseroles.",
};

const RICE: Product = {
  product_id: "RB-1008",
  title: "Riverbend Everyday Long Grain Rice",
  brand: "Riverbend Everyday",
  price: 2.69,
  currency: "USD",
  rating: 4.5,
  review_count: 244,
  category: "pantry",
  labels: [],
  attributes: {
    department: "Pantry",
    pack_size: "32 oz bag",
    unit_count: "32",
    unit_of_measure: "oz",
    allergens: "none",
    may_contain: "none",
    allergen_status: "verified",
    allergen_source: "Riverbend supplier record",
    private_label: "yes",
    age_restricted: "no",
    snap_eligible: "yes",
    delivery: "Pickup today",
  },
  in_stock: true,
  short_description: "Pantry rice for bowls, sides, and batch cooking.",
};

const BEANS: Product = {
  product_id: "RB-1009",
  title: "Copperline Black Beans",
  brand: "Copperline",
  price: 1.19,
  currency: "USD",
  rating: 4.4,
  review_count: 197,
  category: "pantry",
  labels: [],
  attributes: {
    department: "Pantry",
    pack_size: "15 oz can",
    unit_count: "15",
    unit_of_measure: "oz",
    allergens: "none",
    may_contain: "none",
    allergen_status: "verified",
    allergen_source: "Copperline pack statement",
    private_label: "no",
    age_restricted: "no",
    snap_eligible: "yes",
    delivery: "Pickup today",
  },
  in_stock: true,
  short_description: "Black beans for bowls, tacos, and pantry meals.",
};

const VEGETABLES: Product = {
  product_id: "RB-1010",
  title: "Bluestem Fajita Vegetable Blend",
  brand: "Bluestem",
  price: 3.99,
  currency: "USD",
  rating: 4.3,
  review_count: 156,
  category: "frozen",
  labels: [],
  attributes: {
    department: "Frozen",
    pack_size: "16 oz bag",
    unit_count: "16",
    unit_of_measure: "oz",
    allergens: "none",
    may_contain: "none",
    allergen_status: "verified",
    allergen_source: "Bluestem pack statement",
    private_label: "no",
    age_restricted: "no",
    snap_eligible: "yes",
    delivery: "Pickup today",
  },
  in_stock: true,
  short_description: "Frozen peppers and onions ready for tacos or rice bowls.",
};

const APPLES: Product = {
  product_id: "RB-1011",
  title: "Harvest Hollow Apples",
  brand: "Harvest Hollow",
  price: 4.99,
  currency: "USD",
  rating: 4.7,
  review_count: 288,
  category: "produce",
  labels: [],
  attributes: {
    department: "Produce",
    pack_size: "3 lb bag",
    unit_count: "3",
    unit_of_measure: "lb",
    allergens: "none",
    may_contain: "none",
    allergen_status: "verified",
    allergen_source: "Harvest Hollow pack statement",
    private_label: "no",
    age_restricted: "no",
    snap_eligible: "yes",
    delivery: "Pickup today",
  },
  in_stock: true,
  short_description: "Crisp apples for lunches and dinner sides.",
};

function line(
  product: Product,
  quantityPerServing: number,
  quantityUnit: string,
  totalNeeded: number,
  totalUnit: string,
  packs: number,
  leftover: number,
): MealPlanItem {
  const allergens = product.attributes?.allergens;
  const mayContain = product.attributes?.may_contain;
  return {
    product,
    quantity_per_serving: quantityPerServing,
    quantity_unit: quantityUnit,
    total_needed: totalNeeded,
    total_unit: totalUnit,
    pack_size: product.attributes?.pack_size,
    packs,
    line_cost: Number((packs * product.price).toFixed(2)),
    currency: product.currency ?? "USD",
    leftover,
    department: product.attributes?.department,
    allergens: !allergens || allergens === "none" ? [] : allergens.split(",").map((value) => value.trim()),
    may_contain: !mayContain || mayContain === "none" ? [] : mayContain.split(",").map((value) => value.trim()),
    allergen_status: "verified",
    allergen_source: product.attributes?.allergen_source,
    private_label: product.attributes?.private_label === "yes",
    age_restricted: product.attributes?.age_restricted === "yes",
    snap_eligible: product.attributes?.snap_eligible === "yes",
  };
}

const products: ProductsPayload = {
  title: "Family dinner basket starters",
  layout: "carousel",
  items: [
    {
      product: CHICKEN,
      reason: "A larger pack lowers the per-meal protein cost when it is used across tacos and bowls.",
    },
    {
      product: PENNE,
      reason: "Riverbend Everyday pasta keeps one dinner inexpensive and shelf-stable.",
    },
    {
      product: SALAD,
      reason: "The fastest fresh side for pasta night, with a verified allergen statement.",
    },
    {
      product: RICE,
      reason: "A pantry base that stretches leftovers into lunch bowls.",
    },
  ],
};

const comparison: ComparisonPayload = {
  title: "Family pack chicken vs. two small packs",
  entries: [
    {
      product_id: "RB-1005",
      product: CHICKEN,
      best_for: "Batching protein across several meals for a household",
      pros: [
        "One pack covers tacos and rice bowls",
        "Lowest price per ounce in this basket",
        "Verified allergen statement shows no declared allergens",
      ],
      cons: ["Needs cooking or freezing within the freshness window", "One larger package to portion at home"],
    },
    {
      product_id: "RB-1003",
      product: MEATBALLS,
      best_for: "A faster pasta dinner with less prep",
      pros: ["Fully cooked for a quick dinner", "Works with the pasta and sauce already in the basket"],
      cons: ["Higher cost per serving", "Contains wheat and may contain milk"],
    },
  ],
  dimensions: ["Price per ounce", "Prep time", "Allergen statement", "Leftover flexibility"],
  recommended_product_id: "RB-1005",
};

const meal_plan: MealPlanPayload = {
  title: "Three weeknight dinners for five",
  servings: 5,
  meals: [
    {
      name: "Pasta night with turkey meatballs",
      servings: 5,
      items: [
        line(PENNE, 3, "oz", 15, "oz", 1, 1),
        line(SAUCE, 3, "fl oz", 15, "fl oz", 1, 9),
        line(MEATBALLS, 4, "oz", 20, "oz", 1, 0),
        line(SALAD, 2, "oz", 10, "oz", 1, 2),
      ],
    },
    {
      name: "Chicken tacos",
      servings: 5,
      items: [
        line(CHICKEN, 5, "oz", 25, "oz", 1, 23),
        line(TORTILLAS, 2, "ct", 10, "ct", 1, 0),
        line(CHEDDAR, 1, "oz", 5, "oz", 1, 3),
        line(VEGETABLES, 3, "oz", 15, "oz", 1, 1),
      ],
    },
    {
      name: "Rice and black bean bowls",
      servings: 5,
      items: [
        line(RICE, 2.5, "oz", 12.5, "oz", 1, 19.5),
        line(BEANS, 3, "oz", 15, "oz", 1, 0),
        line(CHEDDAR, 1, "oz", 5, "oz", 1, 3),
        line(APPLES, 0.2, "lb", 1, "lb", 1, 2),
      ],
      note: "Uses the rest of the chicken pack if the household wants extra protein.",
    },
  ],
  basket: [
    { product: CHICKEN, total_needed: 25, total_unit: "oz", packs: 1, line_cost: 13.99, currency: "USD" },
    { product: MEATBALLS, total_needed: 20, total_unit: "oz", packs: 1, line_cost: 6.99, currency: "USD" },
    { product: CHEDDAR, total_needed: 10, total_unit: "oz", packs: 2, line_cost: 6.58, currency: "USD" },
    { product: APPLES, total_needed: 1, total_unit: "lb", packs: 1, line_cost: 4.99, currency: "USD" },
    { product: SALAD, total_needed: 10, total_unit: "oz", packs: 1, line_cost: 4.49, currency: "USD" },
    { product: VEGETABLES, total_needed: 15, total_unit: "oz", packs: 1, line_cost: 3.99, currency: "USD" },
    { product: SAUCE, total_needed: 15, total_unit: "fl oz", packs: 1, line_cost: 3.49, currency: "USD" },
    { product: TORTILLAS, total_needed: 10, total_unit: "ct", packs: 1, line_cost: 2.99, currency: "USD" },
    { product: RICE, total_needed: 12.5, total_unit: "oz", packs: 1, line_cost: 2.69, currency: "USD" },
    { product: PENNE, total_needed: 15, total_unit: "oz", packs: 1, line_cost: 1.79, currency: "USD" },
    { product: BEANS, total_needed: 15, total_unit: "oz", packs: 1, line_cost: 1.19, currency: "USD" },
  ],
  item_count: 11,
  pack_count: 12,
  subtotal: 53.18,
  cost_per_serving: 3.55,
  currency: "USD",
  rewards_points: 531,
  fuel_cents_per_gal: 50,
  computed_by: "server",
  avoided_allergens: ["peanuts"],
  budget: 70,
  budget_headroom: 16.82,
  over_budget: false,
  note: "Riverbend Rewards points convert to cents-per-gallon savings at Riverbend Fuel Stop.",
};

const plan: PlanPayload = {
  title: "Dinner prep checklist",
  intro: "Four practical steps before the household starts the week.",
  steps: [
    { label: "Use fresh items first", detail: "Cook the chicken and salad meals early in the week.", products: [CHICKEN, SALAD] },
    { label: "Batch the pantry bases", detail: "Make rice once and use it for bowls and lunches.", products: [RICE, BEANS] },
    { label: "Keep allergy checks visible", detail: "Every item in the meal plan has a verified statement.", products: [PENNE, TORTILLAS] },
    { label: "Save with own brands", detail: "Riverbend Everyday covers the basket basics.", products: [PENNE, RICE] },
  ],
};

const guide: GuidePayload = {
  title: "How Riverbend Rewards fuel savings work",
  sections: [
    {
      heading: "Earn on the basket",
      body: "Riverbend Rewards earns points from eligible grocery baskets. The meal plan shows the points computed from the basket subtotal.",
    },
    {
      heading: "Convert at Fuel Stop",
      body: "Every 100 points converts to ten cents per gallon at Riverbend Fuel Stop, capped by the program rules shown in the card.",
    },
    {
      heading: "Check the package",
      body: "The meal plan screens against Riverbend's stored allergen statements, but the printed package label governs before anyone eats.",
    },
  ],
  related_products: [CHICKEN, PENNE, RICE],
};

const order_status: OrderStatusPayload = {
  order_id: "RB-77024",
  summary:
    "The Riverbend pickup order was placed September 2 and is delayed because the produce tote is being repacked after a quality check.",
  next_step: "Choose curbside pickup later today, or ask me to swap the produce item for an in-stock alternative.",
  order: {
    order_id: "RB-77024",
    status: "delayed",
    placed_at: "2026-09-02",
    items: [
      {
        product_id: "RB-1004",
        title: "Harvest Hollow Garden Salad Kit",
        quantity: 2,
        price: 4.49,
      },
    ],
    total: 8.98,
    currency: "USD",
    estimated_delivery:
      "2026-09-02 (updated after the produce quality check; the original 2026-09-02 10:30 estimate was missed)",
    tracking_url: "https://tracking.riverbend.invalid/RB-77024",
  },
};

const checkout: CheckoutPayload = {
  note: "The meal-plan basket is ready for pickup with refrigerated items held until handoff.",
  fulfillment_method: "pickup",
  cart: {
    items: [
      {
        product_id: "RB-1005",
        title: "Northfield Farms Chicken Breast Family Pack",
        price: 13.99,
        quantity: 1,
        line_total: 13.99,
      },
      {
        product_id: "RB-1007",
        title: "Cedar Creek Dairy Shredded Cheddar",
        price: 3.29,
        quantity: 2,
        line_total: 6.58,
      },
      {
        product_id: "RB-1001",
        title: "Riverbend Everyday Penne Pasta",
        price: 1.79,
        quantity: 1,
        line_total: 1.79,
      },
    ],
    item_count: 4,
    subtotal: 22.36,
    currency: "USD",
  },
};

export const SHOWCASE = {
  products,
  comparison,
  meal_plan,
  plan,
  guide,
  order_status,
  checkout,
};

/** Just under the free-delivery threshold. */
export const SHOWCASE_CART: CartPayload = {
  items: [
    {
      product_id: "RB-1005",
      title: "Northfield Farms Chicken Breast Family Pack",
      price: 13.99,
      quantity: 2,
      line_total: 27.98,
    },
    {
      product_id: "RB-1004",
      title: "Harvest Hollow Garden Salad Kit",
      price: 4.49,
      quantity: 3,
      line_total: 13.47,
    },
    {
      product_id: "RB-1011",
      title: "Harvest Hollow Apples",
      price: 4.99,
      quantity: 2,
      line_total: 9.98,
    },
  ],
  item_count: 7,
  subtotal: 51.43,
  currency: "USD",
};
