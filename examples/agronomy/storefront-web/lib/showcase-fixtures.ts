// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

/** Products are records from examples/agronomy/data/catalog.json. */

import type {
  ApplicationPlanPayload,
  CartPayload,
  CheckoutPayload,
  ComparisonPayload,
  GuidePayload,
  OrderStatusPayload,
  PlanPayload,
  Product,
  ProductsPayload,
} from "./types";

const RESIDUAL: Product = {
  product_id: "HA-1001",
  title: "Vantage Pro SC Residual Herbicide",
  brand: "Heartland Crop Protection",
  price: 289.0,
  rating: 4.6,
  review_count: 214,
  category: "herbicides",
  labels: ["bestseller"],
  attributes: {
    crop: "corn",
    target: "waterhemp, palmer amaranth, foxtail",
    timing: "preemergence",
    mode_of_action: "Group 15",
    rate_min: "1.2",
    rate_max: "2.0",
    rate_unit: "pt/acre",
    package_size: "2.5 gal jug",
    units_per_package: "20",
    package_unit: "pt",
    restricted_use: "no",
    rainfast: "2 hours",
    preharvest_interval: "not applicable (preemergence)",
    // Same count as merchant_inventory.json shows in the portal.
    low_stock: "6",
  },
  in_stock: true,
  short_description: "Long-residual preemergence grass and small-seeded broadleaf control for corn acres.",
};

const PREMIX: Product = {
  product_id: "HA-1002",
  title: "Clearfront XL Preemergence Premix",
  brand: "Heartland Crop Protection",
  price: 344.0,
  rating: 4.4,
  review_count: 158,
  category: "herbicides",
  labels: [],
  attributes: {
    crop: "corn",
    target: "broadleaf and grass complex",
    timing: "preemergence",
    mode_of_action: "Group 4 + Group 15",
    rate_min: "2.0",
    rate_max: "3.0",
    rate_unit: "pt/acre",
    package_size: "2.5 gal jug",
    units_per_package: "20",
    package_unit: "pt",
    restricted_use: "no",
    rainfast: "4 hours",
    preharvest_interval: "not applicable (preemergence)",
  },
  in_stock: true,
  short_description: "Two modes of action in one jug for resistance management on continuous corn.",
};

const SURFACTANT: Product = {
  product_id: "HA-1601",
  title: "Sticktite NIS Nonionic Surfactant",
  brand: "Heartland Adjuvants",
  price: 78.0,
  rating: 4.4,
  review_count: 176,
  category: "adjuvants",
  labels: ["bestseller"],
  attributes: {
    crop: "all labeled crops",
    target: "spray coverage",
    timing: "tank additive",
    rate_min: "0.25",
    rate_max: "0.5",
    rate_unit: "% v/v",
    package_size: "2.5 gal jug",
    units_per_package: "320",
    package_unit: "fl oz",
    restricted_use: "no",
  },
  in_stock: true,
  short_description: "Standard nonionic surfactant for postemergence tank mixes.",
};

const CONDITIONER: Product = {
  product_id: "HA-1603",
  title: "AMS Boost Water Conditioner",
  brand: "Heartland Adjuvants",
  price: 42.0,
  rating: 4.5,
  review_count: 204,
  category: "adjuvants",
  labels: [],
  attributes: {
    crop: "all labeled crops",
    target: "hard water antagonism",
    timing: "tank additive, added first",
    rate_min: "8.5",
    rate_max: "17",
    rate_unit: "lb/100 gal",
    package_size: "50 lb bag",
    units_per_package: "50",
    package_unit: "lb",
    restricted_use: "no",
    // Same count as merchant_inventory.json shows in the portal.
    low_stock: "3",
  },
  in_stock: true,
  short_description: "Ammonium sulfate conditioner that goes in the tank before the herbicide.",
};

const CLEANOUT: Product = {
  product_id: "HA-2203",
  title: "TankClear Sprayer Cleanout Concentrate",
  brand: "Heartland Equipment",
  price: 54.0,
  rating: 4.5,
  review_count: 167,
  category: "application-equipment",
  labels: [],
  attributes: {
    use: "tank cleanout between loads",
    rate_min: "1",
    rate_max: "2",
    rate_unit: "qt/100 gal",
    package_size: "2.5 gal jug",
    units_per_package: "10",
    package_unit: "qt",
    restricted_use: "no",
  },
  in_stock: true,
  short_description: "Cleanout concentrate for switching between sensitive crops.",
};

