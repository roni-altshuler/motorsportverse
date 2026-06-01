"use client";

import { useMemo } from "react";
import { Group } from "@visx/group";
import { scaleLinear, scaleBand } from "@visx/scale";
import { AxisLeft, AxisTop } from "@visx/axis";
import { ParentSize } from "@visx/responsive";
import { resolveDriverHeadshot } from "@/lib/headshots";
import type { ClassificationEntry } from "@/types";

/** SVG <image> ticks store public-rooted paths; basePath is applied here. */
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

interface FinishProbabilityHeatmapProps {
  classification: ClassificationEntry[];
  /** How many drivers (rows) and positions (cols) to show. Default 14×14. */
  driverLimit?: number;
  positionLimit?: number;
}

/**
 * Driver × position probability heatmap.  When per-driver, per-position
 * probabilities aren't published in the round JSON we interpolate
 * from `winProbability` + `finishRangeLow`/`finishRangeHigh` with a
 * triangular distribution centred on the predicted position.  Cells
 * are tinted from --bg-surface (cold) → --accent-live (hot).
 */
function buildMatrix(
  classification: ClassificationEntry[],
  driverLimit: number,
  positionLimit: number,
) {
  const drivers = [...classification]
    .sort((a, b) => a.position - b.position)
    .slice(0, driverLimit);
  const positions = Array.from({ length: positionLimit }, (_, i) => i + 1);

  const matrix: { driver: string; teamColor: string; cells: { position: number; p: number }[] }[] = [];
  for (const c of drivers) {
    const centre = c.position;
    const low = c.finishRangeLow ?? Math.max(1, centre - 3);
    const high = c.finishRangeHigh ?? Math.min(positionLimit, centre + 3);
    const cells = positions.map((position) => {
      // Triangular distribution centered at `centre`, supported on [low, high].
      // Falls off linearly outside [low, high].
      if (position < Math.max(1, low - 2) || position > Math.min(positionLimit, high + 2)) {
        return { position, p: 0 };
      }
      const dist = Math.abs(position - centre);
      const span = Math.max(1, (high - low) / 2);
      const raw = Math.max(0, 1 - dist / (span + 1));
      // P1 spike for the leader
      const winSpike = position === centre && c.winProbability != null ? (c.winProbability / 100) * 0.6 : 0;
      return { position, p: Math.min(1, raw * 0.6 + winSpike) };
    });
    matrix.push({ driver: c.driver, teamColor: c.teamColor || "#888", cells });
  }
  return { drivers, positions, matrix };
}

function HeatmapInner({
  width,
  height,
  drivers,
  positions,
  matrix,
}: ReturnType<typeof buildMatrix> & { width: number; height: number }) {
  const margin = { top: 32, right: 16, bottom: 8, left: 56 };
  const innerW = Math.max(0, width - margin.left - margin.right);
  const innerH = Math.max(0, height - margin.top - margin.bottom);

  const xScale = scaleBand({
    domain: positions.map(String),
    range: [0, innerW],
    padding: 0.06,
  });
  const yScale = scaleBand({
    domain: drivers.map((d) => d.driver),
    range: [0, innerH],
    padding: 0.08,
  });
  const colorScale = scaleLinear({
    domain: [0, 1],
    range: [0, 1],
  });

  return (
    <svg width={width} height={height}>
      <defs>
        <linearGradient id="heat-cold-hot" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="#1c2230" />
          <stop offset="50%" stopColor="#F76B15" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#F76B15" />
        </linearGradient>
      </defs>
      <Group left={margin.left} top={margin.top}>
        {matrix.map((row) => {
          const rowMax = Math.max(...row.cells.map((c) => c.p));
          return row.cells.map((cell) => {
            const cx = xScale(String(cell.position)) ?? 0;
            const cy = yScale(row.driver) ?? 0;
            const isPeak = cell.p > 0 && cell.p === rowMax;
            const t = colorScale(cell.p);
            const bg = cell.p === 0 ? "var(--bg-surface)" : `color-mix(in srgb, ${row.teamColor} ${Math.round(t * 90)}%, transparent)`;
            return (
              <g key={`${row.driver}-${cell.position}`}>
                <rect
                  x={cx}
                  y={cy}
                  width={xScale.bandwidth()}
                  height={yScale.bandwidth()}
                  fill={bg}
                  stroke={isPeak ? "var(--hud-purple)" : "transparent"}
                  strokeWidth={isPeak ? 1.5 : 0}
                  rx={3}
                />
                {cell.p > 0.18 && (
                  <text
                    x={cx + xScale.bandwidth() / 2}
                    y={cy + yScale.bandwidth() / 2}
                    fill="var(--text-primary)"
                    fontSize={10}
                    fontFamily="var(--font-mono)"
                    fontWeight={700}
                    textAnchor="middle"
                    dominantBaseline="central"
                  >
                    {Math.round(cell.p * 100)}
                  </text>
                )}
              </g>
            );
          });
        })}
        <AxisTop
          scale={xScale}
          stroke="var(--border)"
          tickStroke="var(--border)"
          tickFormat={(v) => `P${v}`}
          tickLabelProps={{
            fill: "var(--text-muted)",
            fontSize: 10,
            textAnchor: "middle",
            dy: "-0.33em",
          }}
        />
        <AxisLeft
          scale={yScale}
          stroke="var(--border)"
          tickStroke="var(--border)"
          tickComponent={({ x, y, formattedValue }) => {
            const code = formattedValue ?? "";
            const path = resolveDriverHeadshot(code);
            const SIZE = 22;
            // Left-axis ticks are right-anchored at x; place the circular
            // headshot just left of the axis, vertically centred on the row.
            return path ? (
              <image
                href={`${BASE_PATH}${path}`}
                x={x - SIZE - 4}
                y={y - SIZE / 2}
                width={SIZE}
                height={SIZE}
                clipPath="circle(50%)"
                preserveAspectRatio="xMidYMid slice"
              >
                <title>{code}</title>
              </image>
            ) : (
              <text
                x={x}
                y={y}
                dy="0.33em"
                textAnchor="end"
                fontSize={11}
                fontWeight={700}
                fill="var(--text-secondary)"
              >
                {code}
              </text>
            );
          }}
        />
      </Group>
    </svg>
  );
}

export default function FinishProbabilityHeatmap({
  classification,
  driverLimit = 14,
  positionLimit = 14,
}: FinishProbabilityHeatmapProps) {
  const data = useMemo(
    () => buildMatrix(classification, driverLimit, positionLimit),
    [classification, driverLimit, positionLimit],
  );
  if (data.drivers.length === 0) return null;
  return (
    <div className="w-full" style={{ height: Math.max(320, 32 * data.drivers.length + 60) }}>
      <ParentSize>{({ width, height }) => <HeatmapInner {...data} width={width} height={height} />}</ParentSize>
    </div>
  );
}
