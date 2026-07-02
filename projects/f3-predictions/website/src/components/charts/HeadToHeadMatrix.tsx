// Head-to-head probability grid — P(row driver finishes ahead of column driver).
// Rendered as a coloured table from the probabilities JSON (no chart lib), the
// F3 counterpart to F1's @visx HeadToHeadMatrix.

export function HeadToHeadMatrix({
  h2h,
  accent = "var(--accent)",
}: {
  h2h: Record<string, Record<string, number>>;
  accent?: string;
}) {
  const drivers = Object.keys(h2h);
  if (drivers.length === 0) {
    return <p className="text-sm text-[var(--ink-dim)]">No head-to-head data for this round.</p>;
  }

  const cell = (p: number) => ({
    backgroundColor: `color-mix(in srgb, ${accent} ${Math.round(p * 90)}%, transparent)`,
    color: p > 0.55 ? "var(--accent-ink)" : "var(--ink-muted)",
  });

  return (
    <div className="overflow-x-auto">
      <table className="border-collapse text-xs">
        <thead>
          <tr>
            <th className="sticky left-0 z-10 bg-[var(--surface)] p-1.5 text-left text-[var(--ink-dim)]">
              beats ↓ / →
            </th>
            {drivers.map((d) => (
              <th key={d} className="p-1.5 font-medium text-[var(--ink-dim)]">
                {d}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {drivers.map((row) => (
            <tr key={row}>
              <th className="sticky left-0 z-10 bg-[var(--surface)] p-1.5 text-left font-semibold text-[var(--ink)]">
                {row}
              </th>
              {drivers.map((col) => {
                if (row === col) {
                  return <td key={col} className="bg-[var(--surface-3)] p-1.5 text-center">—</td>;
                }
                const p = h2h[row]?.[col];
                if (p === undefined) {
                  return <td key={col} className="p-1.5 text-center text-[var(--ink-dim)]">·</td>;
                }
                return (
                  <td
                    key={col}
                    className="p-1.5 text-center tabular-nums"
                    style={cell(p)}
                    title={`${row} beats ${col}: ${(p * 100).toFixed(0)}%`}
                  >
                    {(p * 100).toFixed(0)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
