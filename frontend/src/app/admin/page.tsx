"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { readToken, saveToken } from "@/lib/adminToken";
import { api, type AdminOverviewOut, type AgentOut } from "@/lib/api/client";
import { clsx } from "@/lib/clsx";
import { useNow } from "@/lib/useNow";
import { ModelPicker } from "@/components/ModelPicker";

class Unauthorized extends Error {}

function useOverview(token: string) {
  return useQuery<AdminOverviewOut>({
    queryKey: ["admin-overview", token],
    enabled: !!token,
    refetchInterval: 60_000,
    retry: (n, err) => !(err instanceof Unauthorized) && n < 2,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/admin/overview", {
        headers: { "X-Admin-Token": token },
      });
      if (response.status === 401) throw new Unauthorized();
      if (error || !data) throw new Error("Failed to load the admin overview");
      return data;
    },
  });
}

export default function AdminPage() {
  const [token, setToken] = useState<string | null>(null);
  const [rejected, setRejected] = useState(false);
  const { data, error, isPending } = useOverview(token ?? "");
  const now = useNow(30_000);

  useEffect(() => setToken(readToken()), []);

  useEffect(() => {
    if (error instanceof Unauthorized) {
      saveToken("");
      setToken("");
      setRejected(true);
    }
  }, [error]);

  return (
    <>
      <header className="bg-turf text-white">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 h-14 flex items-center gap-4">
          <a href="/" className="font-display text-2xl font-bold tracking-tight leading-none">
            Race Watcher
          </a>
          <span className="text-white/75">Admin</span>
          <a href="/" className="ml-auto text-sm text-white/85 underline underline-offset-2">
            Back to the races
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 sm:px-6 py-6 md:py-8 space-y-8">
        {token === null ? null : !token ? (
          <TokenForm
            rejected={rejected}
            onSave={(t) => {
              saveToken(t);
              setToken(t);
              setRejected(false);
            }}
          />
        ) : isPending ? (
          <p className="text-ink-3">Loading…</p>
        ) : error || !data ? (
          <p className="panel px-5 py-4 text-drift">Couldn&apos;t load the admin overview. Is the API up?</p>
        ) : (
          <Overview data={data} now={now} token={token} />
        )}
      </main>
    </>
  );
}

function TokenForm({ rejected, onSave }: { rejected: boolean; onSave: (token: string) => void }) {
  const [draft, setDraft] = useState("");
  return (
    <form
      className="panel max-w-md px-5 py-5 space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (draft.trim()) onSave(draft.trim());
      }}
    >
      <h1 className="panel-title text-2xl">Admin</h1>
      <label htmlFor="admin-token" className={clsx("block", rejected ? "text-drift" : "text-ink-2")}>
        {rejected ? "That admin token wasn't accepted. Try again:" : "Enter the admin token:"}
      </label>
      <input
        id="admin-token"
        type="password"
        autoComplete="off"
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        className="w-full rounded-md border border-line bg-surface px-3 py-2"
      />
      <button type="submit" className="btn btn-primary">
        Open admin
      </button>
    </form>
  );
}

function Overview({ data, now, token }: { data: AdminOverviewOut; now: number; token: string }) {
  return (
    <>
      <section className="space-y-4" aria-labelledby="agents-title">
        <div className="max-w-[70ch]">
          <h1 id="agents-title" className="font-display text-4xl font-bold leading-none">
            Agents
          </h1>
          <p className="mt-2 text-ink-2">
            What each agent does, when it runs, what it looks at and what it&apos;s done lately. They&apos;re
            defined in <code className="text-[0.9em]">backend/src/race_watcher/agents.py</code>, which also sets the
            worker&apos;s schedules. To add an agent, start there. A model changed here is used from the
            agent&apos;s next run.
          </p>
        </div>
        {data.agents.map((a) => (
          <AgentCard key={a.key} agent={a} now={now} token={token} />
        ))}
      </section>

      <div className="grid gap-5 lg:grid-cols-2 items-start">
        <section className="panel overflow-hidden" aria-labelledby="watching-title">
          <header className="panel-head">
            <h2 id="watching-title" className="panel-title">
              Watching
            </h2>
            {data.card && <p className="text-sm text-ink-3">Card: {data.card}</p>}
          </header>
          <ul className="divide-y divide-line">
            {data.watching.map((w) => (
              <li key={`${w.track}-${w.date}`} className="px-5 py-3 flex items-baseline gap-3">
                <span className="font-semibold">{w.track}</span>
                <span className="text-ink-2">{dayLabel(w.date)}</span>
                <span className="ml-auto text-sm text-ink-3">
                  {w.races ? `R${w.races.join(", R")}` : "All races"}
                  {", "}
                  {w.loaded_races === 0 ? "card to come" : `${w.loaded_races} loaded`}
                </span>
              </li>
            ))}
          </ul>
          <p className="px-5 py-3 border-t border-line text-sm text-ink-3">
            Set in <code>backend/watch.json</code>. Change it, redeploy, then load the card.
          </p>
        </section>

        <section className="panel overflow-hidden" aria-labelledby="settings-title">
          <header className="panel-head">
            <h2 id="settings-title" className="panel-title">
              Settings
            </h2>
            <p className="text-sm text-ink-3">Railway variables</p>
          </header>
          <dl className="divide-y divide-line">
            {data.settings.map((s) => (
              <div key={s.name} className="px-5 py-2.5 grid grid-cols-[minmax(0,1fr)_auto] gap-x-4">
                <dt className="text-sm">
                  <code className="break-all">{s.name}</code>
                  <span className="block text-ink-3">{s.about}</span>
                </dt>
                <dd className="font-semibold text-right break-all">{s.value}</dd>
              </div>
            ))}
          </dl>
          <p className="px-5 py-3 border-t border-line text-sm text-ink-3">
            Change these in Railway, then redeploy the api and worker.
          </p>
        </section>
      </div>
    </>
  );
}

