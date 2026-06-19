"use client";

import { clsx } from "@/lib/clsx";
import type { MeetingOut } from "@/lib/api/client";

type Props = {
  meeting: MeetingOut;
  activeRaceId: number | null;
  onSelect: (raceId: number) => void;
};

export function RaceNav({ meeting, activeRaceId, onSelect }: Props) {
  return (
    <nav className="overflow-x-auto -mx-4 px-4 sticky top-0 bg-zinc-950/90 backdrop-blur z-10 py-2 border-b border-zinc-800">
      <ul className="flex gap-2 min-w-max">
        {meeting.races.map((race) => (
          <li key={race.id}>
            <button
              type="button"
              onClick={() => onSelect(race.id)}
              className={clsx(
                "px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap",
                activeRaceId === race.id
                  ? "bg-zinc-100 text-zinc-900"
                  : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700",
              )}
            >
              R{race.number}
              <span className="ml-2 text-xs opacity-70 font-mono">{race.start_time_local?.slice(0, 5)}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
