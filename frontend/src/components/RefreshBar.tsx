"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { clsx } from "@/lib/clsx";

type Action = {
  id: "odds" | "tips" | "field" | "predict";
  label: string;
  kanji: string;
  path:
    | "/api/v1/admin/refresh-odds"
    | "/api/v1/admin/refresh-tips"
    | "/api/v1/admin/expand-field"
    | "/api/v1/admin/predict";
  hint: string;
  variant?: "primary";
};

const ACTIONS: Action[] = [
  {
    id: "odds",
    label: "Odds",
    kanji: "値",
    path: "/api/v1/admin/refresh-odds",
    hint: "~15s · prices + movements",
    variant: "primary",
  },
  {
    id: "tips",
    label: "Research",
    kanji: "予",
    path: "/api/v1/admin/refresh-tips",
    hint: "~70s · top 3 picks per race",
  },
  {
    id: "field",
    label: "Field",
    kanji: "馬",
    path: "/api/v1/admin/expand-field",
    hint: "~90s · expand to full field",
  },
  {
    id: "predict",
    label: "Predict",
    kanji: "算",
    path: "/api/v1/admin/predict",
    hint: "~1s · recompute heuristic ratings",
  },
];

type State = {
  busy: Action["id"] | null;
  last: { id: Action["id"]; result: string; ok: boolean } | null;
};

export function RefreshBar() {
  const qc = useQueryClient();
  const [state, setState] = useState<State>({ busy: null, last: null });

  async function trigger(action: Action) {
    if (state.busy) return;
    setState({ busy: action.id, last: null });
    try {
      // openapi-fetch typing for arbitrary admin paths is loose; cast through unknown.
      const { data, error } = await (api.POST as unknown as (path: string) => Promise<{
        data?: unknown;
        error?: unknown;
      }>)(action.path);
      if (error || !data) throw new Error(JSON.stringify(error ?? "no data"));
      await qc.invalidateQueries({ queryKey: ["meeting"] });
      await qc.invalidateQueries({ queryKey: ["alerts"] });
      await qc.invalidateQueries({ queryKey: ["status"] });
      setState({
        busy: null,
        last: { id: action.id, result: summarize(data), ok: true },
      });
    } catch (e) {
      setState({
        busy: null,
        last: {
          id: action.id,
          result: e instanceof Error ? e.message.slice(0, 80) : "failed",
          ok: false,
        },
      });
    }
  }

  return (
    <section className="bento bento-ticks animate-bento-in px-4 sm:px-5 py-3 flex flex-col sm:flex-row sm:items-center gap-3">
      <div className="flex items-center gap-2.5 shrink-0">
        <span className="font-display text-base text-ink leading-none">更新</span>
        <span className="font-mono text-[10px] tracking-widest text-ink-3">REFRESH</span>
      </div>

      <div className="flex flex-wrap gap-2 flex-1 sm:justify-end">
        {ACTIONS.map((a) => {
          const isBusy = state.busy === a.id;
          const isDisabled = state.busy != null && !isBusy;
          return (
            <button
              key={a.id}
              type="button"
              data-variant={a.variant}
              className={clsx("btn-bento", isBusy && "animate-pulse")}
              disabled={isDisabled || isBusy}
              onClick={() => trigger(a)}
              title={a.hint}
            >
              <span className={clsx("font-display text-sm leading-none", isBusy && "animate-spin-slow")}>
                {isBusy ? "⟳" : a.kanji}
              </span>
              <span>{a.label}</span>
            </button>
          );
        })}
      </div>

      {state.last && (
        <span
          className={clsx(
            "font-mono text-[10px] tracking-widest whitespace-nowrap",
            state.last.ok ? "text-matcha" : "text-vermilion",
          )}
        >
          {state.last.ok ? "✓" : "×"} {state.last.id.toUpperCase()} ·{" "}
          <span className="text-ink-3">{state.last.result}</span>
        </span>
      )}
    </section>
  );
}

function summarize(data: unknown): string {
  if (!data || typeof data !== "object") return "ok";
  const d = data as Record<string, unknown>;
  if (typeof d.snapshots === "number") return `${d.snapshots} SNAPS / ${d.alerts ?? 0} ALERTS`;
  if (typeof d.picks === "number" && typeof d.races === "number")
    return `${d.picks} PICKS / ${d.races} RACES`;
  if (typeof d.added === "number") return `+${d.added} RUNNERS`;
  if (typeof d.created === "number") return `${d.created} CREATED`;
  return "DONE";
}
