"use client";

/**
 * KeyFactorsPanel — "why the model ranks them" explainability panel for the
 * predicted podium trio. One column per driver: identity row + compact
 * factor-weight bars sourced from `classification[*].keyFactors`.
 *
 * Graceful degradation: when no driver in the trio carries keyFactors (older
 * round JSONs), the panel renders a quiet HUD-styled empty state instead of
 * vanishing — the surface is part of the product, the data arrives with the
 * next model run.
 */
import HUDPanel from "@/components/ui/HUDPanel";
import TeamColorBar from "@/components/ui/TeamColorBar";
import DriverPortrait from "@/components/standings/DriverPortrait";
import KeyFactorBars from "@/components/race-detail/KeyFactorBars";
import { resolveDriverHeadshot } from "@/lib/headshots";
import type { ClassificationEntry } from "@/types";

interface KeyFactorsPanelProps {
  classification: ClassificationEntry[];
  /** Graded rounds have locked predictions — factor data will never arrive
   * for old rounds, so the empty state would be a false promise. Hide the
   * panel instead of teasing data that is not coming. */
  graded?: boolean;
}

export default function KeyFactorsPanel({ classification, graded }: KeyFactorsPanelProps) {
  const trio = classification.slice(0, 3);
  if (trio.length === 0) return null;
  const hasFactors = trio.some((entry) => (entry.keyFactors?.length ?? 0) > 0);
  if (!hasFactors && graded) return null;

  return (
    <div className="mb-8">
      <HUDPanel kicker="Model Forecast" title="Why the model ranks them" bodyClassName="p-5 sm:p-6">
        {hasFactors ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-0 md:divide-x md:divide-[color:var(--hairline)] divide-y md:divide-y-0 divide-[color:var(--hairline)]">
            {trio.map((entry) => (
              <div
                key={`factors-${entry.driver}`}
                className="py-5 first:pt-0 last:pb-0 md:py-0 md:px-6 md:first:pl-0 md:last:pr-0"
              >
                <div className="flex items-center gap-3 mb-4">
                  <DriverPortrait
                    driver={entry.driver}
                    driverFullName={entry.driverFullName}
                    team={entry.team}
                    teamColor={entry.teamColor}
                    headshotUrl={resolveDriverHeadshot(entry.driver, entry.headshotUrl)}
                    size={40}
                  />
                  <div className="min-w-0">
                    <p className="font-mono uppercase tracking-[0.18em] text-[12px] text-[color:var(--muted)]">
                      P{entry.position}
                    </p>
                    <p className="title-sm truncate">{entry.driverFullName ?? entry.driver}</p>
                    <div className="mt-1">
                      <TeamColorBar
                        teamColor={entry.teamColor}
                        team={entry.team}
                        variant="solid"
                        size="sm"
                      />
                    </div>
                  </div>
                </div>
                {entry.keyFactors && entry.keyFactors.length > 0 ? (
                  <KeyFactorBars factors={entry.keyFactors} />
                ) : (
                  <p className="body-sm text-[color:var(--muted)]">
                    No factor breakdown for this driver yet.
                  </p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="py-6 text-center">
            <p className="eyebrow mb-3">Awaiting factor data</p>
            <p className="body-sm text-[color:var(--muted)] max-w-xl mx-auto">
              Per-driver factor breakdowns — qualifying pace, recent form, race strategy, weather
              exposure — publish with the next model run for this round.
            </p>
          </div>
        )}
      </HUDPanel>
    </div>
  );
}
