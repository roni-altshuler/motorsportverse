"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { SeasonTrackerData, SeasonData } from "@/types";
import { fetchSeasonTrackerData, fetchSeasonData } from "@/lib/data";
import { getSeasonYear } from "@/lib/season";

export default function AccuracyDashboardPage() {
  const [tracker, setTracker] = useState<SeasonTrackerData | null>(null);
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchSeasonTrackerData()
      .then((d) => {
        if (!d) setError(true);
        else setTracker(d);
      })
      .catch(() => setError(true));
    fetchSeasonData().then(setSeason).catch(() => {});
  }, []);

  if (error) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-20 text-center">
        <h1
          className="text-3xl font-black mb-4"
          style={{ color: "var(--text)" }}
        >
          Accuracy Data Not Available
        </h1>
        <p className="mb-6" style={{ color: "var(--text-muted)" }}>
          Run the pipeline with{" "}
          <code
            className="px-2 py-0.5 rounded text-xs font-mono"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
            }}
          >
            --advanced
          </code>{" "}
          to generate prediction accuracy tracking data.
        </p>
        <Link
          href="/"
          className="text-f1-red hover:text-f1-accent font-medium transition-colors"
        >
          Back to Home
        </Link>
      </div>
    );
  }

  if (!tracker) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-3 border-f1-red border-t-transparent rounded-full animate-spin" />
          <div className="text-lg" style={{ color: "var(--text-muted)" }}>
            Loading accuracy data...
          </div>
        </div>
      </div>
    );
  }

  const roundsWithActual = tracker.rounds.filter((r) => r.hasActual);
  const roundsWithoutActual = tracker.rounds.filter((r) => !r.hasActual);
  const hasActualResults = roundsWithActual.length > 0;
  const gpReports = tracker.gpReports || [];
  const seasonYear = getSeasonYear(season);

  const getRoundName = (round: number) => {
    if (!season) return `Round ${round}`;
    const race = season.calendar.find((r) => r.round === round);
    return race ? race.name : `Round ${round}`;
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 section-bugatti">
      <motion.div
        className="mb-16 text-center"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <p className="eyebrow mb-4">Model Performance</p>
        <h1 className="display-xl mb-4">Prediction Accuracy</h1>
        <p className="body-md text-[color:var(--muted)]">
          Track how our model predictions compare to actual race results
          across the {seasonYear} season
        </p>
      </motion.div>

      {/* Overall Season Metrics */}
      {tracker.overallAccuracy && (
        <motion.div
          className="card p-6 sm:p-8 mb-8"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <h2 className="section-heading">Season Overview</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="metric-card text-center">
              <p
                className="text-xs font-medium mb-1"
                style={{ color: "var(--text-muted)" }}
              >
                Season Accuracy
              </p>
              <p
                className="text-4xl font-black"
                style={{
                  color:
                    tracker.overallAccuracy.seasonAccuracyPct >= 70
                      ? "#00D2BE"
                      : tracker.overallAccuracy.seasonAccuracyPct >= 50
                      ? "#FF8000"
                      : "#E10600",
                }}
              >
                {tracker.overallAccuracy.seasonAccuracyPct}%
              </p>
              <p
                className="text-xs mt-1"
                style={{ color: "var(--text-muted)" }}
              >
                predictions within 3 positions
              </p>
            </div>
            <div className="metric-card text-center">
              <p
                className="text-xs font-medium mb-1"
                style={{ color: "var(--text-muted)" }}
              >
                Mean Position Error
              </p>
              <p
                className="text-4xl font-black"
                style={{
                  color:
                    tracker.overallAccuracy.seasonMeanError <= 2
                      ? "#00D2BE"
                      : tracker.overallAccuracy.seasonMeanError <= 4
                      ? "#FF8000"
                      : "#E10600",
                }}
              >
                {tracker.overallAccuracy.seasonMeanError.toFixed(1)}
              </p>
              <p
                className="text-xs mt-1"
                style={{ color: "var(--text-muted)" }}
              >
                positions average off
              </p>
            </div>
            <div className="metric-card text-center">
              <p
                className="text-xs font-medium mb-1"
                style={{ color: "var(--text-muted)" }}
              >
                Rounds Compared
              </p>
              <p
                className="text-4xl font-black"
                style={{ color: "var(--text)" }}
              >
                {tracker.overallAccuracy.roundsWithActual}
              </p>
              <p
                className="text-xs mt-1"
                style={{ color: "var(--text-muted)" }}
              >
                of {tracker.rounds.length} total rounds
              </p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Per-Round Accuracy Chart */}
      {hasActualResults && (
        <motion.div
          className="card p-6 sm:p-8 mb-8"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <h2 className="section-heading">Accuracy Per Round</h2>
          <div className="space-y-3">
            {roundsWithActual.map((r, i) => {
              const pct = r.accuracyPct ?? 0;
              const color =
                pct >= 70 ? "#00D2BE" : pct >= 50 ? "#FF8000" : "#E10600";
              return (
                <motion.div
                  key={r.round}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                >
                  <Link
                    href={`/race/${r.round}`}
                    className="flex items-center gap-4 group"
                  >
                    <div
                      className="w-36 sm:w-44 text-sm font-medium truncate group-hover:text-f1-red transition-colors"
                      style={{ color: "var(--text)" }}
                    >
                      R{r.round}:{" "}
                      {getRoundName(r.round).replace(" Grand Prix", "")}
                    </div>
                    <div className="flex-1 progress-bar h-4">
                      <div
                        className="progress-bar-fill h-full"
                        style={{ width: `${pct}%`, background: color }}
                      />
                    </div>
                    <span
                      className="text-sm font-mono w-14 text-right font-bold"
                      style={{ color }}
                    >
                      {pct}%
                    </span>
                  </Link>
                  <div className="flex gap-4 ml-36 sm:ml-44 pl-4 mt-1">
                    <span
                      className="text-xs"
                      style={{ color: "var(--text-muted)" }}
                    >
                      Mean error: {r.meanError?.toFixed(1) ?? "–"} pos
                    </span>
                    <span
                      className="text-xs"
                      style={{ color: "var(--text-muted)" }}
                    >
                      Exact: {r.exactMatches ?? 0}
                    </span>
                    <span
                      className="text-xs"
                      style={{ color: "var(--text-muted)" }}
                    >
                      Within 3: {r.within3 ?? 0}
                    </span>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      )}

      {gpReports.length > 0 && (
        <motion.div
          className="card p-6 sm:p-8 mb-8"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.25 }}
        >
          <h2 className="section-heading">Grand Prix Performance Reports</h2>
          <div className="space-y-3">
            {gpReports
              .slice()
              .sort((a, b) => b.round - a.round)
              .map((report) => (
                <Link key={`gp-report-${report.round}`} href={`/race/${report.round}`} className="block">
                  <div
                    className="p-4 rounded-xl transition-colors"
                    style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                      <p className="font-bold" style={{ color: "var(--text)" }}>
                        R{report.round}: {report.name}
                      </p>
                      <span
                        className="text-xs font-bold uppercase tracking-wider px-2 py-1 rounded-full"
                        style={{
                          background: report.winnerHit ? "rgba(0,210,190,0.12)" : "rgba(225,6,0,0.12)",
                          color: report.winnerHit ? "#00D2BE" : "#E10600",
                        }}
                      >
                        {report.winnerHit ? "Winner Called" : "Winner Miss"}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
                      <div style={{ color: "var(--text-muted)" }}>
                        Mean Error: <span style={{ color: "var(--text)" }}>{report.meanError.toFixed(2)}</span>
                      </div>
                      <div style={{ color: "var(--text-muted)" }}>
                        Exact: <span style={{ color: "var(--text)" }}>{report.exactMatches}</span>
                      </div>
                      <div style={{ color: "var(--text-muted)" }}>
                        Within 3: <span style={{ color: "var(--text)" }}>{report.within3}</span>
                      </div>
                      <div style={{ color: "var(--text-muted)" }}>
                        Podium Hits: <span style={{ color: "var(--text)" }}>{report.podiumHits}/3</span>
                      </div>
                      <div style={{ color: "var(--text-muted)" }}>
                        Compared: <span style={{ color: "var(--text)" }}>{report.comparedDrivers}</span>
                      </div>
                    </div>
                    {report.biggestMisses?.length > 0 && (
                      <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
                        Biggest miss: {report.biggestMisses[0].driver} (Pred P{report.biggestMisses[0].predicted} vs Actual P{report.biggestMisses[0].actual})
                      </p>
                    )}
                  </div>
                </Link>
              ))}
          </div>
          {tracker.generatedAt && (
            <p className="text-xs mt-4" style={{ color: "var(--text-muted)" }}>
              Last tracker sync: {new Date(tracker.generatedAt).toLocaleString()}
            </p>
          )}
        </motion.div>
      )}

      {/* Detailed Round Table */}
      <motion.div
        className="card overflow-hidden mb-8"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.3 }}
      >
        <div className="p-6 sm:p-8">
          <h2 className="section-heading">All Rounds</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {[
                  "Round",
                  "Grand Prix",
                  "Status",
                  "Accuracy",
                  "Mean Error",
                  "Exact",
                  "Within 3",
                ].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider"
                    style={{ color: "var(--text-muted)" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tracker.rounds.map((r) => {
                const statusColor = r.hasActual
                  ? "#00D2BE"
                  : "var(--text-muted)";
                const statusText = r.hasActual
                  ? "Compared"
                  : "Predicted Only";
                return (
                  <tr
                    key={r.round}
                    className="transition-colors cursor-pointer"
                    style={{ borderBottom: "1px solid var(--border)" }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background =
                        "var(--bg-card-hover)")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background = "transparent")
                    }
                    onClick={() =>
                      (window.location.href = `/race/${r.round}`)
                    }
                  >
                    <td
                      className="px-4 py-3 font-bold"
                      style={{ color: "var(--text)" }}
                    >
                      {r.round}
                    </td>
                    <td
                      className="px-4 py-3"
                      style={{ color: "var(--text)" }}
                    >
                      {getRoundName(r.round)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
                        style={{
                          background: r.hasActual
                            ? "rgba(0, 210, 190, 0.1)"
                            : "rgba(136, 136, 136, 0.1)",
                          color: statusColor,
                          border: `1px solid ${
                            r.hasActual
                              ? "rgba(0, 210, 190, 0.2)"
                              : "rgba(136, 136, 136, 0.2)"
                          }`,
                        }}
                      >
                        {statusText}
                      </span>
                    </td>
                    <td
                      className="px-4 py-3 font-mono font-bold"
                      style={{
                        color:
                          r.accuracyPct != null
                            ? r.accuracyPct >= 70
                              ? "#00D2BE"
                              : r.accuracyPct >= 50
                              ? "#FF8000"
                              : "#E10600"
                            : "var(--text-muted)",
                      }}
                    >
                      {r.accuracyPct != null ? `${r.accuracyPct}%` : "–"}
                    </td>
                    <td
                      className="px-4 py-3 font-mono"
                      style={{ color: "var(--text)" }}
                    >
                      {r.meanError != null ? r.meanError.toFixed(1) : "–"}
                    </td>
                    <td
                      className="px-4 py-3 font-mono"
                      style={{ color: "var(--text)" }}
                    >
                      {r.exactMatches ?? "–"}
                    </td>
                    <td
                      className="px-4 py-3 font-mono"
                      style={{ color: "var(--text)" }}
                    >
                      {r.within3 ?? "–"}
                    </td>
                  </tr>
                );
              })}
              {roundsWithoutActual.length === 0 &&
                tracker.rounds.length === 0 && (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-4 py-8 text-center"
                      style={{ color: "var(--text-muted)" }}
                    >
                      No prediction data available yet. Run the pipeline with
                      --advanced to generate tracking data.
                    </td>
                  </tr>
                )}
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* Awaiting Results */}
      {!hasActualResults && (
        <motion.div
          className="card p-8 text-center"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <h3
            className="text-xl font-bold mb-2"
            style={{ color: "var(--text)" }}
          >
            Awaiting Actual Results
          </h3>
          <p
            className="text-sm max-w-lg mx-auto mb-4"
            style={{ color: "var(--text-muted)" }}
          >
            Predictions have been recorded for {tracker.rounds.length} round
            {tracker.rounds.length !== 1 ? "s" : ""}. Once actual race results
            are available, this dashboard will show detailed accuracy
            comparisons including position error charts, exact match counts, and
            trend analysis.
          </p>
          <div
            className="inline-block px-4 py-2 rounded-lg text-sm font-mono"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
            }}
          >
            python gp_weekend.py --round N --phase post-race
          </div>
        </motion.div>
      )}

      {/* How Accuracy Is Measured */}
      <motion.div
        className="card p-6 sm:p-8 mt-8"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.4 }}
      >
        <h2 className="section-heading">How Accuracy Is Measured</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 text-sm">
          <div>
            <h4 className="font-bold mb-2" style={{ color: "var(--text)" }}>
              Mean Position Error
            </h4>
            <p style={{ color: "var(--text-muted)" }}>
              Average absolute difference between predicted and actual finishing
              positions across all drivers. Lower is better.
            </p>
          </div>
          <div>
            <h4 className="font-bold mb-2" style={{ color: "var(--text)" }}>
              Exact Matches
            </h4>
            <p style={{ color: "var(--text-muted)" }}>
              Number of drivers whose predicted position exactly matches their
              actual finishing position.
            </p>
          </div>
          <div>
            <h4 className="font-bold mb-2" style={{ color: "var(--text)" }}>
              Within 3 Positions
            </h4>
            <p style={{ color: "var(--text-muted)" }}>
              Percentage of drivers predicted within 3 positions of their actual
              result. This is our primary accuracy metric.
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
