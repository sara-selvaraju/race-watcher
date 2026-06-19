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
  return (
    <header className="flex items-baseline justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold">{track}</h1>
        <p className="text-sm text-zinc-400">
          {new Date(date).toLocaleDateString(undefined, {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
          })}
          {going && <> · {going}</>}
          {rail && <> · {rail}</>}
        </p>
      </div>
      <div className="text-right text-xs text-zinc-500">
        {status?.in_window ? (
          <span className="text-green-400">● polling</span>
        ) : (
          <span>polling paused</span>
        )}
        <div>{status?.snapshot_count ?? 0} snapshots · {status?.alert_count ?? 0} alerts</div>
      </div>
    </header>
  );
}
