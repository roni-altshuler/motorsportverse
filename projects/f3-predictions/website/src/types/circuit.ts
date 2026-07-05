// Circuit outline geometry — the F1 fastest-lap telemetry path, reused for F3
// (F3 races the same circuits). Shipped in public/data/circuits.json, keyed by
// the calendar venue key (e.g. "monaco", "silverstone").

export interface CircuitGeometry {
  /** SVG viewBox string, e.g. "0 0 1000 1000". */
  viewBox: string;
  /** Closed SVG path data, e.g. "M x0 y0 L x1 y1 …Z". */
  path: string;
  corners: Array<{
    number: number;
    x: number;
    y: number;
    name?: string | null;
  }>;
  drsZones?: Array<{ startIdx: number; endIdx: number }>;
  metresPerUnit?: number;
  source?: string;
  generatedAt?: string;
}

export type CircuitLibrary = Record<string, CircuitGeometry>;
