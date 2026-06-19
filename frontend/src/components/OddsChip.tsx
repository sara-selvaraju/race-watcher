import { clsx } from "@/lib/clsx";

type Props = {
  price: number | null | undefined;
  basePrice?: number | null;
};

export function OddsChip({ price, basePrice }: Props) {
  if (price == null) return <span className="text-zinc-500 font-mono">—</span>;
  let trend: "firm" | "drift" | "flat" = "flat";
  if (basePrice != null && basePrice > 0) {
    const delta = (price - basePrice) / basePrice;
    if (delta < -0.03) trend = "firm";
    else if (delta > 0.03) trend = "drift";
  }
  return (
    <span
      className={clsx(
        "inline-block rounded px-2 py-0.5 font-mono tabular-nums text-sm",
        trend === "firm" && "bg-green-900/40 text-green-300 ring-1 ring-green-700/50",
        trend === "drift" && "bg-red-900/40 text-red-300 ring-1 ring-red-700/50",
        trend === "flat" && "bg-zinc-800 text-zinc-200 ring-1 ring-zinc-700",
      )}
    >
      ${price.toFixed(2)}
    </span>
  );
}
