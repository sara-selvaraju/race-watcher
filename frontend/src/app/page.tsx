"use client";

import { useEffect, useMemo, useState } from "react";
import { useMeetings } from "@/lib/api/hooks";
import { useNow } from "@/lib/useNow";
import { hasJumped, schedule } from "@/lib/tracks";
import { TopBar } from "@/components/Header";
import { NextToJump } from "@/components/NextToJump";
import { MeetingNav } from "@/components/RaceNav";
import { RaceHeader } from "@/components/RaceHeader";
import { TopPicksBox } from "@/components/TopPicksBox";
import { FieldBox } from "@/components/FieldBox";
import { MovementFeed } from "@/components/MovementFeed";

export default function Page() {
  const { data: meetings, isPending, error } = useMeetings();
  const now = useNow(1000);
  const [activeRaceId, setActiveRaceId] = useState<number | null>(null);

  const timeline = useMemo(() => schedule(meetings ?? []), [meetings]);

  // Open on the next race to jump, across every track.
  useEffect(() => {
    if (activeRaceId != null || timeline.length === 0) return;
    const next = timeline.find((s) => !hasJumped(s.startMs, Date.now())) ?? timeline[timeline.length - 1];
    setActiveRaceId(next.race.id);
  }, [timeline, activeRaceId]);

  if (isPending) return <LoadingState />;
  if (error || !meetings) return <ErrorState />;
  if (meetings.length === 0) return <EmptyState />;

  const active = timeline.find((s) => s.race.id === activeRaceId) ?? timeline[0];

  return (
    <>
      <TopBar meeting={active?.meeting ?? null} />
      <main className="mx-auto max-w-7xl px-4 sm:px-6 py-5 md:py-7 space-y-5">
        <NextToJump timeline={timeline} now={now} activeRaceId={active?.race.id ?? null} onSelect={setActiveRaceId} />

        <MeetingNav
          meetings={meetings}
          timeline={timeline}
          now={now}
          activeRaceId={active?.race.id ?? null}
          onSelect={setActiveRaceId}
        />

        {active && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <div className="lg:col-span-3">
              <RaceHeader scheduled={active} now={now} />
            </div>
            <div className="lg:col-span-3">
              <TopPicksBox race={active.race} />
            </div>
            <div className="lg:col-span-2">
              <FieldBox race={active.race} />
            </div>
            <div className="lg:col-span-1">
              <MovementFeed onSelect={setActiveRaceId} />
            </div>
          </div>
        )}
      </main>
    </>
  );
}

function LoadingState() {
  return (
    <main className="mx-auto max-w-7xl px-6 py-12 grid place-items-center min-h-[60vh]">
      <p className="font-display text-2xl text-ink-3 animate-pulse">Loading races…</p>
    </main>
  );
}

function ErrorState() {
  return (
    <main className="mx-auto max-w-xl px-6 py-12">
      <div className="panel p-8">
        <h1 className="panel-title text-drift">Can&apos;t reach the race API</h1>
        <p className="mt-3 text-ink-2">
          Check the api service is running and that{" "}
          <code className="text-sm bg-surface-2 px-1 rounded">NEXT_PUBLIC_API_BASE_URL</code> points at it.
        </p>
      </div>
    </main>
  );
}

function EmptyState() {
  return (
    <main className="mx-auto max-w-xl px-6 py-12">
      <div className="panel p-8">
        <h1 className="panel-title">No race days loaded</h1>
        <p className="mt-3 text-ink-2">
          Load the seed card with <code className="text-sm bg-surface-2 px-1 rounded">POST /api/v1/admin/ingest</code>.
        </p>
      </div>
    </main>
  );
}
