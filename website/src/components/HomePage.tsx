"use client";

/**
 * HomePage — Bugatti redesign.
 *
 * Pure black canvas. Hero band uses the featured round's track_map.webp as
 * the full-bleed photographic backdrop. Headlines in uppercase Saira Display
 * with wide tracking; body in EB Garamond serif; captions in JetBrains Mono.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { SeasonData, StandingsData, RoundData, SeasonTrackerData } from "@/types";
import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import { buttonVariants } from "@/components/ui/Button";
import HeroParallax from "@/components/home/HeroParallax";
import PodiumStage from "@/components/home/PodiumStage";
import RaceCardCarousel from "@/components/home/RaceCardCarousel";
import ChampionshipBento from "@/components/home/ChampionshipBento";
import ConstructorsConstellation from "@/components/home/ConstructorsConstellation";
import { ShimmerButton } from "@/components/magicui/shimmer-button";
import TeamColorBar from "@/components/ui/TeamColorBar";
import DriverPortrait from "@/components/standings/DriverPortrait";
import LoadingTire from "@/components/ui/LoadingTire";
import { resolveDriverHeadshot } from "@/lib/headshots";
import { fadeUp } from "@/lib/motion";
import {
  fetchSeasonData,
  fetchStandingsData,
  fetchRoundData,
  fetchSeasonTrackerData,
  formatDate,
  getCurrentRaceContext,
  getRoundLifecycle,
  getRoundStatusMeta,
} from "@/lib/data";

const TONE_TO_BADGE_VARIANT = {
  red: "negative",
  green: "positive",
  amber: "live",
  slate: "muted",
} as const;
type StatusTone = keyof typeof TONE_TO_BADGE_VARIANT;

const MS_PER_DAY = 24 * 60 * 60 * 1000;

function formatCountdown(targetIso: string, now: Date): string {
  const target = new Date(targetIso).getTime();
  const ms = target - now.getTime();
  if (ms <= 0) return "in progress";
  const days = Math.floor(ms / MS_PER_DAY);
  const hours = Math.floor((ms % MS_PER_DAY) / (60 * 60 * 1000));
  if (days > 0) return `in ${days}d ${hours}h`;
  return `in ${hours}h`;
}

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

export default function HomePage() {
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [standings, setStandings] = useState<StandingsData | null>(null);
  const [featuredRound, setFeaturedRound] = useState<RoundData | null>(null);
  const [latestRound, setLatestRound] = useState<RoundData | null>(null);
  const [tracker, setTracker] = useState<SeasonTrackerData | null>(null);
  const [accuracyPct, setAccuracyPct] = useState<number | null>(null);
  const [roundsGraded, setRoundsGraded] = useState<number>(0);

  useEffect(() => {
    fetchSeasonData().then(setSeason).catch(() => {});
    fetchSeasonTrackerData().then(setTracker).catch(() => {});
    fetchStandingsData()
      .then((s) => {
        setStandings(s);
        if (s.lastUpdatedRound > 0) {
          fetchRoundData(s.lastUpdatedRound).then(setLatestRound).catch(() => {});
        }
      })
      .catch(() => {});
    fetch(`${BASE_PATH}/data/gp_accuracy_report.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d?.overallAccuracy) return;
        setAccuracyPct(d.overallAccuracy.seasonAccuracyPct ?? null);
        setRoundsGraded(d.overallAccuracy.roundsWithActual ?? 0);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!season) return;
    const actuals = (tracker?.rounds || [])
      .filter((r) => r.hasActual)
      .map((r) => r.round);
    const ctx = getCurrentRaceContext(season, actuals);
    const target =
      ctx.liveRound ?? ctx.nextRound ?? ctx.latestPredictionRound ?? season.calendar[0];
    if (target) {
      fetchRoundData(target.round)
        .then(setFeaturedRound)
        .catch(() => {});
    }
  }, [season, tracker]);

  if (!season) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <LoadingTire label="Loading season data" />
      </div>
    );
  }

  const roundsWithActual = (tracker?.rounds || [])
    .filter((r) => r.hasActual)
    .map((r) => r.round);
  const ctx = getCurrentRaceContext(season, roundsWithActual);
  const featuredRace =
    ctx.liveRound ?? ctx.nextRound ?? ctx.latestPredictionRound ?? season.calendar[0];
  const featuredMeta = getRoundStatusMeta(
    getRoundLifecycle(
      featuredRace,
      season.completedRounds.includes(featuredRace.round),
      roundsWithActual.includes(featuredRace.round),
    ),
  );
  const featuredVariant: "live" | "positive" | "negative" | "muted" | "default" =
    TONE_TO_BADGE_VARIANT[featuredMeta.tone as StatusTone] ?? "default";
  const isPredictionView = featuredRound?.round === featuredRace.round;

  return (
    <div>
      <HeroParallax
        className="min-h-[60vh]"
        geometry={featuredRound?.circuitInfo?.geometry ?? null}
      >
        <div className="mx-auto max-w-6xl px-6 lg:px-10">
          <div className="flex flex-wrap items-center gap-4 mb-8">
            <Badge variant={featuredVariant}>{featuredMeta.label}</Badge>
            <span className="eyebrow">
              R{featuredRace.round} · {formatDate(featuredRace.date)} ·{" "}
              {formatCountdown(featuredRace.date, new Date())}
            </span>
          </div>

          <div className="flex items-start gap-6 mb-12">
            <CountryFlag country={featuredRace.country} size={64} />
            <div>
              <p className="eyebrow mb-3">Featured Grand Prix</p>
              <h1 className="display-xl [font-weight:700] text-balance">
                {featuredRace.name}
              </h1>
              <p className="body-md mt-4 max-w-2xl text-[color:var(--body-strong)]">
                {featuredRace.circuit} · {featuredMeta.description}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <Link href={`/race/${featuredRace.round}`}>
              <ShimmerButton
                background="var(--accent-f1-red)"
                shimmerColor="rgba(255,255,255,0.9)"
                borderRadius="9999px"
                className="button-label h-11 !px-7 !py-0 text-[13px]"
              >
                Open Race Report →
              </ShimmerButton>
            </Link>
            <Link href="/calendar" className={buttonVariants({ variant: "primary" })}>
              Full Calendar
            </Link>
            <Link href="/standings" className={buttonVariants({ variant: "ghost" })}>
              Standings
            </Link>
          </div>
        </div>
      </HeroParallax>

      {/* ── Race Card Carousel — F1.com Previous/Current/Next pattern ── */}
      <section className="mx-auto max-w-7xl px-6 lg:px-10 pt-12 sm:pt-16">
        <div className="flex items-baseline justify-between mb-6">
          <div>
            <p className="eyebrow mb-1">Race Window</p>
            <h2 className="display-md">This Weekend &amp; Beyond</h2>
          </div>
          <Link href="/calendar" className="link-bugatti button-label text-[11px]">
            Full Season →
          </Link>
        </div>
        <RaceCardCarousel
          season={season}
          roundsWithActual={roundsWithActual}
          mode="featured"
        />
      </section>

      <div className="mx-auto max-w-6xl px-6 lg:px-10">
        {isPredictionView && featuredRound && featuredRound.classification && (
          <motion.section
            className="section-bugatti"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
          >
            <div className="flex items-baseline justify-between mb-12">
              <div>
                <p className="eyebrow mb-2">Race Forecast · Next Grand Prix</p>
                <h2 className="display-md">
                  Predicted Podium — {featuredRace.name}
                </h2>
                <p className="body-md mt-4 max-w-2xl text-[color:var(--muted)]">
                  The model&apos;s top three picks for the upcoming{" "}
                  {featuredRace.country} race on {formatDate(featuredRace.date)}.
                  Projected race winner plus the two drivers most likely to share
                  the rostrum.
                </p>
              </div>
              <Link
                href={`/race/${featuredRace.round}`}
                className="link-bugatti button-label"
              >
                Full classification
              </Link>
            </div>

            <PodiumStage
              entries={featuredRound.classification.slice(0, 3).map((entry) => {
                const sim = entry as typeof entry & {
                  simulatorWinProbability?: number;
                };
                const winProb =
                  typeof sim.simulatorWinProbability === "number"
                    ? sim.simulatorWinProbability * 100
                    : entry.winProbability ?? 0;
                return {
                  driver: entry.driver,
                  driverFullName: entry.driverFullName,
                  team: entry.team,
                  teamColor: entry.teamColor,
                  winProbability: winProb,
                  predictedTime: entry.predictedTime,
                  gap: entry.gap,
                  headshotUrl: resolveDriverHeadshot(entry.driver, entry.headshotUrl),
                };
              })}
              immediate
            />
          </motion.section>
        )}

        {latestRound && latestRound.round !== featuredRace.round &&
          latestRound.actualResults &&
          Object.keys(latestRound.actualResults).length >= 3 && (() => {
            const predictedByDriver = new Map(
              (latestRound.classification ?? []).map((c) => [c.driver, c]),
            );
            const officialRows = Object.entries(latestRound.actualResults)
              .sort(([, a], [, b]) => a - b)
              .slice(0, 10)
              .map(([driver, position]) => {
                const pred = predictedByDriver.get(driver);
                return {
                  driver,
                  driverFullName: pred?.driverFullName,
                  position,
                  team: pred?.team ?? "—",
                  teamColor: pred?.teamColor ?? "var(--muted)",
                  headshotUrl: resolveDriverHeadshot(driver, pred?.headshotUrl),
                };
              });
            return (
              <motion.section
                className="section-bugatti"
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
              >
                <div className="flex items-baseline justify-between mb-8">
                  <div>
                    <p className="eyebrow mb-2">Race Control</p>
                    <h2 className="display-md">Latest Official Result</h2>
                    <p className="body-md mt-3 text-[color:var(--muted)]">
                      Round {latestRound.round} · {latestRound.name} ·{" "}
                      {formatDate(latestRound.date)}
                    </p>
                  </div>
                  <Link
                    href={`/race/${latestRound.round}`}
                    className="link-bugatti button-label"
                  >
                    Compare to prediction
                  </Link>
                </div>
                <div className="border border-[color:var(--hairline)] overflow-hidden">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-[color:var(--hairline)]">
                        <th className="px-4 py-3 text-left eyebrow">Pos</th>
                        <th className="px-2 py-3 text-left eyebrow">Driver</th>
                        <th className="px-2 py-3 text-left eyebrow hidden sm:table-cell">Team</th>
                        <th className="px-4 py-3 text-right eyebrow">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {officialRows.map((row) => (
                        <tr
                          key={row.driver}
                          className="border-b border-[color:var(--hairline)] last:border-b-0 transition-colors hover:bg-[color:var(--surface-card)]"
                          data-team={row.team}
                        >
                          <td className="px-4 py-3 font-mono font-tabular text-[color:var(--muted)] w-14">
                            {row.position === 1 && (
                              <span className="text-[color:var(--accent-podium-1)]">P1</span>
                            )}
                            {row.position === 2 && (
                              <span className="text-[color:var(--accent-podium-2)]">P2</span>
                            )}
                            {row.position === 3 && (
                              <span className="text-[color:var(--accent-podium-3)]">P3</span>
                            )}
                            {row.position > 3 && `P${row.position}`}
                          </td>
                          <td className="px-2 py-3">
                            <span className="inline-flex items-center gap-3">
                              <DriverPortrait
                                driver={row.driver}
                                driverFullName={row.driverFullName}
                                team={row.team}
                                teamColor={row.teamColor}
                                headshotUrl={row.headshotUrl}
                                size={32}
                              />
                              <TeamColorBar teamColor={row.teamColor} team={row.team} size="sm" />
                              <span className="title-sm">{row.driverFullName ?? row.driver}</span>
                            </span>
                          </td>
                          <td className="px-2 py-3 body-sm text-[color:var(--muted)] hidden sm:table-cell">
                            {row.team}
                          </td>
                          <td className="px-4 py-3 text-right font-mono font-tabular text-[color:var(--muted)]">
                            {row.position === 1 ? "WINNER" : "FINISHED"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.section>
            );
          })()}

        {standings && (
          <section className="section-bugatti">
            <div className="flex items-baseline justify-between mb-10">
              <div>
                <p className="eyebrow mb-2">Championship Snapshot</p>
                <h2 className="display-md">Where the season stands</h2>
              </div>
              <Link href="/standings" className="link-bugatti button-label text-[11px]">
                Open Standings →
              </Link>
            </div>
            <ChampionshipBento
              standings={standings}
              season={season}
              nextRace={
                season.calendar.find(
                  (r) => !season.completedRounds.includes(r.round),
                ) ?? null
              }
              accuracyPct={accuracyPct}
              roundsCompleted={roundsGraded}
            />
          </section>
        )}

        {standings && standings.constructors.length > 0 && (
          <section className="section-bugatti relative">
            <div className="text-center mb-10">
              <p className="eyebrow mb-2">Constellation</p>
              <h2 className="display-md">Eleven teams. One championship.</h2>
              <p className="body-md mt-3 max-w-xl mx-auto text-[color:var(--muted)]">
                Every constructor in orbit around the {season.season} title.
              </p>
            </div>
            <ConstructorsConstellation
              constructors={standings.constructors}
              seasonYear={season.season}
            />
          </section>
        )}

      </div>
    </div>
  );
}
