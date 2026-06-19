"use client";

import { useEffect, useState } from "react";
import { useMeeting } from "@/lib/api/hooks";
import { Header } from "@/components/Header";
import { RaceNav } from "@/components/RaceNav";
import { TopPicksBox } from "@/components/TopPicksBox";
import { FieldBox } from "@/components/FieldBox";
import { MovementFeed } from "@/components/MovementFeed";

export default function Page() {
  const { data: meeting, isPending, error } = useMeeting();
  const [activeRaceId, setActiveRaceId] = useState<number | null>(null);

  useEffect(() => {
    if (meeting && activeRaceId == null && meeting.races[0]) {
      setActiveRaceId(meeting.races[0].id);
    }
  }, [meeting, activeRaceId]);

  if (isPending) {
    return <LoadingState />;
  }
  if (error || !meeting) {
    return <ErrorState />;
  }

  const activeRace = meeting.races.find((r) => r.id === activeRaceId) ?? meeting.races[0];

  return (
    <main className="mx-auto max-w-7xl px-4 sm:px-6 py-6 md:py-8 space-y-6">
      <Header
        track={meeting.track}
        date={meeting.date}
        going={meeting.going}
        rail={meeting.rail}
      />

      <RaceNav
        meeting={meeting}
        activeRaceId={activeRace?.id ?? null}
        onSelect={setActiveRaceId}
      />

      {activeRace && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* RACE HEADER STRIP — runs full width above the bento grid */}
          <div className="lg:col-span-3 bento bento-ticks animate-bento-in px-5 py-4 flex items-end justify-between gap-4">
            <div>
              <div className="flex items-baseline gap-3">
                <span className="font-display text-3xl text-gold leading-none">
                  R{activeRace.number}
                </span>
                <span className="font-mono text-xs tracking-widest text-paper-ghost">
                  {activeRace.start_time_local?.slice(0, 5)} · {activeRace.distance_m}m
                </span>
              </div>
              <h2 className="font-display text-xl md:text-2xl text-paper mt-1.5 leading-tight">
                {activeRace.name}
              </h2>
            </div>
            <div className="text-right shrink-0">
              <div className="label-section justify-end mb-1">
                <span className="font-display tracking-kanji">頭数</span>
                <span className="text-paper-faint normal-case tracking-normal font-sans">
                  Runners
                </span>
              </div>
              <div className="font-mono text-2xl tabular-nums text-paper">
                {activeRace.runners.filter((r) => !r.scratched).length}
                <span className="text-paper-ghost text-base">/{activeRace.runners.length}</span>
              </div>
            </div>
          </div>

          {/* TOP PICKS — full width, three columns inside */}
          <div className="lg:col-span-3">
            <TopPicksBox race={activeRace} />
          </div>

          {/* FULL FIELD — 2/3 width on desktop */}
          <div className="lg:col-span-2">
            <FieldBox race={activeRace} />
          </div>

          {/* MOVEMENTS — sidebar */}
          <div className="lg:col-span-1">
            <MovementFeed />
          </div>
        </div>
      )}
    </main>
  );
}

function LoadingState() {
  return (
    <main className="mx-auto max-w-7xl px-6 py-12 grid place-items-center min-h-[60vh]">
      <div className="text-center">
        <div className="font-display text-6xl text-paper-faint animate-pulse">競</div>
        <p className="mt-6 font-mono text-[10px] tracking-widest text-paper-ghost">
          LOADING THE CARD
        </p>
      </div>
    </main>
  );
}

function ErrorState() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <div className="bento p-8 text-center">
        <div className="font-display text-4xl text-vermilion mb-3">×</div>
        <p className="font-mono text-xs tracking-widest text-paper-dim">
          COULDN&apos;T REACH THE API
        </p>
        <p className="mt-3 text-sm text-paper-faint">
          Confirm the api service is running and{" "}
          <code className="font-mono text-paper-dim">NEXT_PUBLIC_API_BASE_URL</code> points at it.
        </p>
      </div>
    </main>
  );
}
