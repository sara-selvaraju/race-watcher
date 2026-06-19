"use client";

import { useAlerts } from "@/lib/api/hooks";
import { clsx } from "@/lib/clsx";

export function MovementFeed() {
  const { data, isPending, error } = useAlerts();

  if (isPending) return <Skeleton />;
  if (error) return <p className="text-sm text-red-400">Couldn’t load movements.</p>;
  if (!data?.length) {
    return <p className="text-sm text-zinc-500">No significant moves yet.</p>;
  }

  return (
    <ul className="divide-y divide-zinc-800 rounded-lg bg-zinc-950/60 ring-1 ring-zinc-800">
      {data.map((a) => {
        const from = Number(a.from_price);
        const to = Number(a.to_price);
        const pct = Number(a.pct_change);
        return (
          <li key={a.id} className="px-3 py-2 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="font-medium truncate">
                <span className="text-zinc-400 mr-1">R{a.race_number}</span>
                {a.runner_name}
              </div>
              <div className="text-xs text-zinc-500">
                {new Date(a.created_at).toLocaleTimeString()} · {a.baseline} baseline
              </div>
            </div>
            <div className="font-mono text-sm whitespace-nowrap">
              ${from.toFixed(2)} → ${to.toFixed(2)}{" "}
              <span
                className={clsx(
                  "ml-1 rounded px-1.5 py-0.5 text-xs ring-1",
                  a.direction === "firm"
                    ? "bg-green-900/40 text-green-300 ring-green-700/50"
                    : "bg-red-900/40 text-red-300 ring-red-700/50",
                )}
              >
                {pct > 0 ? "+" : ""}
                {pct.toFixed(1)}%
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Skeleton() {
  return (
    <ul className="space-y-2">
      {[0, 1, 2].map((i) => (
        <li key={i} className="h-10 rounded bg-zinc-900 animate-pulse" />
      ))}
    </ul>
  );
}
