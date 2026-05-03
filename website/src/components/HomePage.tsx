"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { SeasonData, StandingsData, RoundData, SeasonTrackerData } from "@/types";
import CountryFlag from "@/components/CountryFlag";
import {
  fetchSeasonData,
  fetchStandingsData,
  fetchRoundData,
  fetchSeasonTrackerData,
  formatDate,
  formatDateTime,
  getCurrentRaceContext,
  getRoundLifecycle,
  getRoundStatusMeta,
} from "@/lib/data";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};
const stagger = { visible: { transition: { staggerChildren: 0.08 } } };
const scaleIn = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.4 } },
};

// F1 news outlets
const NEWS_OUTLETS = [
  { name: "Formula1.com", url: "https://www.formula1.com/en/latest/all", desc: "Official F1 news, interviews, and race reports", color: "#E10600" },
  { name: "Autosport", url: "https://www.autosport.com/f1/news/", desc: "Technical analysis and insider coverage", color: "#FFD700" },
  { name: "Motorsport.com", url: "https://www.motorsport.com/f1/news/", desc: "Global motorsport news and features", color: "#1A8FE3" },
  { name: "The Race", url: "https://www.the-race.com/formula-1/", desc: "In-depth expert analysis and opinion", color: "#FF4444" },
  { name: "RaceFans", url: "https://www.racefans.net/", desc: "Independent F1 journalism since 2005", color: "#00D2BE" },
  { name: "PlanetF1", url: "https://www.planetf1.com/", desc: "Breaking news and driver market updates", color: "#FF8000" },
];

// YouTube channels for F1 content
const YOUTUBE_LINKS = [
  { title: "Race Highlights", channel: "Formula 1", url: "https://www.youtube.com/@Formula1/videos", icon: "🏁" },
  { title: "Qualifying Highlights", channel: "Formula 1", url: "https://www.youtube.com/@Formula1/videos", icon: "⏱️" },
  { title: "Tech Talk", channel: "F1", url: "https://www.youtube.com/@Formula1/videos", icon: "🔧" },
  { title: "Post-Race Analysis", channel: "Sky Sports F1", url: "https://www.youtube.com/@SkySportsF1/videos", icon: "📊" },
];

