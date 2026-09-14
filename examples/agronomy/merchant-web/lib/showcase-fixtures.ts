// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

/** Copied from the agronomy merchant fixtures under data/. */

import type { ChangePreviewPayload, DigestPayload } from "./types";

const digest: DigestPayload = {
  title: "Morning digest",
  items: [
    {
      kind: "low_stock",
      ref_id: "HA-1603",
      headline: "3 bags left of AMS Boost (HA-1603) — under two days of cover",
      why_it_matters: "Selling about 30 bags a month, and every preemergence load this week needs it.",
      listing: {
        listing_id: "HA-1603",
        title: "AMS Boost Water Conditioner",
        status: "active",
        price: 42.0,
        stock: 3,
      },
    },
    {
      kind: "order_issue",
      ref_id: "HA-1802",
      headline: "Returns on the seed treatment colorant are running at 14%",
      why_it_matters: "A return rate that high on a seasonal item usually means the listing is missing a detail.",
    },
    {
      kind: "metric",
      headline: "Fungicide sales are up 21% week-over-week",
      why_it_matters: "Most of the lift traces to the tassel-timing window on corn acres.",
    },
  ],
};

const change_preview: ChangePreviewPayload = {
  change_id: "chg-3021",
  headline: "Refill HA-1603 before the spray window opens",
  note: "Puts about a month of cover back on the shelf at the trailing sales pace.",
  change: {
    change_id: "chg-3021",
    kind: "inventory_action",
    status: "staged",
    summary: "Add 52 bags of AMS Boost Water Conditioner (HA-1603)",
    items: [{ target: "HA-1603", field: "stock", before: 3, after: 55 }],
    created_at: "2026-07-09",
    created_by: "Avery",
    created_by_kind: "agent",
  },
};

export const SHOWCASE = { digest, change_preview };
