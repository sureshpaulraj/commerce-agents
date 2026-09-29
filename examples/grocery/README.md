# Riverbend Market (grocery)

The grocery example runs both agents over a supermarket catalog — produce, meat and
seafood, dairy and eggs, bakery, frozen, pantry, breakfast, snacks, beverages, household,
health and beauty, baby, floral, and the prepared-food counter the store calls **Riverbend
Table**. It adds one component the other examples do not have: a **meal plan** whose
arithmetic runs on the server, not in the model. The storefront proposes the meals and
then hands every number to `api/meals.py`, which scales each quantity across the
household, rounds up to whole packs, totals the basket, and **refuses any item whose
allergen statement is not verified on its record** — before it refuses anything the
household has actually said it is avoiding.

That ordering is the point of the example. The usual allergen demo asks a model to read an
ingredient list and decide. This one never asks. A record either carries a verified
allergen statement or it does not go in the plan, and the model is told, in the refusal
itself, not to reason about the ingredients on its own.

The portal side is the store view: what is short before the weekend ad, what is
short-dated on the prepared-food end caps, where shrink is eating margin, and which
department moved.

Everything here is fictional. There is no real store, brand, product, price, or supplier in
this example, and nothing in it is dietary or medical advice.

## Run

```bash
python scripts/run_demo.py grocery                # API :8005 + storefront :3005
python scripts/run_demo.py grocery --merchant     # API :8005 + portal :3105
python scripts/run_demo.py grocery --all          # both web apps over one API
```

Or start the pieces yourself, after `npm ci` in `examples/`:

```bash
uvicorn grocery.api.main:app --app-dir examples --reload --port 8005
(cd examples/grocery/storefront-web && npm run dev)     # :3005
(cd examples/grocery/merchant-web && npm run dev)       # :3105
```

Chat needs `ANTHROPIC_API_KEY` in the repo-root `.env` or the environment; browsing the
catalog, the portal's widgets, and `/showcase` do not.

Without an Anthropic API key, chat can run instead against a Microsoft Foundry deployment,
authenticated with Entra ID — a managed identity in Azure, a developer login locally.
There are two Foundry surfaces and they are not the same thing:

```bash
# Claude on Foundry, over the native Messages API, so prompt caching and
# extended thinking both survive.
COMMERCE_DEMO_PROVIDER=foundry-anthropic
FOUNDRY_RESOURCE=your-account
FOUNDRY_DEPLOYMENT=claude-opus-5-5

# An OpenAI-compatible deployment, through the adapter in
# commerce_common.foundry_openai. Caching and extended thinking are not
# carried across.
COMMERCE_DEMO_PROVIDER=foundry-openai
FOUNDRY_RESOURCE=your-account
FOUNDRY_DEPLOYMENT=your-deployment
```

The meal plan is computed in `api/meals.py`, so none of its numbers change with the model;
what changes is who chooses the meals. `docs/deployment.md` covers the trade-offs, both
Foundry surfaces, and every other platform.

## Reaching it from somewhere other than this machine

The demo binds to loopback and expects to be alone there. Two variables, both unset by
default, are what a deployment adds:

```bash
DEMO_BASIC_AUTH=user:password          # HTTP Basic in front of the API and both web apps
DEMO_API_ORIGIN=https://<api-host>     # where a web app forwards its own /api calls
```

A browser cannot authenticate to a second origin with `fetch`, so a deployed web app
serves `/api` itself and forwards from the server side, attaching the credentials where the
browser cannot read them. That needs the app built with an empty `NEXT_PUBLIC_API_URL` so
it addresses its own origin. `web-shared/gateway.ts` holds both halves, and
`deploy/web.Dockerfile` shows the build.

`deploy/` holds the two images: `api.Dockerfile` serves the API and the listing photos both
web apps read, and `web.Dockerfile` builds either web app from the `examples/` npm
workspace, choosing which with `--build-arg APP`. Each header carries the command it
expects, and neither image carries a model credential — the provider variables above select
the path at run time.

## Try

Storefront — the turns run in order in one session:

1. I need five weeknight dinners for a family of five. There's a peanut allergy in the house, so nothing with peanuts anywhere near it.
2. Is the family-size pack of ground beef actually cheaper per ounce, or does it just look that way?
3. That works — build me the plan and the basket to go with it, and keep it under ninety dollars.
4. Add the cocoa almond clusters for lunchboxes.

