// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

/** Agronomy-specific labels on top of web-shared's formatters. */

import { formatDayMonth, formatMoney, plural, type RecordRowData, titleCase } from "web-shared";
import { ORDER_STATUS } from "./kinds";
import type { RecentOrder } from "./types";

const CATEGORY_LABELS: Record<string, string> = {
  adjuvants: "Adjuvants",
  "application-equipment": "Application equipment",
  fungicides: "Fungicides",
  herbicides: "Herbicides",
  insecticides: "Insecticides",
  micronutrients: "Micronutrients",
  "safety-ppe": "Safety & PPE",
  "seed-treatments": "Seed treatments",
};

export function formatCategoryLabel(slug: string): string {
  return CATEGORY_LABELS[slug] ?? titleCase(slug.replaceAll("-", "_"));
}

export function orderRows(orders: RecentOrder[]): RecordRowData[] {
  return orders.map((order) => ({
    id: order.order_id,
    detail: plural(order.items, "item"),
    sub: `${formatDayMonth(order.placed_at)} · ${formatMoney(order.total)}`,
    status: ORDER_STATUS[order.status] ?? { label: order.status.replaceAll("_", " "), tone: "muted" },
  }));
}
