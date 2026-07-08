// Predicted-vs-actual finishing slope chart — dependency-free SVG, drawn with
// the shared design tokens like the rest of the F2 chart family.
//
// Left column: the model's pre-race predicted order. Right column: the actual
// classified result. Each driver's line connects the two, coloured by team, so
// the reader sees at a glance where the model was on the money (flat lines)
// and where the race broke from the script (steep lines). Drivers who were
// not classified (DNF/DNS) stay on the left with a dimmed marker and no line.
//
// Only rendered for completed rounds — there is nothing honest to draw before
// the chequered flag.

export interface SlopeRow {
  code: string;
  name: string;
  teamColor: string;
  /** Model's predicted finishing position (1-based). */
  predicted: number;
  /** Actual classified position, or null when not classified. */
  actual: number | null;
}

const ROW_H = 20;
const PAD_TOP = 26;
const PAD_BOTTOM = 10;
const LABEL_W = 78;
const VIEW_W = 560;

export function PredictedVsActualSlope({
  rows,
  title = "Predicted vs actual finishing order",
}: {
  rows: SlopeRow[];
  title?: string;
}) {
  const classified = rows.filter((r) => r.actual != null);
  if (classified.length === 0) return null;

  const n = Math.max(
    rows.length,
    ...classified.map((r) => r.actual as number),
    ...rows.map((r) => r.predicted),
  );
  const height = PAD_TOP + n * ROW_H + PAD_BOTTOM;
  const xLeft = LABEL_W;
  const xRight = VIEW_W - LABEL_W;
  const y = (pos: number) => PAD_TOP + (pos - 0.5) * ROW_H;

  const byPredicted = [...rows].sort((a, b) => a.predicted - b.predicted);
  const byActual = [...classified].sort((a, b) => (a.actual ?? 0) - (b.actual ?? 0));

  const exact = classified.filter((r) => r.actual === r.predicted).length;
  const within3 = classified.filter((r) => Math.abs((r.actual as number) - r.predicted) <= 3).length;

  return (
    <div>
      <p className="eyebrow mb-3">{title}</p>
      <svg
        viewBox={`0 0 ${VIEW_W} ${height}`}
        className="h-auto w-full"
        role="img"
        aria-label="Slope chart connecting each driver's predicted finishing position to their actual result"
      >
        {/* Column headers */}
        <text
          x={xLeft - 8}
          y={14}
          textAnchor="end"
          style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.14em" }}
          fill="var(--ink-dim)"
        >
          PREDICTED
        </text>
        <text
          x={xRight + 8}
          y={14}
          textAnchor="start"
          style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.14em" }}
          fill="var(--ink-dim)"
        >
          ACTUAL
        </text>

        {/* Axis rails */}
        <line x1={xLeft} y1={PAD_TOP - 6} x2={xLeft} y2={height - PAD_BOTTOM} stroke="var(--hairline)" />
        <line x1={xRight} y1={PAD_TOP - 6} x2={xRight} y2={height - PAD_BOTTOM} stroke="var(--hairline)" />

        {/* Slope lines (classified only) */}
        {classified.map((r) => {
          const delta = Math.abs((r.actual as number) - r.predicted);
          return (
            <line
              key={`l-${r.code}`}
              x1={xLeft}
              y1={y(r.predicted)}
              x2={xRight}
              y2={y(r.actual as number)}
              stroke={r.teamColor}
              strokeWidth={delta <= 1 ? 2.25 : 1.5}
              strokeOpacity={delta <= 3 ? 0.9 : 0.55}
            >
              <title>{`${r.name}: predicted P${r.predicted} → finished P${r.actual}`}</title>
            </line>
          );
        })}

        {/* Left labels: predicted order (all drivers) */}
        {byPredicted.map((r) => (
          <g key={`p-${r.code}`} opacity={r.actual == null ? 0.45 : 1}>
            <circle cx={xLeft} cy={y(r.predicted)} r={3} fill={r.teamColor} />
            <text
              x={xLeft - 8}
              y={y(r.predicted) + 3.5}
              textAnchor="end"
              style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}
              fill="var(--ink-muted)"
            >
              {`P${r.predicted} ${r.code}${r.actual == null ? " ·NC" : ""}`}
            </text>
          </g>
        ))}

        {/* Right labels: actual order (classified drivers) */}
        {byActual.map((r) => (
          <g key={`a-${r.code}`}>
            <circle cx={xRight} cy={y(r.actual as number)} r={3} fill={r.teamColor} />
            <text
              x={xRight + 8}
              y={y(r.actual as number) + 3.5}
              textAnchor="start"
              style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}
              fill="var(--ink-muted)"
            >
              {`P${r.actual} ${r.code}`}
            </text>
          </g>
        ))}
      </svg>
      <p className="mt-3 text-xs text-[var(--ink-dim)]">
        Flatter lines = closer calls. {exact} exact, {within3} of {classified.length} classified
        within three places. ·NC marks drivers not classified in the race.
      </p>
    </div>
  );
}
