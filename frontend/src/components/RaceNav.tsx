"use client";

import { clsx } from "@/lib/clsx";
import type { MeetingOut } from "@/lib/api/client";

type Props = {
  meeting: MeetingOut;
  activeRaceId: number | null;
  onSelect: (raceId: number) => void;
};

const KANJI_NUM = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"];
const toKanji = (n: number) => (n >= 1 && n <= 10 ? KANJI_NUM[n] : String(n));

export function RaceNav({ meeting, activeRaceId, onSelect }: Props) {
  return (
    <nav className="bento bento-ticks animate-bento-in">
      <div className="px-5 py-3 flex items-center justify-between border-b border-hairline">
        <span className="label-section">
          <span className="font-display tracking-kanji text-ink-2">本日のレース</span>
          <span className="text-ink-ghost normal-case tracking-normal font-sans">Card</span>
        </span>
        <span className="text-[10px] tracking-widest text-ink-ghost font-mono">
          {meeting.races.length} RACES
        </span>
      </div>
      <ul className="flex overflow-x-auto divide-x divide-hairline">
        {meeting.races.map((race) => {
          const active = activeRaceId === race.id;
          return (
            <li key={race.id} className="flex-1 min-w-[68px]">
              <button
                type="button"
                onClick={() => onSelect(race.id)}
                className={clsx(
                  "w-full h-full py-3 px-2 flex flex-col items-center gap-1 transition-all relative group",
                  active ? "bg-paper-glow" : "hover:bg-paper-raised",
                )}
              >
                {active && (
                  <span className="absolute top-0 left-1/2 -translate-x-1/2 w-6 h-px bg-vermilion" />
                )}
                <span
                  className={clsx(
                    "font-display text-xl leading-none",
                    active ? "text-ink" : "text-ink-3 group-hover:text-ink-2",
                  )}
                >
                  {toKanji(race.number)}
                </span>
                <span
                  className={clsx(
                    "font-mono text-[10px] tracking-widest",
                    active ? "text-gold" : "text-ink-ghost",
                  )}
                >
                  R{race.number}
                </span>
                <span
                  className={clsx(
                    "font-mono text-[10px] tabular-nums",
                    active ? "text-ink-2" : "text-ink-ghost",
                  )}
                >
                  {race.start_time_local?.slice(0, 5) ?? "--:--"}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
