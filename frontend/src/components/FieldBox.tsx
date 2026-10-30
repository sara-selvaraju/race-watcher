"use client";

import { useMemo, useState } from "react";
import type { MeetingOut } from "@/lib/api/client";
import { OddsChip } from "./OddsChip";
import { PriceSparkline } from "./PriceSparkline";

type Race = MeetingOut["races"][number];
type Runner = Race["runners"][number];

type SortKey = "rating" | "price" | "number";

function n(v: string | number | null | undefined): number | null {
  if (v == null) return null;
  const x = typeof v === "number" ? v : Number(v);
  return Number.isFinite(x) ? x : null;
}

const RATING_LABEL: Record<string, string> = {
  top: "Top rated",
  danger: "Danger",
  "each-way": "Each way",
  watch: "Watch",
};

const SORTS: { key: SortKey; label: string }[] = [
  { key: "rating", label: "Rating" },
  { key: "price", label: "Price" },
  { key: "number", label: "Number" },
];

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
        const pa = n(a.current_price?.price) ?? n(a.preview_price) ?? Infinity;
        const pb = n(b.current_price?.price) ?? n(b.preview_price) ?? Infinity;
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
    <section className="panel overflow-hidden">
      <header className="panel-head items-center">
        <h3 className="panel-title">Field</h3>
        <div className="seg" role="group" aria-label="Sort runners">
          {SORTS.map((s) => (
            <button key={s.key} type="button" aria-pressed={sort === s.key} onClick={() => setSort(s.key)}>
              {s.label}
            </button>
          ))}
        </div>
      </header>

      <ul className="divide-y divide-line">
        {rows.live.map((runner) => (
          <RunnerRow key={runner.id} runner={runner} />
        ))}
      </ul>
      {rows.scratched.length > 0 && (
        <div className="border-t border-line bg-surface-2 px-5 py-3 text-sm text-ink-3">
          <span className="font-semibold text-ink-2">Scratched: </span>
          {rows.scratched.map((r, i) => (
            <span key={r.id}>
              {i > 0 && ", "}
              <span className="line-through">
                {r.number}. {r.name}
              </span>
            </span>
          ))}
        </div>
      )}
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
  const rating = runner.prediction?.rating ?? null;
  const form = runner.form_lines.find((f) => f.note)?.note;

  return (
    <li className="px-4 sm:px-5 py-3 flex items-start gap-3 hover:bg-surface-2">
      <span className="cloth shrink-0 mt-0.5">{runner.number}</span>

      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <h4 className="font-display text-xl font-bold leading-tight truncate">{runner.name}</h4>
          {runner.barrier != null && <span className="text-sm text-ink-3 shrink-0">({runner.barrier})</span>}
          {!runner.seeded && (
            <span
              className="text-xs text-drift border border-drift/40 rounded px-1 shrink-0"
              title="Added by LLM research. Connections may be wrong, so verify on racing.com"
            >
              unverified
            </span>
          )}
        </div>
        <p className="text-sm text-ink-3 truncate">
          {runner.jockey ? `J: ${runner.jockey}` : "Jockey not listed"}
          {runner.trainer && <>, T: {runner.trainer}</>}
          {runner.weight_kg != null && <>, {Number(runner.weight_kg)}kg</>}
        </p>
        {form && <p className="text-sm text-ink-2 mt-1 line-clamp-2 sm:line-clamp-1" title={form}>{form}</p>}
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <span className="hidden sm:inline-flex">
          <PriceSparkline prices={prices} />
        </span>
        <div className="text-right w-20">
          <OddsChip price={current} basePrice={baseline} previewPrice={n(runner.preview_price)} />
          {winProb != null && winProb > 0 && (
            <p className="text-xs text-ink-3 mt-1" title={runner.prediction?.rationale ?? undefined}>
              {(winProb * 100).toFixed(0)}%{rating && RATING_LABEL[rating] ? `, ${RATING_LABEL[rating]}` : ""}
            </p>
          )}
        </div>
      </div>
    </li>
  );
}
