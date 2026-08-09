"use client";

/**
 * Win-probability chart (flagship) with uncertainty.
 *
 * Each driver gets a team-coloured win-probability bar (primary) PLUS a
 * companion "projected finish" range band that shows how wide the model's
 * finishing-position outlook is for that driver — the honest uncertainty
 * signal behind a single win number. A tight band hugging P1 reads as a
 * confident favourite; a wide band says the outcome is far from settled.
 *
 * Why the finish RANGE and not a probability whisker: the model publishes a
 * per-driver finishing-position interval (`finishRangeLow`/`High`) for every
 * driver in every round — that IS the exported uncertainty. The bootstrap
 * `predictionInterval*` fields are lap-time seconds (a different axis) and
 * are not populated in the shipped rounds, so they'd render nothing and
 * misstate the scale if plotted here; they stay in the hover detail only.
 *
 * Renders nothing when the round has no win-probability data (e.g. pre-quali
 * rounds where the model hasn't published a P(win) column yet).
 */
import { useMemo } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { resolveDriverHeadshot } from "@/lib/headshots";
import type { ClassificationEntry } from "@/types";

interface ChartRow {
  driver: string;
  driverFullName: string;
  team: string;
  teamColor: string;
  headshotUrl: string | null;
  winProbability: number;
  simulatorWinProbability: number | null;
  position: number;
  finishRangeLow: number | null;
  finishRangeHigh: number | null;
  predictionIntervalLow: number | null;
  predictionIntervalHigh: number | null;
  predictedTime: number;
}

function buildRows(classification: ClassificationEntry[]): ChartRow[] {
  return classification
    .map((c) => {
      const cTyped = c as ClassificationEntry & {
        simulatorWinProbability?: number;
        predictionIntervalLow?: number;
        predictionIntervalHigh?: number;
      };
      return {
        driver: cTyped.driver,
        driverFullName: cTyped.driverFullName,
        team: cTyped.team,
        teamColor: cTyped.teamColor || "#888",
        headshotUrl: cTyped.headshotUrl ?? null,
        winProbability: typeof cTyped.winProbability === "number" ? cTyped.winProbability : 0,
        simulatorWinProbability:
          typeof cTyped.simulatorWinProbability === "number"
            ? cTyped.simulatorWinProbability * 100
            : null,
        position: typeof cTyped.position === "number" ? cTyped.position : 0,
        finishRangeLow: typeof cTyped.finishRangeLow === "number" ? cTyped.finishRangeLow : null,
        finishRangeHigh: typeof cTyped.finishRangeHigh === "number" ? cTyped.finishRangeHigh : null,
        predictionIntervalLow:
          typeof cTyped.predictionIntervalLow === "number" ? cTyped.predictionIntervalLow : null,
        predictionIntervalHigh:
          typeof cTyped.predictionIntervalHigh === "number" ? cTyped.predictionIntervalHigh : null,
        predictedTime: typeof cTyped.predictedTime === "number" ? cTyped.predictedTime : 0,
      };
    })
    .filter((r) => r.winProbability > 0)
    .sort((a, b) => b.winProbability - a.winProbability)
    .slice(0, 12);
}

const GRID_COLS = "grid-cols-[minmax(78px,auto)_minmax(0,1fr)_minmax(116px,148px)]";

function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v));
}

