"use client";

import { useMemo } from "react";
import { useAlerts } from "@/lib/api/hooks";
import { clsx } from "@/lib/clsx";

export function MovementFeed({ onSelect }: { onSelect: (raceId: number) => void }) {
  const { data, isPending, error } = useAlerts();

  // The poller writes alerts against TWO baselines (open + previous) for each
  // significant move, and repeat refreshes can log the same effective move
  // multiple times. Collapse to the most recent alert per runner.
  const deduped = useMemo(() => {
    if (!data) return null;
    const seen = new Set<number>();
    const out: typeof data = [];
    for (const a of data) {
      if (seen.has(a.runner_id)) continue;
      seen.add(a.runner_id);
      out.push(a);
    }
    return out;
  }, [data]);

  return (
    <section className="panel overflow-hidden">
      <header className="panel-head">
        <h3 className="panel-title">Market moves</h3>
        <p className="text-sm text-ink-3">All tracks</p>
      </header>

      <div className="max-h-[480px] overflow-y-auto">
        {isPending && <p className="px-5 py-6 text-ink-3 animate-pulse">Loading moves…</p>}
        {error && !isPending && (
          <p className="px-5 py-6 text-drift">Couldn&apos;t load market moves. They&apos;ll retry in 30 seconds.</p>
        )}
        {deduped && deduped.length === 0 && (
          <p className="px-5 py-8 text-ink-3">
            No big moves yet. A runner shows here when its price shifts by 10% or more between refreshes.
          </p>
        )}
        <ul className="divide-y divide-line">
          {deduped?.map((a) => {
            const from = Number(a.from_price);
            const to = Number(a.to_price);
            const pct = Number(a.pct_change);
            const isFirm = a.direction === "firm";
            const time = new Date(a.created_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
            return (
              <li key={a.id}>
                <button
                  type="button"
                  onClick={() => onSelect(a.race_id)}
                  className="w-full px-5 py-3 flex items-center justify-between gap-3 text-left hover:bg-surface-2"
                >
                  <div className="min-w-0">
                    <p className="font-display text-lg font-bold leading-tight truncate">{a.runner_name}</p>
                    <p className="text-sm text-ink-3">
                      {a.track} R{a.race_number}, {time}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="num text-sm text-ink-2">
                      ${from.toFixed(2)} to ${to.toFixed(2)}
                    </p>
                    <p className={clsx("num font-bold", isFirm ? "text-firm" : "text-drift")}>
                      {isFirm ? "▼ firmed" : "▲ drifted"} {Math.abs(pct).toFixed(0)}%
                    </p>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