const GLOVES: Product = {
  product_id: "HA-2202",
  title: "Chemical-Resistant Nitrile Gloves",
  brand: "Heartland Safety",
  price: 28.0,
  rating: 4.4,
  review_count: 233,
  category: "safety-ppe",
  labels: ["bestseller"],
  attributes: {
    material: "14 mil nitrile",
    length: "13 inch gauntlet",
    pack_count: "3 pairs",
  },
  in_stock: true,
  short_description: "Gauntlet-length nitrile gloves that meet handler requirements on most labels.",
  options: { size: ["M", "L", "XL", "2XL"] },
};

const FACE_SHIELD: Product = {
  product_id: "HA-2205",
  title: "Full Face Shield with Chemical Splash Guard",
  brand: "Heartland Safety",
  price: 44.0,
  rating: 4.3,
  review_count: 118,
  category: "safety-ppe",
  labels: [],
  attributes: {
    standard: "meets handler eye protection requirements",
    adjustable: "ratchet headgear",
  },
  in_stock: true,
  short_description: "Face and eye protection for mixing and loading concentrate.",
};

const products: ProductsPayload = {
  title: "Corn Preemergence Options for Group 2-Resistant Waterhemp",
  layout: "carousel",
  items: [
    {
      product: RESIDUAL,
      reason: "Group 15 residual — a different site of action from the Group 2 that stopped working.",
    },
    {
      product: PREMIX,
      reason: "Two sites of action in one jug when you would rather not build the mix yourself.",
    },
    {
      product: CONDITIONER,
      reason: "Goes in the tank first; hard well water antagonizes the load without it.",
    },
    {
      product: SURFACTANT,
      reason: "The coverage additive most of these labels ask for.",
    },
  ],
};

const comparison: ComparisonPayload = {
  title: "Vantage Pro vs. Clearfront XL on Continuous Corn",
  entries: [
    {
      product_id: "HA-1001",
      product: RESIDUAL,
      best_for: "Building your own mix and controlling what goes in it",
      pros: [
        "Group 15 alone — you choose the partner and the rate",
        "Rainfast in two hours, which matters in a tight spray window",
        "Lower cost per acre at the low end of its range",
      ],
      cons: [
        "One site of action, so it needs a partner for resistance management",
        "Two products to load instead of one",
      ],
    },
    {
      product_id: "HA-1002",
      product: PREMIX,
      best_for: "Fewer decisions at the load pad and a wider spectrum in one jug",
      pros: [
        "Group 4 and Group 15 already in the jug",
        "Broader broadleaf spectrum than the straight residual",
        "One product to inventory, load, and rinse",
      ],
      cons: [
        "Higher cost per acre",
        "Four hours to rainfast instead of two",
        "The ratio is fixed — you cannot lean on one partner",
      ],
    },
  ],
  dimensions: ["Sites of action", "Spectrum", "Rainfast window", "Cost per acre"],
  recommended_product_id: "HA-1001",
};

/**
 * Every number below came out of examples/agronomy/api/rates.py for 640 acres at 15 GPA
 * in a 1,200 gallon tank. The showcase page renders with no API running, so the figures
 * are pasted here; the running demo computes them on the server for each turn.
 */
const application_plan: ApplicationPlanPayload = {
  title: "Corn preemergence, north half",
  acres: 640,
  carrier_gpa: 15,
  tank_capacity_gal: 1200,
  total_carrier_gal: 9600,
  acres_per_load: 80,
  tank_loads: 8,
  computed_by: "server",
  currency: "USD",
  product_cost: 16816.0,
  cost_per_acre: 26.28,
  note: "Load order: conditioner, then the residual, then the surfactant last.",
  rows: [
    {
      product: CONDITIONER,
      rate: 12,
      rate_unit: "lb/100 gal",
      rate_min: 8.5,
      rate_max: 17,
      restricted_use: false,
      total_amount: 1152,
      total_unit: "lb",
      containers: 24,
      package_size: "50 lb bag",
      line_cost: 1008.0,
      currency: "USD",
      note: "Goes in the tank first, before anything else.",
    },
    {
      product: RESIDUAL,
      rate: 1.6,
      rate_unit: "pt/acre",
      rate_min: 1.2,
      rate_max: 2.0,
      restricted_use: false,
      total_amount: 1024,
      total_unit: "pt",
      containers: 52,
      package_size: "2.5 gal jug",
      line_cost: 15028.0,
      currency: "USD",
    },
    {
      product: SURFACTANT,
      rate: 0.25,
      rate_unit: "% v/v",
      rate_min: 0.25,
      rate_max: 0.5,
      restricted_use: false,
      total_amount: 3072,
      total_unit: "fl oz",
      containers: 10,
      package_size: "2.5 gal jug",
      line_cost: 780.0,
      currency: "USD",
    },
  ],
};

