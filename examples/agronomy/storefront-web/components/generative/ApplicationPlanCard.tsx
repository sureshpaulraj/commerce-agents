// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * The tank-mix and acreage card. Every number here was computed in agronomy/api/rates.py
 * from the product's stored label rate range, so the card states where the arithmetic
 * came from rather than leaving the grower to wonder whether the model did it.
 */

import { formatMoney } from "web-shared";
import type { ApplicationPlanPayload, ApplicationPlanRow, Product } from "@/lib/types";
import { ProductRow } from "../ProductTile";

/** Trailing zeros read as false precision on a rate sheet. */
function amount(value: number) {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
}

function Figure({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="min-w-0 rounded-lg bg-(--well) px-2.5 py-2">
      <div className="text-[11px] uppercase tracking-wide text-(--ink-soft)">{label}</div>
      <div className="truncate text-[15px] font-semibold text-(--ink)">{value}</div>
      {sub ? <div className="truncate text-[11px] text-(--ink-soft)">{sub}</div> : null}
    </div>
  );
}

function Row({ row, onAdd }: { row: ApplicationPlanRow; onAdd?: AddHandler }) {
  return (
    <li className="ac-reveal border-t border-(--line) pt-2.5 first:border-0 first:pt-0">
      <ProductRow product={row.product} onAdd={onAdd} />
      <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[13px]">
        <span className="font-semibold text-(--ink)">
          {amount(row.rate)} {row.rate_unit}
        </span>
        <span className="text-(--ink-soft)">
          label range {amount(row.rate_min)}&ndash;{amount(row.rate_max)} {row.rate_unit}
        </span>
        {row.restricted_use ? (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-900">
            Restricted use
          </span>
        ) : null}
      </div>
      {row.total_amount !== undefined ? (
        <div className="mt-1 text-[13px] text-(--ink-soft)">
          <span className="font-semibold text-(--ink)">
            {amount(row.total_amount)} {row.total_unit}
          </span>{" "}
          for the acres
          {row.containers !== undefined ? (
            <>
              {" · "}
              <span className="font-semibold text-(--ink)">
                {row.containers} &times; {row.package_size}
              </span>
              {row.line_cost !== undefined ? ` · ${formatMoney(row.line_cost, row.currency)}` : null}
            </>
          ) : null}
        </div>
      ) : null}
      {row.total_note ? <div className="mt-1 text-[13px] text-(--ink-soft)">{row.total_note}</div> : null}
      {row.note ? <div className="mt-1 text-[13px] text-(--ink-soft)">{row.note}</div> : null}
    </li>
  );
}

type AddHandler = (product: Product) => boolean | void | Promise<boolean | void>;

export default function ApplicationPlanCard({
  payload,
  onAdd,
  partial,
}: {
  payload: ApplicationPlanPayload;
  onAdd?: AddHandler;
  partial?: boolean;
}) {
  const rows = payload.rows ?? [];
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
            title="Calculated by the store's rate engine from each product's label range, not by the assistant."
          >
            Calculated by Heartland
          </span>
        ) : null}
      </div>

      {pending ? (
        <>
          <p className="mt-1 text-[13px] text-(--ink-soft)">Working the rates out&hellip;</p>
          <ul className="mt-2.5 space-y-2.5">
            {(payload.products ?? []).map((product) => (
              <li key={product.product_id}>
                <ProductRow product={product} />
                <div className="ac-skeleton mt-1.5 h-4 w-2/3 rounded" />
              </li>
            ))}
            {(payload.products ?? []).length === 0 ? <li className="ac-skeleton h-[72px] rounded-xl" /> : null}
          </ul>
        </>
      ) : (
        <>
          <div className="mt-2.5 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Figure label="Acres" value={amount(payload.acres ?? 0)} sub={`${amount(payload.carrier_gpa ?? 0)} GPA`} />
            <Figure
              label="Carrier"
              value={`${amount(payload.total_carrier_gal ?? 0)} gal`}
              sub={`${amount(payload.tank_capacity_gal ?? 0)} gal tank`}
            />
            <Figure
              label="Tank loads"
              value={String(payload.tank_loads ?? 0)}
              sub={`${amount(payload.acres_per_load ?? 0)} ac per load`}
            />
            {payload.product_cost !== undefined ? (
              <Figure
                label="Product"
                value={formatMoney(payload.product_cost, payload.currency)}
                sub={
                  payload.cost_per_acre !== undefined
                    ? `${formatMoney(payload.cost_per_acre, payload.currency)} per acre`
                    : undefined
                }
              />
            ) : null}
          </div>

          <ul className="mt-3 space-y-2.5">
            {rows.map((row, index) => (
              <Row key={`${row.product.product_id}-${index}`} row={row} onAdd={onAdd} />
            ))}
          </ul>

          {payload.restricted_use_present ? (
            <p className="mt-2.5 rounded-lg bg-amber-50 px-2.5 py-2 text-[13px] text-amber-900">
              This plan includes a restricted-use product. The order cannot be completed until a current
              applicator licence is verified in the portal.
            </p>
          ) : null}
          {payload.note ? <p className="mt-2 text-[13px] text-(--ink-soft)">{payload.note}</p> : null}
          <p className="mt-2 text-[11px] text-(--ink-soft)">
            Rates, volumes, and container counts come from each product&rsquo;s label range. The label is the
            final word &mdash; read it before you mix.
          </p>
        </>
      )}
    </section>
  );
}
