"use client";

import { Badge } from "@/components/ui/Badge";
import HeroCountdown from "@/components/home/HeroCountdown";
import { forecastState, type CoverageRound } from "@/lib/resultCoverage";
import { useCoverageClock } from "@/lib/useCoverageClock";

export default function SnapshotForecastStatus({ round, asOf, description }: {
  round: CoverageRound;
  asOf: string;
  description: string;
}) {
  const now = useCoverageClock(asOf);
  const state = forecastState(round, now);
  const date = round.featureDate || round.raceDate;
  return (
    <div className="flex flex-wrap items-center gap-4 mb-6" aria-label="Snapshot forecast status">
      <Badge variant="default">{state === "past-due" ? "Past-due forecast" : "Snapshot forecast"}</Badge>
      <span className="eyebrow">
        {description}
        {date && state === "scheduled" ? <> · <HeroCountdown targetDate={date} /></> : null}
      </span>
    </div>
  );
}
