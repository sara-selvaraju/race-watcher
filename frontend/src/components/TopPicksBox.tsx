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

const RANK_KANJI = { 1: "一", 2: "二", 3: "三" } as const;
const RANK_ROMAJI = { 1: "ichi", 2: "ni", 3: "san" } as const;
const RANK_LABEL = { 1: "WIN", 2: "PLACE", 3: "SHOW" } as const;

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
        className="text-ink-2 underline decoration-gold/50 decoration-dotted underline-offset-2 hover:text-gold hover:decoration-gold hover:decoration-solid"
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
    <section className="bento bento-ticks animate-bento-in" style={{ animationDelay: "60ms" }}>
      <header className="px-5 py-4 flex items-center justify-between border-b border-hairline">
        <span className="label-section">
          <span className="font-display tracking-kanji text-ink">予想</span>
          <span className="text-ink-3 normal-case tracking-normal font-sans">Top picks</span>
        </span>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[9px] tracking-widest text-ink-ghost">
            {source === "research" ? "RESEARCH" : "HEURISTIC"}
          </span>
          <span className="font-mono text-[10px] tracking-widest text-ink-ghost">
            R{race.number} · {race.distance_m}m
          </span>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-hairline">
        {picks.length === 0 && (
          <div className="col-span-3 px-6 py-10 text-center text-ink-ghost font-mono text-xs tracking-widest">
            NO PREDICTIONS YET
          </div>
        )}
        {picks.map((pick) => (
          <PickCell key={pick.runner.id} pick={pick} />
        ))}
      </div>
    </section>
  );
}

function PickCell({ pick }: { pick: Pick }) {
  const { runner, rank, win_prob, rationale } = pick;
  const isLead = rank === 1;
  const cp = runner.current_price ? Number(runner.current_price.price) : null;

  return (
    <article
      className={clsx(
        "relative px-5 py-5 flex flex-col gap-3 transition-colors",
        isLead ? "bg-paper-raised" : "hover:bg-paper-raised",
      )}
    >
      {/* rank header */}
      <header className="flex items-start gap-3">
        <div
          className={clsx(
            "shrink-0 w-12 h-14 border flex flex-col items-center justify-center font-display leading-none",
            isLead ? "border-gold bg-gold/5" : "border-hairline-bright",
          )}
        >
          <span
            className={clsx(
              "text-3xl font-bold",
              isLead ? "text-gold" : "text-ink-2",
            )}
          >
            {RANK_KANJI[rank]}
          </span>
          <span className="mt-0.5 font-mono text-[9px] tracking-widest text-ink-ghost">
            {RANK_LABEL[rank]}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-xs text-ink-3 tabular-nums">
              #{runner.number}
            </span>
            {win_prob != null && (
              <span
                className={clsx(
                  "ml-auto font-mono text-sm tabular-nums",
                  isLead ? "text-gold" : "text-ink-2",
                )}
              >
                {(win_prob * 100).toFixed(1)}%
              </span>
            )}
          </div>
          <h3 className="font-display text-lg leading-snug text-ink truncate">
            {runner.name}
          </h3>
          <div className="font-mono text-[10px] tracking-widest text-ink-ghost truncate">
            {(runner.jockey ?? "—").toUpperCase()}
            <span className="mx-1.5 opacity-50">·</span>
            {(runner.trainer ?? "—").toUpperCase()}
          </div>
        </div>
      </header>

      {/* odds + romaji rank */}
      <div className="flex items-center justify-between pt-3 border-t border-hairline">
        <span className="font-display italic text-[11px] tracking-widest text-ink-ghost">
          {RANK_ROMAJI[rank]}
        </span>
        {cp != null ? (
          <span className="font-mono text-sm tabular-nums text-ink">
            <span className="text-ink-3 text-xs mr-0.5">$</span>
            {cp.toFixed(2)}
          </span>
        ) : runner.prediction?.rating ? (
          <span className="font-mono text-[10px] tracking-widest text-ink-3">
            {runner.prediction.rating.toUpperCase()}
          </span>
        ) : null}
      </div>

      {rationale && (
        <p className="text-[11px] leading-relaxed text-ink-3">
          {renderRationale(rationale)}
        </p>
      )}
    </article>
  );
}
