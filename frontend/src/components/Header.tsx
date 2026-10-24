"use client";

import { useStatus } from "@/lib/api/hooks";
import type { MeetingOut } from "@/lib/api/client";

export function TopBar({ meeting }: { meeting: MeetingOut | null }) {
  const { data: status } = useStatus();
  const date = meeting ? new Date(`${meeting.date}T12:00:00`) : null;

  return (
    <header className="bg-turf text-white">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 h-14 flex items-center gap-4">
        <span className="font-display text-2xl font-bold tracking-tight leading-none">Race Watcher</span>
        {date && (
          <span className="text-white/75 text-sm hidden sm:inline">
            {date.toLocaleDateString("en-AU", { weekday: "long", day: "numeric", month: "long" })}
          </span>
        )}
        <span className="ml-auto flex items-center gap-2 text-sm text-white/85">
          <span
            className={`h-2 w-2 rounded-full ${status?.in_window ? "bg-silk animate-pulse" : "bg-white/40"}`}
            aria-hidden
          />
          {status?.in_window ? "Racing now" : "Between meetings"}
        </span>
      </div>
    </header>
  );
}
