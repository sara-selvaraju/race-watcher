import type { MeetingOut } from "@/lib/api/client";
import { raceStartMs } from "@/lib/time";

type Meeting = MeetingOut;
export type Race = Meeting["races"][number];

// One identifying colour per track, used as a stripe on tabs and race rows.
const TRACK_COLOURS: Record<string, string> = {
  flemington: "#b3245b",
  randwick: "#1f5fa8",
  ascot: "#b57a00",
  morphettville: "#6a3fa0",
  "eagle farm": "#0f7c86",
};
const FALLBACK = ["#8a5a2b", "#4d6b1f", "#a33f2f"];

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

// Per track: the most recently run race (for its result/notes) plus every race still to run.
export function visibleRaces(races: ScheduledRace[], now: number): ScheduledRace[] {
  const run = races.filter((s) => hasJumped(s.startMs, now));
  const lastRun = run[run.length - 1];
  return races.filter((s) => s === lastRun || !hasJumped(s.startMs, now));
}

export function hasJumped(startMs: number | null, now: number): boolean {
  return startMs != null && now > startMs + JUMPED_GRACE_MS;
}
