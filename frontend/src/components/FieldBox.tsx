"use client";

import { useMemo, useState } from "react";
import type { MeetingOut } from "@/lib/api/client";
import { OddsChip } from "./OddsChip";
import { PriceSparkline } from "./PriceSparkline";
import { clsx } from "@/lib/clsx";

type Race = MeetingOut["races"][number];
type Runner = Race["runners"][number];

type SortKey = "rating" | "price" | "number";

function n(v: string | number | null | undefined): number | null {
  if (v == null) return null;
  const x = typeof v === "number" ? v : Number(v);
  return Number.isFinite(x) ? x : null;
}

const RATING_COLOR = {
  top: "text-gold",
  danger: "text-vermilion",
  "each-way": "text-indigo-ink",
  watch: "text-ink-2",
} as const;

export function FieldBox({ race }: { race: Race }) {
  const [sort, setSort] = useState<SortKey>("rating");

  const rows = useMemo(() => {
    const live = race.runners.filter((r) => !r.scratched);
    const scratched = race.runners.filter((r) => r.scratched);
    const sorted = [...live];
    if (sort === "number") {
      sorted.sort((a, b) => a.number - b.number);
    } else if (sort === "price") {
      sorted.sort((a, b) => {
        const pa = n(a.current_price?.price) ?? Infinity;
        const pb = n(b.current_price?.price) ?? Infinity;
        return pa - pb;
      });
    } else {
      sorted.sort(
        (a, b) => (n(b.prediction?.win_prob) ?? 0) - (n(a.prediction?.win_prob) ?? 0),
      );
    }
    return { live: sorted, scratched };
  }, [race.runners, sort]);

  return (
    <section
      className="bento bento-ticks animate-bento-in"
      style={{ animationDelay: "120ms" }}
    >
      <header className="px-4 sm:px-5 py-3 sm:py-4 flex items-center justify-between gap-3 border-b border-hairline">
        <span className="label-section">
          <span className="font-display tracking-kanji text-ink">出走馬</span>
          <span className="text-ink-3 normal-case tracking-normal font-sans">
            Full field
          </span>
        </span>
        <div className="flex gap-1 font-mono text-[10px] tracking-widest shrink-0">
          {(["rating", "price", "number"] as SortKey[]).map((k) => (
            <button
              key={k}
              onClick={() => setSort(k)}
              className={clsx(
                "px-2 py-1 border transition-colors",
                sort === k
                  ? "border-gold text-gold bg-gold/5"
                  : "border-hairline text-ink-ghost hover:border-hairline-bright hover:text-ink-3",
              )}
            >
              {k.toUpperCase()}
            </button>
          ))}
        </div>
      </header>

      <ul className="divide-y divide-hairline">
        {rows.live.map((runner) => (
          <RunnerRow key={runner.id} runner={runner} />
        ))}
        {rows.scratched.length > 0 && (
          <li className="px-4 sm:px-5 py-3 bg-bg-soft">
            <div className="label-section">
              <span className="font-display tracking-kanji text-ink-3">取消</span>
              <span className="font-sans normal-case tracking-normal text-ink-ghost">
                Scratched
              </span>
            </div>
          </li>
        )}
        {rows.scratched.map((runner) => (
          <li
            key={runner.id}
            className="px-4 sm:px-5 py-3 flex items-center gap-3 text-ink-ghost"
          >
            <span className="font-mono text-xs">#{runner.number}</span>
            <span className="font-display text-sm line-through opacity-60">
              {runner.name}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function RunnerRow({ runner }: { runner: Runner }) {
  const prices = runner.price_history
    .map((p) => n(p.price))
    .filter((x): x is number => x != null);
  const baseline = prices[0];
  const current = n(runner.current_price?.price);
  const winProb = n(runner.prediction?.win_prob);
  const rating = (runner.prediction?.rating ?? null) as keyof typeof RATING_COLOR | null;

  return (
    <li
      className={clsx(
        "px-4 sm:px-5 py-3 sm:py-3.5 transition-colors hover:bg-paper-raised group",
        "flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4",
      )}
    >
      {/* TOP on mobile / LEFT on desktop: number + name + connections */}
      <div className="flex items-baseline gap-3 sm:items-center sm:flex-1 sm:min-w-0">
        <span className="font-mono text-base tabular-nums text-ink-2 group-hover:text-ink w-6 shrink-0">
          {runner.number}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="font-display text-base text-ink truncate leading-snug">
              {runner.name}
            </h4>
            {!runner.seeded && (
              <span
                className="font-mono text-[8px] tracking-widest text-vermilion/80 border border-vermilion/30 px-1 py-0.5 leading-none shrink-0"
                title="Added via LLM research — connections may be wrong, verify on racing.com"
              >
                RES
              </span>
            )}
          </div>
          <div className="font-mono text-[10px] tracking-widest text-ink-ghost truncate mt-0.5">
            {(runner.jockey ?? "—").toUpperCase()}
            <span className="mx-1.5 opacity-50">·</span>
            {(runner.trainer ?? "—").toUpperCase()}
            {runner.barrier != null && (
              <>
                <span className="mx-1.5 opacity-50">·</span>
                BR {runner.barrier}
              </>
            )}
          </div>
        </div>
      </div>

      {/* BOTTOM on mobile / RIGHT on desktop: odds + sparkline + prediction */}
      <div className="flex items-center justify-between gap-4 pl-9 sm:pl-0 sm:shrink-0 sm:gap-5">
        <div className="flex items-center gap-2.5">
          <OddsChip price={current} basePrice={baseline} />
          <PriceSparkline prices={prices} />
        </div>
        <div className="text-right shrink-0 w-16">
          {winProb != null ? (
            <div
              className="inline-flex flex-col items-end"
              title={runner.prediction?.rationale ?? undefined}
            >
              <span className="font-mono text-sm tabular-nums text-ink">
                {(winProb * 100).toFixed(1)}%
              </span>
              {rating && (
                <span
                  className={clsx(
                    "font-mono text-[9px] tracking-widest mt-0.5",
                    RATING_COLOR[rating] ?? "text-ink-3",
                  )}
                >
                  {rating.toUpperCase().replace("-", " ")}
                </span>
              )}
            </div>
          ) : (
            <span className="font-mono text-[10px] tracking-widest text-ink-ghost">—</span>
          )}
        </div>
      </div>
    </li>
  );
}
