import { clsx } from "@/lib/clsx";

type Props = {
  price: number | null | undefined;
  basePrice?: number | null;
  size?: "sm" | "md";
};

export function OddsChip({ price, basePrice, size = "md" }: Props) {
  if (price == null) {
    return (
      <span className="font-mono text-paper-ghost text-sm tracking-tight">—</span>
    );
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
        "inline-flex items-baseline font-mono tabular-nums leading-none",
        size === "md" ? "text-base" : "text-sm",
        trend === "firm" && "text-matcha",
        trend === "drift" && "text-vermilion",
        trend === "flat" && "text-paper",
      )}
    >
      <span className="text-paper-faint text-[0.7em] mr-0.5">$</span>
      {price.toFixed(2)}
    </span>
  );
}