const plan: PlanPayload = {
  title: "Getting the sprayer ready for the preemergence pass",
  intro: "Three things to have on the pad before the first load.",
  steps: [
    {
      label: "Clean out what was in there",
      detail: "The last load was a sensitive-crop product",
      products: [CLEANOUT],
    },
    { label: "Handler PPE", detail: "What the labels in this mix require", products: [GLOVES, FACE_SHIELD] },
    { label: "Condition the water", detail: "Before the herbicide goes in", products: [CONDITIONER] },
    {
      label: "Already covered: nozzles",
      detail: "Your AIXR 110-04 tips cover this mix at 15 GPA — nothing to buy.",
      products: [],
    },
  ],
};

const guide: GuidePayload = {
  title: "Tank mixing order for a preemergence load",
  sections: [
    {
      heading: "The order",
      body: "Fill the tank half to two-thirds with water and start agitation. Water conditioners go in first and are given time to dissolve. Dry flowables and water-dispersible granules follow, then suspension concentrates, then emulsifiable concentrates, and surfactants and oils go in last with the tank nearly full.",
    },
    {
      heading: "Why last matters",
      body: "A surfactant added early foams under agitation and makes the rest of the load hard to mix. Adding it at the end, with the tank almost full, keeps the foam down and the mix uniform.",
    },
    {
      heading: "The jar test",
      body: "When a combination is new to you, mix it in the same proportions in a jar first and let it stand for fifteen minutes. Anything that separates, gels, or settles in the jar will do the same in the tank.",
    },
  ],
  related_products: [CONDITIONER, SURFACTANT],
};

const order_status: OrderStatusPayload = {
  order_id: "HA-48812",
  summary:
    "The Canopy Shield SC order was placed September 2 and is marked delayed — the delivery estimate moved to September 19 after the original September 12 date was missed.",
  next_step: "Track the freight for the latest update, or ask me about pulling it from branch stock instead.",
  order: {
    order_id: "HA-48812",
    status: "delayed",
    placed_at: "2026-09-02",
    items: [
      {
        product_id: "HA-1201",
        title: "Canopy Shield SC Fungicide",
        quantity: 4,
        price: 412.0,
      },
    ],
    total: 1648.0,
    currency: "USD",
    // Same shape as the orders fixture: current estimate first, missed original in the note.
    estimated_delivery:
      "2026-09-19 (updated after a freight delay; the original 2026-09-12 estimate was missed)",
    tracking_url: "https://track.example.com/HA-48812",
  },
};

const checkout: CheckoutPayload = {
  note: "Both are at the branch and can go on the same pickup.",
  fulfillment_method: "pickup",
  cart: {
    items: [
      {
        product_id: "HA-1603",
        title: "AMS Boost Water Conditioner",
        price: 42.0,
        quantity: 24,
        line_total: 1008.0,
      },
      {
        product_id: "HA-1601",
        title: "Sticktite NIS Nonionic Surfactant",
        price: 78.0,
        quantity: 10,
        line_total: 780.0,
      },
    ],
    item_count: 34,
    subtotal: 1788.0,
    currency: "USD",
  },
};

export const SHOWCASE = {
  products,
  comparison,
  application_plan,
  plan,
  guide,
  order_status,
  checkout,
};

/** Just under the free-delivery threshold. */
export const SHOWCASE_CART: CartPayload = {
  items: [
    {
      product_id: "HA-2203",
      title: "TankClear Sprayer Cleanout Concentrate",
      price: 54.0,
      quantity: 6,
      line_total: 324.0,
    },
    {
      product_id: "HA-2202-XL",
      title: "Chemical-Resistant Nitrile Gloves",
      price: 28.0,
      quantity: 4,
      option_values: { size: "XL" },
      variant_of: "HA-2202",
      line_total: 112.0,
    },
  ],
  item_count: 10,
  subtotal: 436.0,
  currency: "USD",
};
