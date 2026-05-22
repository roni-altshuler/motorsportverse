"use client";

import { useMemo } from "react";
import { Group } from "@visx/group";
import { scaleLinear, scaleBand } from "@visx/scale";
import { AxisLeft, AxisBottom } from "@visx/axis";
import { ParentSize } from "@visx/responsive";
import type { ClassificationEntry, ModelMetrics } from "@/types";

interface LapTimeDistributionChartProps {
  classification: ClassificationEntry[];
  metrics: ModelMetrics;
}

/**
 * Per-team lap-time distribution.  Real per-lap samples are not yet
 * exported by the Python pipeline (followup work); v1 ships a
 * symmetric synthetic distribution centred on the team's mean
 * predicted lap time with a width proportional to model uncertainty.
 * The chart is footnoted as "approximation" so consumers know.
 */
function buildTeams(classification: ClassificationEntry[]) {
  const map = new Map<string, { team: string; teamColor: string; samples: number[] }>();
  for (const c of classification) {
    if (!map.has(c.team)) map.set(c.team, { team: c.team, teamColor: c.teamColor || "#888", samples: [] });
    map.get(c.team)!.samples.push(c.predictedTime);
  }
  return Array.from(map.values())
    .map((t) => {
      const mean = t.samples.reduce((a, b) => a + b, 0) / t.samples.length;
      const min = Math.min(...t.samples);
      const max = Math.max(...t.samples);
      return { ...t, mean, min, max };
    })
    .sort((a, b) => a.mean - b.mean);
}

function DistInner({
  width,
  height,
  teams,
  uncertainty,
}: {
  width: number;
  height: number;
  teams: ReturnType<typeof buildTeams>;
  uncertainty: number;
}) {
  const margin = { top: 12, right: 20, bottom: 36, left: 88 };
  const innerW = Math.max(0, width - margin.left - margin.right);
  const innerH = Math.max(0, height - margin.top - margin.bottom);

  const fastest = Math.min(...teams.map((t) => t.min - uncertainty));
  const slowest = Math.max(...teams.map((t) => t.max + uncertainty));
  const xScale = scaleLinear({ domain: [fastest, slowest], range: [0, innerW], nice: true });
  const yScale = scaleBand({
    domain: teams.map((t) => t.team),
    range: [0, innerH],
    padding: 0.18,
  });

  return (
    <svg width={width} height={height}>
      <Group left={margin.left} top={margin.top}>
        {teams.map((t) => {
          const y = yScale(t.team) ?? 0;
          const bh = yScale.bandwidth();
          const cx = xScale(t.mean);
          const halfWidth = xScale(t.mean + uncertainty) - cx;
          const halfHeight = bh / 2;
          return (
            <g key={t.team}>
              {/* Outer envelope */}
              <ellipse
                cx={cx}
                cy={y + halfHeight}
                rx={Math.max(2, halfWidth * 1.4)}
                ry={halfHeight * 0.9}
                fill={t.teamColor}
                fillOpacity={0.15}
              />
              {/* IQR-ish band (tighter) */}
              <ellipse
                cx={cx}
                cy={y + halfHeight}
                rx={Math.max(1.5, halfWidth * 0.7)}
                ry={halfHeight * 0.6}
                fill={t.teamColor}
                fillOpacity={0.5}
              />
              {/* Mean spike */}
              <line
                x1={cx}
                x2={cx}
                y1={y + halfHeight - halfHeight * 0.55}
                y2={y + halfHeight + halfHeight * 0.55}
                stroke="var(--text-primary)"
                strokeWidth={2}
              />
              {/* Range whiskers */}
              <line
                x1={xScale(t.min)}
                x2={xScale(t.max)}
                y1={y + halfHeight}
                y2={y + halfHeight}
                stroke={t.teamColor}
                strokeWidth={1.5}
                strokeDasharray="2 3"
              />
            </g>
          );
        })}
        <AxisLeft
          scale={yScale}
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
        <AxisBottom
          scale={xScale}
          top={innerH}
          numTicks={6}
          stroke="var(--border)"
          tickStroke="var(--border)"
          tickFormat={(v) => `${(+v).toFixed(2)}s`}
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

export default function LapTimeDistributionChart({ classification, metrics }: LapTimeDistributionChartProps) {
  const teams = useMemo(() => buildTeams(classification), [classification]);
  const uncertainty = metrics.avgUncertainty ?? Math.max(0.1, metrics.maxSpread / 6);
  if (teams.length === 0) return null;
  return (
    <div>
      <div className="w-full" style={{ height: Math.max(280, 40 * teams.length + 60) }}>
        <ParentSize>
          {({ width, height }) => <DistInner width={width} height={height} teams={teams} uncertainty={uncertainty} />}
        </ParentSize>
      </div>
      <p className="text-[11px] mt-2 text-[color:var(--text-muted)] font-mono">
        Approximation — per-lap samples not yet exported. Width ∝ model uncertainty.
      </p>
    </div>
  );
}
