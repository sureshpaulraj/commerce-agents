// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

/** Copied from ../data/policies.json; keep in sync with it. */
export const STORE_POLICY = {
  returnsShort: "30-day returns, sealed only",
  returnsLine:
    "Unopened product in its original packaging with the seal intact can be returned within 30 days of delivery. Opened chemical containers cannot be returned, and seed treatments are not returnable once they leave the warehouse.",
  freeShippingThreshold: 500,
  standardShippingEta: "2–4 business days",
} as const;
