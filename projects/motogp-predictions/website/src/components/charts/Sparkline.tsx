// Tiny inline-SVG sparkline (no chart lib) for the accuracy page's per-round
// Brier trend.

export function Sparkline({
  points,
  width = 240,
  height = 48,
  accent = "var(--accent)",
}: {
  points: number[];
  width?: number;
  height?: number;
  accent?: string;
}) {
  if (points.length < 2) {
    return <span className="text-xs text-[var(--ink-dim)]">not enough rounds yet</span>;
  }
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const stepX = width / (points.length - 1);
  const coords = points.map((p, i) => {
    const x = i * stepX;
    const y = height - ((p - min) / span) * (height - 6) - 3;
    return [x, y] as const;
  });
  const path = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  return (
    <svg width={width} height={height} role="img" aria-label="Per-round Brier trend">
      <path d={path} fill="none" stroke={accent} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      {coords.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={2} fill={accent} />
      ))}
    </svg>
  );
}
