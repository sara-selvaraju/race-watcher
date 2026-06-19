type Props = {
  prices: number[];
  width?: number;
  height?: number;
};

export function PriceSparkline({ prices, width = 80, height = 22 }: Props) {
  if (!prices.length) return <span className="text-zinc-600 text-xs">no data</span>;
  if (prices.length === 1) return <span className="text-zinc-500 text-xs">just one</span>;

  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = Math.max(max - min, 0.01);
  const step = prices.length === 1 ? width : width / (prices.length - 1);

  // For odds: lower price = "firmer" = up visually
  const points = prices.map((p, i) => {
    const x = i * step;
    const y = ((p - min) / range) * (height - 4) + 2;
    return `${x.toFixed(1)},${(height - y).toFixed(1)}`;
  });

  const last = prices[prices.length - 1];
  const first = prices[0];
  const stroke = last < first ? "#16a34a" : last > first ? "#dc2626" : "#a1a1aa";

  return (
    <svg width={width} height={height} role="img" aria-label="price trend">
      <polyline
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        points={points.join(" ")}
      />
    </svg>
  );
}
