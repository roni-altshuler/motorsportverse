"use client";

import { useId } from "react";

// Dependency-free SVG points-progression chart — the F2 analogue of RaceIQ F1's
// recharts ProgressionChart. A solid cumulative line per entity up to the latest
// completed round, then a dashed "projected at current pace" segment out to the
// end of the season. Drawn with the shared design tokens so the static export
// never needs a runtime charting library. Honours prefers-reduced-motion (the
// draw-in is CSS and short-circuited by the global media query in globals.css).

export interface ProgressionSeries {
  /** Stable id (driver code or team name). */
  key: string;
  label: string;
  color: string;
  /** Cumulative points after each completed round (length === rounds.length). */
  history: number[];
  /** Projected end-of-season total for the dashed segment. */
  projectedTotal: number;
}

interface Props {
  series: ProgressionSeries[];
  /** Completed round numbers, e.g. [1,2,3,4,5,6,7]. */
  rounds: number[];
  /** Total rounds in the season (extends the x-axis + dashed projection). */
  totalRounds: number;
}

const W = 720;
const H = 320;
const PAD = { top: 16, right: 18, bottom: 28, left: 38 };

export default function ProgressionChart({ series, rounds, totalRounds }: Props) {
  const uid = useId();
  if (!series.length || !rounds.length) return null;

  const lastRound = rounds[rounds.length - 1] ?? rounds.length;
  const maxY = Math.max(
    1,
    ...series.map((s) => Math.max(s.projectedTotal, ...(s.history.length ? s.history : [0]))),
  );
  // round the y-axis ceiling up to a nice number
  const yCeil = Math.ceil(maxY / 50) * 50 || 50;

  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const x = (round: number) => PAD.left + ((round - 1) / (totalRounds - 1)) * innerW;
  const y = (pts: number) => PAD.top + innerH - (pts / yCeil) * innerH;

  const yTicks = Array.from({ length: 5 }, (_, i) => Math.round((yCeil / 4) * i));
  const xTicks = Array.from({ length: totalRounds }, (_, i) => i + 1).filter(
    (r) => r === 1 || r === totalRounds || r % 2 === 0,
  );

  return (
    <div className="w-full">
      <div className="mono-label mb-3 flex flex-wrap items-center gap-x-5 gap-y-1">
        <span className="inline-flex items-center gap-2 text-[var(--ink-muted)]">
          <svg width="22" height="6" aria-hidden>
            <line x1="0" y1="3" x2="22" y2="3" stroke="currentColor" strokeWidth="2.5" />
          </svg>
          Current standings
        </span>
        <span className="inline-flex items-center gap-2 text-[var(--ink-muted)]">
          <svg width="22" height="6" aria-hidden>
            <line
              x1="0"
              y1="3"
              x2="22"
              y2="3"
              stroke="currentColor"
              strokeWidth="2"
              strokeDasharray="4 4"
              strokeOpacity="0.7"
            />
          </svg>
          Projected at current pace
        </span>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ height: "auto", maxHeight: 360 }}
        role="img"
        aria-label="Championship points progression and projection by round"
      >
        {/* y grid + labels */}
        {yTicks.map((t) => (
          <g key={`y-${t}`}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(t)}
              y2={y(t)}
              stroke="var(--hairline)"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
            <text
              x={PAD.left - 6}
              y={y(t) + 3}
              textAnchor="end"
              className="font-tabular"
              style={{ fontFamily: "var(--font-mono)", fontSize: 10, fill: "var(--ink-dim)" }}
            >
              {t}
            </text>
          </g>
        ))}

        {/* x labels */}
        {xTicks.map((r) => (
          <text
            key={`x-${r}`}
            x={x(r)}
            y={H - 8}
            textAnchor="middle"
            style={{ fontFamily: "var(--font-mono)", fontSize: 10, fill: "var(--ink-dim)" }}
          >
            R{r}
          </text>
        ))}

        {/* "NOW" cursor at the last completed round */}
        <line
          x1={x(lastRound)}
          x2={x(lastRound)}
          y1={PAD.top}
          y2={PAD.top + innerH}
          stroke="var(--accent)"
          strokeWidth="1"
          strokeDasharray="2 4"
          opacity="0.8"
        />
        <text
          x={x(lastRound)}
          y={PAD.top - 4}
          textAnchor="middle"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 9,
            letterSpacing: "0.18em",
            fill: "var(--accent)",
          }}
        >
          NOW
        </text>

        {/* one solid + one dashed polyline per entity */}
        {series.map((s, idx) => {
          const solidPts = s.history
            .map((pts, i) => `${x(rounds[i])},${y(pts)}`)
            .join(" ");
          const tipRound = lastRound;
          const tipPts = s.history[s.history.length - 1] ?? 0;
          const dashed = `${x(tipRound)},${y(tipPts)} ${x(totalRounds)},${y(s.projectedTotal)}`;
          return (
            <g key={s.key} className="prog-line" style={{ animationDelay: `${idx * 60}ms` }}>
              <polyline
                points={solidPts}
                fill="none"
                stroke={s.color}
                strokeWidth="2.5"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              <polyline
                points={dashed}
                fill="none"
                stroke={s.color}
                strokeWidth="2"
                strokeDasharray="5 5"
                strokeOpacity="0.5"
              />
              {/* endpoint dot + label */}
              <circle cx={x(totalRounds)} cy={y(s.projectedTotal)} r="3" fill={s.color} />
              <circle cx={x(tipRound)} cy={y(tipPts)} r="3.2" fill={s.color} />
              <text
                x={x(totalRounds) + 4}
                y={y(s.projectedTotal) + 3}
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 9.5,
                  fill: s.color,
                  fontWeight: 600,
                }}
              >
                {s.key}
              </text>
            </g>
          );
        })}
      </svg>

      <style>{`
        .prog-line {
          opacity: 0;
          animation: progFade var(--dur-slow, 520ms) var(--ease-launch, ease) forwards;
        }
        @keyframes progFade { to { opacity: 1; } }
        @media (prefers-reduced-motion: reduce) {
          .prog-line { animation: none; opacity: 1; }
        }
      `}</style>
      <p key={uid} className="sr-only">
        Points progression chart across {totalRounds} rounds.
      </p>
    </div>
  );
}
