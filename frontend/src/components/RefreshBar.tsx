"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { clsx } from "@/lib/clsx";

type StepId = "odds" | "research" | "ratings" | "field";

type Step = {
  id: StepId;
  label: string;
  kanji: string;
  path: string;
  hint: string;
  summarize: (d: Record<string, unknown>) => string;
};

// Order matters: odds + research + ratings settle from the trusted seed roster
// FIRST, then field expansion can add the rest of the runners as awareness-only
// rows without affecting the picks or ratings already computed for the seed set.
const STEPS: Step[] = [
  {
    id: "odds",
    label: "Odds",
    kanji: "値",
    path: "/api/v1/admin/refresh-odds",
    hint: "fetch current prices",
    summarize: (d) =>
      `${num(d.snapshots) ?? 0} prices · ${num(d.alerts) ?? 0} movements`,
  },
  {
    id: "research",
    label: "Research",
    kanji: "予",
    path: "/api/v1/admin/refresh-tips",
    hint: "web search per race for tips",
    summarize: (d) =>
      `${num(d.picks) ?? 0} picks · ${num(d.races) ?? 0} races`,
  },
  {
    id: "ratings",
    label: "Ratings",
    kanji: "算",
    path: "/api/v1/admin/predict",
    hint: "recompute heuristic ratings",
    summarize: (d) => `${num(d.created) ?? 0} ratings`,
  },
  {
    id: "field",
    label: "Field",
    kanji: "馬",
    path: "/api/v1/admin/expand-field",
    hint: "fill out runner list (racing.com only)",
    summarize: (d) =>
      `+${num(d.added) ?? 0} runners · ${num(d.races) ?? 0} races`,
  },
];

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

type StepStatus = "pending" | "running" | "done" | "error";
type StepState = {
  id: StepId;
  status: StepStatus;
  summary?: string;
  error?: string;
};

type State = {
  running: boolean;
  steps: StepState[];
  startedAt?: number;
  finishedAt?: number;
};

const INITIAL_STEPS: StepState[] = STEPS.map((s) => ({
  id: s.id,
  status: "pending",
}));

export function RefreshBar() {
  const qc = useQueryClient();
  const [state, setState] = useState<State>({
    running: false,
    steps: INITIAL_STEPS,
  });

  async function runAll() {
    if (state.running) return;
    setState({
      running: true,
      steps: STEPS.map((s) => ({ id: s.id, status: "pending" })),
      startedAt: Date.now(),
    });

    for (let i = 0; i < STEPS.length; i++) {
      const step = STEPS[i];
      setState((s) => ({
        ...s,
        steps: s.steps.map((x, idx) =>
          idx === i ? { ...x, status: "running" } : x,
        ),
      }));
      try {
        // openapi-fetch typing for arbitrary admin paths is loose; cast through unknown.
        const { data, error } = await (
          api.POST as unknown as (
            path: string,
          ) => Promise<{ data?: unknown; error?: unknown }>
        )(step.path);
        if (error || !data) {
          throw new Error(
            typeof error === "string"
              ? error
              : JSON.stringify(error ?? "no data"),
          );
        }
        const summary = step.summarize(data as Record<string, unknown>);
        setState((s) => ({
          ...s,
          steps: s.steps.map((x, idx) =>
            idx === i ? { ...x, status: "done", summary } : x,
          ),
        }));
        // Invalidate after each step so the UI updates progressively as data lands.
        await invalidate();
      } catch (err) {
        const msg = err instanceof Error ? err.message.slice(0, 120) : "failed";
        setState((s) => ({
          ...s,
          running: false,
          steps: s.steps.map((x, idx) =>
            idx === i ? { ...x, status: "error", error: msg } : x,
          ),
          finishedAt: Date.now(),
        }));
        return;
      }
    }

    setState((s) => ({ ...s, running: false, finishedAt: Date.now() }));
  }

  async function invalidate() {
    await qc.invalidateQueries({ queryKey: ["meeting"] });
    await qc.invalidateQueries({ queryKey: ["alerts"] });
    await qc.invalidateQueries({ queryKey: ["status"] });
  }

  const errorIdx = state.steps.findIndex((s) => s.status === "error");
  const elapsed =
    state.finishedAt && state.startedAt
      ? Math.max(1, Math.round((state.finishedAt - state.startedAt) / 1000))
      : null;
  const idle = !state.running && state.finishedAt == null;

  return (
    <section className="bento bento-ticks animate-bento-in px-4 sm:px-5 py-3.5 flex flex-col gap-3">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5 shrink-0">
          <span className="font-display text-base text-ink leading-none">
            更新
          </span>
          <span className="font-mono text-[10px] tracking-widest text-ink-3">
            REFRESH
          </span>
        </div>

        <p className="font-mono text-[10px] tracking-widest text-ink-ghost hidden md:block">
          ODDS → RESEARCH → RATINGS → FIELD · ~3 MIN
        </p>

        <button
          type="button"
          data-variant="primary"
          className={clsx("btn-bento ml-auto", state.running && "animate-pulse")}
          disabled={state.running}
          onClick={runAll}
          title="Run the full refresh sequence: field, odds, research, ratings"
        >
          <span
            className={clsx(
              "font-display text-sm leading-none",
              state.running && "animate-spin-slow",
            )}
          >
            {state.running ? "⟳" : "↻"}
          </span>
          <span>
            {state.running
              ? "Refreshing…"
              : state.finishedAt
                ? "Refresh again"
                : "Refresh card"}
          </span>
        </button>
      </div>

      {!idle && (
        <ol className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {state.steps.map((step, idx) => {
            const meta = STEPS[idx];
            const icon =
              step.status === "done"
                ? "✓"
                : step.status === "error"
                  ? "×"
                  : step.status === "running"
                    ? "⟳"
                    : `${idx + 1}`;
            const tone =
              step.status === "done"
                ? "text-matcha border-matcha/40"
                : step.status === "error"
                  ? "text-vermilion border-vermilion/60 bg-vermilion/5"
                  : step.status === "running"
                    ? "text-gold border-gold/70 bg-gold/5"
                    : "text-ink-ghost border-hairline";
            return (
              <li
                key={step.id}
                className={clsx(
                  "border px-3 py-2 flex flex-col gap-1 transition-colors",
                  tone,
                )}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={clsx(
                      "font-mono text-sm leading-none w-4 text-center",
                      step.status === "running" && "animate-spin-slow",
                    )}
                  >
                    {icon}
                  </span>
                  <span className="font-display text-sm text-ink leading-none">
                    {meta.kanji}
                  </span>
                  <span className="font-mono text-[10px] tracking-widest uppercase">
                    {meta.label}
                  </span>
                </div>
                <span
                  className="font-mono text-[10px] text-ink-3 leading-snug truncate"
                  title={
                    step.status === "error"
                      ? step.error
                      : step.status === "done"
                        ? step.summary
                        : meta.hint
                  }
                >
                  {step.status === "done" && step.summary}
                  {step.status === "error" && (step.error ?? "failed")}
                  {step.status === "running" && "working…"}
                  {step.status === "pending" && "queued"}
                </span>
              </li>
            );
          })}
        </ol>
      )}

      {!state.running && state.finishedAt && (
        <p className="font-mono text-[10px] tracking-widest">
          {errorIdx >= 0 ? (
            <span className="text-vermilion">
              × Stopped at {STEPS[errorIdx].label.toUpperCase()}
            </span>
          ) : (
            <span className="text-matcha">✓ Card refreshed</span>
          )}
          {elapsed != null && (
            <span className="text-ink-ghost"> · {elapsed}s</span>
          )}
        </p>
      )}
    </section>
  );
}
