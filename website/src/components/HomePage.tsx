"use client";

/**
 * HomePage — live race-weekend command center (2026-05 redesign).
 *
 * Strict job: when a visitor lands on /, they should immediately know
 *
 *   1. WHICH race is up next (or live)
 *   2. WHO the model thinks wins it
 *   3. WHAT the weekend looks like (weather, sessions)
 *
 * Everything else (calendar, standings, news, methodology) is a link.
 *
 * Visual language: Linear / Vercel — flat surfaces, lots of whitespace,
 * single telemetry-orange accent, big typography.  No glass, no
 * gradients, no decorative stripes.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { SeasonData, StandingsData, RoundData, SeasonTrackerData } from "@/types";
import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import { buttonVariants } from "@/components/ui/Button";
import {
  fetchSeasonData,
  fetchStandingsData,
  fetchRoundData,
  fetchSeasonTrackerData,
  formatDate,
  getCurrentRaceContext,
  getRoundLifecycle,
  getRoundStatusMeta,
  getVisualizationPath,
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

  // Once we know which race is featured, pull its round payload so we can
  // render the model's predicted podium + simulator probabilities.
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
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Loading season data…
        </p>
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

  // Track A: ghost the featured race's track map behind the hero so the
  // landing page instantly reads as F1 without a literal car/red overlay.
  const heroImage = getVisualizationPath(featuredRace.round, "track_map.png");

  return (
    <div className="mx-auto max-w-6xl px-6 lg:px-10">
      {/* ━━━ HERO ━━━ */}
      <section
        className="pt-12 pb-12 lg:pt-20 lg:pb-16 hero-circuit-bg -mx-6 lg:-mx-10 px-6 lg:px-10"
        style={{ ["--hero-image" as string]: `url("${heroImage}")` }}
      >
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <Badge variant={featuredVariant}>{featuredMeta.label}</Badge>
          <span className="text-sm text-[color:var(--text-muted)]">
            Round {featuredRace.round} · {formatDate(featuredRace.date)} ·{" "}
            {formatCountdown(featuredRace.date, new Date())}
          </span>
        </div>

        <div className="flex items-start gap-4 mb-8">
          <CountryFlag country={featuredRace.country} size={56} />
          <div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight leading-[1.05]">
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
      </section>

      {/* ━━━ PREDICTED PODIUM ━━━ */}
      {isPredictionView && featuredRound && featuredRound.classification && (
        <section className="pb-16">
          <div className="flex items-baseline justify-between mb-6">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">
                Model&apos;s predicted podium
              </h2>
              <p className="mt-1 text-sm text-[color:var(--text-muted)]">
                Plackett-Luce probabilities from the qualifying-time ensemble
                {featuredRound.classification[0] &&
                "simulatorWinProbability" in (featuredRound.classification[0] as object)
                  ? ", plus the Monte-Carlo race simulator"
                  : ""}
                .
              </p>
            </div>
            <Link
              href={`/race/${featuredRace.round}`}
              className="text-sm font-semibold text-[color:var(--accent-live)] hover:underline"
            >
              Full classification →
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {featuredRound.classification.slice(0, 3).map((entry, i) => {
              const sim = entry as typeof entry & {
                simulatorWinProbability?: number;
              };
              const winProb =
                typeof sim.simulatorWinProbability === "number"
                  ? sim.simulatorWinProbability * 100
                  : entry.winProbability ?? 0;
              return (
                <div
                  key={entry.driver}
                  className="rounded-[12px] border border-[color:var(--border)] bg-[color:var(--surface)] p-6 hover:border-[color:var(--border-strong)] transition-colors"
                >
                  <div className="flex items-center gap-3 mb-5">
                    <span
                      className="font-mono font-tabular text-3xl font-bold text-[color:var(--text-muted)]"
                      aria-hidden
                    >
                      P{i + 1}
                    </span>
                    <span
                      className="h-8 w-1.5 rounded-full"
                      style={{ background: entry.teamColor || "var(--accent-live)" }}
                      aria-hidden
                    />
                  </div>
                  <div className="text-3xl font-bold tracking-tight mb-1">
                    {entry.driver}
                  </div>
                  <div className="text-sm text-[color:var(--text-muted)] mb-6">
                    {entry.team}
                  </div>
                  <div className="text-xs uppercase tracking-[0.14em] text-[color:var(--text-muted)] mb-1">
                    Win probability
                  </div>
                  <div className="font-mono font-tabular text-4xl font-bold text-[color:var(--accent-live)]">
                    {winProb.toFixed(1)}%
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ━━━ LATEST OFFICIAL RESULT (compact) ━━━ */}
      {latestRound && latestRound.round !== featuredRace.round && (
        <section className="pb-16">
          <div className="flex items-baseline justify-between mb-6">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">
                Latest official result
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
          <div className="rounded-[12px] border border-[color:var(--border)] bg-[color:var(--surface)] p-1">
            <table className="w-full text-sm">
              <tbody>
                {(latestRound.classification ?? []).slice(0, 10).map((entry) => (
                  <tr
                    key={entry.driver}
                    className="border-b border-[color:var(--border)] last:border-b-0"
                  >
                    <td className="px-4 py-3 font-mono font-tabular text-[color:var(--text-muted)] w-12">
                      P{entry.position}
                    </td>
                    <td className="px-2 py-3">
                      <span
                        className="inline-block h-4 w-1.5 mr-3 align-middle rounded-sm"
                        style={{ background: entry.teamColor || "var(--accent-live)" }}
                        aria-hidden
                      />
                      <span className="font-semibold">{entry.driver}</span>
                    </td>
                    <td className="px-2 py-3 text-[color:var(--text-muted)]">
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
        </section>
      )}

      {/* ━━━ CHAMPIONSHIP PREVIEW ━━━ */}
      {standings && (
        <section className="pb-16">
          <div className="grid gap-8 sm:grid-cols-2">
            <div>
              <div className="flex items-baseline justify-between mb-4">
                <h2 className="text-xl font-bold tracking-tight">Drivers</h2>
                <Link
                  href="/standings"
                  className="text-sm font-semibold text-[color:var(--accent-live)] hover:underline"
                >
                  All →
                </Link>
              </div>
              <ol className="space-y-2">
                {standings.drivers.slice(0, 5).map((d, i) => (
                  <li
                    key={d.driver}
                    className="flex items-center gap-3 py-2 px-3 rounded-[8px] border border-[color:var(--border)]"
                  >
                    <span className="font-mono font-tabular text-[color:var(--text-muted)] w-6 text-sm">
                      {i + 1}
                    </span>
                    <span
                      className="h-4 w-1.5 rounded-sm"
                      style={{ background: d.teamColor || "var(--accent-live)" }}
                      aria-hidden
                    />
                    <span className="flex-1 font-semibold">{d.driver}</span>
                    <span className="font-mono font-tabular text-[color:var(--text-muted)] text-sm">
                      {d.points}pt
                    </span>
                  </li>
                ))}
              </ol>
            </div>
            <div>
              <div className="flex items-baseline justify-between mb-4">
                <h2 className="text-xl font-bold tracking-tight">Constructors</h2>
                <Link
                  href="/standings"
                  className="text-sm font-semibold text-[color:var(--accent-live)] hover:underline"
                >
                  All →
                </Link>
              </div>
              <ol className="space-y-2">
                {standings.constructors.slice(0, 5).map((t, i) => (
                  <li
                    key={t.team}
                    className="flex items-center gap-3 py-2 px-3 rounded-[8px] border border-[color:var(--border)]"
                  >
                    <span className="font-mono font-tabular text-[color:var(--text-muted)] w-6 text-sm">
                      {i + 1}
                    </span>
                    <span
                      className="h-4 w-1.5 rounded-sm"
                      style={{ background: t.teamColor || "var(--accent-live)" }}
                      aria-hidden
                    />
                    <span className="flex-1 font-semibold">{t.team}</span>
                    <span className="font-mono font-tabular text-[color:var(--text-muted)] text-sm">
                      {t.points}pt
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>
      )}

      {/* ━━━ ABOUT / METHODOLOGY LINK ━━━ */}
      <section className="pb-20 pt-4 border-t border-[color:var(--border)]">
        <h2 className="text-xl font-bold tracking-tight mb-2">
          How the predictions are made
        </h2>
        <p className="text-sm text-[color:var(--text-muted)] max-w-2xl mb-4">
          A per-driver lap-time ensemble (gradient boosting + XGBoost) feeds a
          Monte-Carlo race simulator that handles pit stops, safety cars, and
          tyre degradation. Output is calibrated against historical
          (predicted, observed) pairs via isotonic regression.
        </p>
        <Link
          href="/about"
          className="text-sm font-semibold text-[color:var(--accent-live)] hover:underline"
        >
          Read the methodology →
        </Link>
      </section>
    </div>
  );
}
