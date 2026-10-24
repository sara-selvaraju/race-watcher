"use client";

import type { ReactNode } from "react";
import { clsx } from "@/lib/clsx";
import type { MeetingOut } from "@/lib/api/client";

type Race = MeetingOut["races"][number];
type Runner = Race["runners"][number];

type Pick = {
  runner: Runner;
  rank: 1 | 2 | 3;
  win_prob: number | null;
  rationale: string | null;
  source: "research" | "heuristic";
};

const RANK_LABEL = { 1: "Top pick", 2: "Second", 3: "Third" } as const;

function n(v: string | number | null | undefined): number | null {
  if (v == null) return null;
  const x = typeof v === "number" ? v : Number(v);
  return Number.isFinite(x) ? x : null;
}

// Parse [label](https://url) markdown links and render the rest as plain text.
// Only http(s) URLs are linkified — anything else stays as text (prevents javascript: injection).
const MD_LINK_RE = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;

function renderRationale(text: string): ReactNode {
  const out: ReactNode[] = [];
  let lastIdx = 0;
  let match: RegExpExecArray | null;
  MD_LINK_RE.lastIndex = 0;
  while ((match = MD_LINK_RE.exec(text)) !== null) {
    if (match.index > lastIdx) {
      out.push(text.slice(lastIdx, match.index));
    }
    const [, label, url] = match;
    out.push(
      <a
        key={`${match.index}-${url}`}
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-turf underline decoration-turf/40 underline-offset-2 hover:decoration-turf"
      >
        {label}
      </a>,
    );
    lastIdx = match.index + match[0].length;
  }
  if (lastIdx < text.length) out.push(text.slice(lastIdx));
  return out.length > 0 ? out : text;
}

function pickTop3(race: Race): Pick[] {
  const byId = new Map(race.runners.map((r) => [r.id, r]));

  // Research-backed picks from /admin/refresh-tips, if present.
  const research = (race.top_picks ?? [])
    .filter((p) => byId.has(p.runner_id))
    .sort((a, b) => a.rank - b.rank)
    .slice(0, 3);

  if (research.length > 0) {
    return research.map((p) => {
      const runner = byId.get(p.runner_id)!;
      return {
        runner,
        rank: p.rank as 1 | 2 | 3,
        win_prob: n(runner.prediction?.win_prob),
        rationale: p.rationale,
        source: "research" as const,
      };
    });
  }

  // Fallback: derive from heuristic prediction win_prob.
  const sorted = race.runners
    .filter((r) => !r.scratched)
    .map((r) => ({ r, p: n(r.prediction?.win_prob) ?? 0 }))
    .sort((a, b) => b.p - a.p)
    .slice(0, 3);
  return sorted.map(({ r }, i) => ({
    runner: r,
    rank: (i + 1) as 1 | 2 | 3,
    win_prob: n(r.prediction?.win_prob),
    rationale: r.prediction?.rationale ?? null,
    source: "heuristic" as const,
  }));
}

export function TopPicksBox({ race }: { race: Race }) {
  const picks = pickTop3(race);
  const source = picks[0]?.source ?? "heuristic";

  return (
    <section className="panel overflow-hidden">
      <header className="panel-head">
        <h3 className="panel-title">Top picks</h3>
        <p className="text-sm text-ink-3" title={source === "research" ? "LLM-researched picks: check the cited sources before betting" : undefined}>
          {source === "research" ? "From web research. Check the sources." : "From the heuristic rating"}
        </p>
      </header>

      {picks.length === 0 ? (
        <p className="px-5 py-8 text-center text-ink-3">
          No picks yet. Refresh this track to research tips and ratings.
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-line">
          {picks.map((pick) => (
            <PickCell key={pick.runner.id} pick={pick} />
          ))}
        </div>
      )}
    </section>
  );
}

function PickCell({ pick }: { pick: Pick }) {
  const { runner, rank, win_prob, rationale } = pick;
  const isLead = rank === 1;
  const cp = runner.current_price ? Number(runner.current_price.price) : null;

  return (
    <article className={clsx("px-5 py-4 flex flex-col gap-3", isLead && "bg-silk/15")}>
      <p className={clsx("text-sm font-semibold", isLead ? "text-ink" : "text-ink-3")}>{RANK_LABEL[rank]}</p>
      <header className="flex items-start gap-3">
        <span className={clsx("cloth", isLead && "!bg-silk !text-ink")}>{runner.number}</span>
        <div className="min-w-0 flex-1">
          <h4 className="font-display text-2xl font-bold leading-none truncate">{runner.name}</h4>
          <p className="text-sm text-ink-3 truncate mt-1">
            {[runner.jockey, runner.trainer].filter(Boolean).join(", ") || "Connections not listed"}
          </p>
        </div>
        <div className="text-right shrink-0">
          {cp != null && <p className="num text-2xl font-bold leading-none">${cp.toFixed(2)}</p>}
          {win_prob != null && win_prob > 0 && <p className="num text-sm text-ink-3 mt-1">{(win_prob * 100).toFixed(0)}% chance</p>}
        </div>
      </header>
      {rationale && <p className="text-sm leading-relaxed text-ink-2">{renderRationale(rationale)}</p>}
    </article>
  );
}
