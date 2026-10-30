// Race start times are stored as wall-clock times in the meeting's own timezone (Flemington is
// Melbourne time, Ascot is Perth time). Convert to an absolute instant so meetings in different
// zones can be sorted together and counted down from the viewer's clock.

function tzOffsetMs(utcMs: number, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(new Date(utcMs));
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value);
  const asUtc = Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"), get("second"));
  return asUtc - utcMs;
}

export function raceStartMs(date: string, timeLocal: string | null | undefined, timeZone: string): number | null {
  if (!timeLocal) return null;
  const [y, mo, d] = date.split("-").map(Number);
  const [h, mi] = timeLocal.split(":").map(Number);
  const naive = Date.UTC(y, mo - 1, d, h, mi);
  // Two passes handle the rare case where the offset differs either side of a DST change.
  const first = naive - tzOffsetMs(naive, timeZone);
  return naive - tzOffsetMs(first, timeZone);
}

export function countdown(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s <= 0) return "Jumping";
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m >= 10) return `${m} min`;
  return `${m}m ${String(sec).padStart(2, "0")}s`;
}

export function viewerTime(ms: number, now = Date.now()): string {
  const at = new Date(ms);
  const time = at.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  if (at.toDateString() === new Date(now).toDateString()) return time;
  return `${at.toLocaleDateString([], { weekday: "short" })} ${time}`;
}

// "Sat 31 Oct" for a meeting's YYYY-MM-DD date (noon avoids any timezone date slip).
export function raceDayLabel(date: string): string {
  return new Date(`${date}T12:00:00`).toLocaleDateString("en-AU", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}
