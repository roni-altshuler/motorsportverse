"use client";

import type { CSSProperties } from "react";

import { cn } from "@/components/ui/cn";
import type { CircuitGeometry } from "@/types";

interface CircuitMapProps {
  geometry: CircuitGeometry;
  /** Render corner number badges on top of the track. Default true. */
  showCorners?: boolean;
  /** Render DRS zone underlay (where geometry includes drsZones). */
  showDrsZones?: boolean;
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
 * Renders a circuit as a clean monochrome SVG outline.
 *
 * Geometry comes from ``generate_circuit_svg.py``, which extracts the
 * fastest-lap telemetry from FastF1 and stores a Ramer-Douglas-Peucker
 * simplified path in ``circuitInfo.geometry`` of each round JSON.
 *
 * Scales to any container via ``preserveAspectRatio="xMidYMid meet"``.
 * No animation, no GSAP, no framer-motion — pure SVG with CSS hover.
 */
export default function CircuitMap({
  geometry,
  showCorners = true,
  showDrsZones = true,
  accentColor = "var(--ink)",
  strokeWidth = 2,
  padding = 24,
  className,
  style,
}: CircuitMapProps) {
  if (!geometry || !geometry.path) return null;

  // Expand the viewBox by `padding` so stroke + corner badges don't clip.
  const [vx, vy, vw, vh] = geometry.viewBox.split(/\s+/).map(Number);
  const paddedViewBox = `${vx - padding} ${vy - padding} ${vw + 2 * padding} ${
    vh + 2 * padding
  }`;

  return (
    <svg
      viewBox={paddedViewBox}
      preserveAspectRatio="xMidYMid meet"
      className={cn("h-full w-full select-none", className)}
      style={style}
      role="img"
      aria-label="Circuit layout"
    >
      {/* DRS underlay — sits beneath the main stroke. Only renders when
       *  generate_circuit_svg.py populates drsZones. */}
      {showDrsZones && geometry.drsZones.length > 0 && (
        <path
          d={geometry.path}
          fill="none"
          stroke="var(--accent-f1-red)"
          strokeOpacity={0.35}
          strokeWidth={strokeWidth * 2.5}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      )}
      {/* Main track stroke. */}
      <path
        d={geometry.path}
        fill="none"
        stroke={accentColor}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      {/* Corner badges. */}
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
              fill="var(--surface-card)"
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
