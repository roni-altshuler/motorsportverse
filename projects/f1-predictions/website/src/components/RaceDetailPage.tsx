"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { motion } from "framer-motion";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  LineChart,
  Line,
} from "recharts";
import { RoundData, SeasonData, DriverStanding } from "@/types";
import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import RaceNarrativeCard from "@/components/race-weekend/RaceNarrativeCard";
import WinProbabilityChart from "@/components/charts/WinProbabilityChart";
import DriverDetailSheet from "@/components/DriverDetailSheet";
import StrategyExplorer from "@/components/StrategyExplorer";
import HUDHeader from "@/components/race-detail/HUDHeader";
import PodiumPredictionTrio from "@/components/race-detail/PodiumPredictionTrio";
import CircuitMap from "@/components/race-detail/CircuitMap";
import RaceVolatilityBadge from "@/components/race-detail/RaceVolatilityBadge";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { resolveDriverHeadshot } from "@/lib/headshots";
import HUDPanel from "@/components/ui/HUDPanel";
import LoadingTire from "@/components/ui/LoadingTire";
import ChartContainer from "@/components/charts/ChartContainer";
import PredictedPaceChart from "@/components/charts/PredictedPaceChart";
import PodiumProbabilityChart from "@/components/charts/PodiumProbabilityChart";
import FinishProbabilityHeatmap from "@/components/charts/FinishProbabilityHeatmap";
import HeadToHeadMatrix from "@/components/charts/HeadToHeadMatrix";
import LapTimeDistributionChart from "@/components/charts/LapTimeDistributionChart";
import {
  fetchRoundData,
  fetchSeasonData,
  fetchStandingsData,
  getVisualizationPath,
  formatDate,
  formatDateTime,
  formatGap,
  getRoundLifecycle,
  getRoundStatusMeta,
} from "@/lib/data";
import { useSeason } from "@/lib/SeasonProvider";
import { DEFAULT_SEASON_YEAR } from "@/lib/season";

// Centralised legacy status-pill tone → Badge variant map.  Same as the
// HomePage / Navbar table so the rest of the codebase can migrate
// piecemeal using this single mapping.
const TONE_TO_BADGE_VARIANT = {
  red: "negative",
  green: "positive",
  amber: "live",
  slate: "muted",
} as const;
type StatusTone = keyof typeof TONE_TO_BADGE_VARIANT;
const toneVariant = (tone: string | undefined) =>
  TONE_TO_BADGE_VARIANT[(tone || "slate") as StatusTone] ?? "default";

// 2026-05-21 redesign: the page collapses from 5 tabs to 2 — "weekend"
// (FP/Quali/Sprint/Race session tables) and "deepdive" (everything else,
// rendered as accordion sections so visitors can pop just what they want).
// The legacy "classification" / "analysis" / "strategy" / "visualizations"
// types stay in the union for type-safety on existing render guards,
// but the actual UI only routes through "weekend" + "deepdive".
type Tab = "weekend" | "deepdive" | "classification" | "analysis" | "strategy" | "visualizations";

interface Props {
  round: number;
}

function getYouTubeSearchUrl(raceName: string, type: string, seasonYear: number): string {
  const q = encodeURIComponent(`Formula 1 ${seasonYear} ${raceName} ${type} highlights`);
  return `https://www.youtube.com/results?search_query=${q}`;
}

function formatSessionStatus(status: string): string {
  if (status === "official") return "Official";
  if (status === "timing") return "Timing-Derived";
  if (status === "pending") return "Awaiting Data";
  return status || "Unavailable";
}

function sessionStatusTone(status: string): "green" | "amber" | "slate" | "red" {
  if (status === "official") return "green";
  if (status === "timing") return "amber";
  if (status === "pending") return "slate";
  return "red";
}

function bestQualifyingTime(row: { q1?: string | null; q2?: string | null; q3?: string | null; time?: string | null }): string {
  return row.q3 || row.q2 || row.q1 || row.time || "—";
}

