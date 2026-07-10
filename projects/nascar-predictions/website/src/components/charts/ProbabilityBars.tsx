// Dependency-free horizontal probability bars — the FE analogue of F1's
// WinProbabilityChart, drawn with the shared design tokens so the two sites match
// without pulling a charting library into the static export.

export interface ProbRow {
  code: string;
  label: string;
  team: string;
  teamColor: string;
  probability: number; // 0..1
}

export function ProbabilityBars({
  title,
  rows,
  accent = "var(--accent)",
}: {
  title: string;
  rows: ProbRow[];
  accent?: string;
}) {
  const max = Math.max(0.0001, ...rows.map((r) => r.probability));
  return (
    <div>
      <p className="eyebrow mb-3">{title}</p>
      <div className="flex flex-col gap-2">
        {rows.map((r) => (
          <div key={r.code} className="flex items-center gap-3">
            <span className="w-28 shrink-0 truncate text-sm text-[var(--ink)]" title={r.label}>
              {r.label}
            </span>
            <div className="relative h-5 flex-1 overflow-hidden rounded-[var(--radius-sm)] bg-[var(--surface-2)]">
              <div
                className="absolute inset-y-0 left-0 rounded-[var(--radius-sm)]"
                style={{
                  width: `${(r.probability / max) * 100}%`,
                  background: `linear-gradient(90deg, ${r.teamColor}, ${accent})`,
                  opacity: 0.9,
                }}
              />
            </div>
            <span className="w-12 shrink-0 text-right text-sm tabular-nums text-[var(--ink-muted)]">
              {(r.probability * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
