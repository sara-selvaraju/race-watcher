import { clsx } from "@/lib/clsx";

type Props = {
  price: number | null | undefined;
  basePrice?: number | null;
  // Shown, muted, when there's no live price yet.
  previewPrice?: number | null;
};

export function OddsChip({ price, basePrice, previewPrice }: Props) {
  if (price == null) {
    if (previewPrice != null) {
      return (
        <span className="num text-xl font-bold leading-none text-ink-3" title="Preview price from the race card, before live odds">
          ${previewPrice.toFixed(2)}
        </span>
      );
    }
    return <span className="num text-xl text-ink-3">—</span>;
  }

  let trend: "firm" | "drift" | "flat" = "flat";
  if (basePrice != null && basePrice > 0) {
    const delta = (price - basePrice) / basePrice;
    if (delta < -0.03) trend = "firm";
    else if (delta > 0.03) trend = "drift";
  }

  return (
    <span
      className={clsx(
        "num inline-flex items-baseline gap-1 text-xl font-bold leading-none",
        trend === "firm" && "text-firm",
        trend === "drift" && "text-drift",
      )}
      title={trend === "firm" ? "Firming" : trend === "drift" ? "Drifting" : undefined}
    >
      {trend !== "flat" && <span className="text-sm">{trend === "firm" ? "▼" : "▲"}</span>}${price.toFixed(2)}
    </span>
  );
}