export default function RaceDetailPage({ round }: Props) {
  const { basePath } = useSeason();
  const [data, setData] = useState<RoundData | null>(null);
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("weekend");
  const [activeWeekendSession, setActiveWeekendSession] = useState<string | null>(null);
  const [lightboxImg, setLightboxImg] = useState<string | null>(null);
  // B-P1.3b: which classification row is expanded (driver code).
  const [expandedDriver, setExpandedDriver] = useState<string | null>(null);
  // B-P1.3b: per-driver standings used by the detail sheet (sparkline +
  // season stats).  Fetched once on mount.
  const [standings, setStandings] = useState<DriverStanding[] | null>(null);

  // B-P1.3b: fetch standings once for the driver-detail sheet.  Independent
  // of the season/round-data fetch so it can run in parallel.
  useEffect(() => {
    let active = true;
    fetchStandingsData(basePath)
      .then((s) => {
        if (active) setStandings(s.drivers ?? null);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [basePath]);

  useEffect(() => {
    let active = true;
    fetchSeasonData(basePath)
      .then((seasonData) => {
        if (!active) return;
        setSeason(seasonData);
        const expectedRace = seasonData.calendar.find((race) => race.round === round);
        fetchRoundData(round, basePath)
          .then((roundData) => {
            if (!active) return;
            const matchesCalendar =
              !expectedRace ||
              (roundData.round === expectedRace.round && roundData.gpKey === expectedRace.gpKey);
            setData(matchesCalendar ? roundData : null);
          })
          .catch(() => active && setData(null));
      })
      .catch(() => {
        if (!active) return;
        setSeason(null);
        fetchRoundData(round, basePath).then(setData).catch(() => setData(null));
      });
    return () => {
      active = false;
    };
  }, [round, basePath]);

  if (!season && !data) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <LoadingTire label="Loading race data" />
      </div>
    );
  }

  const seasonRace = season?.calendar.find((r) => r.round === round) || null;
  const seasonYear = season?.season ?? DEFAULT_SEASON_YEAR;
  const totalRounds = season?.totalRounds ?? 22;
  const liveMeta = seasonRace
    ? getRoundStatusMeta(getRoundLifecycle(seasonRace, !!data, !!data?.actualResults))
    : null;

  if (!data && seasonRace) {
    const raceName = seasonRace.name;
    const isPostponed = !!seasonRace.postponed;

    return (
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-10 pb-8">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex items-center gap-4 mb-2">
            <CountryFlag country={seasonRace.country} size={44} />
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Badge variant="live">Round {seasonRace.round}</Badge>
                <Badge variant={toneVariant(liveMeta?.tone)}>
                  {liveMeta?.label || "Preview Scheduled"}
                </Badge>
              </div>
              <h1 className="text-2xl sm:text-3xl font-black" style={{ color: "var(--text)" }}>{seasonRace.name}</h1>
            </div>
          </div>
          <p className="mb-6 text-sm" style={{ color: "var(--text-muted)" }}>
            {seasonRace.circuit} • {formatDate(seasonRace.date)}
            {isPostponed ? " (original slot)" : ""}
          </p>

          <div className="card p-6 mb-8">
            <h3 className="section-heading">{isPostponed ? "Race Postponed" : "Race Preview"}</h3>
            <p style={{ color: "var(--text-muted)" }}>
              {isPostponed
                ? (seasonRace.statusNote || "This Grand Prix has been postponed. Predictions and race-comparison reporting will resume once a revised race date is confirmed.")
                : "This Grand Prix page is available now, but the model has not published predictions yet. Once the workflow runs for this round, predicted classification, real outcome comparison, accuracy metrics, and strategy visualizations will automatically appear here."}
            </p>
          </div>

          <div className="card p-6 mb-8">
            <h3 className="section-heading">Circuit Profile</h3>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
              <div className="metric-card"><p className="text-xs" style={{ color: "var(--text-muted)" }}>Circuit</p><p className="text-lg font-black" style={{ color: "var(--text)" }}>{seasonRace.circuit}</p></div>
              <div className="metric-card"><p className="text-xs" style={{ color: "var(--text-muted)" }}>Length</p><p className="text-lg font-black" style={{ color: "var(--text)" }}>{seasonRace.circuitKm} km</p></div>
              <div className="metric-card"><p className="text-xs" style={{ color: "var(--text-muted)" }}>Laps</p><p className="text-lg font-black" style={{ color: "var(--text)" }}>{seasonRace.laps}</p></div>
              <div className="metric-card"><p className="text-xs" style={{ color: "var(--text-muted)" }}>DRS Zones</p><p className="text-lg font-black" style={{ color: "var(--text)" }}>{seasonRace.drsZones}</p></div>
            </div>
          </div>

          <div className="flex flex-wrap gap-3 mb-8">
            {["Free Practice", "Qualifying", "Race"].map((type) => (
              <a
                key={type}
                href={getYouTubeSearchUrl(raceName, type, seasonYear)}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all hover:scale-[1.03]"
                style={{ background: "var(--bg-card)", color: "var(--text)", border: "1px solid var(--glass-border)" }}
              >
                {type} Highlights
              </a>
            ))}
          </div>

          <Link href="/calendar" className="text-f1-red font-bold hover:underline">← Back to Calendar</Link>
        </motion.div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-20 text-center">
        <div className="text-5xl mb-6">🏁</div>
        <h1 className="text-3xl font-black mb-4" style={{ color: "var(--text)" }}>Race Not Found</h1>
        <p className="mb-6" style={{ color: "var(--text-muted)" }}>Round {round} is outside the {seasonYear} calendar.</p>
        <Link href="/calendar" className="text-f1-red font-bold hover:underline">← Back to Calendar</Link>
      </div>
    );
  }

  // Two-tab structure (2026-05-21 redesign).  Deep Dive folds the
  // legacy Model Forecast + Analysis + Strategy + Visualisations tabs
  // into a single tab body with collapsed-by-default accordions.
  const tabs: { key: Tab; label: string }[] = [
    { key: "weekend", label: "Weekend Sessions" },
    { key: "deepdive", label: "Deep Dive" },
  ];

  const weekendSessions = data.weekendResults?.sessions || [];
  const defaultWeekendSession = weekendSessions.find((session) => session.rows.length > 0) || weekendSessions[0] || null;
  const activeSession = weekendSessions.find((session) => session.key === activeWeekendSession) || defaultWeekendSession;
  const loadedWeekendSessions = weekendSessions.filter((session) => session.rows.length > 0);
  const actualRows = data.actualResults ? Object.entries(data.actualResults).sort((a, b) => a[1] - b[1]) : [];
  // The model only publishes its final forecast once qualifying is in.
  // Pre-qualifying we hide the classification table, win-probability
  // chart, and the model-narrative card behind a single "Awaiting
  // Qualifying" placeholder so the page never advertises predictions
  // built on synthetic lap times. Officially-classified races stay
  // visible — they're history, not forecasts.
  const isPredictionPublished =
    actualRows.length > 0 ||
    data.predictionPhase === "post-quali" ||
    data.predictionPhase === "post-race";
  const gpReport = data.gpReport || null;
  const actualStatus = data.actualStatus || {};
  const predictedByDriver = new Map(data.classification.map((e) => [e.driver, e]));
  const confidenceTone = (value?: string) =>
    value === "High" ? "var(--accent-positive)" : value === "Low" ? "var(--accent-live)" : "var(--accent-info)";
  const comparisonChartData = actualRows
    .map(([driver, actualPos]) => {
      const pred = predictedByDriver.get(driver);
      if (!pred) return null;
      return {
        driver,
        predicted: pred.position,
        actual: actualPos,
        delta: pred.position - actualPos,
      };
    })
    .filter((x): x is { driver: string; predicted: number; actual: number; delta: number } => x !== null)
    .slice(0, 12);
  const teamErrorBars = Array.from(
    actualRows
      .map(([driver, actualPos]) => {
        const pred = predictedByDriver.get(driver);
        if (!pred) return null;
        return {
          team: pred.team,
          absDelta: Math.abs(pred.position - actualPos),
        };
      })
      .filter((x): x is { team: string; absDelta: number } => x !== null)
      .reduce((acc, cur) => {
        const prev = acc.get(cur.team) || { sum: 0, count: 0 };
        prev.sum += cur.absDelta;
        prev.count += 1;
        acc.set(cur.team, prev);
        return acc;
      }, new Map<string, { sum: number; count: number }>())
      .entries()
  )
    .map(([team, v]) => ({ team, meanError: Number((v.sum / v.count).toFixed(2)) }))
    .sort((a, b) => a.meanError - b.meanError)
    .slice(0, 10);
  const speedTrapChartData = (data.telemetryData?.speedTraps || [])
    .slice(0, 10)
    .map((st) => ({
      driver: st.driver,
      speed: st.speedKmh,
      sector: `S${st.sector}`,
    }));
  const pitImpactChartData = (data.telemetryData?.pitStopImpact || [])
    .slice(0, 12)
    .map((p) => ({
      label: `${p.driver} L${p.lap}`,
      outlapDelta: p.outlapDelta,
      pitTimeLoss: p.pitTimeLoss ?? 0,
      driver: p.driver,
      team: p.team,
    }));
  const trackStatusEvents = data.telemetryData?.trackStatusEvents || [];
  const raceControlEvents = data.telemetryData?.raceControlEvents || [];
  const sectorDominance = data.telemetryData?.sectorDominance || [];
  const stintTimeline = data.telemetryData?.stintTimeline || [];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const strategyData = (data as any).strategyData;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const tyreDegData = (data as any).tyreDegData;

  return (
    <div>
      {/* Race detail hero — track circuit anchored to the left of the title
          (per product direction); replaces the prior full-bleed backdrop. */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-10">
        <div className="flex flex-col sm:flex-row sm:items-center gap-6 sm:gap-10">
          <div
            className="shrink-0 w-full sm:w-64 md:w-72 lg:w-80 aspect-square relative"
            style={{
              border: "1px solid var(--hairline)",
              background: "var(--surface-card)",
            }}
          >
            {data.circuitInfo?.geometry ? (
              <div className="absolute inset-0 p-4">
                <CircuitMap
                  geometry={data.circuitInfo.geometry}
                  showCorners={false}
                  showDrsZones={false}
                  strokeWidth={2.5}
                  accentColor="var(--ink)"
                />
              </div>
            ) : (
              <div
                className="absolute inset-0 flex items-center justify-center"
                aria-label={`${data.circuit} circuit map`}
                role="img"
              >
                <svg
                  viewBox="0 0 100 100"
                  className="w-1/2 h-1/2 opacity-40"
                  fill="none"
                  stroke="var(--ink)"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <path d="M20 50 Q 20 20 50 20 T 80 50 Q 80 80 50 80 T 20 50 Z" />
                </svg>
              </div>
            )}
          </div>
          <div className="min-w-0">
            <p className="eyebrow mb-4">Round {String(data.round).padStart(2, "0")}</p>
            <div className="flex flex-wrap items-center gap-4 mb-4">
              <CountryFlag country={data.gpKey} size={48} />
              <h1 className="display-xl">{data.name}</h1>
            </div>
            <p className="body-md text-[color:var(--body-strong)]">
              {data.circuit} · {formatDate(data.date)}
            </p>
          </div>
        </div>
      </section>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-8">
      {/* Lightbox */}
      {lightboxImg && (
        <div className="lightbox-overlay" onClick={() => setLightboxImg(null)}>
          <button
            className="absolute top-6 right-6 w-10 h-10 rounded-full flex items-center justify-center text-white/80 hover:text-white hover:bg-white/10 transition-colors text-2xl font-light z-10"
            onClick={() => setLightboxImg(null)}
            aria-label="Close lightbox"
          >
            ✕
          </button>
          <Image
            src={lightboxImg}
            alt="Visualization"
            className="lightbox-image"
            width={2000}
            height={1200}
            onClick={(e) => e.stopPropagation()}
            unoptimized
          />
        </div>
      )}

      {/* ━━━ HUD HEADER (cinematic overhaul) ━━━ */}
      <HUDHeader
        round={data.round}
        name={data.name}
        country={data.gpKey}
        circuit={data.circuit}
        date={formatDate(data.date)}
        sprint={data.sprint}
        liveLabel={
          isPredictionPublished
            ? liveMeta?.label
            : "Awaiting Qualifying"
        }
        liveBadgeVariant={
          isPredictionPublished ? toneVariant(liveMeta?.tone) : "muted"
        }
        weather={data.weatherData ? {
          temperatureC: data.weatherData.temperatureC,
          rainProbability: Math.round((data.weatherData.rainProbability ?? 0) * 100),
          humidity: data.weatherData.humidity,
          windSpeedKmh: data.weatherData.windSpeedKmh,
          weatherDescription: data.weatherData.weatherDescription,
        } : undefined}
      />

      {/* Prediction-publish gate. The model only publishes a final
          forecast after qualifying — pre-quali the page focuses on the
          circuit, the calendar slot, and the weather, and explicitly
          tells the user the prediction will land on Saturday. */}
      {isPredictionPublished ? (
        <>
          <RaceNarrativeCard round={data} />
          <div className="mb-6">
            <WinProbabilityChart classification={data.classification ?? []} />
          </div>
        </>
      ) : (
        <div className="mb-8 p-6 sm:p-8 rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)]">
          <p className="eyebrow mb-3">Predictions publish on Saturday</p>
          <h3 className="title-md mb-3" style={{ color: "var(--text)" }}>
            Awaiting Qualifying
          </h3>
          <p className="body-sm max-w-2xl" style={{ color: "var(--text-muted)" }}>
            The race prediction for {data.name} publishes after qualifying is
            complete. Qualifying pace is the strongest single-lap signal of
            race competitiveness — the model holds back until it has those
            lap times to ensure the published forecast reflects the freshest
            data available before lights out.
          </p>
        </div>
      )}


      {isPredictionPublished && (
      <motion.div
        className="report-shell p-6 sm:p-7 mb-8"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08 }}
      >
        <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] mb-2" style={{ color: "var(--accent-live)" }}>Race Report</p>
            <h2 className="text-2xl font-black" style={{ color: "var(--text)" }}>
              {actualRows.length > 0 ? "Prediction vs Official Outcome" : "Pre-Race Prediction Briefing"}
            </h2>
            <p className="text-sm mt-2 max-w-3xl" style={{ color: "var(--text-muted)" }}>
              {actualRows.length > 0
                ? "The model forecast remains visible alongside the official result so visitors can evaluate accuracy and team-level performance."
                : data.predictionPhase === "preview"
                ? "Tentative outlook published ahead of qualifying. The final prediction updates once qualifying lap times are confirmed — that's when the model gets its strongest single-lap pace signal."
                : "Prediction front-and-centre for the live Grand Prix weekend flow; the official result will replace the headline state once the race is complete."}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 justify-end">
            <Badge variant={actualRows.length > 0 ? "positive" : toneVariant(liveMeta?.tone)}>
              {actualRows.length > 0
                ? "Official Result Loaded"
                : data.predictionPhase === "preview"
                ? "Preview · Awaiting Qualifying"
                : data.predictionPhase === "post-quali"
                ? "Final Prediction · Post-Qualifying"
                : liveMeta?.label || "Prediction Published"}
            </Badge>
            <RaceVolatilityBadge classification={data.classification ?? []} />
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="report-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] mb-3" style={{ color: "var(--accent-live)" }}>Model Forecast</p>
            <div className="space-y-3">
              {data.classification.slice(0, 5).map((entry) => (
                <div key={`pred-${entry.driver}`} className="report-row">
                  <div className="flex items-center gap-3">
                    <span className="position-badge points">P{entry.position}</span>
                    <div className="team-color-bar h-8" style={{ backgroundColor: entry.teamColor }} />
                    <div>
                      <p className="font-bold" style={{ color: "var(--text)" }}>{entry.driverFullName}</p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>{entry.team}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-mono" style={{ color: "var(--text-muted)" }}>{entry.gap === "LEADER" ? "Projected leader" : `+${entry.gap}s`}</p>
                    {entry.winProbability != null && (
                      <p className="text-xs font-bold mt-1" style={{ color: confidenceTone(entry.confidence) }}>
                        {entry.winProbability.toFixed(1)}% win
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="report-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] mb-3" style={{ color: actualRows.length > 0 ? "var(--accent-positive)" : "var(--accent-info)" }}>
              {actualRows.length > 0 ? "Official Classification" : "Post-Race Slot"}
            </p>
            {actualRows.length > 0 ? (
              <div className="space-y-3">
                {actualRows.slice(0, 5).map(([driver, position]) => {
                  const predicted = predictedByDriver.get(driver);
                  const delta = predicted ? predicted.position - position : null;
                  const actualLabel = actualStatus[driver] || `P${position}`;
                  return (
                    <div key={`actual-${driver}`} className="report-row">
                      <div className="flex items-center gap-3">
                        <span className="position-badge no-points">P{position}</span>
                        <div className="team-color-bar h-8" style={{ backgroundColor: predicted?.teamColor || "#888" }} />
                        <div>
                          <p className="font-bold" style={{ color: "var(--text)" }}>{predicted?.driverFullName || driver}</p>
                          <p className="text-xs" style={{ color: "var(--text-muted)" }}>{predicted?.team || "Official result"}</p>
                        </div>
                      </div>
                      <p className="text-sm font-mono" style={{ color: delta == null ? "var(--text-muted)" : Math.abs(delta) <= 2 ? "var(--accent-positive)" : "var(--accent-live)" }}>
                        {actualLabel} • {delta == null ? "No forecast match" : delta === 0 ? "Exact match" : delta > 0 ? `${delta} better than predicted` : `${Math.abs(delta)} worse than predicted`}
                      </p>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="report-panel-muted">
                Official results will appear here automatically after the Grand Prix weekend once the post-race workflow syncs the classified order.
              </div>
            )}
          </div>
        </div>
        {data.predictionInsights && (
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mt-4">
            <div className="metric-card">
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>Likeliest Winner</p>
              <p className="text-xl font-black" style={{ color: "var(--text)" }}>{data.predictionInsights.mostLikelyWinner}</p>
              {data.predictionInsights.winnerProbability != null && (
                <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                  {data.predictionInsights.winnerProbability.toFixed(1)}% projected win probability
                </p>
              )}
            </div>
            <div className="metric-card">
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>Closest Battle</p>
              <p className="text-xl font-black" style={{ color: "var(--text)" }}>{data.predictionInsights.closestBattle.drivers.join(" vs ")}</p>
              <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{data.predictionInsights.closestBattle.gap.toFixed(3)}s projected gap</p>
            </div>
            <div className="metric-card">
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>High Confidence Calls</p>
              <p className="text-xl font-black" style={{ color: "var(--accent-positive)" }}>{data.predictionInsights.highConfidenceCount}</p>
            </div>
            <div className="metric-card">
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>Avg Uncertainty</p>
              <p className="text-xl font-black" style={{ color: "var(--text)" }}>{data.metrics.avgUncertainty?.toFixed(2) ?? "—"}</p>
            </div>
          </div>
        )}
        <div className="data-freshness-card mt-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em]" style={{ color: "var(--text-muted)" }}>Freshness & Sources</p>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              Generated {formatDateTime(data.generatedAt)} with qualifying from {data.dataFreshness?.qualifyingSource || "the model pipeline"} and weather from {data.dataFreshness?.weatherSource || data.weatherData?.source || "static estimates"}.
            </p>
          </div>
          <div className="data-freshness-meta">
            <span>{actualRows.length > 0 ? "Official result loaded" : liveMeta?.shortLabel || "Prediction"}</span>
            <span>{data.metrics.trainingYears.join(", ")} training data</span>
          </div>
        </div>
      </motion.div>
      )}


      {/* ━━━ YouTube Highlight Links ━━━ */}
      <motion.div
        className="flex flex-wrap gap-3 mb-10"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
      >
        {[
          { label: "FP Highlights", type: "Free Practice" },
          { label: "Qualifying Highlights", type: "Qualifying" },
          { label: "Race Highlights", type: "Race" },
        ].map((yt) => (
          <a
            key={yt.label}
            href={getYouTubeSearchUrl(data.name, yt.type, seasonYear)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all hover:scale-[1.03]"
            style={{ background: "var(--bg-card)", color: "var(--text)", border: "1px solid var(--glass-border)" }}
          >
            <svg className="w-4 h-4 text-f1-red" fill="currentColor" viewBox="0 0 24 24"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
            {yt.label}
          </a>
        ))}
      </motion.div>

      {/* Prediction-gated podium + chart strip. Hidden pre-quali so
          synthetic lap times never reach the user-facing surface. */}
      {isPredictionPublished && (
        <>
          <PodiumPredictionTrio
            classification={data.classification}
            actualPodium={
              actualRows.length >= 3
                ? actualRows.slice(0, 3).map(([driver, position]) => {
                    const pred = predictedByDriver.get(driver);
                    return {
                      driver,
                      team: pred?.team,
                      teamColor: pred?.teamColor,
                      position,
                      headshotUrl: resolveDriverHeadshot(driver, pred?.headshotUrl),
                    };
                  })
                : undefined
            }
          />

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-8">
            <HUDPanel
              kicker="Model Forecast"
              title="Predicted Race Pace"
              rightSlot={<Badge variant="live">Interactive</Badge>}
              bodyClassName="p-4 sm:p-5"
            >
              <ChartContainer
                fallbackSrc={getVisualizationPath(round, "predicted_laptimes.png")}
                fallbackAlt="Predicted race pace"
                height={400}
              >
                <PredictedPaceChart classification={data.classification} />
              </ChartContainer>
            </HUDPanel>
            <HUDPanel
              kicker="Probability Layer"
              title="Podium Probability"
              rightSlot={<Badge variant="live">Interactive</Badge>}
              bodyClassName="p-4 sm:p-5"
            >
              <ChartContainer
                fallbackSrc={getVisualizationPath(round, "podium_probability_board.png")}
                fallbackAlt="Podium probability"
                height={400}
              >
                <PodiumProbabilityChart classification={data.classification} />
              </ChartContainer>
            </HUDPanel>
          </div>
        </>
      )}

      {/* ━━━ TAB NAVIGATION ━━━ */}
      <div className="flex gap-2 mb-10 overflow-x-auto pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`tab-button whitespace-nowrap ${activeTab === tab.key ? "active" : ""}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ═══ Weekend Results Tab ═══ */}
      {activeTab === "weekend" && (
        <motion.div className="space-y-6" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          <div className="weekend-results-shell p-6 sm:p-7">
            <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
              <div>
                <p className="viz-kicker">Race Weekend Control Room</p>
                <h3 className="text-2xl font-black" style={{ color: "var(--text)" }}>Session Results Explorer</h3>
                <p className="text-sm mt-1 max-w-3xl" style={{ color: "var(--text-muted)" }}>
                  Review the full Grand Prix weekend timeline: sprint qualifying, sprint race, Grand Prix qualifying, and the race result as soon as official or timing-backed data is available.
                </p>
              </div>
              <div className="data-freshness-meta">
                <span>{loadedWeekendSessions.length}/{weekendSessions.length || (data.sprint ? 4 : 2)} sessions loaded</span>
                <span>{data.weekendResults?.source || "Weekend data pipeline"}</span>
              </div>
            </div>

            {weekendSessions.length > 0 ? (
              <>
                <div className="session-tab-grid mb-5">
                  {weekendSessions.map((session) => (
                    <button
                      key={session.key}
                      onClick={() => setActiveWeekendSession(session.key)}
                      className={`session-tab ${activeSession?.key === session.key ? "active" : ""}`}
                    >
                      <span className="session-tab-short">{session.shortLabel}</span>
                      <span className="session-tab-main">{session.label}</span>
                      <Badge variant={toneVariant(sessionStatusTone(session.status))}>
                        {formatSessionStatus(session.status)}
                      </Badge>
                    </button>
                  ))}
                </div>

                {activeSession && (
                  <div className="session-detail-card">
                    <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                      <div>
                        <h4 className="text-lg font-black" style={{ color: "var(--text)" }}>{activeSession.label}</h4>
                        <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                          Source: {activeSession.source}
                          {activeSession.note ? ` • ${activeSession.note}` : ""}
                        </p>
                      </div>
                      <Badge variant={toneVariant(sessionStatusTone(activeSession.status))}>
                        {activeSession.rows.length ? `${activeSession.rows.length} classified` : formatSessionStatus(activeSession.status)}
                      </Badge>
                    </div>

                    {activeSession.rows.length > 0 ? (
                      <>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
                          {activeSession.rows.slice(0, 3).map((row) => (
                            <div key={`session-podium-${activeSession.key}-${row.driver}`} className="session-podium-card">
                              <span className={`position-badge ${row.position === 1 ? "p1" : row.position === 2 ? "p2" : row.position === 3 ? "p3" : "points"}`}>
                                P{row.position}
                              </span>
                              <div className="team-color-bar h-10" style={{ backgroundColor: row.teamColor }} />
                              <DriverPortrait
                                driver={row.driver}
                                driverFullName={row.driverFullName}
                                team={row.team}
                                teamColor={row.teamColor}
                                headshotUrl={resolveDriverHeadshot(row.driver)}
                                size={56}
                              />
                              <div>
                                <p className="font-black" style={{ color: "var(--text)" }}>{row.driverFullName ?? row.driver}</p>
                                <p className="text-xs" style={{ color: "var(--text-muted)" }}>{row.team}</p>
                              </div>
                              <p className="ml-auto text-sm font-mono" style={{ color: "var(--text-muted)" }}>
                                {activeSession.kind === "qualifying" ? bestQualifyingTime(row) : row.position === 1 ? row.time || "Winner" : row.gap || row.status || "—"}
                              </p>
                            </div>
                          ))}
                        </div>

                        <div className="overflow-x-auto">
                          <table className="session-results-table">
                            <thead>
                              <tr>
                                {(activeSession.kind === "qualifying"
                                  ? ["POS", "DRIVER", "TEAM", "Q1", "Q2", "Q3", "BEST"]
                                  : ["POS", "DRIVER", "TEAM", "GRID", "TIME / GAP", "LAPS", "STATUS", "PTS"]
                                ).map((header) => (
                                  <th key={header}>{header}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {activeSession.rows.map((row) => (
                                <tr key={`${activeSession.key}-${row.driver}`}>
                                  <td><span className={`position-badge ${row.position <= 3 ? `p${row.position}` : row.position <= 10 ? "points" : "no-points"}`}>P{row.position}</span></td>
                                  <td>
                                    <span className="flex items-center gap-2">
                                      <DriverPortrait
                                        driver={row.driver}
                                        driverFullName={row.driverFullName}
                                        team={row.team}
                                        teamColor={row.teamColor}
                                        headshotUrl={resolveDriverHeadshot(row.driver)}
                                        size={28}
                                      />
                                      <span className="font-bold" style={{ color: "var(--text)" }}>{row.driverFullName ?? row.driver}</span>
                                    </span>
                                  </td>
                                  <td>
                                    <span className="inline-flex items-center gap-2">
                                      <span className="team-color-bar h-5" style={{ backgroundColor: row.teamColor }} />
                                      <span style={{ color: "var(--text-muted)" }}>{row.team}</span>
                                    </span>
                                  </td>
                                  {activeSession.kind === "qualifying" ? (
                                    <>
                                      <td className="font-mono">{row.q1 || "—"}</td>
                                      <td className="font-mono">{row.q2 || "—"}</td>
                                      <td className="font-mono">{row.q3 || "—"}</td>
                                      <td className="font-mono font-bold" style={{ color: row.position === 1 ? "var(--accent-positive)" : "var(--text)" }}>{bestQualifyingTime(row)}</td>
                                    </>
                                  ) : (
                                    <>
                                      <td className="font-mono">{row.grid ?? "—"}</td>
                                      <td className="font-mono font-bold" style={{ color: row.position === 1 ? "var(--accent-positive)" : "var(--text)" }}>
                                        {row.position === 1 ? row.time || "Winner" : row.gap || row.time || "—"}
                                      </td>
                                      <td className="font-mono">{row.laps ?? "—"}</td>
                                      <td>{row.status || row.positionText || "—"}</td>
                                      <td className="font-mono font-bold" style={{ color: Number(row.points || 0) > 0 ? "var(--accent-live)" : "var(--text-muted)" }}>{row.points ?? 0}</td>
                                    </>
                                  )}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </>
                    ) : (
                      <div className="report-panel-muted">
                        {activeSession.note || "This session has not been published yet. The automated data pipeline will populate this tab once the result appears upstream."}
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <div className="report-panel-muted">
                Weekend session tabs will appear after the export pipeline refreshes this round with live qualifying, sprint, and race result metadata.
              </div>
            )}
          </div>
        </motion.div>
      )}

      {/* ═══ Deep Dive ═══ — folds Classification + Analysis + Strategy +
           Visualizations into accordion sections, all closed by default. */}
      {activeTab === "deepdive" && isPredictionPublished && (
      <details className="deep-dive-section">
        <summary className="deep-dive-summary">Model Forecast</summary>
        <div className="deep-dive-section-body">
        <motion.div className="space-y-6" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          {actualRows.length > 0 && (
            <div className="card p-6">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <h3 className="section-heading mb-0">Predicted vs Actual Race Outcome</h3>
                <div className="flex flex-wrap items-center gap-2">
                  {data.accuracy?.accuracy_pct != null && (
                    <span className="text-xs font-bold uppercase tracking-wider px-3 py-1 rounded-full" style={{ background: "color-mix(in srgb, var(--accent-live) 14%, transparent)", color: "var(--accent-live)", border: "1px solid color-mix(in srgb, var(--accent-live) 30%, transparent)" }}>
                      Podium &amp; points accuracy: {data.accuracy.accuracy_pct}%
                    </span>
                  )}
                  {data.accuracy?.within_3_accuracy_pct != null && (
                    <span className="text-xs font-semibold tracking-wide px-3 py-1 rounded-full" style={{ background: "color-mix(in srgb, var(--text-muted) 8%, transparent)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
                      Within 3 (all): {data.accuracy.within_3_accuracy_pct}%
                    </span>
                  )}
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                <div className="metric-card">
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>Podium</p>
                  <p className="text-xl font-black" style={{ color: "var(--text)" }}>{data.accuracy?.podium_hits ?? 0}<span className="text-sm font-semibold" style={{ color: "var(--text-muted)" }}>/{data.accuracy?.podium_total ?? 3}</span></p>
                  {data.accuracy?.podium_accuracy_pct != null && (
                    <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>{data.accuracy.podium_accuracy_pct}% of podium</p>
                  )}
                </div>
                <div className="metric-card">
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>Points</p>
                  <p className="text-xl font-black" style={{ color: "var(--text)" }}>{data.accuracy?.points_hits ?? 0}<span className="text-sm font-semibold" style={{ color: "var(--text-muted)" }}>/{data.accuracy?.points_total ?? 10}</span></p>
                  {data.accuracy?.points_accuracy_pct != null && (
                    <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>{data.accuracy.points_accuracy_pct}% of points</p>
                  )}
                </div>
                <div className="metric-card">
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>Mean Error (finishers)</p>
                  <p className="text-xl font-black" style={{ color: "var(--text)" }}>{data.accuracy?.mean_position_error_classified ?? data.accuracy?.mean_position_error ?? "-"}</p>
                  {data.accuracy?.mean_position_error != null && data.accuracy?.mean_position_error_classified != null && (
                    <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>{data.accuracy.mean_position_error} all drivers</p>
                  )}
                </div>
                <div className="metric-card">
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>Within 3 (all)</p>
                  <p className="text-xl font-black" style={{ color: "var(--text)" }}>{data.accuracy?.within_3_positions ?? 0}<span className="text-sm font-semibold" style={{ color: "var(--text-muted)" }}>/{data.accuracy?.total_drivers ?? actualRows.length}</span></p>
                </div>
              </div>
              {(data.accuracy?.dnf_count != null || data.circuitVolatility) && (
                <p className="text-xs mb-4 leading-relaxed" style={{ color: "var(--text-muted)" }}>
                  {data.accuracy?.dnf_count != null && data.accuracy.dnf_count > 0 && (
                    <>Finisher accuracy excludes <strong style={{ color: "var(--text)" }}>{data.accuracy.dnf_count}</strong> retirement{data.accuracy.dnf_count === 1 ? "" : "s"}/DNS — outcomes driven by reliability and incidents, not race-pace prediction. </>
                  )}
                  {data.circuitVolatility && (
                    <>Circuit volatility <strong style={{ color: "var(--text)" }}>{Math.round(data.circuitVolatility.volatilityScore * 100)}%</strong> (expected deviation from pace order; {Math.round(data.circuitVolatility.safetyCarProbability * 100)}% safety-car risk).</>
                  )}
                </p>
              )}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      {["ACTUAL", "PRED", "Δ", "DRIVER", "TEAM"].map((h) => (
                        <th key={h} className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {actualRows.map(([drv, actualPos]) => {
                      const pred = predictedByDriver.get(drv);
                      const predPos = pred?.position;
                      const delta = predPos != null ? predPos - actualPos : null;
                      return (
                        <tr key={`cmp-${drv}`} style={{ borderBottom: "1px solid var(--border)" }}>
                          <td className="px-3 py-2 font-mono font-bold" style={{ color: "var(--text)" }}>{actualStatus[drv] || `P${actualPos}`}</td>
                          <td className="px-3 py-2 font-mono" style={{ color: "var(--text)" }}>{predPos != null ? `P${predPos}` : "-"}</td>
                          <td className="px-3 py-2 font-mono" style={{ color: delta == null ? "var(--text-muted)" : Math.abs(delta) <= 2 ? "var(--accent-positive)" : "var(--accent-live)" }}>
                            {delta == null ? "-" : delta === 0 ? "0" : delta > 0 ? `+${delta}` : `${delta}`}
                          </td>
                          <td className="px-3 py-2 font-bold" style={{ color: "var(--text)" }}>{drv}</td>
                          <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{pred?.team ?? "-"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {comparisonChartData.length > 0 && (
                <div className="mt-6">
                  <h4 className="text-sm font-bold uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>
                    Interactive Position Comparison (Top 12)
                  </h4>
                  <div className="h-72 w-full" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "12px", padding: "12px" }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={comparisonChartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" />
                        <XAxis dataKey="driver" stroke="#9ca3af" />
                        <YAxis reversed allowDecimals={false} domain={[1, "dataMax"]} stroke="#9ca3af" />
                        <Tooltip
                          contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
                          labelStyle={{ color: "#f3f4f6" }}
                        />
                        <Bar dataKey="actual" fill="var(--accent-positive)" name="Actual" />
                        <Bar dataKey="predicted" fill="var(--accent-live)" name="Predicted" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {teamErrorBars.length > 0 && (
                <div className="mt-6">
                  <h4 className="text-sm font-bold uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>
                    Team-Level Mean Prediction Error
                  </h4>
                  <div className="h-72 w-full" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "12px", padding: "12px" }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={teamErrorBars} layout="vertical" margin={{ left: 40 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" />
                        <XAxis type="number" stroke="#9ca3af" />
                        <YAxis type="category" dataKey="team" stroke="#9ca3af" width={120} />
                        <Tooltip
                          formatter={(value) => [`${value} positions`, "Mean absolute error"]}
                          contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
                          labelStyle={{ color: "#f3f4f6" }}
                        />
                        <Bar dataKey="meanError" fill="var(--accent-info)" radius={[0, 6, 6, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {gpReport && (
                <div className="mt-6 space-y-4">
                  <h4 className="text-sm font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                    Grand Prix Performance Report
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="metric-card">
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>Winner Called</p>
                      <p className="text-xl font-black" style={{ color: gpReport.winnerHit ? "var(--accent-positive)" : "var(--accent-live)" }}>
                        {gpReport.winnerHit ? "Yes" : "No"}
                      </p>
                    </div>
                    <div className="metric-card">
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>Podium Hits</p>
                      <p className="text-xl font-black" style={{ color: "var(--text)" }}>{gpReport.podiumHits}/3</p>
                    </div>
                    <div className="metric-card">
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>Within 5</p>
                      <p className="text-xl font-black" style={{ color: "var(--text)" }}>{gpReport.within5}</p>
                    </div>
                    <div className="metric-card">
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>Median Error</p>
                      <p className="text-xl font-black" style={{ color: "var(--text)" }}>{gpReport.medianError.toFixed(1)}</p>
                    </div>
                  </div>

                  {gpReport.biggestMisses?.length > 0 && (
                    <div className="card p-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                      <p className="text-xs font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
                        Biggest Misses
                      </p>
                      <div className="space-y-2">
                        {gpReport.biggestMisses.slice(0, 5).map((miss) => (
                          <div key={`miss-${miss.driver}`} className="flex items-center justify-between text-sm">
                            <span style={{ color: "var(--text)" }}>
                              {miss.driver} <span style={{ color: "var(--text-muted)" }}>({miss.team})</span>
                            </span>
                            <span className="font-mono" style={{ color: "var(--accent-live)" }}>
                              Pred P{miss.predicted} vs Actual P{miss.actual} ({miss.delta > 0 ? `+${miss.delta}` : miss.delta})
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="card overflow-hidden">
            <div className="px-5 py-4" style={{ borderBottom: "1px solid var(--border)" }}>
              <h3 className="section-heading mb-0">Model Predicted Classification</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["POS", "DRIVER", "", "TEAM", "TIME", "RANGE", "WIN", "CONF", "PTS"].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.classification.map((entry) => {
                    const isExpanded = expandedDriver === entry.driver;
                    return (
                      <React.Fragment key={entry.driver}>
                        <tr
                          className="transition-colors hover:bg-[var(--bg-card-hover)] cursor-pointer"
                          style={{ borderBottom: "1px solid var(--border)" }}
                          onClick={() =>
                            setExpandedDriver(isExpanded ? null : entry.driver)
                          }
                          aria-expanded={isExpanded}
                          title={`${isExpanded ? "Hide" : "Show"} season form for ${entry.driver}`}
                        >
                          <td className="px-4 py-3">
                            <span className={`position-badge ${entry.position === 1 ? "p1" : entry.position === 2 ? "p2" : entry.position === 3 ? "p3" : entry.position <= 10 ? "points" : "no-points"}`}>{entry.position}</span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="inline-flex items-center gap-3">
                              <DriverPortrait
                                driver={entry.driver}
                                driverFullName={entry.driverFullName}
                                team={entry.team}
                                teamColor={entry.teamColor}
                                headshotUrl={resolveDriverHeadshot(entry.driver, entry.headshotUrl)}
                                size={28}
                              />
                              <span className="font-bold" style={{ color: "var(--text)" }}>{entry.driverFullName ?? entry.driver}</span>
                              <span
                                className="text-xs font-mono select-none"
                                style={{ color: "var(--text-muted)" }}
                                aria-hidden
                              >
                                {isExpanded ? "−" : "+"}
                              </span>
                            </span>
                          </td>
                          <td className="px-1 py-3"><div className="w-1 h-6 rounded" style={{ backgroundColor: entry.teamColor }} /></td>
                          <td className="px-4 py-3" style={{ color: "var(--text-muted)" }}>{entry.team}</td>
                          <td className="px-4 py-3 font-mono text-sm" style={{ color: "var(--text)" }}>{entry.predictedTime}s</td>
                          <td className="px-4 py-3 font-mono text-sm" style={{ color: "var(--text-muted)" }}>
                            {entry.finishRangeLow && entry.finishRangeHigh
                              ? `P${entry.finishRangeLow}-P${entry.finishRangeHigh}`
                              : formatGap(entry.gap)}
                          </td>
                          <td className="px-4 py-3 font-mono text-sm" style={{ color: "var(--text-muted)" }}>
                            {entry.winProbability != null ? `${entry.winProbability.toFixed(1)}%` : "—"}
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-xs font-bold uppercase tracking-wider" style={{ color: confidenceTone(entry.confidence) }}>
                              {entry.confidence || "Medium"}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            {entry.points > 0 ? <span className="font-bold text-f1-red">{entry.points}</span> : <span style={{ color: "var(--text-muted)" }}>—</span>}
                          </td>
                        </tr>
                        {/* B-P1.3b: inline driver-detail expansion */}
                        {isExpanded && (
                          <tr style={{ borderBottom: "1px solid var(--border)" }}>
                            <td colSpan={9} className="px-4 py-1">
                              <DriverDetailSheet
                                driver={entry.driver}
                                standings={standings ?? []}
                                fullName={entry.driverFullName}
                              />
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
        </div>
      </details>
      )}

      {/* ═══ Deep Dive: Circuit & Telemetry ═══ */}
      {activeTab === "deepdive" && (
      <details className="deep-dive-section">
        <summary className="deep-dive-summary">Circuit & Telemetry</summary>
        <div className="deep-dive-section-body">
        <motion.div className="space-y-8" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          {/* Circuit Info */}
          <div className="card p-6 sm:p-8">
            <h3 className="section-heading">Circuit Information</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
              {[
                { label: "Circuit Type", value: data.circuitInfo.type },
                { label: "Laps", value: data.circuitInfo.laps },
                { label: "Length", value: `${data.circuitInfo.circuitKm} km` },
                { label: "Pit Stops", value: data.circuitInfo.expectedStops },
                { label: "DRS Zones", value: data.circuitInfo.drsZones || 2 },
                { label: "Tyre Deg", value: `${Math.round(data.circuitInfo.tyreDeg * 100)}%`, bar: data.circuitInfo.tyreDeg, barColor: data.circuitInfo.tyreDeg > 0.5 ? "var(--accent-live)" : "var(--accent-positive)" },
                { label: "Overtaking", value: `${Math.round(data.circuitInfo.overtaking * 100)}%`, bar: data.circuitInfo.overtaking, barColor: "var(--accent-info)" },
                { label: "Safety Car", value: `${Math.round((data.circuitInfo.safetyCarLikelihood || 0.4) * 100)}%`, bar: data.circuitInfo.safetyCarLikelihood || 0.4, barColor: (data.circuitInfo.safetyCarLikelihood || 0.4) > 0.6 ? "var(--accent-info)" : "var(--accent-positive)" },
                { label: "Altitude", value: `${data.circuitInfo.altitudeM || 0} m` },
                ...(data.sprint ? [{ label: "Sprint Laps", value: data.sprintLaps || 0 }] : []),
              ].map((item) => (
                <div key={item.label} className="metric-card">
                  <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>{item.label}</p>
                  <p className="text-lg font-bold" style={{ color: "var(--text)" }}>{item.value}</p>
                  {"bar" in item && item.bar !== undefined && (
                    <div className="progress-bar mt-2">
                      <div className="progress-bar-fill" style={{ width: `${(item.bar as number) * 100}%`, background: item.barColor as string }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {data.predictionInsights && (
            <div className="card p-6 sm:p-8">
              <h3 className="section-heading">Model Readout</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="metric-card">
                  <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Pole-to-Win Bias</p>
                  <p className="text-2xl font-black" style={{ color: "var(--text)" }}>{data.predictionInsights.poleToWinBias}%</p>
                  <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>How strongly this circuit rewards track position in our forecast blend.</p>
                </div>
                <div className="metric-card">
                  <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Likeliest Winner</p>
                  <p className="text-2xl font-black" style={{ color: "var(--text)" }}>{data.predictionInsights.mostLikelyWinner}</p>
                  <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                    {data.predictionInsights.winnerProbability?.toFixed(1) ?? "—"}% projected win probability
                  </p>
                </div>
                <div className="metric-card">
                  <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>High Confidence</p>
                  <p className="text-2xl font-black" style={{ color: "var(--accent-positive)" }}>{data.predictionInsights.highConfidenceCount}</p>
                </div>
                <div className="metric-card">
                  <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Medium / Low Confidence</p>
                  <p className="text-2xl font-black" style={{ color: "var(--accent-info)" }}>
                    {data.predictionInsights.mediumConfidenceCount} / <span style={{ color: "var(--accent-live)" }}>{data.predictionInsights.lowConfidenceCount}</span>
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Weather */}
          {data.weatherData && (
            <div className="card p-6 sm:p-8">
              <h3 className="section-heading">Weather Conditions</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                <div className="metric-card">
                  <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Rain Probability</p>
                  <p className="text-2xl font-black" style={{ color: data.weatherData.rainProbability > 0.5 ? "var(--accent-info)" : data.weatherData.rainProbability > 0.25 ? "var(--accent-info)" : "var(--accent-positive)" }}>
                    {Math.round(data.weatherData.rainProbability * 100)}%
                  </p>
                  <div className="progress-bar mt-2">
                    <div className="progress-bar-fill" style={{ width: `${data.weatherData.rainProbability * 100}%`, background: data.weatherData.rainProbability > 0.5 ? "var(--accent-info)" : "var(--accent-positive)" }} />
                  </div>
                </div>
                <div className="metric-card">
                  <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Temperature</p>
                  <p className="text-2xl font-black" style={{ color: data.weatherData.temperatureC > 35 ? "var(--accent-live)" : data.weatherData.temperatureC < 15 ? "var(--accent-info)" : "var(--text)" }}>
                    {Math.round(data.weatherData.temperatureC)}°C
                  </p>
                </div>
                {data.weatherData.humidity != null && (
                  <div className="metric-card">
                    <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Humidity</p>
                    <p className="text-2xl font-black" style={{ color: "var(--text)" }}>{Math.round(data.weatherData.humidity)}%</p>
                  </div>
                )}
                {data.weatherData.windSpeedKmh != null && (
                  <div className="metric-card">
                    <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Wind Speed</p>
                    <p className="text-2xl font-black" style={{ color: data.weatherData.windSpeedKmh > 30 ? "var(--accent-info)" : "var(--text)" }}>
                      {Math.round(data.weatherData.windSpeedKmh)} km/h
                    </p>
                  </div>
                )}
                {data.weatherData.cloudCover != null && (
                  <div className="metric-card">
                    <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Cloud Cover</p>
                    <p className="text-2xl font-black" style={{ color: "var(--text)" }}>{Math.round(data.weatherData.cloudCover)}%</p>
                  </div>
                )}
                {data.weatherData.precipitationMm != null && data.weatherData.precipitationMm > 0 && (
                  <div className="metric-card">
                    <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Precipitation</p>
                    <p className="text-2xl font-black" style={{ color: "var(--accent-info)" }}>{data.weatherData.precipitationMm.toFixed(1)} mm</p>
                  </div>
                )}
              </div>
              {data.weatherData.weatherDescription && (
                <p className="mt-4 text-sm" style={{ color: "var(--text-muted)" }}>
                  Forecast: <span className="font-medium" style={{ color: "var(--text)" }}>{data.weatherData.weatherDescription}</span>
                </p>
              )}
              {data.weatherData.source && (
                <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                  Source: {data.weatherData.source === "static" ? "Historical estimates" : "Open-Meteo API"}
                </p>
              )}
            </div>
          )}

          {/* Telemetry */}
          {data.telemetryData && (
            <div className="card p-6 sm:p-8">
              <h3 className="section-heading">Speed Traps & Sector Times</h3>
              {speedTrapChartData.length > 0 && (
                <div className="mb-6">
                  <h4 className="text-sm font-bold uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>
                    Interactive Speed Trap Trend
                  </h4>
                  <div className="h-72 w-full" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "12px", padding: "12px" }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={speedTrapChartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" />
                        <XAxis dataKey="driver" stroke="#9ca3af" />
                        <YAxis stroke="#9ca3af" />
                        <Tooltip
                          formatter={(value, _name, props) => [`${value} km/h`, `Speed (${props?.payload?.sector})`]}
                          contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
                          labelStyle={{ color: "#f3f4f6" }}
                        />
                        <Line type="monotone" dataKey="speed" stroke="var(--accent-live)" strokeWidth={2.5} dot={{ r: 4, fill: "var(--accent-live)" }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
              {data.telemetryData.speedTraps && data.telemetryData.speedTraps.length > 0 && (
                <div className="mb-6">
                  <h4 className="text-sm font-bold uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>Speed Traps</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--border)" }}>
                          {["#", "Driver", "Team", "Speed", "Sector"].map((h) => (
                            <th key={h} className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {data.telemetryData.speedTraps.slice(0, 10).map((st, i) => (
                          <tr key={`${st.driver}-${st.sector}`} style={{ borderBottom: "1px solid var(--border)" }}>
                            <td className="px-3 py-2 font-bold" style={{ color: "var(--text-muted)" }}>{i + 1}</td>
                            <td className="px-3 py-2 font-bold" style={{ color: "var(--text)" }}>
                              <span className="flex items-center gap-2">
                                <DriverPortrait
                                  driver={st.driver}
                                  team={st.team}
                                  teamColor={st.teamColor}
                                  headshotUrl={resolveDriverHeadshot(st.driver)}
                                  size={24}
                                />
                                <span>{st.driver}</span>
                              </span>
                            </td>
                            <td className="px-3 py-2 flex items-center gap-2">
                              <div className="w-1 h-4 rounded" style={{ backgroundColor: st.teamColor }} />
                              <span style={{ color: "var(--text-muted)" }}>{st.team}</span>
                            </td>
                            <td className="px-3 py-2 font-mono font-bold" style={{ color: i === 0 ? "var(--accent-live)" : "var(--text)" }}>{st.speedKmh} km/h</td>
                            <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>S{st.sector}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              {data.telemetryData.sectorTimes && data.telemetryData.sectorTimes.length > 0 && (
                <div>
                  <h4 className="text-sm font-bold uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>Best Sector Times</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--border)" }}>
                          {["#", "Driver", "Team", "S1", "S2", "S3", "Ideal Lap"].map((h) => (
                            <th key={h} className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {data.telemetryData.sectorTimes.slice(0, 10).map((st, i) => (
                          <tr key={st.driver} style={{ borderBottom: "1px solid var(--border)" }}>
                            <td className="px-3 py-2 font-bold" style={{ color: "var(--text-muted)" }}>{i + 1}</td>
                            <td className="px-3 py-2 font-bold" style={{ color: "var(--text)" }}>
                              <span className="flex items-center gap-2">
                                <DriverPortrait
                                  driver={st.driver}
                                  team={st.team}
                                  teamColor={st.teamColor}
                                  headshotUrl={resolveDriverHeadshot(st.driver)}
                                  size={24}
                                />
                                <span>{st.driver}</span>
                              </span>
                            </td>
                            <td className="px-3 py-2 flex items-center gap-2">
                              <div className="w-1 h-4 rounded" style={{ backgroundColor: st.teamColor }} />
                              <span style={{ color: "var(--text-muted)" }}>{st.team}</span>
                            </td>
                            <td className="px-3 py-2 font-mono" style={{ color: "var(--text)" }}>{st.sector1.toFixed(3)}s</td>
                            <td className="px-3 py-2 font-mono" style={{ color: "var(--text)" }}>{st.sector2.toFixed(3)}s</td>
                            <td className="px-3 py-2 font-mono" style={{ color: "var(--text)" }}>{st.sector3.toFixed(3)}s</td>
                            <td className="px-3 py-2 font-mono font-bold" style={{ color: i === 0 ? "var(--accent-positive)" : "var(--text)" }}>{st.idealLap.toFixed(3)}s</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {stintTimeline.length > 0 && (
            <div className="card p-6 sm:p-8">
              <h3 className="section-heading">Stint Timeline (Compounds by Driver)</h3>
              <div className="space-y-3">
                {stintTimeline.slice(0, 12).map((row) => {
                  const totalLaps = Math.max(1, row.stints.reduce((acc, s) => Math.max(acc, s.endLap), 0));
                  return (
                    <div key={`stint-${row.driver}`}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="flex items-center gap-2 text-sm font-bold" style={{ color: "var(--text)" }}>
                          <DriverPortrait
                            driver={row.driver}
                            team={row.team}
                            teamColor={row.teamColor}
                            headshotUrl={resolveDriverHeadshot(row.driver)}
                            size={24}
                          />
                          <span>{row.driver}</span>
                        </span>
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>{row.team}</span>
                      </div>
                      <div className="h-6 rounded-md overflow-hidden flex" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                        {row.stints.map((s, idx) => {
                          const widthPct = Math.max(3, (s.laps / totalLaps) * 100);
                          const compoundColor = s.compound.toLowerCase().includes("soft")
                            ? "var(--accent-live)"
                            : s.compound.toLowerCase().includes("medium")
                            ? "#FBBF24"
                            : s.compound.toLowerCase().includes("hard")
                            ? "#e5e7eb"
                            : s.compound.toLowerCase().includes("inter")
                            ? "#22c55e"
                            : s.compound.toLowerCase().includes("wet")
                            ? "#3b82f6"
                            : row.teamColor;
                          return (
                            <div
                              key={`${row.driver}-st-${idx}`}
                              title={`${s.compound}: L${s.startLap}-L${s.endLap}`}
                              className="h-full"
                              style={{ width: `${widthPct}%`, background: compoundColor, borderRight: "1px solid rgba(0,0,0,0.2)" }}
                            />
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {(trackStatusEvents.length > 0 || raceControlEvents.length > 0) && (
            <div className="card p-6 sm:p-8">
              <h3 className="section-heading">Track Status & Race Control Timeline</h3>
              {trackStatusEvents.length > 0 && (
                <div className="mb-6">
                  <h4 className="text-sm font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
                    Safety Car / VSC / Flag Events
                  </h4>
                  <div className="space-y-2">
                    {trackStatusEvents.slice(0, 20).map((e, i) => (
                      <div key={`status-${i}`} className="flex items-center gap-3 p-2 rounded" style={{ background: "var(--bg-surface)" }}>
                        <span className="text-xs font-mono" style={{ color: "var(--text-muted)", minWidth: 82 }}>{e.time || "--:--"}</span>
                        <span className="text-xs font-bold px-2 py-0.5 rounded" style={{ background: "rgba(225,6,0,0.12)", color: "var(--accent-live)" }}>{e.statusLabel}</span>
                        <span className="text-sm" style={{ color: "var(--text)" }}>{e.message}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {raceControlEvents.length > 0 && (
                <div>
                  <h4 className="text-sm font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
                    Race Control Messages
                  </h4>
                  <div className="space-y-2 max-h-72 overflow-auto pr-1">
                    {raceControlEvents.slice(0, 40).map((e, i) => (
                      <div key={`rcm-${i}`} className="p-2 rounded" style={{ background: "var(--bg-surface)" }}>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>{e.time || "--:--"}</span>
                          {e.lap > 0 && <span className="text-xs" style={{ color: "var(--text-muted)" }}>Lap {e.lap}</span>}
                          <span className="text-xs font-semibold" style={{ color: "var(--accent-info)" }}>{e.category}</span>
                        </div>
                        <p className="text-sm" style={{ color: "var(--text)" }}>{e.message}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {pitImpactChartData.length > 0 && (
            <div className="card p-6 sm:p-8">
              <h3 className="section-heading">Pit Stop Delta Impact</h3>
              <div className="h-72 w-full" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "12px", padding: "12px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={pitImpactChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" />
                    <XAxis dataKey="label" stroke="#9ca3af" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#9ca3af" />
                    <Tooltip
                      formatter={(value, name) => [
                        `${value} s`,
                        name === "outlapDelta" ? "Out-lap Delta" : "Pit Time Loss"
                      ]}
                      contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
                      labelStyle={{ color: "#f3f4f6" }}
                    />
                    <Bar dataKey="outlapDelta" fill="var(--accent-live)" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="pitTimeLoss" fill="var(--accent-info)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {sectorDominance.length > 0 && (
            <div className="card p-6 sm:p-8">
              <h3 className="section-heading">Sector Dominance Heatmap</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      {['Driver', 'Team', 'S1 Rank', 'S2 Rank', 'S3 Rank', 'Overall'].map((h) => (
                        <th key={h} className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sectorDominance.slice(0, 12).map((row) => {
                      const rankColor = (r: number) => r <= 3 ? "var(--accent-positive)" : r <= 8 ? "var(--accent-info)" : "var(--accent-live)";
                      return (
                        <tr key={`dom-${row.driver}`} style={{ borderBottom: "1px solid var(--border)" }}>
                          <td className="px-3 py-2 font-bold" style={{ color: "var(--text)" }}>
                            <span className="flex items-center gap-2">
                              <DriverPortrait
                                driver={row.driver}
                                team={row.team}
                                teamColor={row.teamColor}
                                headshotUrl={resolveDriverHeadshot(row.driver)}
                                size={24}
                              />
                              <span>{row.driver}</span>
                            </span>
                          </td>
                          <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{row.team}</td>
                          <td className="px-3 py-2 font-mono" style={{ color: rankColor(row.sector1Rank) }}>#{row.sector1Rank}</td>
                          <td className="px-3 py-2 font-mono" style={{ color: rankColor(row.sector2Rank) }}>#{row.sector2Rank}</td>
                          <td className="px-3 py-2 font-mono" style={{ color: rankColor(row.sector3Rank) }}>#{row.sector3Rank}</td>
                          <td className="px-3 py-2 font-mono font-bold" style={{ color: rankColor(row.overallRank) }}>#{row.overallRank}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Model Metrics */}
          <div className="card p-6">
            <h3 className="section-heading">Model Performance</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="metric-card">
                <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>R² Score</p>
                <p className="text-2xl font-black" style={{ color: data.metrics.r2Score > 0.9 ? "var(--accent-positive)" : "var(--text)" }}>{data.metrics.r2Score.toFixed(3)}</p>
              </div>
              <div className="metric-card">
                <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Mean Abs. Error</p>
                <p className="text-2xl font-black" style={{ color: "var(--text)" }}>{data.metrics.mae.toFixed(3)}s</p>
              </div>
              <div className="metric-card">
                <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Max Spread</p>
                <p className="text-2xl font-black" style={{ color: "var(--text)" }}>{data.metrics.maxSpread.toFixed(2)}s</p>
              </div>
              <div className="metric-card">
                <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Training Data</p>
                <p className="text-2xl font-black" style={{ color: "var(--text)" }}>{data.metrics.trainingYears.join(", ")}</p>
              </div>
              <div className="metric-card">
                <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Avg Uncertainty</p>
                <p className="text-2xl font-black" style={{ color: "var(--text)" }}>{data.metrics.avgUncertainty?.toFixed(2) ?? "—"}</p>
              </div>
            </div>
          </div>

          {/* Feature Importance */}
          <div className="card p-6">
            <h3 className="section-heading">Feature Importance</h3>
            <div className="space-y-3">
              {data.featureImportance.slice(0, 9).map((f, i) => {
                const pct = Math.round(f.importance * 100 * 10) / 10;
                return (
                  <motion.div key={f.feature} className="flex items-center gap-4" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}>
                    <div className="w-40 sm:w-52 text-sm font-medium truncate" style={{ color: "var(--text)" }}>{f.feature}</div>
                    <div className="flex-1 progress-bar h-3">
                      <div className="progress-bar-fill" style={{ width: `${Math.min(pct, 100)}%`, background: pct > 50 ? "var(--accent-live)" : pct > 10 ? "var(--accent-info)" : "var(--accent-info)" }} />
                    </div>
                    <span className="text-sm font-mono w-14 text-right" style={{ color: "var(--text-muted)" }}>{pct}%</span>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </motion.div>
        </div>
      </details>
      )}

      {/* ═══ Deep Dive: Strategy ═══ */}
      {activeTab === "deepdive" && isPredictionPublished && (
      <details className="deep-dive-section">
        <summary className="deep-dive-summary">Strategy</summary>
        <div className="deep-dive-section-body">
        <motion.div className="space-y-8" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          {/* B-P2.1: Interactive strategy comparison (recharts).  Leads
              with the explorer so the existing 4-up grid below acts as
              the "more detail" view. */}
          <StrategyExplorer
            strategyData={strategyData ?? null}
            totalLaps={data.circuitInfo?.laps}
          />
          {strategyData ? (
            <div className="card p-6 sm:p-8">
              <h3 className="section-heading">Pit Strategy Comparison</h3>
              <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>Projected race time over {data.circuitInfo.laps} laps</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                {Object.entries(strategyData).map(([name, d]: [string, any]) => {
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  const isOptimal = Object.values(strategyData).every((o: any) => d.meanTime <= o.meanTime);
                  return (
                    <div key={name} className="metric-card relative" style={isOptimal ? { border: "1px solid rgba(0,210,190,0.3)" } : {}}>
                      {isOptimal && <span className="absolute -top-2 left-3 px-2 py-0.5 text-xs font-bold rounded-full" style={{ background: "rgba(0,210,190,0.15)", color: "var(--accent-positive)" }}>OPTIMAL</span>}
                      <p className="font-bold text-sm mb-2" style={{ color: "var(--text)" }}>{name}</p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>{d.numStops} stop{d.numStops !== 1 ? "s" : ""}</p>
                      <p className="text-lg font-black mt-2" style={{ color: "var(--text)" }}>{(d.meanTime / 60).toFixed(1)} min</p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>±{d.stdTime.toFixed(1)}s variance</p>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="card p-10 text-center">
              <div className="text-4xl mb-4">⛽</div>
              <p className="font-semibold mb-2" style={{ color: "var(--text)" }}>Pit Strategy Data</p>
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                Run the pipeline with <code className="px-2 py-0.5 rounded text-xs font-mono" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>--advanced</code> to generate strategy data
              </p>
            </div>
          )}

          {tyreDegData ? (
            <div className="card p-6">
              <h3 className="section-heading">Tyre Degradation Analysis</h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                {Object.entries(tyreDegData).map(([compound, d]: [string, any]) => {
                  const compoundColors: Record<string, string> = { SOFT: "var(--accent-live)", MEDIUM: "#FFD700", HARD: "#FFFFFF" };
                  return (
                    <div key={compound} className="metric-card">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: compoundColors[compound] || "#888" }} />
                        <span className="font-bold text-sm" style={{ color: "var(--text)" }}>{compound}</span>
                      </div>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between"><span style={{ color: "var(--text-muted)" }}>Deg Rate</span><span className="font-mono" style={{ color: "var(--text)" }}>{d.degRate.toFixed(3)}s/lap</span></div>
                        <div className="flex justify-between"><span style={{ color: "var(--text-muted)" }}>Cliff Lap</span><span className="font-mono" style={{ color: "var(--text)" }}>Lap {d.cliffLap}</span></div>
                        <div className="flex justify-between"><span style={{ color: "var(--text-muted)" }}>Pace Offset</span><span className="font-mono" style={{ color: d.paceOffset < 0 ? "var(--accent-positive)" : "var(--accent-live)" }}>{d.paceOffset > 0 ? "+" : ""}{d.paceOffset.toFixed(1)}s</span></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="card p-10 text-center">
              <div className="text-4xl mb-4">🔴</div>
              <p className="font-semibold mb-2" style={{ color: "var(--text)" }}>Tyre Degradation Data</p>
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>Run the pipeline with advanced models to generate tyre data</p>
            </div>
          )}

          {/* Intentionally keep image galleries in one place (Visualizations tab) to avoid duplicates. */}
        </motion.div>
        </div>
      </details>
      )}

      {/* ═══ Deep Dive: Visualisations ═══ */}
      {activeTab === "deepdive" && isPredictionPublished && (
      <details className="deep-dive-section">
        <summary className="deep-dive-summary">Visualisations</summary>
        <div className="deep-dive-section-body">
          <motion.div className="grid grid-cols-1 xl:grid-cols-2 gap-4" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
            <HUDPanel
              kicker="Probability"
              title="Finish Probability Heatmap"
              rightSlot={<Badge variant="live">Interactive</Badge>}
              bodyClassName="p-4 sm:p-5"
            >
              <ChartContainer
                fallbackSrc={null}
                fallbackAlt="Finish probability heatmap"
                height={420}
              >
                <FinishProbabilityHeatmap classification={data.classification} />
              </ChartContainer>
            </HUDPanel>
            <HUDPanel
              kicker="Pairwise"
              title="Head-to-Head Edges"
              rightSlot={<Badge variant="live">Interactive</Badge>}
              bodyClassName="p-4 sm:p-5"
            >
              <ChartContainer
                fallbackSrc={null}
                fallbackAlt="Head-to-head edges"
                height={420}
              >
                <HeadToHeadMatrix classification={data.classification} />
              </ChartContainer>
            </HUDPanel>
            <HUDPanel
              kicker="Distribution"
              title="Lap-Time Distribution"
              rightSlot={<Badge variant="muted">Approximation</Badge>}
              bodyClassName="p-4 sm:p-5"
            >
              <ChartContainer
                fallbackSrc={null}
                fallbackAlt="Lap-time distribution"
                height={380}
              >
                <LapTimeDistributionChart classification={data.classification} metrics={data.metrics} />
              </ChartContainer>
            </HUDPanel>
          </motion.div>
        </div>
      </details>
      )}

      {/* ━━━ NAVIGATION ━━━ */}
      <div className="flex items-center justify-between mt-16 pt-8" style={{ borderTop: "1px solid var(--border)" }}>
        {round > 1 ? (
          <Link href={`/race/${round - 1}`} className="group text-f1-red font-bold transition-colors inline-flex items-center gap-1 hover:underline">
            <span className="group-hover:-translate-x-1 transition-transform inline-block">←</span> Previous Round
          </Link>
        ) : (
          <Link href="/calendar" className="group font-medium inline-flex items-center gap-1" style={{ color: "var(--text-muted)" }}>
            <span className="group-hover:-translate-x-1 transition-transform inline-block">←</span> Calendar
          </Link>
        )}
        {round < totalRounds && (
          <Link href={`/race/${round + 1}`} className="group text-f1-red font-bold transition-colors inline-flex items-center gap-1 hover:underline">
            Next Round <span className="group-hover:translate-x-1 transition-transform inline-block">→</span>
          </Link>
        )}
      </div>
      </div>
    </div>
  );
}
