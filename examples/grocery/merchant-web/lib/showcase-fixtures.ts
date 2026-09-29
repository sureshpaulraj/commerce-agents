// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

/** Invented Riverbend Market merchant fixtures. */

import type { ChangePreviewPayload, DigestPayload } from "./types";

const digest: DigestPayload = {
  title: "Morning digest",
  items: [
    {
      kind: "low_stock",
      ref_id: "RB-1004",
      headline: "7 Harvest Hollow Garden Salad Kits left — less than one day of cover",
      why_it_matters: "The weekly ad is lifting salad-kit demand, and substitutions on this item are often refused.",
      listing: {
        listing_id: "RB-1004",
        title: "Harvest Hollow Garden Salad Kit",
        status: "active",
        price: 4.49,
        stock: 7,
        category: "produce",
      },
    },
    {
      kind: "slow_mover",
      ref_id: "RB-1308",
      headline: "Bluestem Berry Parfaits are short-dated in prepared foods",
      why_it_matters: "Margin is better protected by a planned markdown than by end-of-day shrink.",
      listing: {
        listing_id: "RB-1308",
        title: "Bluestem Berry Parfait",
        status: "active",
        price: 3.99,
        stock: 18,
        category: "prepared-foods",
      },
    },
    {
      kind: "metric",
      headline: "Prepared-foods baskets are up 16% week-over-week",
      why_it_matters: "Most of the lift traces to Riverbend Table dinner bundles featured in the weekly ad.",
    },
  ],
};

const change_preview: ChangePreviewPayload = {
  change_id: "chg-4107",
  headline: "Refill RB-1004 before the dinner rush",
  note: "Puts about four days of cover back on the shelf at the current sales pace.",
  change: {
    change_id: "chg-4107",
    kind: "inventory_action",
    status: "staged",
    summary: "Add 36 Harvest Hollow Garden Salad Kits (RB-1004)",
    items: [{ target: "RB-1004", field: "stock", before: 7, after: 43 }],
    created_at: "2026-09-28",
    created_by: "Dana",
    created_by_kind: "operator",
  },
};

export const SHOWCASE = { digest, change_preview };
