"use client";

import { clsx } from "@/lib/clsx";
import type { MeetingsOut } from "@/lib/api/client";
import { raceDayLabel } from "@/lib/time";
import { hasJumped, trackColour, type ScheduledRace } from "@/lib/tracks";

type Props = {
  meetings: MeetingsOut;
  timeline: ScheduledRace[];
  now: number;
  activeRaceId: number | null;
  onSelect: (raceId: number) => void;
};

export function MeetingNav({ meetings, timeline, now, activeRaceId, onSelect }: Props) {
  const activeMeeting = timeline.find((s) => s.race.id === activeRaceId)?.meeting ?? meetings[0];
  const races = timeline
    .filter((s) => s.meeting.id === activeMeeting.id)
    .sort((a, b) => a.race.number - b.race.number);
  // Several days at one track (a carnival): tabs are days. Otherwise tabs are tracks.
  const byDay = new Set(meetings.map((m) => m.date)).size > 1;

  function openMeeting(meetingId: number) {
    const own = timeline.filter((s) => s.meeting.id === meetingId);
    const pick = own.find((s) => !hasJumped(s.startMs, now)) ?? own[own.length - 1];
    if (pick) onSelect(pick.race.id);
  }

  return (
    <nav className="panel overflow-hidden" aria-label={byDay ? "Race days and races" : "Meetings and races"}>
      <div role="tablist" className="flex border-b border-line overflow-x-auto">
        {meetings.map((m, i) => {
          const selected = m.id === activeMeeting.id;
          const left = timeline.filter((s) => s.meeting.id === m.id && !hasJumped(s.startMs, now)).length;
          return (
            <button
              key={m.id}
              role="tab"
              aria-selected={selected}
              onClick={() => openMeeting(m.id)}
              disabled={m.races.length === 0}
              className={clsx(
                "relative flex-1 min-w-[8.5rem] px-4 py-3 text-left disabled:cursor-default disabled:hover:text-ink-3",
                selected ? "bg-surface" : "bg-surface-2 text-ink-3 hover:text-ink-2",
              )}
            >
              <span
                className="absolute left-0 right-0 bottom-0 h-[3px]"
                style={{ background: selected ? trackColour(m.track, i) : "transparent" }}
              />
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: trackColour(m.track, i) }} />
                <span className={clsx("font-display text-xl font-bold leading-none", selected && "text-ink")}>
                  {byDay ? raceDayLabel(m.date) : m.track}
                </span>
              </span>
              <span className="block text-sm mt-1">
                {byDay && `${m.track}, `}
                {m.races.length === 0 ? "Card to come" : left > 0 ? `${left} to run` : "Finished"}
              </span>
            </button>
          );
        })}
      </div>

      <ul className="flex overflow-x-auto p-2 gap-1.5">
        {races.map((s) => {
          const active = s.race.id === activeRaceId;
          const done = hasJumped(s.startMs, now);
          return (
            <li key={s.race.id} className="shrink-0">
              <button
                type="button"
                onClick={() => onSelect(s.race.id)}
                aria-current={active ? "true" : undefined}
                className={clsx(
                  "rounded-lg px-3 py-2 text-left min-w-[4.5rem]",
                  active ? "bg-turf text-white" : done ? "text-ink-3 hover:bg-surface-2" : "hover:bg-surface-2",
                )}
              >
                <span className="block font-display text-lg font-bold leading-none">R{s.race.number}</span>
                <span className={clsx("num block text-sm mt-0.5", active ? "text-white/80" : "text-ink-3")}>
                  {done ? "Run" : (s.race.start_time_local?.slice(0, 5) ?? "--:--")}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
