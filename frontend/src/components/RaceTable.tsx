"use client";

import { useMemo, useState } from "react";
import type { MeetingOut } from "@/lib/api/client";
import { OddsChip } from "./OddsChip";
import { PriceSparkline } from "./PriceSparkline";
import { clsx } from "@/lib/clsx";

type Race = MeetingOut["races"][number];
type Runner = Race["runners"][number];

type SortKey = "number" | "price" | "rating";

function n(v: string | number | null | undefined): number | null {
  if (v == null) return null;
  const x = typeof v === "number" ? v : Number(v);
  return Number.isFinite(x) ? x : null;
}

function ratingColor(rating: string | null | undefined) {
  switch (rating) {
    case "top":
      return "bg-amber-900/40 text-amber-200 ring-amber-700/50";
    case "danger":
      return "bg-violet-900/40 text-violet-200 ring-violet-700/50";
    case "each-way":
      return "bg-sky-900/40 text-sky-200 ring-sky-700/50";
    case "watch":
      return "bg-zinc-800 text-zinc-200 ring-zinc-700";
    default:
      return "bg-zinc-900 text-zinc-400 ring-zinc-800";
  }
}

export function RaceTable({ race }: { race: Race }) {
  const [sort, setSort] = useState<SortKey>("price");

  const sortedRunners = useMemo(() => {
    const xs = [...race.runners].filter((r) => !r.scratched);
    if (sort === "number") return xs.sort((a, b) => a.number - b.number);
    if (sort === "rating") {
      return xs.sort((a, b) => (n(b.prediction?.win_prob) ?? 0) - (n(a.prediction?.win_prob) ?? 0));
    }
    return xs.sort((a, b) => {
      const pa = n(a.current_price?.price) ?? Infinity;
      const pb = n(b.current_price?.price) ?? Infinity;
      return pa - pb;
    });
  }, [race.runners, sort]);

  return (
    <section className="mt-4">
      <header className="flex items-baseline justify-between mb-3">
        <h2 className="text-lg font-semibold">
          <span className="text-zinc-400">R{race.number}</span> {race.name}
        </h2>
        <div className="text-sm text-zinc-400 font-mono">
          {race.distance_m}m · {race.start_time_local?.slice(0, 5)}
        </div>
      </header>

      <div className="flex gap-2 mb-2 text-xs">
        <span className="text-zinc-500">Sort:</span>
        {(["price", "rating", "number"] as SortKey[]).map((k) => (
          <button
            key={k}
            onClick={() => setSort(k)}
            className={clsx(
              "px-2 py-0.5 rounded",
              sort === k ? "bg-zinc-100 text-zinc-900" : "bg-zinc-800 text-zinc-300",
            )}
          >
            {k}
          </button>
        ))}
      </div>

      <ul className="divide-y divide-zinc-800 rounded-lg bg-zinc-950/60 ring-1 ring-zinc-800">
        {sortedRunners.map((runner) => (
          <RunnerRow key={runner.id} runner={runner} />
        ))}
      </ul>
    </section>
  );
}

function RunnerRow({ runner }: { runner: Runner }) {
  const prices = runner.price_history.map((p) => n(p.price)).filter((x): x is number => x != null);
  const baseline = prices[0];
  const current = n(runner.current_price?.price);
  const winProb = n(runner.prediction?.win_prob);

  return (
    <li className="px-3 py-3 grid grid-cols-12 items-center gap-2">
      <span className="col-span-1 font-mono text-zinc-300">{runner.number}</span>
      <div className="col-span-4 sm:col-span-5">
        <div className="font-medium truncate">{runner.name}</div>
        <div className="text-xs text-zinc-500 truncate">
          {runner.jockey ?? "—"} · {runner.trainer ?? "—"}
        </div>
      </div>
      <div className="col-span-3 sm:col-span-2 flex items-center gap-2">
        <OddsChip price={current} basePrice={baseline} />
        <PriceSparkline prices={prices} />
      </div>
      <div className="col-span-4 sm:col-span-4 text-right">
        {runner.prediction ? (
          <div
            className="inline-flex items-center gap-2"
            title={runner.prediction.rationale ?? undefined}
          >
            {winProb != null && (
              <span className="font-mono tabular-nums text-sm text-zinc-300">
                {(winProb * 100).toFixed(1)}%
              </span>
            )}
            <span
              className={clsx(
                "rounded px-2 py-0.5 text-xs ring-1",
                ratingColor(runner.prediction.rating),
              )}
            >
              {runner.prediction.rating ?? "?"}
            </span>
          </div>
        ) : (
          <span className="text-xs text-zinc-500">no rating</span>
        )}
      </div>
    </li>
  );
}
