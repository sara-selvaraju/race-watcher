"use client";

import { clsx } from "@/lib/clsx";
import { countdown, raceDayLabel, viewerTime } from "@/lib/time";
import { hasJumped, trackColour, type ScheduledRace } from "@/lib/tracks";

type Props = {
  timeline: ScheduledRace[];
  now: number;
  activeRaceId: number | null;
  onSelect: (raceId: number) => void;
};

export function NextToJump({ timeline, now, activeRaceId, onSelect }: Props) {
  const upcoming = timeline.filter((s) => !hasJumped(s.startMs, now));

  if (upcoming.length === 0) {
    return (
      <section className="panel px-5 py-6">
        <h2 className="panel-title">All races have run</h2>
        <p className="mt-1 text-ink-3">Every race day is finished. Each race stays browsable below.</p>
      </section>
    );
  }

  const [next, ...rest] = upcoming;

  return (
    <section aria-label="Next to jump" className="grid grid-cols-1 md:grid-cols-[minmax(0,1.1fr)_minmax(0,2fr)] gap-3">
      <button
        type="button"
        onClick={() => onSelect(next.race.id)}
        className="text-left rounded-[10px] bg-silk text-ink px-5 py-4 flex items-end justify-between gap-4"
      >
        <div className="min-w-0">
          <p className="text-sm font-semibold">Next to jump</p>
          <p className="font-display text-3xl font-bold leading-tight mt-1 truncate">
            {next.meeting.track} R{next.race.number}
          </p>
          <p className="text-sm text-ink-2 truncate">{next.race.name}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="num font-bold text-5xl leading-none">{next.startMs ? countdown(next.startMs - now) : "—"}</p>
          {next.startMs && <p className="text-sm text-ink-2 mt-1">{viewerTime(next.startMs, now)} your time</p>}
        </div>
      </button>

      <ol className="flex gap-2 overflow-x-auto pb-1 -mb-1">
        {rest.map((s) => (
          <li key={s.race.id} className="shrink-0">
            <button
              type="button"
              onClick={() => onSelect(s.race.id)}
              aria-pressed={activeRaceId === s.race.id}
              className={clsx(
                "h-full w-36 rounded-[10px] border bg-surface px-3 py-3 text-left",
                activeRaceId === s.race.id ? "border-turf ring-1 ring-turf" : "border-line hover:border-line-strong",
              )}
              style={{ borderTopWidth: 4, borderTopColor: trackColour(s.meeting.track, s.meetingIndex) }}
            >
              <span className="block text-sm text-ink-3 truncate">
                {s.meeting.date === next.meeting.date ? s.meeting.track : raceDayLabel(s.meeting.date)}
              </span>
              <span className="block font-display text-xl font-bold leading-tight">R{s.race.number}</span>
              <span className="num block text-lg text-ink-2">{s.startMs ? countdown(s.startMs - now) : "—"}</span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
