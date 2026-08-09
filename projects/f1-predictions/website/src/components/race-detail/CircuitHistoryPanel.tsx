"use client";

/**
 * CircuitHistoryPanel — "This circuit" mini-panel for the race-detail circuit
 * section. Renders recent race winners plus two plain-language context stats
 * (pole-to-win conversion, safety-car frequency) for the venue.
 *
 * Data comes from the optional `circuit_history.json` export, indexed upstream
 * by the round's `gpKey`. Everything here is null-tolerant: a missing entry, an
 * empty winners list, or an absent stat renders nothing rather than fabricating
 * a value. The panel hides entirely when there is nothing worth showing.
 */

import HUDPanel from "@/components/ui/HUDPanel";

export interface CircuitHistoryWinner {
  season: number;
  driver: string;
  constructor?: string;
}

export interface CircuitHistoryEntry {
  circuit: string;
  pastWinners: CircuitHistoryWinner[];
  poleToWinPct: number | null;
  safetyCarRate: number | null;
}

/** The whole `circuit_history.json` file — an object keyed by circuit id. */
export type CircuitHistoryData = Record<string, CircuitHistoryEntry>;

interface CircuitHistoryPanelProps {
  entry: CircuitHistoryEntry | null;
  /** Fallback circuit name for the winners heading (entry.circuit wins). */
  circuitName?: string;
}

/**
 * Normalise a rate/percentage to a 0–100 display value. The producer may emit
 * either a fraction (0.63) or an already-scaled percentage (63); values at or
 * below 1 are treated as fractions. Real pole-to-win / safety-car rates are
 * never a genuine 1%, so this heuristic is unambiguous in practice.
 */
function toPercent(value: number): number {
  return Math.round(value <= 1 ? value * 100 : value);
}

export default function CircuitHistoryPanel({
  entry,
  circuitName,
}: CircuitHistoryPanelProps) {
  if (!entry) return null;

  const winners = Array.isArray(entry.pastWinners)
    ? entry.pastWinners
        .filter(
          (w): w is CircuitHistoryWinner =>
            !!w && typeof w.season === "number" && typeof w.driver === "string" && !!w.driver,
        )
        .slice()
        .sort((a, b) => b.season - a.season)
    : [];

  const hasPole = typeof entry.poleToWinPct === "number" && Number.isFinite(entry.poleToWinPct);
  const hasSc = typeof entry.safetyCarRate === "number" && Number.isFinite(entry.safetyCarRate);

  // Nothing worth showing — hide rather than render an empty shell.
  if (winners.length === 0 && !hasPole && !hasSc) return null;

  const venue = entry.circuit || circuitName || "";

  return (
    <HUDPanel kicker="History" title="This circuit" bodyClassName="p-5 sm:p-6">
      <div className="space-y-6">
        {(hasPole || hasSc) && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {hasPole && (
              <div className="metric-card">
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Pole converted to a win
                </p>
                <p className="text-2xl font-black" style={{ color: "var(--text)" }}>
                  {toPercent(entry.poleToWinPct as number)}%
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                  How often the driver starting on pole has gone on to win here.
                </p>
              </div>
            )}
            {hasSc && (
              <div className="metric-card">
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Safety car appeared
                </p>
                <p className="text-2xl font-black" style={{ color: "var(--text)" }}>
                  {toPercent(entry.safetyCarRate as number)}%
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                  Share of recent races here that saw at least one safety car.
                </p>
              </div>
            )}
          </div>
        )}

        {winners.length > 0 && (
          <div>
            <p
              className="text-xs font-bold uppercase tracking-wider mb-3"
              style={{ color: "var(--text-muted)" }}
            >
              Recent winners{venue ? ` at ${venue}` : ""}
            </p>
            <div className="flex flex-wrap gap-2">
              {winners.slice(0, 6).map((w) => (
                <span
                  key={`${w.season}-${w.driver}`}
                  className="inline-flex items-center gap-2 rounded-full border border-[color:var(--hairline)] bg-[color:var(--surface-card)] px-3 py-1.5"
                >
                  <span className="font-mono text-xs" style={{ color: "var(--text-muted)" }}>
                    {w.season}
                  </span>
                  <span className="font-bold text-sm" style={{ color: "var(--text)" }}>
                    {w.driver}
                  </span>
                  {w.constructor && (
                    <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                      {w.constructor}
                    </span>
                  )}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </HUDPanel>
  );
}
