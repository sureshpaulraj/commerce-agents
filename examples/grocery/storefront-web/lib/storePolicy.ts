// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

/** Copied from ../data/policies.json; keep in sync with it. */
export const STORE_POLICY = {
  returnsShort: "30-day returns on unopened shelf-stable items",
  returnsLine:
    "Unopened shelf-stable groceries in their original packaging can be returned within 30 days of delivery. Fresh, prepared, frozen, and pharmacy items are handled by the Riverbend Market service desk.",
  freeShippingThreshold: 75,
  standardShippingEta: "same day or next morning",
} as const;
