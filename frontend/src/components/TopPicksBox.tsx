"use client";

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
          <span className="font-display tracking-kanji text-paper">予想</span>
          <span className="text-paper-faint normal-case tracking-normal font-sans">Top picks</span>
        </span>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[9px] tracking-widest text-paper-ghost">
            {source === "research" ? "RESEARCH" : "HEURISTIC"}
          </span>
          <span className="font-mono text-[10px] tracking-widest text-paper-ghost">
            R{race.number} · {race.distance_m}m
          </span>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-hairline">
        {picks.length === 0 && (
          <div className="col-span-3 px-6 py-10 text-center text-paper-ghost font-mono text-xs tracking-widest">
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
        isLead ? "bg-washi-raised" : "hover:bg-washi-raised",
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
              isLead ? "text-gold" : "text-paper-dim",
            )}
          >
            {RANK_KANJI[rank]}
          </span>
          <span className="mt-0.5 font-mono text-[9px] tracking-widest text-paper-ghost">
            {RANK_LABEL[rank]}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-xs text-paper-faint tabular-nums">
              #{runner.number}
            </span>
            {win_prob != null && (
              <span
                className={clsx(
                  "ml-auto font-mono text-sm tabular-nums",
                  isLead ? "text-gold" : "text-paper-dim",
                )}
              >
                {(win_prob * 100).toFixed(1)}%
              </span>
            )}
          </div>
          <h3 className="font-display text-lg leading-snug text-paper truncate">
            {runner.name}
          </h3>
          <div className="font-mono text-[10px] tracking-widest text-paper-ghost truncate">
            {(runner.jockey ?? "—").toUpperCase()}
            <span className="mx-1.5 opacity-50">·</span>
            {(runner.trainer ?? "—").toUpperCase()}
          </div>
        </div>
      </header>

      {/* odds + romaji rank */}
      <div className="flex items-center justify-between pt-3 border-t border-hairline">
        <span className="font-display italic text-[11px] tracking-widest text-paper-ghost">
          {RANK_ROMAJI[rank]}
        </span>
        {cp != null ? (
          <span className="font-mono text-sm tabular-nums text-paper">
            <span className="text-paper-faint text-xs mr-0.5">$</span>
            {cp.toFixed(2)}
          </span>
        ) : runner.prediction?.rating ? (
          <span className="font-mono text-[10px] tracking-widest text-paper-faint">
            {runner.prediction.rating.toUpperCase()}
          </span>
        ) : null}
      </div>

      {rationale && (
        <p className="text-[11px] leading-relaxed text-paper-faint line-clamp-3">
          {rationale}
        </p>
      )}
    </article>
  );
}