function AgentCard({ agent: a, now, token }: { agent: AgentOut; now: number; token: string }) {
  return (
    <article className="panel overflow-hidden" aria-labelledby={`agent-${a.key}`}>
      <header className="panel-head flex-wrap">
        <h2 id={`agent-${a.key}`} className="panel-title text-2xl">
          {a.name}
        </h2>
        <p className="text-sm">
          <span className="text-ink-3">
            {!a.model ? "Not AI" : a.web_search ? "AI, with web search" : "AI, no web access"}
          </span>
        </p>
      </header>

      <div className="grid md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div className="px-5 py-4 space-y-3">
          <p className="font-semibold">{a.purpose}</p>
          <p className="text-ink-2 leading-relaxed max-w-[70ch]">{a.how}</p>
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
            <dt className="text-ink-3">Reads</dt>
            <dd>{a.reads.join(", ")}</dd>
            <dt className="text-ink-3">Writes</dt>
            <dd>{a.writes.join(", ")}</dd>
          </dl>
          {a.prompt && (
            <details className="group">
              <summary className="cursor-pointer text-sm font-semibold text-turf">System prompt</summary>
              <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded-md bg-surface-2 border border-line p-3 text-[13px] leading-relaxed">
                {a.prompt}
              </pre>
            </details>
          )}
        </div>

        <dl className="px-5 py-4 space-y-3 text-sm md:border-l border-t md:border-t-0 border-line bg-surface-2">
          {a.model_choice && <ModelPicker agent={a} choice={a.model_choice} token={token} />}
          <div>
            <dt className="text-ink-3">When it runs</dt>
            <dd>
              <ul className="space-y-0.5">
                {a.schedule.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </dd>
          </div>
          <div>
            <dt className="text-ink-3">Next run</dt>
            <dd className="font-semibold">{a.next_run ? when(a.next_run, now) : "Not scheduled"}</dd>
          </div>
          {a.last_checked && (
            <div>
              <dt className="text-ink-3">Last checked</dt>
              <dd>{when(a.last_checked, now)}</dd>
            </div>
          )}
          <div>
            <dt className="text-ink-3">Looks at</dt>
            <dd>{a.looks_at}</dd>
          </div>
        </dl>
      </div>

      <RecentRuns agent={a} now={now} />
    </article>
  );
}

const TRIGGERS: Record<string, string> = { timer: "Timer", "morning check": "Morning check", refresh: "Refresh" };

function RecentRuns({ agent: a, now }: { agent: AgentOut; now: number }) {
  if (a.runs.length === 0) {
    return (
      <p className="px-5 py-3 border-t border-line text-sm text-ink-3">
        No runs with anything to do yet. Runs are logged from this version on.
      </p>
    );
  }
  return (
    <div className="border-t border-line">
      <h3 className="px-5 pt-3 text-sm font-semibold">Recent runs</h3>
      <ul className="divide-y divide-line">
        {a.runs.map((r) => {
          const sites = Object.entries(r.sites);
          return (
            <li
              key={r.started_at}
              className="px-5 py-2.5 text-sm grid grid-cols-[minmax(0,1fr)_auto] md:grid-cols-[13rem_8rem_minmax(0,1fr)] gap-x-4 gap-y-1"
            >
              <span className="text-ink-2">{when(r.started_at, now)}</span>
              <span className="text-ink-3 text-right md:text-left">{TRIGGERS[r.trigger] ?? r.trigger}</span>
              <span className={clsx("col-span-2 md:col-span-1", r.status === "error" && "text-drift")}>
                {r.status === "error" ? `Failed: ${r.error ?? "unknown error"}` : r.result}
                {r.model && <code className="block text-xs text-ink-3 break-all">{r.model}</code>}
                {r.races > 0 && r.status !== "error" && (
                  <span className="text-ink-3">
                    {" "}
                    ({r.races} {r.races === 1 ? "race" : "races"}
                    {r.finished_at && `, ${duration(r.started_at, r.finished_at)}`})
                  </span>
                )}
              </span>
              {sites.length > 0 && (
                <ul className="col-span-2 md:col-start-3 md:col-span-1 flex flex-wrap gap-1.5" aria-label="Sites cited">
                  {sites.map(([site, n]) => (
                    <li key={site} className="rounded-full border border-line px-2 py-0.5 text-xs text-ink-2">
                      {site}
                      {n > 1 && <span className="text-ink-3"> ×{n}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function when(iso: string, now: number): string {
  const ms = new Date(iso).getTime();
  const mins = Math.round((ms - now) / 60_000);
  const clock = new Date(ms).toLocaleString("en-AU", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
  if (Math.abs(mins) < 1) return `${clock} (now)`;
  if (Math.abs(mins) < 120) return `${clock} (${mins > 0 ? `in ${mins} min` : `${-mins} min ago`})`;
  return clock;
}

function duration(from: string, to: string): string {
  const s = Math.round((new Date(to).getTime() - new Date(from).getTime()) / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

function dayLabel(date: string): string {
  return new Date(`${date}T12:00:00`).toLocaleDateString("en-AU", { weekday: "short", day: "numeric", month: "short" });
}
