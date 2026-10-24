import type { MeetingOut } from "@/lib/api/client";
import { raceStartMs } from "@/lib/time";

type Meeting = MeetingOut;
export type Race = Meeting["races"][number];

// One identifying colour per track, used as a stripe on tabs and race rows.
const TRACK_COLOURS: Record<string, string> = {
  flemington: "#b3245b",
  randwick: "#1f5fa8",
  ascot: "#b57a00",
};
const FALLBACK = ["#6a3fa0", "#0f7c86", "#8a5a2b"];

export function trackColour(track: string, index = 0): string {
  return TRACK_COLOURS[track.toLowerCase()] ?? FALLBACK[index % FALLBACK.length];
}

export type ScheduledRace = {
  meeting: Meeting;
  meetingIndex: number;
  race: Race;
  startMs: number | null;
};

export function schedule(meetings: Meeting[]): ScheduledRace[] {
  return meetings
    .flatMap((meeting, meetingIndex) =>
      meeting.races.map((race) => ({
        meeting,
        meetingIndex,
        race,
        startMs: raceStartMs(meeting.date, race.start_time_local, meeting.timezone),
      })),
    )
    .sort((a, b) => (a.startMs ?? Infinity) - (b.startMs ?? Infinity));
}

// A race counts as run two minutes after its advertised start.
export const JUMPED_GRACE_MS = 2 * 60_000;

export function hasJumped(startMs: number | null, now: number): boolean {
  return startMs != null && now > startMs + JUMPED_GRACE_MS;
}
