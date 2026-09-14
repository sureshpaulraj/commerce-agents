# Heartland Agronomy Supply (agronomy)

The agronomy example runs both agents over a crop-input catalog — herbicides, fungicides,
insecticides, adjuvants, seed treatments, micronutrients, application equipment, and
handler PPE. It adds one component the other examples do not have: an **application plan**
whose arithmetic runs on the server, not in the model. The storefront recommends products
and then hands the rate math to `api/rates.py`, which converts label rates to a total, a
container count, and a tank-load count, and **refuses any rate outside the product's
labeled range**. The portal side is the branch view: what is short before the spray window,
what the return rate is telling you, and which segment moved.

Everything here is fictional. There is no real brand, product, label, or rate in this
example, and nothing in it is agronomic advice.

## Run

```bash
python scripts/run_demo.py agronomy               # API :8004 + storefront :3004
python scripts/run_demo.py agronomy --merchant     # API :8004 + portal :3104
python scripts/run_demo.py agronomy --all          # both web apps over one API
```

Or start the pieces yourself, after `npm ci` in `examples/`:

```bash
uvicorn agronomy.api.main:app --app-dir examples --reload --port 8004
(cd examples/agronomy/storefront-web && npm run dev)     # :3004
(cd examples/agronomy/merchant-web && npm run dev)       # :3104
```

Chat needs `ANTHROPIC_API_KEY` in the repo-root `.env` or the environment; browsing the
catalog, the portal's widgets, and `/showcase` do not.

## Try

Storefront — the three turns run in order in one session:

1. My Group 2 chemistry stopped holding waterhemp on continuous corn. What should I be looking at for a preemergence pass?
2. Compare the straight residual against the premix — I care about resistance management and what it costs me an acre.
3. Go with the residual at 1.6 pints. I've got 640 acres, I run 15 gallons an acre, and the tank holds 1,200. What am I buying?

Turn 3 is the one to watch. The model names the products, the rate, and the acreage; every
number on the card — 1,024 pints, 52 jugs, 8 tank loads, $15,028 — comes back from
`api/rates.py`. Ask for 2.6 pints instead and the plan is refused, by name, against the
label range. Ask again with the conditioner and the surfactant in the mix and the same
card carries three rows on three different rate bases (per acre, per 100 gallons, and
percent by volume).

Portal:

1. What needs my attention this morning?
2. Restock AMS Boost with enough to cover the next month at the current pace, and fix that listing's description so it covers what's been missing. Show me both before anything goes live.
3. Looks right — approve the restock.
4. Fungicide feels like it's having a moment. Pull the numbers — is it really outperforming the rest of the branch this month?

Single prompts, each in a fresh session:

| Surface | Prompt | A good answer |
|---|---|---|
| Storefront | Build me a tank mix for 320 acres: the residual at 1.6 pints, AMS at 12 pounds per hundred gallons, and NIS at a quarter percent. | One card, three rows, three rate bases, one container count each, and one product cost. No arithmetic in the prose. |
| Storefront | Same mix, but run the residual at 2.6 pints — I want it to hold longer. | Refuses the plan and names the labeled range (1.2 to 2.0 pt/acre). It does not build the card with a footnote. |
| Storefront | What goes in the tank first? | Answers from the mixing-order guide and names the two adjuvants, without turning it into a plan. |
| Storefront | I need the restricted-use insecticide for corn rootworm beetle. | Shows the product, flags it restricted-use, and says a certified applicator licence is required before it can ship. |
| Portal | AMS Boost is three bags. What does the next month look like? | Reads the listing and the trailing pace, proposes a restock, and stages it for approval rather than writing it. |
| Portal | The seed treatment colorant is getting returned. Why? | Reads the return rate and the listing, and says which attributes are missing rather than inventing a cause. |

## What is specific to this example

- `api/rates.py`: `build_application_plan_extension`, the `PresentationExtension` that
  computes the plan. `_resolve` refuses a product the session has not seen, `_row_amounts`
  refuses a rate outside the label range, `_rate_basis` handles the four rate bases, and
  `_enrich_partial` streams product names only — never a number that is not final.
- `api/mock_agronomy.py`: `MockAgronomy`, the `StorefrontBackend` over the fixtures.
- `api/mock_merchant.py`: `MockAgronomyMerchant`, the `MerchantBackend` over the same
  catalog; `execute_analysis_query` serves the analysis delegate from a read-only SQLite
  view of the same state.
- `api/agent_config.py`: the two configs.
- `api/main.py`: registers the application-plan extension alongside the built-in
  components, plus product-detail enrichment and the add-to-cart route.
- `storefront-web/components/generative/ApplicationPlanCard.tsx`: the card. The
  "Calculated by Heartland" badge is `data-computed-by="server"` — it is rendered from the
  payload field, so it cannot appear on a payload the server did not compute.

## Data

`data/catalog.json`, `users.json`, `orders.json`, and `policies.json` feed the storefront;
`merchant_metrics.json`, `merchant_inventory.json`, `merchant_campaigns.json`, and
`merchant_messages.json` feed the portal. Every chemical listing carries `rate_min`,
`rate_max`, `rate_unit`, `units_per_package`, and `package_unit` as string attributes;
`rates.py` parses them and there is a test that fails if one goes missing. Three products
come with options (nozzles by orifice size, gloves and coveralls by size): the catalog
authors their variants compactly and `demo_common` derives the rest, as
[`docs/backends.md`](../../docs/backends.md) describes. This catalog ships no product
photos, so every product renders as a tile.

Sessions and identity are the shared host code in [`../demo_common/`](../demo_common/): a
session id stands for a demo profile or the one merchant.