export default function HomePage() {
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [standings, setStandings] = useState<StandingsData | null>(null);
  const [latestRace, setLatestRace] = useState<RoundData | null>(null);
  const [tracker, setTracker] = useState<SeasonTrackerData | null>(null);

  const actualRows = latestRace?.actualResults
    ? Object.entries(latestRace.actualResults).sort((a, b) => a[1] - b[1])
    : [];
  const predictedByDriver = new Map(latestRace?.classification.map((e) => [e.driver, e]) || []);

  useEffect(() => {
    fetchSeasonData().then(setSeason).catch(console.error);
    fetchSeasonTrackerData().then(setTracker).catch(() => {});
    fetchStandingsData()
      .then((s) => {
        setStandings(s);
        if (s.lastUpdatedRound > 0) {
          fetchRoundData(s.lastUpdatedRound).then(setLatestRace).catch(console.error);
        }
      })
      .catch(console.error);
  }, []);

  if (!season) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-3 border-f1-red border-t-transparent rounded-full animate-spin" />
          <p style={{ color: "var(--text-muted)" }}>Loading season data...</p>
        </div>
      </div>
    );
  }

  const roundsWithActual = (tracker?.rounds || []).filter((round) => round.hasActual).map((round) => round.round);
  const context = getCurrentRaceContext(season, roundsWithActual);
  const featuredRace =
    context.liveRound ||
    context.latestOfficialRound ||
    context.latestPredictionRound ||
    context.nextRound ||
    season.calendar[0];
  const featuredRaceStatus = getRoundStatusMeta(
    getRoundLifecycle(
      featuredRace,
      season.completedRounds.includes(featuredRace.round),
      roundsWithActual.includes(featuredRace.round),
    ),
  );

  return (
    <div className="hero-gradient">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* ━━━ HERO ━━━ */}
        <motion.section className="text-center mb-20" initial="hidden" animate="visible" variants={stagger}>
          <motion.div variants={fadeUp} className="inline-flex items-center gap-2 px-5 py-2 rounded-full text-sm font-bold mb-8" style={{ background: "rgba(225,6,0,0.1)", color: "#E10600", border: "1px solid rgba(225,6,0,0.2)" }}>
            <span className="w-2 h-2 bg-f1-red rounded-full animate-pulse" />
            {season.season} SEASON
          </motion.div>
          <motion.h1 variants={fadeUp} className="text-5xl sm:text-6xl lg:text-7xl font-black mb-6 tracking-tight leading-[0.95]">
            <span style={{ color: "var(--text)" }}>F1 Race</span>
            <br />
            <span className="gradient-text">Predictions</span>
          </motion.h1>
          <motion.p variants={fadeUp} className="text-lg sm:text-xl max-w-2xl mx-auto mb-10 leading-relaxed" style={{ color: "var(--text-muted)" }}>
            AI-powered race forecasts with official standings, weekend context, weather risk, team form, and model confidence shown in one race-control view.
          </motion.p>
          <motion.div variants={fadeUp} className="max-w-4xl mx-auto mb-10">
            <div className="weekend-spotlight p-6 sm:p-7 text-left">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.32em] mb-3" style={{ color: "#E10600" }}>Weekend Command Center</p>
                  <div className="flex flex-wrap items-center gap-3 mb-3">
                    <CountryFlag country={featuredRace.country} size={28} />
                    <h2 className="text-2xl sm:text-3xl font-black" style={{ color: "var(--text)" }}>{featuredRace.name}</h2>
                    <span className={`status-pill status-pill-${featuredRaceStatus.tone}`}>{featuredRaceStatus.label}</span>
                  </div>
                  <p className="text-sm sm:text-base" style={{ color: "var(--text-muted)" }}>
                    {featuredRace.circuit} • {formatDate(featuredRace.date)} • {featuredRaceStatus.description}
                  </p>
                </div>
                <Link href={`/race/${featuredRace.round}`} className="px-5 py-3 rounded-xl font-bold text-white bg-f1-red hover:bg-f1-red-dark transition-colors">
                  Open Race Report
                </Link>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-6">
                <div className="metric-card">
                  <p className="text-xs uppercase tracking-[0.2em]" style={{ color: "var(--text-muted)" }}>Forecasts Published</p>
                  <p className="text-2xl font-black mt-2" style={{ color: "var(--text)" }}>{season.completedRounds.length}</p>
                </div>
                <div className="metric-card">
                  <p className="text-xs uppercase tracking-[0.2em]" style={{ color: "var(--text-muted)" }}>Official Results</p>
                  <p className="text-2xl font-black mt-2" style={{ color: "#00D2BE" }}>{roundsWithActual.length}</p>
                </div>
                <div className="metric-card">
                  <p className="text-xs uppercase tracking-[0.2em]" style={{ color: "var(--text-muted)" }}>Current Focus</p>
                  <p className="text-2xl font-black mt-2" style={{ color: featuredRaceStatus.tone === "green" ? "#00D2BE" : featuredRaceStatus.tone === "red" ? "#E10600" : featuredRaceStatus.tone === "amber" ? "#FF8000" : "var(--text)" }}>
                    {featuredRaceStatus.shortLabel}
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
          <motion.div variants={fadeUp} className="flex flex-wrap justify-center gap-4">
            <Link href="/calendar" className="group px-8 py-3.5 bg-f1-red hover:bg-f1-red-dark text-white font-bold rounded-xl transition-all hover:scale-[1.03] active:scale-95 shadow-lg shadow-f1-red/25">
              Explore All Races
              <span className="ml-2 inline-block group-hover:translate-x-1 transition-transform">→</span>
            </Link>
            <Link href="/standings" className="px-8 py-3.5 font-bold rounded-xl transition-all hover:scale-[1.03] active:scale-95" style={{ background: "var(--bg-card)", color: "var(--text)", border: "1px solid var(--glass-border)" }}>
              Championship Standings
            </Link>
          </motion.div>
        </motion.section>

        {standings && (
          <motion.section className="data-freshness-card mb-12" initial="hidden" animate="visible" variants={fadeUp}>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em]" style={{ color: "#9FB0C8" }}>Official Data Snapshot</p>
              <h2 className="text-xl sm:text-2xl font-black mt-1" style={{ color: "var(--text)" }}>
                Standings synced through Round {standings.lastUpdatedRound}
              </h2>
              <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
                {standings.statusNote || "Championship tables are shown with source and freshness metadata so stale data is easy to spot."}
              </p>
            </div>
            <div className="data-freshness-meta">
              <span>{standings.source || "Official standings source"}</span>
              <span>{formatDateTime(standings.lastUpdated)}</span>
            </div>
          </motion.section>
        )}

        {/* ━━━ STATS BAR ━━━ */}
        <motion.section className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-20" initial="hidden" animate="visible" variants={stagger}>
          {[
            { value: season.totalRounds, label: "Grand Prix", accent: "#E10600" },
            { value: season.drivers.length, label: "Drivers", accent: "#00D2BE" },
            { value: season.teams.length, label: "Teams", accent: "#FF8000" },
            { value: roundsWithActual.length, label: "Official", accent: "#FFD700" },
          ].map((s) => (
            <motion.div key={s.label} variants={scaleIn} className="card p-6 text-center">
              <p className="text-4xl font-black stat-number" style={{ color: s.accent }}>{s.value}</p>
              <p className="text-xs mt-2 uppercase tracking-widest font-semibold" style={{ color: "var(--text-muted)" }}>{s.label}</p>
            </motion.div>
          ))}
        </motion.section>

        {/* ━━━ LATEST RACE RESULT / PREDICTION ━━━ */}
        {latestRace && (
          <motion.section className="mb-20" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }} variants={stagger}>
            <motion.div variants={fadeUp} className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-2xl sm:text-3xl font-black" style={{ color: "var(--text)" }}>
                  {actualRows.length > 0 ? "Latest Grand Prix Result" : "Latest Prediction"}
                </h2>
                <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
                  {actualRows.length > 0
                    ? "Official race outcome with model comparison"
                    : "AI-predicted race classification"}
                </p>
              </div>
              <Link href={`/race/${latestRace.round}`} className="group text-f1-red text-sm font-bold transition-colors inline-flex items-center gap-1 hover:underline">
                Full Race Details <span className="group-hover:translate-x-1 transition-transform inline-block">→</span>
              </Link>
            </motion.div>
            <motion.div variants={fadeUp} className="card overflow-hidden card-glow">
              {/* Race header */}
              <div className="p-6 sm:p-8 border-b" style={{ borderColor: "var(--border)" }}>
                <div className="flex items-center gap-3">
                  <CountryFlag country={latestRace.gpKey || latestRace.name} size={36} />
                  <div>
                    <h3 className="text-xl sm:text-2xl font-black" style={{ color: "var(--text)" }}>{latestRace.name}</h3>
                    <p className="text-sm" style={{ color: "var(--text-muted)" }}>Round {latestRace.round} • {latestRace.circuit} • {formatDate(latestRace.date)}</p>
                  </div>
                </div>
              </div>
              {/* Podium */}
              <div className="grid grid-cols-3">
                {(actualRows.length > 0 ? actualRows.slice(0, 3).map(([driver, position]) => ({
                  driver,
                  position,
                  predicted: predictedByDriver.get(driver),
                })) : latestRace.classification.slice(0, 3).map((entry) => ({
                  driver: entry.driver,
                  position: entry.position,
                  predicted: entry,
                }))).map((entry, i) => (
                  <div key={entry.driver} className="p-6 sm:p-8 text-center border-r last:border-r-0 relative group" style={{ borderColor: "var(--border)" }}>
                    <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity" style={{ background: `radial-gradient(circle at 50% 100%, ${(entry.predicted?.teamColor || "#888")}15, transparent 70%)` }} />
                    <div className="relative">
                      <div className={`text-4xl font-black mb-2 ${i === 0 ? "podium-1" : i === 1 ? "podium-2" : "podium-3"}`}>P{entry.position}</div>
                      <div className="w-10 h-1 rounded-full mx-auto mb-3" style={{ backgroundColor: entry.predicted?.teamColor || "#888" }} />
                      <p className="font-black text-lg" style={{ color: "var(--text)" }}>{entry.driver}</p>
                      <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{entry.predicted?.team || "Team"}</p>
                      <p className="text-f1-red font-bold mt-3 text-sm">
                        {actualRows.length > 0 ? "Official Result" : `+${entry.predicted?.points || 0} pts`}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
              {/* P4-P10 */}
              <div className="p-6 border-t" style={{ borderColor: "var(--border)" }}>
                <div className="grid gap-1">
                  {(actualRows.length > 0
                    ? actualRows.slice(3, 10).map(([driver, position]) => ({
                        driver,
                        position,
                        predicted: predictedByDriver.get(driver),
                      }))
                    : latestRace.classification.slice(3, 10).map((entry) => ({
                        driver: entry.driver,
                        position: entry.position,
                        predicted: entry,
                      }))
                  ).map((entry) => (
                    <div key={entry.driver} className="flex items-center gap-4 py-2.5 px-4 rounded-xl transition-colors hover:bg-[var(--bg-card-hover)]">
                      <span className={`position-badge ${entry.position <= 10 ? "points" : "no-points"}`}>{entry.position}</span>
                        <div className="team-color-bar h-8" style={{ backgroundColor: entry.predicted?.teamColor || "#888" }} />
                      <div className="flex-1">
                        <span className="font-semibold" style={{ color: "var(--text)" }}>{entry.driver}</span>
                          <span className="ml-2 text-sm" style={{ color: "var(--text-muted)" }}>{entry.predicted?.team || "Team"}</span>
                      </div>
                        {actualRows.length === 0 && (
                          <span className="text-sm font-mono" style={{ color: "var(--text-muted)" }}>
                            {entry.predicted?.gap === "LEADER" ? "—" : `+${entry.predicted?.gap}s`}
                          </span>
                        )}
                        <span className="text-f1-red text-sm font-bold">
                          {actualRows.length > 0 ? "Official" : `+${entry.predicted?.points || 0}`}
                        </span>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          </motion.section>
        )}

        {/* ━━━ AI / ML MODEL SHOWCASE ━━━ */}
        <motion.section className="mb-20" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }} variants={stagger}>
          <motion.div variants={fadeUp} className="text-center mb-10">
            <h2 className="text-2xl sm:text-3xl font-black mb-2" style={{ color: "var(--text)" }}>Powered by AI</h2>
            <p className="text-sm max-w-xl mx-auto" style={{ color: "var(--text-muted)" }}>
              Our ensemble model combines three machine learning approaches trained on real Formula 1 data
            </p>
          </motion.div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            {[
              {
                title: "XGBoost + GBR Ensemble",
                desc: "40% XGBoost + 40% GradientBoosting weighted blend with StandardScaler normalization. Trained on 2023–2025 qualifying and race data from FastF1.",
                icon: "🤖",
                accent: "#E10600",
              },
              {
                title: "LSTM Neural Network",
                desc: "PyTorch LSTM with 64 hidden units, 2 layers, sequence length 5. Captures temporal patterns in driver and team performance over race weekends.",
                icon: "🧠",
                accent: "#00D2BE",
              },
              {
                title: "Strategy Simulator",
                desc: "Monte-Carlo pit strategy evaluation with compound-specific degradation curves, tyre cliffs, and pit time loss modeling for optimal race strategy.",
                icon: "⛽",
                accent: "#FF8000",
              },
            ].map((item) => (
              <motion.div key={item.title} variants={fadeUp} className="card p-6 group">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl mb-4 transition-transform group-hover:scale-110" style={{ background: `${item.accent}15` }}>
                  {item.icon}
                </div>
                <h3 className="font-bold text-lg mb-2" style={{ color: "var(--text)" }}>{item.title}</h3>
                <p className="text-sm leading-relaxed" style={{ color: "var(--text-muted)" }}>{item.desc}</p>
              </motion.div>
            ))}
          </div>
          <motion.div variants={fadeUp} className="mt-8 card p-6">
            <h4 className="section-heading">12 Prediction Features</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {[
                "Team Performance Score", "Team-Adjusted Pace", "Clean Air Pace", "Current Form",
                "Experience Factor", "Pit Time Loss", "Tyre Degradation", "Rain Probability",
                "Temperature", "Previous Position", "Season Momentum", "Position Trend",
              ].map((f) => (
                <div key={f} className="flex items-center gap-2 text-sm py-1.5 px-3 rounded-lg" style={{ background: "var(--bg-surface)", color: "var(--text-muted)" }}>
                  <span className="text-f1-red text-xs">▸</span>
                  {f}
                </div>
              ))}
            </div>
          </motion.div>
        </motion.section>

        {/* ━━━ CHAMPIONSHIPS ━━━ */}
        {standings && (
          <motion.section className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-20" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }} variants={stagger}>
            <motion.div variants={fadeUp} className="card p-6 card-glow">
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-lg font-bold" style={{ color: "var(--text)" }}>🏆 Drivers Championship</h2>
                <Link href="/standings?tab=drivers" className="text-f1-red text-sm font-bold hover:underline">Full Standings →</Link>
              </div>
              <div className="space-y-3">
                {standings.drivers.slice(0, 5).map((d) => (
                  <div key={d.driver} className="flex items-center gap-3 py-1 px-2 rounded-lg transition-colors hover:bg-[var(--bg-card-hover)]">
                    <span className={`position-badge ${d.position === 1 ? "p1" : d.position === 2 ? "p2" : d.position === 3 ? "p3" : "points"}`}>{d.position}</span>
                    <div className="team-color-bar h-10" style={{ backgroundColor: d.teamColor }} />
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold truncate" style={{ color: "var(--text)" }}>{d.driverFullName}</p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>{d.team}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-black text-lg" style={{ color: "var(--text)" }}>{d.points}</p>
                      <p className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>PTS</p>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
            <motion.div variants={fadeUp} className="card p-6 card-glow">
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-lg font-bold" style={{ color: "var(--text)" }}>🏎️ Constructors Championship</h2>
                <Link href="/standings?tab=constructors" className="text-f1-red text-sm font-bold hover:underline">Full Standings →</Link>
              </div>
              <div className="space-y-3">
                {standings.constructors.slice(0, 5).map((c) => (
                  <div key={c.team} className="flex items-center gap-3 py-1 px-2 rounded-lg transition-colors hover:bg-[var(--bg-card-hover)]">
                    <span className={`position-badge ${c.position === 1 ? "p1" : c.position === 2 ? "p2" : c.position === 3 ? "p3" : "points"}`}>{c.position}</span>
                    <div className="team-color-bar h-10" style={{ backgroundColor: c.teamColor }} />
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold truncate" style={{ color: "var(--text)" }}>{c.team}</p>
                      <p className="text-xs truncate" style={{ color: "var(--text-muted)" }}>{c.drivers.join(" • ")}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-black text-lg" style={{ color: "var(--text)" }}>{c.points}</p>
                      <p className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>PTS</p>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          </motion.section>
        )}

        {/* ━━━ SEASON CALENDAR PREVIEW ━━━ */}
        <motion.section className="mb-20" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }} variants={stagger}>
          <motion.div variants={fadeUp} className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-2xl sm:text-3xl font-black" style={{ color: "var(--text)" }}>Season Calendar</h2>
              <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>All {season.totalRounds} races in the {season.season} season</p>
            </div>
            <Link href="/calendar" className="text-f1-red text-sm font-bold hover:underline inline-flex items-center gap-1 group">
              View All <span className="group-hover:translate-x-1 transition-transform inline-block">→</span>
            </Link>
          </motion.div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {season.calendar.slice(0, 6).map((race) => {
              return (
                <motion.div key={race.round} variants={fadeUp}>
                  <Link href={`/race/${race.round}`} className="card p-5 group block">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Round {race.round}</span>
                      {season.completedRounds.includes(race.round) ? (
                        <span className="px-2.5 py-1 rounded-full text-xs font-bold" style={{ background: "rgba(0,210,190,0.1)", color: "#00D2BE", border: "1px solid rgba(0,210,190,0.2)" }}>Data Ready</span>
                      ) : <span className="px-2.5 py-1 rounded-full text-xs font-medium" style={{ background: "var(--bg-surface)", color: "var(--text-muted)" }}>Preview Available</span>}
                    </div>
                    <div className="flex items-center gap-2 mb-1">
                      <CountryFlag country={race.country} size={24} />
                      <h3 className="font-bold group-hover:text-f1-red transition-colors" style={{ color: "var(--text)" }}>{race.name}</h3>
                    </div>
                    <p className="text-sm" style={{ color: "var(--text-muted)" }}>{race.circuit} • {formatDate(race.date)}</p>
                  </Link>
                </motion.div>
              );
            })}
          </div>
        </motion.section>

        {/* ━━━ F1 NEWS & MEDIA ━━━ */}
        <motion.section className="mb-20" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.1 }} variants={stagger}>
          <motion.div variants={fadeUp} className="text-center mb-10">
            <h2 className="text-2xl sm:text-3xl font-black mb-2" style={{ color: "var(--text)" }}>F1 News & Media</h2>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>Stay updated with the latest from the paddock</p>
          </motion.div>

          {/* YouTube Highlights */}
          <motion.div variants={fadeUp} className="mb-8">
            <h3 className="section-heading">📺 Watch Highlights</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {YOUTUBE_LINKS.map((yt) => (
                <a key={yt.title} href={yt.url} target="_blank" rel="noopener noreferrer" className="video-card group">
                  <div className="relative bg-[var(--bg-surface)] aspect-video flex items-center justify-center">
                    <div className="w-12 h-12 bg-[rgba(225,6,0,0.9)] rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                      <svg className="w-5 h-5 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    </div>
                    <span className="absolute top-2 left-2 text-2xl">{yt.icon}</span>
                  </div>
                  <div className="p-3">
                    <p className="font-bold text-sm" style={{ color: "var(--text)" }}>{yt.title}</p>
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>{yt.channel}</p>
                  </div>
                </a>
              ))}
            </div>
          </motion.div>

          {/* News Outlets */}
          <motion.div variants={fadeUp}>
            <h3 className="section-heading">📰 News Outlets</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {NEWS_OUTLETS.map((outlet) => (
                <a key={outlet.name} href={outlet.url} target="_blank" rel="noopener noreferrer" className="news-card group">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-8 rounded-full" style={{ background: outlet.color }} />
                    <div>
                      <p className="font-bold text-sm group-hover:text-f1-red transition-colors" style={{ color: "var(--text)" }}>{outlet.name}</p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>{outlet.desc}</p>
                    </div>
                    <svg className="w-4 h-4 ml-auto shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ color: "var(--text-muted)" }}>
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </div>
                </a>
              ))}
            </div>
          </motion.div>
        </motion.section>
      </div>
    </div>
  );
}
