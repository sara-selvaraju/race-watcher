"use client";

import { useEffect, useState } from "react";
import { useMeeting } from "@/lib/api/hooks";
import { Header } from "@/components/Header";
import { RaceNav } from "@/components/RaceNav";
import { RaceTable } from "@/components/RaceTable";
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
    return (
      <main className="mx-auto max-w-6xl px-4 py-6">
        <p className="text-zinc-400">Loading the card…</p>
      </main>
    );
  }
  if (error || !meeting) {
    return (
      <main className="mx-auto max-w-6xl px-4 py-6">
        <p className="text-red-400">
          Couldn’t reach the API. Make sure it’s running and{" "}
          <code className="font-mono">NEXT_PUBLIC_API_BASE_URL</code> points at it.
        </p>
      </main>
    );
  }

  const activeRace = meeting.races.find((r) => r.id === activeRaceId) ?? meeting.races[0];

  return (
    <main className="mx-auto max-w-6xl px-4 py-6 space-y-4">
      <Header
        track={meeting.track}
        date={meeting.date}
        going={meeting.going}
        rail={meeting.rail}
      />

      <RaceNav meeting={meeting} activeRaceId={activeRace?.id ?? null} onSelect={setActiveRaceId} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {activeRace && <RaceTable race={activeRace} />}
        </div>

        <aside className="space-y-3">
          <h2 className="text-base font-semibold">Movements</h2>
          <MovementFeed />
        </aside>
      </div>
    </main>
  );
}
