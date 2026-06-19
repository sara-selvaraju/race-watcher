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
  watch: "text-paper-dim",
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
      <header className="px-5 py-4 flex items-center justify-between border-b border-hairline">
        <span className="label-section">
          <span className="font-display tracking-kanji text-paper">出走馬</span>
          <span className="text-paper-faint normal-case tracking-normal font-sans">
            Full field
          </span>
        </span>
        <div className="flex gap-1 font-mono text-[10px] tracking-widest">
          {(["rating", "price", "number"] as SortKey[]).map((k) => (
            <button
              key={k}
              onClick={() => setSort(k)}
              className={clsx(
                "px-2 py-1 border transition-colors",
                sort === k
                  ? "border-gold text-gold bg-gold/5"
                  : "border-hairline text-paper-ghost hover:border-hairline-bright hover:text-paper-faint",
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
          <li className="px-5 py-3 bg-ink-deep">
            <div className="label-section">
              <span className="font-display tracking-kanji text-paper-faint">取消</span>
              <span className="font-sans normal-case tracking-normal text-paper-ghost">
                Scratched
              </span>
            </div>
          </li>
        )}
        {rows.scratched.map((runner) => (
          <li
            key={runner.id}
            className="px-5 py-3 flex items-center gap-3 text-paper-ghost"
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
    <li className="px-5 py-3.5 grid grid-cols-12 gap-3 items-center transition-colors hover:bg-washi-raised group">
      {/* number + silk slot */}
      <div className="col-span-1 flex items-center gap-2">
        <span className="font-mono text-base tabular-nums text-paper-dim group-hover:text-paper">
          {runner.number}
        </span>
      </div>

      {/* name + connections */}
      <div className="col-span-5 sm:col-span-5 min-w-0">
        <h4 className="font-display text-base text-paper truncate leading-snug">
          {runner.name}
        </h4>
        <div className="font-mono text-[10px] tracking-widest text-paper-ghost truncate mt-0.5">
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

      {/* odds + sparkline */}
      <div className="col-span-3 sm:col-span-3 flex items-center gap-2.5 justify-end sm:justify-start">
        <OddsChip price={current} basePrice={baseline} />
        <PriceSparkline prices={prices} />
      </div>

      {/* prediction */}
      <div className="col-span-3 text-right">
        {winProb != null ? (
          <div
            className="inline-flex flex-col items-end"
            title={runner.prediction?.rationale ?? undefined}
          >
            <span className="font-mono text-sm tabular-nums text-paper">
              {(winProb * 100).toFixed(1)}%
            </span>
            {rating && (
              <span
                className={clsx(
                  "font-mono text-[9px] tracking-widest mt-0.5",
                  RATING_COLOR[rating] ?? "text-paper-faint",
                )}
              >
                {rating.toUpperCase().replace("-", " ")}
              </span>
            )}
          </div>
        ) : (
          <span className="font-mono text-[10px] tracking-widest text-paper-ghost">—</span>
        )}
      </div>
    </li>
  );
}
