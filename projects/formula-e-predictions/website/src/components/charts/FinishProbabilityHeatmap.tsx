"use client";

// Dependency-free finish-probability heatmap — the FE analogue of RaceIQ F1's
// visx FinishProbabilityHeatmap. Drivers are rows; finishing positions are
// columns. Each cell's intensity is a triangular distribution centred on the
// driver's predicted mean finish and spread across their forecast finish range,
// tinted with the accent. When a round is completed, the driver's ACTUAL finish
// position is ringed so the reader can see where the model landed vs reality.

export interface HeatmapRow {
  code: string;
  name: string;
  teamColor: string;
  meanFinish: number;
  finishRangeLow: number;
  finishRangeHigh: number;
  actualPosition: number | null;
}

/** Triangular weight at integer position p given mean + [low,high] support. */
function weight(p: number, mean: number, low: number, high: number): number {
  if (p < low || p > high) return 0;
  // distance from the mode, normalised by the longer half-span
  const span = Math.max(mean - low, high - mean, 0.5);
  const w = 1 - Math.abs(p - mean) / (span + 0.5);
  return Math.max(0, w);
}

export function FinishProbabilityHeatmap({
  rows,
  maxPosition,
  completed,
}: {
  rows: HeatmapRow[];
  maxPosition: number;
  completed: boolean;
}) {
  const positions = Array.from({ length: maxPosition }, (_, i) => i + 1);

  return (
    <div>
      <p className="eyebrow mb-3">Finish-position likelihood</p>
      <div className="overflow-x-auto">
        <table className="border-separate" style={{ borderSpacing: 2 }}>
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-[var(--surface)] pr-2 text-left" />
              {positions.map((p) => (
                <th
                  key={p}
                  className="font-tabular pb-1 text-center"
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 9,
                    color: "var(--ink-dim)",
                    minWidth: 16,
                  }}
                >
                  {p}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.code}>
                <td
                  className="sticky left-0 z-10 bg-[var(--surface)] pr-2 text-right"
                  style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--ink-muted)" }}
                >
                  {r.code}
                </td>
                {positions.map((p) => {
                  const w = weight(p, r.meanFinish, r.finishRangeLow, r.finishRangeHigh);
                  const isActual = completed && r.actualPosition === p;
                  return (
                    <td key={p} className="p-0">
                      <div
                        title={`${r.name} · P${p}`}
                        style={{
                          width: 16,
                          height: 16,
                          borderRadius: 2,
                          background:
                            w > 0
                              ? `color-mix(in srgb, var(--accent) ${Math.round(w * 100)}%, var(--surface-2))`
                              : "var(--surface-2)",
                          boxShadow: isActual ? "inset 0 0 0 2px var(--ink)" : undefined,
                        }}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-[var(--ink-dim)]">
        Brighter = more likely. Columns are finishing positions.
        {completed ? " White ring marks the actual finish." : ""}
      </p>
    </div>
  );
}
