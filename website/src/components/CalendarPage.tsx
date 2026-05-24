"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { SeasonData, SeasonTrackerData } from "@/types";
import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import LoadingTire from "@/components/ui/LoadingTire";
import SeasonRibbon from "@/components/calendar/SeasonRibbon";
import RaceCardCarousel from "@/components/home/RaceCardCarousel";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { fetchSeasonData, fetchSeasonTrackerData, formatDate, getRoundLifecycle, getRoundStatusMeta } from "@/lib/data";

const TONE_TO_BADGE_VARIANT = {
  red: "negative",
  green: "positive",
  amber: "live",
  slate: "muted",
} as const;
type StatusTone = keyof typeof TONE_TO_BADGE_VARIANT;

const LIFECYCLE_BORDER: Record<string, string> = {
  "live-weekend": "var(--accent-f1-red)",
  "awaiting-results": "var(--accent-f1-red)",
  "official": "var(--success)",
  "prediction-ready": "var(--accent-podium-1)",
  "upcoming": "var(--hairline-strong)",
  "postponed": "var(--warning)",
};

export default function CalendarPage() {
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [tracker, setTracker] = useState<SeasonTrackerData | null>(null);

  useEffect(() => {
    fetchSeasonData().then(setSeason).catch(console.error);
    fetchSeasonTrackerData().then(setTracker).catch(() => {});
  }, []);

  if (!season) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <LoadingTire label="Loading calendar" />
      </div>
    );
  }

  const completedCount = season.completedRounds.length;
  const actualSet = new Set((tracker?.rounds || []).filter((round) => round.hasActual).map((round) => round.round));
  const officialCount = actualSet.size;
  const liveCount = season.calendar.filter(
    (race) =>
      getRoundLifecycle(race, season.completedRounds.includes(race.round), actualSet.has(race.round)) === "live-weekend",
  ).length;
  const roundsWithActual = Array.from(actualSet);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 section-bugatti">
      <div className="mb-12">
        <p className="eyebrow mb-4">{season.season} Championship</p>
        <h1 className="display-xl [font-weight:700] mb-4">Season Calendar</h1>
        <p className="body-md text-[color:var(--muted)]">
          {season.totalRounds} Grand Prix · {completedCount} forecasts published · {officialCount} official result{officialCount !== 1 ? "s" : ""}
        </p>
      </div>

      {/* ── Photographic carousel — full season ── */}
      <div className="mb-16">
        <div className="flex items-baseline justify-between mb-6">
          <div>
            <p className="eyebrow mb-1">Season Window</p>
            <h2 className="display-md">All 22 Grand Prix in photography</h2>
          </div>
        </div>
        <RaceCardCarousel
          season={season}
          roundsWithActual={roundsWithActual}
          mode="full-season"
        />
      </div>

      <SeasonRibbon
        calendar={season.calendar}
        completedRounds={season.completedRounds}
        actualRounds={actualSet}
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-0 mb-16 mt-12 hairline-divider-top">
        <div className="row-spec sm:border-b-0 sm:pr-8 sm:border-r border-[color:var(--hairline)]">
          <p className="eyebrow mb-3">Forecast Coverage</p>
          <div className="flex items-baseline gap-2">
            <span className="display-xl !text-[64px] !leading-none [font-weight:700] text-[color:var(--ink)]">
              <NumberTicker value={completedCount} />
            </span>
            <span className="body-md text-[color:var(--muted)]">/ {season.totalRounds}</span>
          </div>
          <p className="body-sm text-[color:var(--muted)] mt-3">
            Rounds with model predictions published.
          </p>
        </div>
        <div className="row-spec sm:border-b-0 sm:px-8 sm:border-r border-[color:var(--hairline)]">
          <p className="eyebrow mb-3">Official Results</p>
          <span className="display-xl !text-[64px] !leading-none [font-weight:700] text-[color:var(--success)]">
            <NumberTicker value={officialCount} />
          </span>
          <p className="body-sm text-[color:var(--muted)] mt-3">
            Predictions now compared against real outcomes.
          </p>
        </div>
        <div className="row-spec sm:border-b-0 sm:pl-8">
          <p className="eyebrow mb-3">Weekend Live</p>
          <span
            className="display-xl !text-[64px] !leading-none [font-weight:700]"
            style={{ color: liveCount > 0 ? "var(--accent-f1-red)" : "var(--ink)" }}
          >
            <NumberTicker value={liveCount} />
          </span>
          <p className="body-sm text-[color:var(--muted)] mt-3">
            Grand Prix weekend currently in progress.
          </p>
        </div>
      </div>

      <div className="hairline-divider-top">
        {season.calendar.map((race) => {
          const hasPrediction = season.completedRounds.includes(race.round);
          const hasActual = actualSet.has(race.round);
          const lifecycle = getRoundLifecycle(race, hasPrediction, hasActual);
          const statusMeta = getRoundStatusMeta(lifecycle);
          const variant = TONE_TO_BADGE_VARIANT[statusMeta.tone as StatusTone] ?? "default";
          const leftBorder = LIFECYCLE_BORDER[lifecycle] ?? "var(--hairline-strong)";

          return (
            <Link
              key={race.round}
              href={`/race/${race.round}`}
              className="row-spec flex items-center gap-6 group transition-colors hover:bg-[color:var(--surface-card)] border-l-2"
              style={{ borderLeftColor: "transparent" }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderLeftColor = leftBorder;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderLeftColor = "transparent";
              }}
            >
              <div className="text-center shrink-0 w-12 pl-3">
                <span className="font-mono font-tabular text-[20px] tracking-[0.05em] text-[color:var(--muted)]">
                  {String(race.round).padStart(2, "0")}
                </span>
              </div>

              <div className="flex items-center gap-3 flex-1 min-w-0">
                <CountryFlag country={race.country} size={32} className="shrink-0" />
                <div className="min-w-0">
                  <div className="flex items-center gap-3 flex-wrap mb-1">
                    <h3 className="title-md truncate group-hover:text-[color:var(--ink)] transition-colors">
                      {race.name}
                    </h3>
                    <Badge variant={variant}>{statusMeta.shortLabel}</Badge>
                    {race.sprint && <Badge variant="info">Sprint</Badge>}
                  </div>
                  <p className="eyebrow truncate">
                    {race.circuit} · {race.expectedStops === 1 ? "1 stop" : `${race.expectedStops} stops`} · {race.drsZones} DRS
                  </p>
                </div>
              </div>

              <div className="hidden lg:flex items-center gap-8 shrink-0">
                <div className="text-center w-14">
                  <p className="eyebrow">Laps</p>
                  <p className="title-sm font-mono mt-1">{race.laps}</p>
                </div>
                <div className="text-center w-20">
                  <p className="eyebrow">Length</p>
                  <p className="title-sm font-mono mt-1">{race.circuitKm} km</p>
                </div>
              </div>

              <div className="text-right shrink-0 w-32">
                <p className="body-sm font-mono">{formatDate(race.date)}</p>
                <p className="eyebrow mt-1">
                  {statusMeta.label}
                </p>
              </div>

              <span className="text-[color:var(--muted)] shrink-0 group-hover:text-[color:var(--ink)] transition-colors pr-2" aria-hidden>
                →
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
