"use client";

import { countdown, viewerTime } from "@/lib/time";
import { hasJumped, trackColour, type ScheduledRace } from "@/lib/tracks";
import { RefreshBar } from "./RefreshBar";

export function RaceHeader({ scheduled, now }: { scheduled: ScheduledRace; now: number }) {
  const { meeting, meetingIndex, race, startMs } = scheduled;
  const running = race.runners.filter((r) => !r.scratched).length;
  const jumped = hasJumped(startMs, now);
  const localTime = race.start_time_local?.slice(0, 5);
  const viewer = startMs ? viewerTime(startMs) : null;

  return (
    <section className="panel overflow-hidden">
      <div className="h-1.5" style={{ background: trackColour(meeting.track, meetingIndex) }} />
      <div className="px-5 py-4 flex flex-col md:flex-row md:items-end gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-ink-3">
            {meeting.track}, race {race.number}
          </p>
          <h2 className="font-display text-3xl md:text-4xl font-bold leading-tight">{race.name}</h2>
          <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-2">
            {race.distance_m && (
              <div>
                <dt className="sr-only">Distance</dt>
                <dd>{race.distance_m}m</dd>
              </div>
            )}
            {race.klass && (
              <div>
                <dt className="sr-only">Class</dt>
                <dd>{race.klass}</dd>
              </div>
            )}
            <div>
              <dt className="sr-only">Runners</dt>
              <dd>{running} runners</dd>
            </div>
            {meeting.going && (
              <div className="flex gap-1">
                <dt className="text-ink-3">Track</dt>
                <dd>{meeting.going}</dd>
              </div>
            )}
            {meeting.rail && (
              <div className="flex gap-1">
                <dt className="text-ink-3">Rail</dt>
                <dd>{meeting.rail}</dd>
              </div>
            )}
          </dl>
        </div>

        <div className="md:text-right shrink-0">
          <p className="num text-4xl font-bold leading-none">
            {jumped ? "Run" : startMs ? countdown(startMs - now) : "—"}
          </p>
          <p className="text-sm text-ink-3 mt-1">
            {localTime} local
            {viewer && viewer.replace(/\s/g, "").toLowerCase() !== localTime && <> / {viewer} yours</>}
          </p>
        </div>
      </div>
      <RefreshBar meetingId={meeting.id} track={meeting.track} />
    </section>
  );
}
