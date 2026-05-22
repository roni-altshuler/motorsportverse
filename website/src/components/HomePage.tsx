"use client";

/**
 * HomePage — cinematic race-weekend command center.
 *
 * Visual language: F1 broadcast HUD + paddock badge wall.  3-layer
 * parallax track silhouette behind the headline, RaceLightsGrid
 * announces predicted podium reveal, AnimatedNumber tickers run
 * win-prob counters when each card enters viewport.  Reduced-motion
 * collapses every effect to a calm static state.
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
import PaddockWall from "@/components/home/PaddockWall";
import RaceLightsGrid from "@/components/ui/RaceLightsGrid";
import TeamColorBar from "@/components/ui/TeamColorBar";
import LoadingTire from "@/components/ui/LoadingTire";
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

export default function HomePage() {
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [standings, setStandings] = useState<StandingsData | null>(null);
  const [featuredRound, setFeaturedRound] = useState<RoundData | null>(null);
  const [latestRound, setLatestRound] = useState<RoundData | null>(null);
  const [tracker, setTracker] = useState<SeasonTrackerData | null>(null);
  const [podiumRevealed, setPodiumRevealed] = useState(false);

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
  const favourite = featuredRound?.classification?.[0];
  const heroTeamColor = favourite?.teamColor ?? "var(--accent-live)";

  return (
    <div>
      {/* ━━━ CINEMATIC HERO ━━━ */}
      <HeroParallax
        teamColor={heroTeamColor}
        className="pt-10 pb-16 lg:pt-16 lg:pb-20"
      >
        <div className="mx-auto max-w-6xl px-6 lg:px-10 relative z-10">
          <div className="flex flex-wrap items-center gap-3 mb-6">
            <RaceLightsGrid
              panels={5}
              stepMs={650}
              holdMs={650}
              skipKey="home-lights-played"
              onSequenceComplete={() => setPodiumRevealed(true)}
            />
            <Badge variant={featuredVariant}>{featuredMeta.label}</Badge>
            <span className="text-sm text-[color:var(--text-muted)] font-mono">
              R{featuredRace.round} · {formatDate(featuredRace.date)} ·{" "}
              {formatCountdown(featuredRace.date, new Date())}
            </span>
          </div>

          <div className="flex items-start gap-4 mb-8">
            <CountryFlag country={featuredRace.country} size={80} />
            <div>
              <p className="hud-kicker mb-2">Featured Grand Prix</p>
              <h1 className="text-4xl sm:text-5xl lg:text-7xl font-black tracking-tighter leading-[1.02]">
                {featuredRace.name}
              </h1>
              <p className="mt-3 text-base sm:text-lg text-[color:var(--text-secondary)] max-w-2xl">
                {featuredRace.circuit} · {featuredMeta.description}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link
              href={`/race/${featuredRace.round}`}
              className={buttonVariants({ size: "lg", variant: "primary" })}
            >
              Open Race Report →
            </Link>
            <Link
              href="/calendar"
              className={buttonVariants({ size: "lg", variant: "secondary" })}
            >
              Full Calendar
            </Link>
            <Link
              href="/standings"
              className={buttonVariants({ size: "lg", variant: "ghost" })}
            >
              Standings
            </Link>
          </div>
        </div>
      </HeroParallax>

      <div className="mx-auto max-w-6xl px-6 lg:px-10">
        {/* ━━━ PREDICTED PODIUM (reveals when lights go out) ━━━ */}
        {isPredictionView && featuredRound && featuredRound.classification && (
          <motion.section
            className="pb-16 -mt-6"
            initial={{ opacity: 0 }}
            animate={podiumRevealed ? { opacity: 1 } : { opacity: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="flex items-baseline justify-between mb-6">
              <div>
                <p className="hud-kicker mb-1">Model Forecast</p>
                <h2 className="text-3xl font-black tracking-tight">
                  Predicted Podium
                </h2>
                <p className="mt-1 text-sm text-[color:var(--text-muted)] max-w-xl">
                  Projected race winner and the two drivers most likely to share the rostrum.
                </p>
              </div>
              <Link
                href={`/race/${featuredRace.round}`}
                className="text-sm font-semibold text-[color:var(--accent-live)] hover:underline"
              >
                Full classification →
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
                };
              })}
              immediate={!podiumRevealed ? false : true}
            />
          </motion.section>
        )}

        {/* ━━━ LATEST OFFICIAL RESULT (timing-screen style) ━━━ */}
        {latestRound && latestRound.round !== featuredRace.round && (
          <motion.section
            className="pb-16"
            variants={fadeUp}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
          >
            <div className="flex items-baseline justify-between mb-6">
              <div>
                <p className="hud-kicker mb-1">Race Control</p>
                <h2 className="text-2xl font-black tracking-tight">
                  Latest Official Result
                </h2>
                <p className="mt-1 text-sm text-[color:var(--text-muted)]">
                  Round {latestRound.round} · {latestRound.name} ·{" "}
                  {formatDate(latestRound.date)}
                </p>
              </div>
              <Link
                href={`/race/${latestRound.round}`}
                className="text-sm font-semibold text-[color:var(--accent-live)] hover:underline"
              >
                Compare to prediction →
              </Link>
            </div>
            <div className="hud-frame overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[color:var(--border)]">
                    <th className="px-4 py-3 text-left hud-kicker">Pos</th>
                    <th className="px-2 py-3 text-left hud-kicker">Driver</th>
                    <th className="px-2 py-3 text-left hud-kicker hidden sm:table-cell">Team</th>
                    <th className="px-4 py-3 text-right hud-kicker">Gap</th>
                  </tr>
                </thead>
                <tbody>
                  {(latestRound.classification ?? []).slice(0, 10).map((entry) => (
                    <tr
                      key={entry.driver}
                      className="border-b border-[color:var(--border)] last:border-b-0 transition-colors hover:bg-[color:var(--surface-elevated)]"
                      data-team={entry.team}
                    >
                      <td className="px-4 py-3 font-mono font-tabular text-[color:var(--text-muted)] w-14">
                        {entry.position === 1 && (
                          <span className="text-[color:var(--hud-champagne)] font-bold">P1</span>
                        )}
                        {entry.position === 2 && <span className="text-[color:var(--accent-podium-2)] font-bold">P2</span>}
                        {entry.position === 3 && <span className="text-[color:var(--accent-podium-3)] font-bold">P3</span>}
                        {entry.position > 3 && `P${entry.position}`}
                      </td>
                      <td className="px-2 py-3">
                        <span className="inline-flex items-center gap-3">
                          <TeamColorBar teamColor={entry.teamColor} team={entry.team} size="sm" />
                          <span className="font-semibold">{entry.driver}</span>
                        </span>
                      </td>
                      <td className="px-2 py-3 text-[color:var(--text-muted)] hidden sm:table-cell">
                        {entry.team}
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-tabular text-[color:var(--text-muted)]">
                        {entry.position === 1 ? "LEADER" : entry.gap}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.section>
        )}

        {/* ━━━ CHAMPIONSHIP PADDOCK WALL ━━━ */}
        {standings && (
          <section className="pb-16">
            <div className="grid gap-10 lg:gap-12 lg:grid-cols-2">
              <PaddockWall
                title="Drivers"
                href="/standings"
                entries={standings.drivers.slice(0, 5).map((d) => ({
                  name: d.driver,
                  subtitle: d.team,
                  team: d.team,
                  teamColor: d.teamColor || "var(--accent-live)",
                  points: d.points,
                }))}
                limit={5}
              />
              <PaddockWall
                title="Constructors"
                href="/standings"
                entries={standings.constructors.slice(0, 5).map((t) => ({
                  name: t.team,
                  team: t.team,
                  teamColor: t.teamColor || "var(--accent-live)",
                  points: t.points,
                }))}
                limit={5}
              />
            </div>
          </section>
        )}

      </div>
    </div>
  );
}
