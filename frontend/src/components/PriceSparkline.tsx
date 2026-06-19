type Props = {
  prices: number[];
  width?: number;
  height?: number;
};

export function PriceSparkline({ prices, width = 72, height = 18 }: Props) {
  if (!prices.length) {
    return <span className="text-ink-ghost text-[10px] tracking-widest font-mono">—</span>;
  }
  if (prices.length === 1) {
    return <span className="text-ink-ghost text-[10px] tracking-widest font-mono">FRESH</span>;
  }

  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = Math.max(max - min, 0.01);
  const step = width / (prices.length - 1);

  // odds: lower price = firmer = visually higher
  const points = prices.map((p, i) => {
    const x = i * step;
    const y = ((p - min) / range) * (height - 4) + 2;
    return `${x.toFixed(1)},${(height - y).toFixed(1)}`;
  });

  const first = prices[0];
  const last = prices[prices.length - 1];
  // firmed = price fell = matcha; drifted = price rose = vermilion
  const stroke = last < first ? "var(--matcha)" : last > first ? "var(--vermilion)" : "var(--paper-faint)";
  const finalX = (prices.length - 1) * step;
  const finalY = ((last - min) / range) * (height - 4) + 2;

  return (
    <svg width={width} height={height} role="img" aria-label="price trend" className="overflow-visible">
      <polyline
        fill="none"
        stroke={stroke}
        strokeWidth={1.2}
        strokeLinejoin="round"
        strokeLinecap="round"
        points={points.join(" ")}
        opacity={0.85}
      />
      <circle cx={finalX} cy={height - finalY} r={1.6} fill={stroke} />
    </svg>
  );
}
