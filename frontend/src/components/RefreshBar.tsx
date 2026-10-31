"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { readToken, saveToken } from "@/lib/adminToken";
import { api } from "@/lib/api/client";
import { clsx } from "@/lib/clsx";

type StepId = "odds" | "research" | "ratings" | "field" | "summary";

type Step = {
  id: StepId;
  label: string;
  path: string;
  summarize: (d: Record<string, unknown>) => string;
};

// Order matters: odds + research + ratings settle from the trusted seed roster
// FIRST, then field expansion can add the rest of the runners as awareness-only
// rows without affecting the picks or ratings already computed for the seed set.
const STEPS: Step[] = [
  {
    id: "odds",
    label: "Odds",
    path: "/api/v1/admin/refresh-odds",
    summarize: (d) => `${num(d.snapshots) ?? 0} prices, ${num(d.alerts) ?? 0} moves`,
  },
  {
    id: "research",
    label: "Tips",
    path: "/api/v1/admin/refresh-tips",
    summarize: (d) => `${num(d.picks) ?? 0} picks in ${num(d.races) ?? 0} races`,
  },
  {
    id: "ratings",
    label: "Ratings",
    path: "/api/v1/admin/predict",
    summarize: (d) => `${num(d.created) ?? 0} rated`,
  },
  {
    id: "field",
    label: "Field",
    path: "/api/v1/admin/expand-field",
    summarize: (d) => `${num(d.added) ?? 0} runners added`,
  },
  {
    id: "summary",
    label: "Notes",
    path: "/api/v1/admin/summarize",
    summarize: (d) => `${num(d.written) ?? 0} races written`,
  },
];

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

type StepStatus = "pending" | "running" | "done" | "error";
type StepState = { status: StepStatus; summary?: string; error?: string };

type Props = { meetingId: number; track: string };

// Viewers never see the Refresh bar: it appears only where an admin token is saved, or when the
// page is opened with ?admin to enter one.

class Unauthorized extends Error {}

export function RefreshBar({ meetingId, track }: Props) {
  const qc = useQueryClient();
  const [runningFor, setRunningFor] = useState<number | null>(null);
  const [steps, setSteps] = useState<StepState[] | null>(null);
  const [stepsFor, setStepsFor] = useState<number | null>(null);
  const running = runningFor != null;
  const [token, setToken] = useState("");
  const [askToken, setAskToken] = useState(false);
  const [tokenRejected, setTokenRejected] = useState(false);
  const [draft, setDraft] = useState("");

  useEffect(() => {
    const saved = readToken();
    setToken(saved);
    if (!saved && new URLSearchParams(window.location.search).has("admin")) setAskToken(true);
  }, []);

  async function runAll(withToken = token) {
    if (running) return;
    if (!withToken) {
      setAskToken(true);
      return;
    }
    setRunningFor(meetingId);
    setStepsFor(meetingId);
    setSteps(STEPS.map(() => ({ status: "pending" })));
    const update = (i: number, s: StepState) =>
      setSteps((prev) => prev && prev.map((x, idx) => (idx === i ? s : x)));

    for (let i = 0; i < STEPS.length; i++) {
      update(i, { status: "running" });
      try {
        // openapi-fetch typing for arbitrary admin paths is loose; cast through unknown.
        const { data, error, response } = await (
          api.POST as unknown as (
            path: string,
            init: { params: { query: { meeting_id: number } }; headers: Record<string, string> },
          ) => Promise<{ data?: unknown; error?: unknown; response: Response }>
        )(STEPS[i].path, {
          params: { query: { meeting_id: meetingId } },
          headers: { "X-Admin-Token": withToken },
        });
        if (response.status === 401) throw new Unauthorized();
        if (error || !data) {
          throw new Error(typeof error === "string" ? error : JSON.stringify(error ?? "no data"));
        }
        update(i, { status: "done", summary: STEPS[i].summarize(data as Record<string, unknown>) });
        // Invalidate after each step so the UI updates progressively as data lands.
        await Promise.all(
          ["meetings", "alerts", "status"].map((k) => qc.invalidateQueries({ queryKey: [k] })),
        );
      } catch (err) {
        if (err instanceof Unauthorized) {
          saveToken("");
          setToken("");
          setTokenRejected(true);
          setAskToken(true);
          setSteps(null);
          break;
        }
        update(i, { status: "error", error: err instanceof Error ? err.message.slice(0, 120) : "failed" });
        break;
      }
    }
    setRunningFor(null);
  }

  function submitToken(e: React.FormEvent) {
    e.preventDefault();
    const t = draft.trim();
    if (!t) return;
    saveToken(t);
    setToken(t);
    setDraft("");
    setAskToken(false);
    setTokenRejected(false);
    void runAll(t);
  }

  function forgetToken() {
    saveToken("");
    setToken("");
    setSteps(null);
  }

  const shown = stepsFor === meetingId ? steps : null;
  const otherRunning = running && runningFor !== meetingId;

  // Read-only for everyone without the token.
  if (!token && !askToken) return null;

  return (
    <div className="border-t border-line bg-surface-2 px-5 py-3 flex flex-wrap items-center gap-x-4 gap-y-2">
      <button
        type="button"
        className="btn btn-primary"
        disabled={running}
        onClick={() => void runAll()}
        title="Fetch odds, research tips, recompute ratings, fill out the field, then write race notes. Takes a few minutes."
      >
        <span className={clsx(running && "animate-spin-slow")} aria-hidden>
          ↻
        </span>
        {otherRunning ? "Another track is refreshing" : running ? `Refreshing ${track}…` : `Refresh ${track}`}
      </button>

      {askToken ? (
        <form onSubmit={submitToken} className="flex flex-wrap items-center gap-2 text-sm">
          <label htmlFor="admin-token" className={clsx(tokenRejected ? "text-drift" : "text-ink-2")}>
            {tokenRejected ? "That admin token wasn't accepted. Try again:" : "Enter the admin token to refresh:"}
          </label>
          <input
            id="admin-token"
            type="password"
            autoComplete="off"
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="rounded-md border border-line bg-surface px-2 py-1 w-56"
          />
          <button type="submit" className="btn">Save and refresh</button>
          <button type="button" className="text-ink-3 underline" onClick={() => setAskToken(false)}>
            Cancel
          </button>
        </form>
      ) : shown ? (
        <ol className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {shown.map((s, i) => (
            <li
              key={STEPS[i].id}
              className={clsx(
                s.status === "done" && "text-firm",
                s.status === "error" && "text-drift",
                s.status === "running" && "text-ink font-semibold",
                s.status === "pending" && "text-ink-3",
              )}
              title={s.error}
            >
              {s.status === "done" ? "✓" : s.status === "error" ? "✕" : s.status === "running" ? "…" : "○"}{" "}
              {STEPS[i].label}
              {s.summary && <span className="text-ink-3"> ({s.summary})</span>}
              {s.status === "error" && <span> failed</span>}
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-sm text-ink-3">Odds, tips, ratings, field and notes for every {track} race.</p>
      )}

      {token && !running && (
        <span className="ml-auto flex gap-4 text-sm text-ink-3">
          <a href="/admin" className="underline">
            Admin page
          </a>
          <button type="button" className="underline" onClick={forgetToken}>
            Forget token on this browser
          </button>
        </span>
      )}
    </div>
  );
}
