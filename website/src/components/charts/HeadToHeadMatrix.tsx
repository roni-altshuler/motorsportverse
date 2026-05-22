"use client";

import { useMemo } from "react";
import { Group } from "@visx/group";
import { scaleBand } from "@visx/scale";
import { AxisLeft, AxisTop } from "@visx/axis";
import { ParentSize } from "@visx/responsive";
import type { ClassificationEntry } from "@/types";

interface HeadToHeadMatrixProps {
  classification: ClassificationEntry[];
  /** N×N matrix; capped at this many drivers. */
  driverLimit?: number;
}

/**
 * Pairwise "A beats B" probability heatmap.  When the round JSON
 * doesn't ship an explicit H2H matrix we derive one from each
 * driver's win-probability ranking — a serviceable proxy that
 * preserves expected ordering and asymmetric strength deltas.
 */
function buildMatrix(classification: ClassificationEntry[], driverLimit: number) {
  const drivers = [...classification]
    .sort((a, b) => a.position - b.position)
    .slice(0, driverLimit);
  // Use winProbability if present, else 1/position as a strength proxy.
  const strength = (e: ClassificationEntry) =>
    e.winProbability != null && e.winProbability > 0 ? e.winProbability : 100 / Math.max(1, e.position);
  const matrix = drivers.map((a) =>
    drivers.map((b) => {
      if (a.driver === b.driver) return null;
      const sA = strength(a);
      const sB = strength(b);
      const total = sA + sB;
      // Slight steepening so the visual contrast pops without leaving 0/1.
      const raw = total > 0 ? sA / total : 0.5;
      const adj = 0.5 + (raw - 0.5) * 1.25;
      return Math.max(0.05, Math.min(0.95, adj));
    }),
  );
  return { drivers, matrix };
}

function MatrixInner({
  width,
  height,
  drivers,
  matrix,
}: ReturnType<typeof buildMatrix> & { width: number; height: number }) {
  const margin = { top: 48, right: 16, bottom: 8, left: 56 };
  const innerW = Math.max(0, width - margin.left - margin.right);
  const innerH = Math.max(0, height - margin.top - margin.bottom);
  const axis = scaleBand({
    domain: drivers.map((d) => d.driver),
    range: [0, Math.min(innerW, innerH)],
    padding: 0.08,
  });

  return (
    <svg width={width} height={height}>
      <Group left={margin.left} top={margin.top}>
        {matrix.map((row, rowIdx) =>
          row.map((cell, colIdx) => {
            const driverA = drivers[rowIdx];
            const driverB = drivers[colIdx];
            const x = axis(driverB.driver) ?? 0;
            const y = axis(driverA.driver) ?? 0;
            if (cell == null) {
              return (
                <rect
                  key={`d-${rowIdx}-${colIdx}`}
                  x={x}
                  y={y}
                  width={axis.bandwidth()}
                  height={axis.bandwidth()}
                  fill="var(--surface-elevated)"
                  rx={3}
                />
              );
            }
            const isAdvantage = cell > 0.5;
            const t = Math.abs(cell - 0.5) * 2;
            const fill = isAdvantage
              ? `color-mix(in srgb, var(--accent-live) ${Math.round(t * 70 + 12)}%, var(--surface))`
              : `color-mix(in srgb, var(--hud-cyan) ${Math.round(t * 70 + 12)}%, var(--surface))`;
            return (
              <g key={`${rowIdx}-${colIdx}`}>
                <rect
                  x={x}
                  y={y}
                  width={axis.bandwidth()}
                  height={axis.bandwidth()}
                  fill={fill}
                  stroke="var(--border)"
                  strokeWidth={0.5}
                  rx={3}
                >
                  <title>{`${driverA.driver} beats ${driverB.driver}: ${Math.round(cell * 100)}%`}</title>
                </rect>
                {axis.bandwidth() > 28 && (
                  <text
                    x={x + axis.bandwidth() / 2}
                    y={y + axis.bandwidth() / 2}
                    fill="var(--text-primary)"
                    fontSize={10}
                    fontFamily="var(--font-mono)"
                    fontWeight={700}
                    textAnchor="middle"
                    dominantBaseline="central"
                  >
                    {Math.round(cell * 100)}
                  </text>
                )}
              </g>
            );
          }),
        )}
        <AxisTop
          scale={axis}
          stroke="var(--border)"
          tickStroke="var(--border)"
          tickLabelProps={{
            fill: "var(--text-secondary)",
            fontSize: 10,
            fontWeight: 700,
            textAnchor: "middle",
            angle: -45,
            dy: "-0.5em",
          }}
        />
        <AxisLeft
          scale={axis}
          stroke="var(--border)"
          tickStroke="var(--border)"
          tickLabelProps={{
            fill: "var(--text-secondary)",
            fontSize: 11,
            fontWeight: 700,
            textAnchor: "end",
            dy: "0.33em",
          }}
        />
      </Group>
    </svg>
  );
}

export default function HeadToHeadMatrix({ classification, driverLimit = 12 }: HeadToHeadMatrixProps) {
  const data = useMemo(() => buildMatrix(classification, driverLimit), [classification, driverLimit]);
  if (data.drivers.length === 0) return null;
  return (
    <div className="w-full" style={{ height: Math.max(320, 30 * data.drivers.length + 80) }}>
      <ParentSize>{({ width, height }) => <MatrixInner {...data} width={width} height={height} />}</ParentSize>
    </div>
  );
}
