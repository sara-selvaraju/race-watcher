"use client";

import { useAlerts } from "@/lib/api/hooks";
import { clsx } from "@/lib/clsx";

export function MovementFeed() {
  const { data, isPending, error } = useAlerts();

  return (
    <section
      className="bento bento-ticks animate-bento-in"
      style={{ animationDelay: "180ms" }}
    >
      <header className="px-5 py-4 flex items-center justify-between border-b border-hairline">
        <span className="label-section">
          <span className="font-display tracking-kanji text-paper">動向</span>
          <span className="text-paper-faint normal-case tracking-normal font-sans">
            Movements
          </span>
        </span>
        {data && (
          <span className="font-mono text-[10px] tracking-widest text-paper-ghost">
            {data.length} EVENTS
          </span>
        )}
      </header>

      <div className="max-h-[420px] overflow-y-auto">
        {isPending && <SkeletonRows />}
        {error && !isPending && (
          <div className="px-5 py-6 text-center text-vermilion font-mono text-xs tracking-widest">
            FEED UNAVAILABLE
          </div>
        )}
        {data && data.length === 0 && (
          <div className="px-5 py-10 text-center text-paper-ghost">
            <div className="font-display text-3xl mb-2 text-paper-faint">静</div>
            <p className="font-mono text-[10px] tracking-widest">QUIET — NO SIGNIFICANT MOVES</p>
          </div>
        )}
        <ul className="divide-y divide-hairline">
          {data?.map((a) => {
            const from = Number(a.from_price);
            const to = Number(a.to_price);
            const pct = Number(a.pct_change);
            const isFirm = a.direction === "firm";
            const time = new Date(a.created_at).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            });
            return (
              <li
                key={a.id}
                className="px-5 py-3 flex items-center justify-between gap-3 hover:bg-washi-raised transition-colors"
              >
                <div className="min-w-0">
                  <div className="font-display text-sm text-paper truncate flex items-baseline gap-2">
                    <span className="font-mono text-xs text-paper-faint">
                      R{a.race_number}
                    </span>
                    {a.runner_name}
                  </div>
                  <div className="font-mono text-[10px] tracking-widest text-paper-ghost mt-0.5">
                    {time} · {a.baseline.toUpperCase()}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-xs tabular-nums text-paper-dim">
                    ${from.toFixed(2)} → ${to.toFixed(2)}
                  </div>
                  <div
                    className={clsx(
                      "font-mono text-xs tabular-nums tracking-tight mt-0.5",
                      isFirm ? "text-matcha" : "text-vermilion",
                    )}
                  >
                    {isFirm ? "↓" : "↑"} {Math.abs(pct).toFixed(1)}%
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

function SkeletonRows() {
  return (
    <ul className="divide-y divide-hairline">
      {[0, 1, 2].map((i) => (
        <li key={i} className="px-5 py-4 h-14 animate-pulse">
          <div className="h-3 w-1/2 bg-washi-raised mb-2" />
          <div className="h-2 w-1/3 bg-washi-raised" />
        </li>
      ))}
    </ul>
  );
}
