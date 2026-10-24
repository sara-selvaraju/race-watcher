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
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

export function viewerTime(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}
