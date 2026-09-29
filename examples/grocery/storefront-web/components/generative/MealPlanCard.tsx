// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * The meals-to-basket card. Every number here was computed in grocery/api/meals.py from
 * each product's stored pack size and price, so the card states where the arithmetic
 * came from rather than leaving the shopper to wonder whether the model did it.
 *
 * The allergen line is the same kind of claim: an item only reaches this card if its
 * allergen statement is verified on the product record, so the card can say what was
 * checked, and say plainly that the printed package label is what governs.
 */

import { formatMoney } from "web-shared";
import type { MealPlanItem, MealPlanMeal, MealPlanPayload, Product } from "@/lib/types";
import { ProductRow } from "../ProductTile";

/** Trailing zeros read as false precision on a shopping list. */
function amount(value: number) {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
}

type AddHandler = (product: Product) => boolean | void | Promise<boolean | void>;

function Figure({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="min-w-0 rounded-lg bg-(--well) px-2.5 py-2">
      <div className="text-[11px] uppercase tracking-wide text-(--ink-soft)">{label}</div>
      <div className="truncate text-[15px] font-semibold text-(--ink)">{value}</div>
      {sub ? <div className="truncate text-[11px] text-(--ink-soft)">{sub}</div> : null}
    </div>
  );
}

function Item({ item, onAdd }: { item: MealPlanItem; onAdd?: AddHandler }) {
  return (
    <li className="ac-reveal border-t border-(--line) pt-2.5 first:border-0 first:pt-0">
      <ProductRow product={item.product} onAdd={onAdd} />
      <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[13px]">
        <span className="font-semibold text-(--ink)">
          {amount(item.packs)} &times; {item.pack_size ?? "pack"}
        </span>
        <span className="text-(--ink-soft)">
          {amount(item.total_needed)} {item.total_unit} needed
        </span>
        <span className="font-semibold text-(--ink)">{formatMoney(item.line_cost, item.currency)}</span>
        {item.private_label ? (
          <span className="rounded-full bg-(--accent-soft) px-2 py-0.5 text-[11px] font-semibold text-(--ink)">
            Store brand
          </span>
        ) : null}
        {item.age_restricted ? (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-900">
            ID required
          </span>
        ) : null}
      </div>
      {item.allergens.length > 0 ? (
        <div className="mt-1 text-[13px] text-(--ink-soft)">Contains {item.allergens.join(", ")}</div>
      ) : null}
      {item.leftover > 0 ? (
        <div className="mt-1 text-[13px] text-(--ink-soft)">
          {amount(item.leftover)} {item.total_unit} left over
        </div>
      ) : null}
      {item.note ? <div className="mt-1 text-[13px] text-(--ink-soft)">{item.note}</div> : null}
    </li>
  );
}

function Meal({ meal, onAdd }: { meal: MealPlanMeal; onAdd?: AddHandler }) {
  return (
    <section className="rounded-xl bg-(--well) p-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <h4 className="text-[14px] font-semibold text-(--ink)">{meal.name}</h4>
        <span className="shrink-0 text-[11px] text-(--ink-soft)">{meal.servings} servings</span>
      </div>
      <ul className="mt-2 space-y-2.5">
        {(meal.items ?? []).map((item, index) => (
          <Item key={`${item.product.product_id}-${index}`} item={item} onAdd={onAdd} />
        ))}
      </ul>
      {meal.note ? <p className="mt-1.5 text-[13px] text-(--ink-soft)">{meal.note}</p> : null}
    </section>
  );
}

