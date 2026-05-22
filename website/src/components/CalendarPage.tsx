"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { SeasonData, SeasonTrackerData } from "@/types";
import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import HUDPanel from "@/components/ui/HUDPanel";
import AnimatedNumber from "@/components/ui/AnimatedNumber";
import LoadingTire from "@/components/ui/LoadingTire";
import SeasonRibbon from "@/components/calendar/SeasonRibbon";
import { fadeUp } from "@/lib/motion";
import { fetchSeasonData, fetchSeasonTrackerData, formatDate, getRoundLifecycle, getRoundStatusMeta } from "@/lib/data";

const TONE_TO_BADGE_VARIANT = {
  red: "negative",
  green: "positive",
  amber: "live",
  slate: "muted",
} as const;
type StatusTone = keyof typeof TONE_TO_BADGE_VARIANT;

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

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      {/* Header */}
      <div className="mb-6">
        <p className="hud-kicker mb-2">{season.season} Championship</p>
        <h1 className="text-4xl sm:text-5xl font-black tracking-tighter mb-2">Season Calendar</h1>
        <p className="text-[color:var(--text-muted)]">
          {season.totalRounds} Grand Prix · {completedCount} forecasts published · {officialCount} official result{officialCount !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Season Ribbon */}
      <SeasonRibbon
        calendar={season.calendar}
        completedRounds={season.completedRounds}
        actualRounds={actualSet}
      />

      {/* HUD KPI strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
        <HUDPanel kicker="Forecast Coverage" intensity="subtle">
          <div className="flex items-baseline gap-2">
            <AnimatedNumber value={completedCount} variant="huge" />
            <span className="text-lg text-[color:var(--text-muted)]">/ {season.totalRounds}</span>
          </div>
          <p className="text-xs text-[color:var(--text-muted)] mt-2">
            Rounds with model predictions published.
          </p>
        </HUDPanel>
        <HUDPanel kicker="Official Results" intensity="subtle">
          <AnimatedNumber value={officialCount} variant="huge" className="text-[color:var(--accent-positive)]" />
          <p className="text-xs text-[color:var(--text-muted)] mt-2">
            Predictions now compared against real outcomes.
          </p>
        </HUDPanel>
        <HUDPanel kicker="Weekend Live" intensity="subtle">
          <AnimatedNumber
            value={liveCount}
            variant="huge"
            className={liveCount > 0 ? "text-[color:var(--accent-live)]" : ""}
          />
          <p className="text-xs text-[color:var(--text-muted)] mt-2">
            Grand Prix weekend currently in progress.
          </p>
        </HUDPanel>
      </div>

      {/* Race List */}
      <div className="space-y-3">
        {season.calendar.map((race, index) => {
          const hasPrediction = season.completedRounds.includes(race.round);
          const hasActual = actualSet.has(race.round);
          const lifecycle = getRoundLifecycle(race, hasPrediction, hasActual);
          const statusMeta = getRoundStatusMeta(lifecycle);
          const variant = TONE_TO_BADGE_VARIANT[statusMeta.tone as StatusTone] ?? "default";

          return (
            <motion.div
              key={race.round}
              custom={index}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: "0px 0px -8% 0px" }}
              variants={fadeUp}
            >
              <Link
                href={`/race/${race.round}`}
                className="card-glow flex items-center gap-4 sm:gap-6 px-5 py-4 rounded-xl group transition-all"
              >
                {/* Round number */}
                <div className="text-center shrink-0 w-12">
                  <span
                    className="text-3xl font-black stat-number font-tabular"
                    style={{
                      color: hasActual
                        ? "var(--accent-positive)"
                        : hasPrediction
                        ? "var(--accent-live)"
                        : "var(--text-muted)",
                    }}
                  >
                    {race.round}
                  </span>
                </div>

                {/* Flag + Name */}
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <CountryFlag country={race.country} size={32} className="shrink-0" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3
                        className={`font-bold truncate transition-colors ${hasPrediction ? "group-hover:text-[color:var(--accent-live)]" : ""}`}
                      >
                        {race.name}
                      </h3>
                      <Badge variant={variant}>{statusMeta.shortLabel}</Badge>
                      {race.sprint && <Badge variant="info">Sprint</Badge>}
                    </div>
                    <p className="text-sm truncate text-[color:var(--text-muted)]">
                      {race.circuit} ·{" "}
                      {race.expectedStops === 1 ? "1 stop" : `${race.expectedStops} stops`} ·{" "}
                      {race.drsZones} DRS
                    </p>
                  </div>
                </div>

                {/* Circuit characteristics */}
                <div className="hidden lg:flex items-center gap-6 shrink-0">
                  <div className="text-center w-14">
                    <p className="hud-kicker">Laps</p>
                    <p className="font-bold font-mono text-sm">{race.laps}</p>
                  </div>
                  <div className="text-center w-16">
                    <p className="hud-kicker">Length</p>
                    <p className="font-bold font-mono text-sm">{race.circuitKm} km</p>
                  </div>
                  <div className="w-20">
                    <p className="hud-kicker mb-1">Tyre Deg</p>
                    <div className="progress-bar">
                      <div
                        className="progress-bar-fill"
                        style={{
                          width: `${race.tyreDeg * 100}%`,
                          background:
                            race.tyreDeg > 0.6
                              ? "var(--accent-live)"
                              : race.tyreDeg > 0.4
                              ? "var(--hud-yellow)"
                              : "var(--accent-positive)",
                        }}
                      />
                    </div>
                  </div>
                  <div className="w-20">
                    <p className="hud-kicker mb-1">Overtake</p>
                    <div className="progress-bar">
                      <div
                        className="progress-bar-fill"
                        style={{ width: `${race.overtaking * 100}%`, background: "var(--accent-info)" }}
                      />
                    </div>
                  </div>
                </div>

                {/* Date */}
                <div className="text-right shrink-0 w-28">
                  <p className="text-sm font-medium font-mono">{formatDate(race.date)}</p>
                  <p
                    className="text-xs font-semibold mt-0.5"
                    style={{
                      color:
                        statusMeta.tone === "green"
                          ? "var(--accent-positive)"
                          : statusMeta.tone === "red"
                          ? "var(--accent-live)"
                          : statusMeta.tone === "amber"
                          ? "var(--hud-yellow)"
                          : "var(--text-muted)",
                    }}
                  >
                    {statusMeta.label}
                  </p>
                </div>
              </Link>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
