"use client";

import type { CSSProperties } from "react";

import { cn } from "@/components/ui/cn";
import type { CircuitGeometry } from "@/types/circuit";

interface CircuitMapProps {
  geometry: CircuitGeometry;
  /** Render corner number badges on top of the track. Default true. */
  showCorners?: boolean;
  /** Stroke colour for the main track line. Default `var(--ink)`. */
  accentColor?: string;
  /** Stroke width in viewBox units. Default 2. */
  strokeWidth?: number;
  /** Padding inside the SVG viewBox (in viewBox units). Default 24. */
  padding?: number;
  className?: string;
  style?: CSSProperties;
}

/**
 * Renders a circuit as a clean monochrome SVG outline — the same track-map
 * vocabulary as the RaceIQ F1 flagship. Geometry is the F1 fastest-lap telemetry
 * outline (shared circuits), shipped in `public/data/circuits.json`.
 */
export default function CircuitMap({
  geometry,
  showCorners = true,
  accentColor = "var(--ink)",
  strokeWidth = 2,
  padding = 24,
  className,
  style,
}: CircuitMapProps) {
  if (!geometry || !geometry.path) return null;

  const [vx, vy, vw, vh] = geometry.viewBox.split(/\s+/).map(Number);
  const paddedViewBox = `${vx - padding} ${vy - padding} ${vw + 2 * padding} ${vh + 2 * padding}`;

  return (
    <svg
      viewBox={paddedViewBox}
      preserveAspectRatio="xMidYMid meet"
      className={cn("h-full w-full select-none", className)}
      style={style}
      role="img"
      aria-label="Circuit layout"
    >
      <path
        d={geometry.path}
        fill="none"
        stroke={accentColor}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      {showCorners &&
        geometry.corners.map((corner) => (
          <g
            key={`corner-${corner.number}`}
            className="opacity-70 transition-opacity hover:opacity-100"
          >
            <circle
              cx={corner.x}
              cy={corner.y}
              r={11}
              fill="var(--surface-2)"
              stroke={accentColor}
              strokeWidth={1}
            />
            <text
              x={corner.x}
              y={corner.y}
              textAnchor="middle"
              dominantBaseline="central"
              fontFamily="var(--font-mono, monospace)"
              fontSize={12}
              fill={accentColor}
              style={{ pointerEvents: "none", userSelect: "none" }}
            >
              {corner.number}
            </text>
            {corner.name ? <title>{`T${corner.number} — ${corner.name}`}</title> : null}
          </g>
        ))}
    </svg>
  );
}