export default function MealPlanCard({
  payload,
  onAdd,
  partial,
}: {
  payload: MealPlanPayload;
  onAdd?: AddHandler;
  partial?: boolean;
}) {
  const meals = payload.meals ?? [];
  // While the call streams, the server sends the named products and no numbers at all.
  const pending = payload.pending || partial;

  return (
    <section className="rounded-2xl border border-(--line) bg-(--card) p-3.5 shadow-(--shadow-sm)">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[15px] font-semibold text-(--ink)">{payload.title}</h3>
        {payload.computed_by === "server" ? (
          <span
            data-computed-by="server"
            className="shrink-0 rounded-full bg-(--accent-soft) px-2 py-0.5 text-[11px] font-semibold text-(--ink)"
            title="Calculated by the store from each product's pack size and price, not by the assistant."
          >
            Calculated by Riverbend
          </span>
        ) : null}
      </div>

      {pending ? (
        <>
          <p className="mt-1 text-[13px] text-(--ink-soft)">Working the basket out&hellip;</p>
          <ul className="mt-2.5 space-y-2.5">
            {meals.flatMap((meal) =>
              (meal.products ?? []).map((product) => (
                <li key={`${meal.name}-${product.product_id}`}>
                  <ProductRow product={product} />
                  <div className="ac-skeleton mt-1.5 h-4 w-2/3 rounded" />
                </li>
              )),
            )}
            {meals.every((meal) => (meal.products ?? []).length === 0) ? (
              <li className="ac-skeleton h-[72px] rounded-xl" />
            ) : null}
          </ul>
        </>
      ) : (
        <>
          <div className="mt-2.5 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Figure
              label="Subtotal"
              value={formatMoney(payload.subtotal ?? 0, payload.currency)}
              sub={`${payload.item_count ?? 0} items · ${payload.pack_count ?? 0} packs`}
            />
            <Figure
              label="Per serving"
              value={formatMoney(payload.cost_per_serving ?? 0, payload.currency)}
              sub={`${meals.length} meals for ${payload.servings ?? 0}`}
            />
            <Figure
              label="Rewards"
              value={`${payload.rewards_points ?? 0} pts`}
              sub={
                payload.fuel_cents_per_gal
                  ? `${payload.fuel_cents_per_gal}¢ per gallon`
                  : "toward fuel savings"
              }
            />
            {payload.budget !== undefined ? (
              <Figure
                label={payload.over_budget ? "Over budget" : "Left in budget"}
                value={formatMoney(Math.abs(payload.budget_headroom ?? 0), payload.currency)}
                sub={`of ${formatMoney(payload.budget, payload.currency)}`}
              />
            ) : null}
          </div>

          {payload.avoided_allergens?.length ? (
            <p className="mt-2.5 rounded-lg bg-(--accent-soft) px-2.5 py-2 text-[13px] text-(--ink)">
              Every item was checked against our stored allergen statements for{" "}
              <span className="font-semibold">{payload.avoided_allergens.join(", ")}</span>, and anything
              without a verified statement was left out. The printed package label is the final word.
            </p>
          ) : null}

          <div className="mt-3 space-y-2.5">
            {meals.map((meal, index) => (
              <Meal key={`${meal.name}-${index}`} meal={meal} onAdd={onAdd} />
            ))}
          </div>

          {payload.over_budget ? (
            <p className="mt-2.5 rounded-lg bg-amber-50 px-2.5 py-2 text-[13px] text-amber-900">
              This plan is over the budget you gave. Ask me to swap the costliest lines for Riverbend
              store brands and I&rsquo;ll rework it.
            </p>
          ) : null}
          {payload.age_restricted_present ? (
            <p className="mt-2.5 rounded-lg bg-amber-50 px-2.5 py-2 text-[13px] text-amber-900">
              This plan includes an age-restricted item. It needs ID at handoff and cannot be left
              unattended for curbside or delivery.
            </p>
          ) : null}
          {payload.note ? <p className="mt-2 text-[13px] text-(--ink-soft)">{payload.note}</p> : null}
          <p className="mt-2 text-[11px] text-(--ink-soft)">
            Quantities, packs, and totals come from each product&rsquo;s pack size and shelf price. Allergen
            statements are summaries &mdash; read the package label before you serve.
          </p>
        </>
      )}
    </section>
  );
}
