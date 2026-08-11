"use client";

import { useId } from "react";

export interface ProgressionSeries {
  code: string;
  label: string;
  color: string;
  /** Cumulative value per round, aligned to `rounds`; null = not yet scored. */
  values: (number | null)[];
}

/**
 * ProgressionChart — a responsive inline-SVG multi-line chart of cumulative
 * championship points across the completed rounds. Pure SVG (no chart library)
 * so it renders identically in a static export and consumes exactly the data
 * the export supplies (genuine per-round `pointsHistory`). Lines break across
 * null gaps rather than inventing points for rounds a car did not contest.
 */
export default function ProgressionChart({
  rounds,
  series,
  height = 320,
  className = "",
}: {
  rounds: number[];
  series: ProgressionSeries[];
  height?: number;
  className?: string;
}) {
  const gid = useId().replace(/:/g, "");
  const W = 720;
  const H = height;
  const padL = 44;
  const padR = 16;
  const padT = 18;
  const padB = 34;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const n = rounds.length;
  const maxY = Math.max(
    10,
    ...series.flatMap((s) => s.values.map((v) => (v == null ? 0 : v))),
  );
  // Nice-ish rounded top.
  const top = Math.ceil(maxY / 10) * 10;

  const x = (i: number) => padL + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW);
  const y = (v: number) => padT + innerH - (v / top) * innerH;

  const yTicks = 4;
  const gridVals = Array.from({ length: yTicks + 1 }, (_, k) => Math.round((top / yTicks) * k));

  function pathFor(values: (number | null)[]): string {
    let d = "";
    let started = false;
    values.forEach((v, i) => {
      if (v == null) {
        started = false;
        return;
      }
      d += `${started ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)} `;
      started = true;
    });
    return d.trim();
  }

  return (
    <div className={className}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        height="auto"
        role="img"
        aria-label="Cumulative championship points by round"
        style={{ display: "block" }}
      >
        {/* horizontal gridlines + y labels */}
        {gridVals.map((gv) => (
          <g key={gv}>
            <line
              x1={padL}
              x2={W - padR}
              y1={y(gv)}
              y2={y(gv)}
              stroke="var(--hairline)"
              strokeWidth={1}
            />
            <text
              x={padL - 8}
              y={y(gv) + 3}
              textAnchor="end"
              fontFamily="var(--font-mono)"
              fontSize={10}
              fill="var(--muted)"
            >
              {gv}
            </text>
          </g>
        ))}

        {/* x labels (round numbers) */}
        {rounds.map((r, i) => (
          <text
            key={r}
            x={x(i)}
            y={H - padB + 18}
            textAnchor="middle"
            fontFamily="var(--font-mono)"
            fontSize={10}
            fill="var(--muted)"
          >
            R{r}
          </text>
        ))}

        {/* lines */}
        {series.map((s) => {
          const d = pathFor(s.values);
          if (!d) return null;
          const lastIdx = [...s.values].map((v, i) => (v == null ? -1 : i)).filter((i) => i >= 0).pop();
          return (
            <g key={s.code}>
              <path d={d} fill="none" stroke={s.color} strokeWidth={2.25} strokeLinejoin="round" strokeLinecap="round" />
              {lastIdx != null && s.values[lastIdx] != null && (
                <circle cx={x(lastIdx)} cy={y(s.values[lastIdx] as number)} r={3.5} fill={s.color} stroke="var(--canvas)" strokeWidth={1.5} />
              )}
            </g>
          );
        })}
        <title>{`Cumulative points across ${n} round(s) — ${gid}`}</title>
      </svg>

      {/* legend */}
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
        {series.map((s) => (
          <span key={s.code} className="inline-flex items-center gap-2 text-[12px]" style={{ color: "var(--body)" }}>
            <span className="inline-block rounded-full" style={{ width: 10, height: 10, background: s.color }} />
            <span className="font-mono tracking-[0.04em]">{s.label}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