Turn 3 is the one to watch. The model names the meals and how much of each item one serving
takes; every number on the card comes back from `api/meals.py`. Five dinners at five
servings each — chicken and peppers, spaghetti and meat sauce, a sausage and rice skillet,
salmon with greens, and chicken tacos — report 17 items, 23 packs, a $130.27 subtotal,
$5.21 a serving, 1,302 Riverbend Rewards points, and the capped $1.00 a gallon in fuel
savings; and because a $90 budget was stated, $40.27 over, marked as over. Not one of those
figures was produced by the model, and the partial card that streams while the plan is
still being written carries product names only, never a number that is not final.

Turn 4 is the refusal. The clusters carry no verified allergen statement, so the plan will
not hold them at all — not because of what is in them, but because the store cannot show
what is in them. Ask instead for the peanut spread, which *does* declare its allergens, and
a different refusal names peanuts and leaves it out. Both refusals come from
`_check_allergens`; neither asks the model to read a label.

Portal:

1. What needs my attention this morning?
2. Restock the chicken cutlets with enough to cover the next month at the current pace, and fix that listing's description so it covers what's been missing. Show me both before anything goes live.
3. Looks right — approve the restock.
4. Riverbend Table feels like it's having a moment. Pull the numbers — is prepared food really outperforming the rest of the store this month?

Single prompts, each in a fresh session:

| Surface | Prompt | A good answer |
|---|---|---|
| Storefront | Three dinners for four, nothing with milk or wheat in it. | One card, three meals, whole packs, one subtotal. Every item on it declares neither, and the prose does no arithmetic. |
| Storefront | Put the cocoa almond clusters in the plan — we're only avoiding peanuts. | Refuses on provenance, not ingredients: the item has no verified allergen statement, so it will not go in a plan on that basis. It does not offer its own reading of the label. |
| Storefront | Is the family pack of ground beef cheaper than two of the regular? | Compares the stored unit prices and says which, without recomputing them in prose. |
| Storefront | I want a bottle of the red table wine with the salmon night. | Shows it, flags it age-restricted, and says ID is checked at handoff — pickup or delivery. |
| Portal | The cutlets are down to three cases. What does the next month look like? | Reads the listing and the trailing pace, proposes a restock, and stages it for approval rather than writing it. |
| Portal | Why is the pico getting returned? | Reads the return rate and the listing, and says the short-dated end cap is what the messages point at, rather than inventing a cause. |

## What is specific to this example

- `api/meals.py`: `build_meal_plan_extension`, the `PresentationExtension` that computes
  the plan. `_resolve` refuses a product the session has not seen, `_check_allergens` holds
  both refusals — provenance first, then declared allergens, then shared equipment —
  `_item_amounts` does one line's unit conversion and pack rounding, `_build` does every
  total, and `_enrich_partial` streams product names only, never a number that is not
  final.
- `api/mock_grocery.py`: `MockGrocery`, the `StorefrontBackend` over the fixtures.
  Fulfillment is pickup-first with a delivery fee that falls away over $75, and
  `substitutes_for` exposes each substitute's allergen-verification status, so a
  substitution can be refused on the same basis a plan is.
- `api/mock_merchant.py`: `MockGroceryMerchant`, the `MerchantBackend` over the same
  catalog; `execute_analysis_query` serves the analysis delegate from a read-only SQLite
  view of the same state.
- `api/agent_config.py`: the two configs.
- `api/main.py`: registers the meal-plan extension alongside the built-in components, plus
  product-detail enrichment and the add-to-cart route.
- `storefront-web/components/generative/MealPlanCard.tsx`: the card. The "Calculated by
  Riverbend" badge is `data-computed-by="server"` — it is rendered from the payload field,
  so it cannot appear on a payload the server did not compute.

## Data

`data/catalog.json`, `users.json`, `orders.json`, and `policies.json` feed the storefront;
`merchant_metrics.json`, `merchant_inventory.json`, `merchant_campaigns.json`, and
`merchant_messages.json` feed the portal.

The catalog carries 180 products across fourteen departments. Every listing carries
`unit_count`, `unit_of_measure`, `pack_size`, and `unit_price` as string attributes, which
is what lets `meals.py` fill a quantity given in one measure from a pack sold in another
inside the same family — ounces from pounds, cups from quarts — and refuse across families.
Every listing also carries `allergens`, `may_contain`, `allergen_status`, and
`allergen_source`. Ten products are deliberately left `unverified`: they are the ones a
plan refuses on provenance, and a test fails if that set empties out. Seven are out of
stock and five are age-restricted. This catalog ships no product photos, so every product
renders as a tile.

Sessions and identity are the shared host code in [`../demo_common/`](../demo_common/): a
session id stands for a demo profile or the one merchant.
