"use client";

import { useStatus } from "@/lib/api/hooks";

type Props = {
  track: string;
  date: string;
  going: string | null | undefined;
  rail: string | null | undefined;
};

export function Header({ track, date, going, rail }: Props) {
  const { data: status } = useStatus();

  const dateObj = new Date(date);
  const dayJa = ["日", "月", "火", "水", "木", "金", "土"][dateObj.getDay()];
  const yyyy = dateObj.getFullYear();
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  const dd = String(dateObj.getDate()).padStart(2, "0");

  return (
    <header className="flex items-end justify-between gap-6 pt-2 pb-1">
      <div>
        <div className="label-section mb-3">
          <span className="font-display tracking-kanji">競馬 · TURF</span>
        </div>
        <h1 className="font-display text-4xl md:text-5xl font-bold text-ink leading-none tracking-tight">
          {track}
        </h1>
        <p className="mt-3 font-mono text-xs tracking-widest text-ink-3 flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="text-ink-2">
            {yyyy}.{mm}.{dd}
          </span>
          <span className="text-gold font-display text-sm">{dayJa}</span>
          {going && (
            <>
              <span className="enso" />
              <span>{going.toUpperCase()}</span>
            </>
          )}
          {rail && (
            <>
              <span className="enso" />
              <span>{rail.toUpperCase()}</span>
            </>
          )}
        </p>
      </div>
      <div className="text-right shrink-0 hidden sm:block">
        <div className="label-section justify-end mb-2">STATUS</div>
        <div className="flex items-center gap-2 justify-end font-mono text-[11px] tracking-widest">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              status?.in_window ? "bg-matcha animate-pulse" : "bg-ink-ghost"
            }`}
          />
          <span className={status?.in_window ? "text-matcha" : "text-ink-3"}>
            {status?.in_window ? "LIVE WINDOW" : "STANDBY"}
          </span>
        </div>
        <div className="mt-2 font-mono text-[10px] text-ink-ghost tracking-widest">
          {status?.snapshot_count ?? 0} SNAPS · {status?.alert_count ?? 0} ALERTS
        </div>
      </div>
    </header>
  );
}
