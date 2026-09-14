// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

/** Mirrors shopping_agent/types.py and tools/presentation.py; detail extras are the vertical's api/. */

export interface Product {
  product_id: string;
  title: string;
  brand?: string | null;
  price: number;
  currency?: string;
  rating?: number | null;
  review_count?: number | null;
  image_url?: string | null;
  category?: string | null;
  labels?: string[];
  attributes?: Record<string, string>;
  in_stock?: boolean;
  short_description?: string | null;
  /** Options still to choose on a family record; the cart takes one of its variants. */
  options?: Record<string, string[]>;
  /** A variant's value for each option. */
  option_values?: Record<string, string>;
  variant_of?: string | null;
}

/** Computed in agronomy/api/mock_agronomy.py. */
export interface PriceIntelligence {
  days: number;
  series: number[];
  low: number;
  high: number;
  position: "low" | "typical" | "high";
  verdict: string;
}

/** Computed in agronomy/api/mock_agronomy.py. */
export interface ReviewAspects {
  review_count: number;
  aspects: { name: string; positive_pct: number; mentions: number }[];
}

export interface ProductDetails extends Product {
  variants?: Product[];
  long_description?: string | null;
  specs?: Record<string, string>;
  review_highlights?: string[];
  price_intelligence?: PriceIntelligence | null;
  review_aspects?: ReviewAspects | null;
}

export interface CartItem {
  product_id: string;
  title: string;
  price: number;
  quantity: number;
  image_url?: string | null;
  option_values?: Record<string, string>;
  variant_of?: string | null;
  line_total: number;
}

export interface CartPayload {
  items: CartItem[];
  item_count: number;
  subtotal: number;
  currency: string;
}

// --- Presentation payloads, as streamed after server enrichment ---

export interface ProductsPayload {
  title?: string;
  layout?: "carousel" | "grid" | "list";
  items: { product: Product; reason?: string | null }[];
}

export interface ComparisonPayload {
  title?: string;
  entries: {
    product_id: string;
    product: Product;
    pros?: string[];
    cons?: string[];
    best_for?: string | null;
  }[];
  dimensions?: string[];
  recommended_product_id?: string | null;
  // Stamped by the server: the spread between the cheapest and dearest compared items.
  price_delta?: {
    amount: number;
    low_product_id: string;
    low_price: number;
    high_product_id: string;
    high_price: number;
  };
}

export interface PlanPayload {
  title: string;
  intro?: string;
  steps: { label: string; detail?: string | null; products: Product[] }[];
}

export interface GuidePayload {
  title: string;
  sections: { heading: string; body: string }[];
  related_products?: Product[];
  sources?: string[];
}

export interface OrderStatusPayload {
  order_id: string;
  summary: string;
  next_step?: string;
  order?: {
    order_id: string;
    status: string;
    placed_at: string;
    items: { product_id: string; title: string; quantity: number; price: number }[];
    total: number;
    currency?: string;
    estimated_delivery?: string;
    tracking_url?: string;
  };
}

export interface CheckoutHandoff {
  url: string;
  label?: string;
  seller?: string;
}

export interface CheckoutPayload {
  /** Where payment happens when it is not a route in this app; filled by the backend. */
  handoffs?: CheckoutHandoff[];
  note?: string;
  fulfillment_method?: "delivery" | "pickup" | "shipping";
  cart: CartPayload;
}

/** One product's line in an application plan. Every number is computed in agronomy/api/rates.py. */
export interface ApplicationPlanRow {
  product: Product;
  rate: number;
  rate_unit: string;
  rate_min: number;
  rate_max: number;
  restricted_use: boolean;
  total_amount?: number;
  total_unit?: string;
  /** Set instead of a total when the rate is not charged against acres. */
  total_note?: string;
  containers?: number;
  package_size?: string;
  line_cost?: number;
  currency?: string;
  note?: string;
}

/** Computed in agronomy/api/rates.py; the model supplies only ids, rates, and acres. */
export interface ApplicationPlanPayload {
  title: string;
  /** Present while the tool call is still streaming; no number has been label-checked yet. */
  pending?: boolean;
  products?: Product[];
  acres?: number;
  carrier_gpa?: number;
  tank_capacity_gal?: number;
  total_carrier_gal?: number;
  acres_per_load?: number;
  tank_loads?: number;
  rows?: ApplicationPlanRow[];
  product_cost?: number;
  cost_per_acre?: number;
  currency?: string;
  note?: string;
  restricted_use_present?: boolean;
  computed_by?: string;
}
