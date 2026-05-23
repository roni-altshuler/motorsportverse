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
import PaddockWall from "@/components/home/PaddockWall";
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

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

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

function trackMapPath(round: number): string {
  return `${BASE_PATH}/visualizations/round_${String(round).padStart(2, "0")}/track_map.webp`;
}

export default function HomePage() {
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [standings, setStandings] = useState<StandingsData | null>(null);
  const [featuredRound, setFeaturedRound] = useState<RoundData | null>(null);
  const [latestRound, setLatestRound] = useState<RoundData | null>(null);
  const [tracker, setTracker] = useState<SeasonTrackerData | null>(null);

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

  return (
    <div>
      <HeroParallax
        trackImage={trackMapPath(featuredRace.round)}
        className="min-h-[60vh]"
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
              <h1 className="display-xl">{featuredRace.name}</h1>
              <p className="body-md mt-4 max-w-2xl text-[color:var(--body-strong)]">
                {featuredRace.circuit} · {featuredMeta.description}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-4">
            <Link
              href={`/race/${featuredRace.round}`}
              className={buttonVariants({ variant: "primary" })}
            >
              Open Race Report
            </Link>
            <Link
              href="/calendar"
              className={buttonVariants({ variant: "primary" })}
            >
              Full Calendar
            </Link>
            <Link
              href="/standings"
              className={buttonVariants({ variant: "ghost" })}
            >
              Standings
            </Link>
          </div>
        </div>
      </HeroParallax>

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
                <p className="eyebrow mb-2">Model Forecast</p>
                <h2 className="display-md">Predicted Podium</h2>
                <p className="body-md mt-4 max-w-xl text-[color:var(--muted)]">
                  Projected race winner and the two drivers most likely to share the rostrum.
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
                };
              })}
              immediate
            />
          </motion.section>
        )}

        {latestRound && latestRound.round !== featuredRace.round && (
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
                  Round {latestRound.round} · {latestRound.name} · {formatDate(latestRound.date)}
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
                    <th className="px-4 py-3 text-right eyebrow">Gap</th>
                  </tr>
                </thead>
                <tbody>
                  {(latestRound.classification ?? []).slice(0, 10).map((entry) => (
                    <tr
                      key={entry.driver}
                      className="border-b border-[color:var(--hairline)] last:border-b-0 transition-colors hover:bg-[color:var(--surface-card)]"
                      data-team={entry.team}
                    >
                      <td className="px-4 py-3 font-mono font-tabular text-[color:var(--muted)] w-14">
                        {entry.position === 1 && (
                          <span className="text-[color:var(--accent-podium-1)]">P1</span>
                        )}
                        {entry.position === 2 && (
                          <span className="text-[color:var(--accent-podium-2)]">P2</span>
                        )}
                        {entry.position === 3 && (
                          <span className="text-[color:var(--accent-podium-3)]">P3</span>
                        )}
                        {entry.position > 3 && `P${entry.position}`}
                      </td>
                      <td className="px-2 py-3">
                        <span className="inline-flex items-center gap-3">
                          <TeamColorBar teamColor={entry.teamColor} team={entry.team} size="sm" />
                          <span className="title-sm">{entry.driver}</span>
                        </span>
                      </td>
                      <td className="px-2 py-3 body-sm text-[color:var(--muted)] hidden sm:table-cell">
                        {entry.team}
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-tabular text-[color:var(--muted)]">
                        {entry.position === 1 ? "LEADER" : entry.gap}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.section>
        )}

        {standings && (
          <section className="section-bugatti">
            <div className="grid gap-16 lg:grid-cols-2">
              <PaddockWall
                title="Drivers"
                href="/standings"
                entries={standings.drivers.slice(0, 6).map((d) => ({
                  name: d.driver,
                  subtitle: d.team,
                  team: d.team,
                  teamColor: d.teamColor || "var(--ink)",
                  points: d.points,
                }))}
                limit={6}
              />
              <PaddockWall
                title="Constructors"
                href="/standings"
                entries={standings.constructors.slice(0, 6).map((t) => ({
                  name: t.team,
                  team: t.team,
                  teamColor: t.teamColor || "var(--ink)",
                  points: t.points,
                }))}
                limit={6}
              />
            </div>
          </section>
        )}

      </div>
    </div>
  );
}
