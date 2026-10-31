"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type AgentOut, type PlaygroundOut } from "@/lib/api/client";
import { useMeetings } from "@/lib/api/hooks";
import { clsx } from "@/lib/clsx";
import { raceDayLabel } from "@/lib/time";
import { hasJumped, schedule } from "@/lib/tracks";
import { price, useModels } from "@/components/ModelPicker";
import { renderRationale } from "@/components/TopPicksBox";

// Results are kept in this browser only, so they survive a reload. Nothing is saved on the server.
const RESULTS_KEY = "race-watcher.playground-results";
const KEEP = 12;

function loadResults(): PlaygroundOut[] {
  try {
    return JSON.parse(localStorage.getItem(RESULTS_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function storeResults(results: PlaygroundOut[]) {
  try {
    localStorage.setItem(RESULTS_KEY, JSON.stringify(results));
  } catch {
    // Private mode etc.: results just won't survive a reload.
  }
}

/** Run one agent once on one race with any model, and compare what comes back. */
export function Playground({ agents, token }: { agents: AgentOut[]; token: string }) {
  const runnable = agents.filter((a) => a.model_choice);
  const { data: meetings } = useMeetings();
  const { data: models } = useModels(token);
  const timeline = useMemo(() => schedule(meetings ?? []), [meetings]);

  const [agentKey, setAgentKey] = useState(runnable[0]?.key ?? "");
  const [raceId, setRaceId] = useState<number | null>(null);
  const [model, setModel] = useState("");
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<PlaygroundOut[]>([]);

  const agent = runnable.find((a) => a.key === agentKey);
  const choice = agent?.model_choice;
  const needsRunners = agentKey === "odds" || agentKey === "tipster";

  useEffect(() => setResults(loadResults()), []);

  // Default to the next race to jump that has a field.
  useEffect(() => {
    if (raceId != null || timeline.length === 0) return;
    const now = Date.now();
    const next =
      timeline.find((s) => !hasJumped(s.startMs, now) && s.race.runners.length > 0) ??
      timeline.find((s) => s.race.runners.length > 0);
    if (next) setRaceId(next.race.id);
  }, [timeline, raceId]);

  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    const id = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(id);
  }, [running]);

  function keep(next: PlaygroundOut[]) {
    const trimmed = next.slice(0, KEEP);
    setResults(trimmed);
    storeResults(trimmed);
  }

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (!agent || raceId == null || running) return;
    setRunning(true);
    setElapsed(0);
    setError(null);
    const { data, error: err } = await api.POST("/api/v1/admin/playground", {
      body: { agent: agent.key, race_id: raceId, model: model.trim() || null },
      headers: { "X-Admin-Token": token },
    });
    setRunning(false);
    if (err || !data) {
      const detail = (err as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "The run didn't complete. Try again.");
      return;
    }
    keep([data, ...results]);
  }

  const days = useMemo(() => {
    const out = new Map<string, typeof timeline>();
    for (const s of timeline) out.set(s.meeting.date, [...(out.get(s.meeting.date) ?? []), s]);
    return [...out.entries()];
  }, [timeline]);

  const typed = models?.find((m) => m.id === model.trim());

  return (
    <section className="space-y-4" aria-labelledby="playground-title">
      <div className="max-w-[70ch]">
        <h2 id="playground-title" className="font-display text-4xl font-bold leading-none">
          Playground
        </h2>
        <p className="mt-2 text-ink-2">
          Run one agent once, on one race, with any model, and see what it produces. Nothing is saved: the race page
          and run history don&apos;t change. Each run does cost real OpenRouter credit, shown on its result.
        </p>
      </div>

      <form onSubmit={run} className="panel px-5 py-4 grid gap-3 md:grid-cols-[auto_minmax(0,1.4fr)_minmax(0,1.2fr)_auto] md:items-end">
        <label className="text-sm">
          <span className="block text-ink-3 mb-1">Agent</span>
          <select
            value={agentKey}
            onChange={(e) => {
              setAgentKey(e.target.value);
              setModel("");
            }}
            className="w-full rounded-md border border-line bg-surface px-2 py-1.5"
          >
            {runnable.map((a) => (
              <option key={a.key} value={a.key}>
                {a.name}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm min-w-0">
          <span className="block text-ink-3 mb-1">Race</span>
          <select
            value={raceId ?? ""}
            onChange={(e) => setRaceId(Number(e.target.value))}
            className="w-full rounded-md border border-line bg-surface px-2 py-1.5"
          >
            {days.map(([date, races]) => (
              <optgroup key={date} label={`${raceDayLabel(date)}, ${races[0].meeting.track}`}>
                {races.map((s) => (
                  <option key={s.race.id} value={s.race.id} disabled={needsRunners && s.race.runners.length === 0}>
                    R{s.race.number} {s.race.start_time_local?.slice(0, 5)} {s.race.name}
                    {s.race.runners.length === 0 ? " (no field yet)" : ""}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>

        <label className="text-sm min-w-0">
          <span className="block text-ink-3 mb-1">Model</span>
          <input
            list="playground-models"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={choice ? `${choice.id} (current)` : ""}
            className="w-full rounded-md border border-line bg-surface px-2 py-1.5"
          />
          <datalist id="playground-models">
            {[...new Set([...(choice?.suggested ?? []), ...(models ?? []).map((m) => m.id)])]
              .filter((id) => !choice?.needs_tools || models?.find((m) => m.id === id)?.tools !== false)
              .map((id) => (
                <option key={id} value={id} />
              ))}
          </datalist>
        </label>

        <button type="submit" className="btn btn-primary justify-center" disabled={running || !agent || raceId == null}>
          {running ? `Running… ${elapsed}s` : "Run"}
        </button>

        <p className="md:col-span-4 text-sm text-ink-3">
          {typed ? `${typed.name}: ${price(typed)}. ` : ""}
          Leave the model empty to use the agent&apos;s current one. Runs take from a few seconds (notes) to a minute
          or two (web search).
        </p>
        {error && <p className="md:col-span-4 text-sm text-drift">{error}</p>}
      </form>

      {results.length > 0 && (
        <>
          <div className="flex items-baseline gap-4">
            <h3 className="font-semibold">Results, newest first</h3>
            <button type="button" className="text-sm text-ink-3 underline" onClick={() => keep([])}>
              Clear all
            </button>
          </div>
          <div className="grid gap-4 lg:grid-cols-2 items-start">
            {results.map((r, i) => (
              <Result key={`${r.started_at}-${i}`} result={r} onRemove={() => keep(results.filter((_, j) => j !== i))} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function Result({ result: r, onRemove }: { result: PlaygroundOut; onRemove: () => void }) {
  const sites = Object.entries(r.sites);
  const tokens = r.prompt_tokens + r.completion_tokens;
  const empty =
    !r.error &&
    ((r.prices && r.prices.length === 0) ||
      (r.picks && r.picks.length === 0) ||
      (r.field && r.field.length === 0) ||
      (r.note && !r.note.text));

  return (
    <article className="panel overflow-hidden">
      <header className="px-5 py-3 border-b border-line flex items-start gap-3">
        <div className="min-w-0">
          <h4 className="font-display text-xl font-bold leading-tight">{r.agent_name}</h4>
          <p className="text-sm text-ink-2">{r.race_label}</p>
          <code className="block text-sm font-semibold break-all mt-1">{r.model}</code>
        </div>
        <button type="button" onClick={onRemove} className="ml-auto text-sm text-ink-3 underline shrink-0">
          Remove
        </button>
      </header>

      <div className="px-5 py-3 border-b border-line bg-surface-2 text-sm flex flex-wrap gap-x-5 gap-y-1">
        <span>
          <span className="text-ink-3">Cost </span>
          <strong>{r.cost_usd != null ? dollars(r.cost_usd) : "not reported"}</strong>
        </span>
        <span>
          <span className="text-ink-3">Tokens </span>
          {tokens.toLocaleString()}
        </span>
        <span>
          <span className="text-ink-3">Time </span>
          {r.seconds}s
        </span>
        <span className="text-ink-3">
          {new Date(r.started_at).toLocaleString("en-AU", { weekday: "short", hour: "numeric", minute: "2-digit" })}
        </span>
        {sites.length > 0 && (
          <ul className="basis-full flex flex-wrap gap-1.5" aria-label="Sites cited">
            {sites.map(([site, n]) => (
              <li key={site} className="rounded-full border border-line bg-surface px-2 py-0.5 text-xs text-ink-2">
                {site}
                {n > 1 && <span className="text-ink-3"> ×{n}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="px-5 py-4 text-sm">
        {r.error ? (
          <p className="text-drift">Failed: {r.error}</p>
        ) : empty ? (
          <p className="text-ink-3">No usable answer: the model returned nothing the agent could use.</p>
        ) : null}

        {r.prices && r.prices.length > 0 && (
          <table className="w-full">
            <thead className="text-ink-3 text-left">
              <tr>
                <th className="font-normal pb-1">Runner</th>
                <th className="font-normal pb-1 text-right">This run</th>
                <th className="font-normal pb-1 text-right">Saved now</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {r.prices.map((p) => (
                <tr key={p.runner_number}>
                  <td className="py-1">
                    {p.runner_number}. {p.runner_name}
                  </td>
                  <td className="py-1 text-right num text-base">
                    ${Number(p.price).toFixed(2)} <span className="text-ink-3 text-xs">{p.source}</span>
                  </td>
                  <td className="py-1 text-right num text-base text-ink-3">
                    {p.saved_price != null ? `$${Number(p.saved_price).toFixed(2)}` : "none"}{" "}
                    {p.saved_source && <span className="text-xs">{p.saved_source}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {r.picks && r.picks.length > 0 && (
          <ol className="space-y-3">
            {r.picks.map((p) => (
              <li key={p.rank}>
                <p className="font-semibold">
                  {p.rank}. {p.runner_name} ({p.runner_number})
                </p>
                {p.rationale && <p className="text-ink-2 leading-relaxed">{renderRationale(p.rationale)}</p>}
              </li>
            ))}
          </ol>
        )}

        {r.field && r.field.length > 0 && (
          <ul className="divide-y divide-line">
            {r.field.map((f) => (
              <li key={`${f.runner_number}-${f.runner_name}`} className={clsx("py-1 flex gap-2", f.scratched && "line-through text-ink-3")}>
                <span>
                  {f.runner_number}. {f.runner_name}
                </span>
                <span className="text-ink-3">
                  {[f.barrier != null && `barrier ${f.barrier}`, f.jockey, f.trainer].filter(Boolean).join(", ")}
                </span>
                {!f.on_card && <span className="ml-auto text-xs font-semibold text-turf">Not on card</span>}
              </li>
            ))}
          </ul>
        )}

        {r.note && (
          <div className="space-y-3">
            {r.note.text && <p className="text-[15px] leading-relaxed">{r.note.text}</p>}
            {r.note.current && (
              <details>
                <summary className="cursor-pointer font-semibold text-turf">Note on the race page now</summary>
                <p className="mt-2 leading-relaxed text-ink-2">{r.note.current}</p>
              </details>
            )}
            <details>
              <summary className="cursor-pointer font-semibold text-turf">Facts it was given</summary>
              <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-line bg-surface-2 p-3 text-[13px]">
                {r.note.facts}
              </pre>
            </details>
          </div>
        )}
      </div>
    </article>
  );
}

function dollars(v: string): string {
  const n = Number(v);
  return n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(3)}`;
}