export default function WinProbabilityChart({
  classification,
}: {
  classification: ClassificationEntry[];
}) {
  const rows = useMemo(() => buildRows(classification), [classification]);

  const { maxWin, posMax, posDenom, hasRange } = useMemo(() => {
    const maxWin = Math.max(1, ...rows.map((r) => r.winProbability));
    const posMax = Math.max(3, ...rows.map((r) => r.finishRangeHigh ?? r.position ?? 3));
    return {
      maxWin,
      posMax,
      posDenom: Math.max(1, posMax - 1),
      hasRange: rows.some((r) => r.finishRangeLow != null && r.finishRangeHigh != null),
    };
  }, [rows]);

  if (rows.length === 0) return null;

  const xPos = (pos: number) => ((clamp(pos, 1, posMax) - 1) / posDenom) * 100;

  return (
    <Card>
      <CardHeader className="gap-2">
        <Badge variant="live" className="self-start">
          Interactive
        </Badge>
        <CardTitle>Win Probability</CardTitle>
        <CardDescription>
          Win chances for the top {rows.length}. The bar is each driver&apos;s chance of victory;
          the band on the right is their projected finishing range — a tighter band means a more
          settled result.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <div className="min-w-[440px]">
            {/* Column headers */}
            <div className={`grid ${GRID_COLS} gap-3 sm:gap-4 pb-2 mb-1 border-b border-[color:var(--hairline)]`}>
              <span className="eyebrow">Driver</span>
              <span className="eyebrow">Win probability</span>
              <span className="eyebrow text-right sm:text-left">
                {hasRange ? "Projected finish" : ""}
              </span>
            </div>

            <div className="divide-y divide-[color:var(--hairline)]">
              {rows.map((row) => {
                const winW = (row.winProbability / maxWin) * 100;
                const low = row.finishRangeLow;
                const high = row.finishRangeHigh;
                const showBand = low != null && high != null;
                const bandLeft = showBand ? xPos(low) : 0;
                const bandRight = showBand ? xPos(high) : 0;
                const markerLeft = xPos(row.position || low || 1);

                const rangeText = showBand ? `P${low}–P${high}` : null;
                const paceText =
                  row.predictionIntervalLow != null && row.predictionIntervalHigh != null
                    ? ` · pace ${row.predictionIntervalLow.toFixed(2)}–${row.predictionIntervalHigh.toFixed(2)}s`
                    : "";
                const outlookText =
                  row.simulatorWinProbability != null
                    ? ` · race outlook ${row.simulatorWinProbability.toFixed(1)}%`
                    : "";
                const title =
                  `${row.driverFullName ?? row.driver} — ${row.winProbability.toFixed(1)}% to win` +
                  (rangeText ? ` · projected finish ${rangeText}` : "") +
                  outlookText +
                  ` · predicted lap ${row.predictedTime.toFixed(3)}s` +
                  paceText;

                return (
                  <div
                    key={row.driver}
                    title={title}
                    className={`grid ${GRID_COLS} gap-3 sm:gap-4 items-center py-2.5 transition-colors hover:bg-[color:var(--surface-elevated)]`}
                  >
                    {/* Driver identity */}
                    <div className="flex items-center gap-2 min-w-0">
                      <DriverPortrait
                        driver={row.driver}
                        driverFullName={row.driverFullName}
                        team={row.team}
                        teamColor={row.teamColor}
                        headshotUrl={resolveDriverHeadshot(row.driver, row.headshotUrl)}
                        size={24}
                      />
                      <span className="font-mono font-tabular text-sm text-[color:var(--ink)]">
                        {row.driver}
                      </span>
                    </div>

                    {/* Win-probability bar + tip label */}
                    <div className="flex items-center gap-3 min-w-0">
                      <div
                        className="relative flex-1 h-4 min-w-0"
                        style={{ background: "var(--hairline)" }}
                      >
                        <div
                          className="absolute inset-y-0 left-0 rounded-r-[3px]"
                          style={{ width: `${winW}%`, background: row.teamColor }}
                        />
                      </div>
                      <span className="w-12 shrink-0 text-right font-mono font-tabular text-sm text-[color:var(--ink)]">
                        {row.winProbability.toFixed(1)}%
                      </span>
                    </div>

                    {/* Projected-finish uncertainty band */}
                    <div className="min-w-0">
                      {showBand ? (
                        <>
                          <div
                            className="relative h-2 w-full"
                            style={{ background: "var(--hairline)" }}
                            role="img"
                            aria-label={`Projected finish range ${rangeText}, most likely P${row.position}`}
                          >
                            {/* faint range wash */}
                            <div
                              className="absolute inset-y-0"
                              style={{
                                left: `${bandLeft}%`,
                                width: `${Math.max(bandRight - bandLeft, 2)}%`,
                                background: `color-mix(in srgb, ${row.teamColor} 34%, transparent)`,
                              }}
                            />
                            {/* most-likely-position marker with surface ring */}
                            <span
                              className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
                              style={{
                                left: `${markerLeft}%`,
                                background: row.teamColor,
                                boxShadow: "0 0 0 2px var(--surface-card)",
                              }}
                            />
                          </div>
                          <span className="mt-1 block font-mono font-tabular text-[11px] text-[color:var(--muted)]">
                            {rangeText}
                          </span>
                        </>
                      ) : (
                        <span className="font-mono text-[11px] text-[color:var(--muted)]">—</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
