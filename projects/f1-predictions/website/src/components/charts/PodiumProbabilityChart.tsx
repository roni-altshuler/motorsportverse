"use client";

import { useMemo, useState } from "react";
import { Group } from "@visx/group";
import { Bar } from "@visx/shape";
import { scaleBand, scaleLinear } from "@visx/scale";
import { AxisLeft, AxisBottom } from "@visx/axis";
import { ParentSize } from "@visx/responsive";
import { resolveDriverHeadshot } from "@/lib/headshots";
import type { ClassificationEntry } from "@/types";

/** SVG <image> ticks store public-rooted paths; basePath is applied here. */
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

interface PodiumProbabilityChartProps {
  classification: ClassificationEntry[];
  limit?: number;
}

interface Row {
  driver: string;
  teamColor: string;
  winP: number;
  podiumP: number;
  team: string;
}

function buildRows(classification: ClassificationEntry[], limit: number): Row[] {
  return classification
    .map((c) => {
      const cTyped = c as ClassificationEntry & {
        simulatorPodiumProbability?: number;
        simulatorWinProbability?: number;
      };
      const winP =
        typeof cTyped.simulatorWinProbability === "number"
          ? cTyped.simulatorWinProbability * 100
          : cTyped.winProbability ?? 0;
      const podiumP =
        typeof cTyped.simulatorPodiumProbability === "number"
          ? cTyped.simulatorPodiumProbability * 100
          : null;
      return {
        driver: cTyped.driver,
        team: cTyped.team,
        teamColor: cTyped.teamColor || "#888",
        winP,
        podiumP: podiumP ?? winP * 2.4, // rough fallback: P(top3) ~ 2-3x P(win)
      };
    })
    .filter((r) => r.podiumP > 0 || r.winP > 0)
    .sort((a, b) => b.podiumP - a.podiumP)
    .slice(0, limit);
}

function PodiumProbabilityChartInner({
  rows,
  width,
  height,
}: {
  rows: Row[];
  width: number;
  height: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const margin = { top: 16, right: 16, bottom: 36, left: 76 };
  const innerW = Math.max(0, width - margin.left - margin.right);
  const innerH = Math.max(0, height - margin.top - margin.bottom);

  const yScale = scaleBand({
    domain: rows.map((r) => r.driver),
    range: [0, innerH],
    padding: 0.2,
  });
  const maxX = Math.max(100, ...rows.map((r) => r.podiumP));
  const xScale = scaleLinear({ domain: [0, maxX], range: [0, innerW] });

  return (
    <svg width={width} height={height}>
      <Group left={margin.left} top={margin.top}>
        {rows.map((row, i) => {
          const podBarW = xScale(row.podiumP);
          const winBarW = xScale(row.winP);
          const y = yScale(row.driver) ?? 0;
          const bh = yScale.bandwidth();
          const isHover = hover === i;
          return (
            <Group
              key={row.driver}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            >
              <Bar
                x={0}
                y={y}
                width={podBarW}
                height={bh}
                fill={row.teamColor}
                fillOpacity={isHover ? 0.45 : 0.28}
                rx={4}
              />
              <Bar
                x={0}
                y={y}
                width={winBarW}
                height={bh}
                fill={row.teamColor}
                fillOpacity={isHover ? 1 : 0.85}
                rx={4}
              />
              <text
                x={podBarW + 6}
                y={y + bh / 2}
                fill="var(--text-secondary)"
                fontSize={11}
                dominantBaseline="middle"
                fontFamily="var(--font-mono)"
              >
                {row.podiumP.toFixed(0)}% podium
              </text>
              {row.winP > 1 && (
                <text
                  x={Math.max(8, winBarW - 6)}
                  y={y + bh / 2}
                  fill="var(--text-primary)"
                  fontSize={11}
                  fontWeight={700}
                  textAnchor="end"
                  dominantBaseline="middle"
                  fontFamily="var(--font-mono)"
                >
                  {row.winP.toFixed(0)}%
                </text>
              )}
            </Group>
          );
        })}
        <AxisLeft
          scale={yScale}
          stroke="var(--border)"
          tickStroke="var(--border)"
          tickComponent={({ x, y, formattedValue }) => {
            const code = formattedValue ?? "";
            const path = resolveDriverHeadshot(code);
            const SIZE = 24;
            // Left-axis ticks are right-anchored at x; place the circular
            // headshot just left of the axis, vertically centred on the bar.
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
        <AxisBottom
          scale={xScale}
          top={innerH}
          stroke="var(--border)"
          tickStroke="var(--border)"
          tickFormat={(d) => `${d}%`}
          tickLabelProps={{
            fill: "var(--text-muted)",
            fontSize: 10,
            textAnchor: "middle",
          }}
        />
      </Group>
    </svg>
  );
}

export default function PodiumProbabilityChart({ classification, limit = 10 }: PodiumProbabilityChartProps) {
  const rows = useMemo(() => buildRows(classification, limit), [classification, limit]);
  if (rows.length === 0) return null;
  return (
    <div className="w-full" style={{ height: Math.max(280, 36 * rows.length + 60) }}>
      <ParentSize>{({ width, height }) => <PodiumProbabilityChartInner rows={rows} width={width} height={height} />}</ParentSize>
    </div>
  );
}
