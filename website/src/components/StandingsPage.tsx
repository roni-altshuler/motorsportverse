"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { StandingsData, SeasonData } from "@/types";
import { fetchStandingsData, fetchSeasonData, formatDateTime } from "@/lib/data";
import { getSeasonYear } from "@/lib/season";
import StandingsChart from "@/components/charts/StandingsChart";
import DriverBadge from "@/components/standings/DriverBadge";
import ChampionshipKPIs from "@/components/standings/ChampionshipKPIs";
import LoadingTire from "@/components/ui/LoadingTire";
import { motion } from "framer-motion";

type Tab = "drivers" | "constructors" | "wdc";

function parseTab(value: string | null): Tab {
  if (value === "constructors" || value === "wdc") {
    return value;
  }
  return "drivers";
}

export default function StandingsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [data, setData] = useState<StandingsData | null>(null);
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [error, setError] = useState(false);
  const activeTab = parseTab(searchParams.get("tab"));

  useEffect(() => {
    fetchStandingsData().then(setData).catch(() => setError(true));
    fetchSeasonData().then(setSeason).catch(() => {});
  }, []);

  if (error) {
    return (
      <div className="max-w-6xl mx-auto px-4 section-bugatti text-center">
        <h1 className="display-lg mb-6">Standings Not Available</h1>
        <p className="body-md text-[color:var(--muted)]">
          No standings data has been generated yet.
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <LoadingTire label="Loading standings" />
      </div>
    );
  }

  const completedRounds = season?.completedRounds || [];
  const seasonYear = getSeasonYear(season);
  const totalRounds = season?.totalRounds ?? 22;
  const handleTabChange = (tab: Tab) => {
    const params = new URLSearchParams(searchParams.toString());
    if (tab === "drivers") {
      params.delete("tab");
    } else {
      params.set("tab", tab);
    }
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 section-bugatti">
      <div className="mb-16 text-center">
        <p className="eyebrow mb-4">Championship</p>
        <h1 className="display-xl mb-4">{seasonYear} Standings</h1>
        <p className="body-md text-[color:var(--muted)]">
          Updated through Round {data.lastUpdatedRound} of {totalRounds}
        </p>
        <div className="progress-bar w-48 mx-auto mt-6">
          <div
            className="progress-bar-fill"
            style={{ width: `${(data.lastUpdatedRound / totalRounds) * 100}%` }}
          />
        </div>
      </div>

      {/* ━━━ Cinematic championship KPI strip ━━━ */}
      <ChampionshipKPIs drivers={data.drivers} />

      <div className="data-freshness-card mb-8">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em]" style={{ color: "#9FB0C8" }}>Data Freshness</p>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            {data.statusNote || "Standings are refreshed from the configured official data pipeline when the export workflow runs."}
          </p>
        </div>
        <div className="data-freshness-meta">
          <span>{data.source || "Standings data"}</span>
          <span>{formatDateTime(data.lastUpdated)}</span>
        </div>
      </div>

      {/* Tab Navigation with sliding active underline */}
      <div className="flex justify-center gap-2 mb-10 relative">
        {(
          [
            { key: "drivers" as Tab, label: "Drivers" },
            { key: "constructors" as Tab, label: "Constructors" },
            { key: "wdc" as Tab, label: "Who Can Still Win?" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.key}
            onClick={() => handleTabChange(tab.key)}
            className={`tab-button relative ${activeTab === tab.key ? "active" : ""}`}
          >
            {tab.label}
            {activeTab === tab.key && (
              <motion.span
                layoutId="standings-underline"
                className="absolute left-3 right-3 -bottom-1 h-0.5 rounded-full"
                style={{
                  background: "var(--accent-live)",
                  boxShadow: "0 0 10px var(--accent-live)",
                }}
              />
            )}
          </button>
        ))}
      </div>

      {/* Drivers Tab */}
      {activeTab === "drivers" && (
        <div className="space-y-8">
          {/* ━━━ PADDOCK BADGE WALL — top 8 drivers as cinematic cards ━━━ */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {data.drivers.slice(0, 8).map((d, i) => (
              <DriverBadge
                key={d.driver}
                index={i}
                position={d.position}
                driver={d.driver}
                driverFullName={d.driverFullName}
                team={d.team}
                teamColor={d.teamColor || "var(--accent-live)"}
                points={d.points}
                wins={d.wins}
                podiums={d.podiums}
              />
            ))}
          </div>

          {completedRounds.length > 0 && (
            <div className="card p-6">
              <h3 className="section-heading">Points Progression</h3>
              <StandingsChart
                data={data.drivers.slice(0, 10)}
                rounds={completedRounds}
              />
            </div>
          )}

          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table
                className="w-full text-sm"
                aria-label="Driver championship standings"
              >
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {[
                      { label: "POS", sort: "ascending" as const },
                      { label: "", sort: undefined },
                      { label: "DRIVER", sort: undefined },
                      { label: "TEAM", sort: undefined },
                      // The table is pre-sorted by points descending — surface
                      // that via aria-sort so screen-reader users know.
                      { label: "PTS", sort: "descending" as const },
                      { label: "WINS", sort: undefined },
                      { label: "PODIUMS", sort: undefined },
                    ].map((h) => (
                      <th
                        key={h.label}
                        scope="col"
                        aria-sort={h.sort}
                        className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider"
                        style={{ color: "var(--text-muted)" }}
                      >
                        {h.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.drivers.map((d) => {
                    const maxPts = data.drivers[0]?.points || 1;
                    return (
                      <tr
                        key={d.driver}
                        className="transition-colors"
                        style={{ borderBottom: "1px solid var(--border)" }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.background =
                            "var(--bg-card-hover)")
                        }
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.background = "transparent")
                        }
                      >
                        <td className="px-4 py-3">
                          <span
                            className={`position-badge ${
                              d.position === 1
                                ? "p1"
                                : d.position === 2
                                ? "p2"
                                : d.position === 3
                                ? "p3"
                                : d.position <= 10
                                ? "points"
                                : "no-points"
                            }`}
                          >
                            {d.position}
                          </span>
                        </td>
                        <td className="px-1 py-3">
                          <div
                            className="w-1 h-8 rounded"
                            style={{ backgroundColor: d.teamColor }}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-bold" style={{ color: "var(--text)" }}>
                            {d.driver}
                          </span>
                          <span
                            className="ml-2 text-xs hidden sm:inline"
                            style={{ color: "var(--text-muted)" }}
                          >
                            {d.driverFullName}
                          </span>
                        </td>
                        <td className="px-4 py-3" style={{ color: "var(--text-muted)" }}>
                          {d.team}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <span
                              className="font-black text-lg"
                              style={{ color: "var(--text)" }}
                            >
                              {d.points}
                            </span>
                            <div className="hidden sm:block progress-bar w-24 h-1.5">
                              <div
                                className="progress-bar-fill"
                                style={{
                                  width: `${(d.points / maxPts) * 100}%`,
                                  background: d.teamColor,
                                }}
                              />
                            </div>
                          </div>
                        </td>
                        <td
                          className="px-4 py-3 text-center font-bold"
                          style={{
                            color: d.wins > 0 ? "#FFD700" : "var(--text-muted)",
                          }}
                        >
                          {d.wins}
                        </td>
                        <td
                          className="px-4 py-3 text-center"
                          style={{ color: "var(--text-muted)" }}
                        >
                          {d.podiums}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Constructors Tab */}
      {activeTab === "constructors" && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.constructors.slice(0, 6).map((c) => {
              const maxPts = data.constructors[0]?.points || 1;
              return (
                <div key={c.team} className="card p-5 relative overflow-hidden">
                  <div
                    className="absolute top-0 left-0 w-full h-1"
                    style={{ background: c.teamColor }}
                  />
                  <div className="flex items-center justify-between mb-3">
                    <span
                      className={`position-badge ${
                        c.position === 1
                          ? "p1"
                          : c.position === 2
                          ? "p2"
                          : c.position === 3
                          ? "p3"
                          : "points"
                      }`}
                    >
                      P{c.position}
                    </span>
                    <span
                      className="text-2xl font-black"
                      style={{ color: "var(--text)" }}
                    >
                      {c.points} pts
                    </span>
                  </div>
                  <h3
                    className="font-bold text-lg mb-1"
                    style={{ color: "var(--text)" }}
                  >
                    {c.team}
                  </h3>
                  <p className="text-sm mb-3" style={{ color: "var(--text-muted)" }}>
                    {c.drivers.join(" • ")}
                  </p>
                  <div className="progress-bar h-2">
                    <div
                      className="progress-bar-fill"
                      style={{
                        width: `${(c.points / maxPts) * 100}%`,
                        background: c.teamColor,
                      }}
                    />
                  </div>
                  <div
                    className="flex justify-between mt-3 text-xs"
                    style={{ color: "var(--text-muted)" }}
                  >
                    <span>
                      {c.wins} win{c.wins !== 1 ? "s" : ""}
                    </span>
                    <span>{Math.round((c.points / maxPts) * 100)}% of leader</span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table
                className="w-full text-sm"
                aria-label="Constructor championship standings"
              >
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {[
                      { label: "POS", sort: "ascending" as const },
                      { label: "", sort: undefined },
                      { label: "TEAM", sort: undefined },
                      { label: "DRIVERS", sort: undefined },
                      { label: "PTS", sort: "descending" as const },
                      { label: "WINS", sort: undefined },
                    ].map((h) => (
                      <th
                        key={h.label}
                        scope="col"
                        aria-sort={h.sort}
                        className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider"
                        style={{ color: "var(--text-muted)" }}
                      >
                        {h.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.constructors.map((c) => (
                    <tr
                      key={c.team}
                      className="transition-colors"
                      style={{ borderBottom: "1px solid var(--border)" }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.background =
                          "var(--bg-card-hover)")
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.background = "transparent")
                      }
                    >
                      <td className="px-4 py-3">
                        <span
                          className={`position-badge ${
                            c.position === 1
                              ? "p1"
                              : c.position === 2
                              ? "p2"
                              : c.position === 3
                              ? "p3"
                              : "points"
                          }`}
                        >
                          {c.position}
                        </span>
                      </td>
                      <td className="px-1 py-3">
                        <div
                          className="w-1 h-8 rounded"
                          style={{ backgroundColor: c.teamColor }}
                        />
                      </td>
                      <td
                        className="px-4 py-3 font-bold"
                        style={{ color: "var(--text)" }}
                      >
                        {c.team}
                      </td>
                      <td className="px-4 py-3" style={{ color: "var(--text-muted)" }}>
                        {c.drivers.join(", ")}
                      </td>
                      <td
                        className="px-4 py-3 font-black text-lg"
                        style={{ color: "var(--text)" }}
                      >
                        {c.points}
                      </td>
                      <td
                        className="px-4 py-3 text-center font-bold"
                        style={{
                          color: c.wins > 0 ? "#FFD700" : "var(--text-muted)",
                        }}
                      >
                        {c.wins}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* WDC Possibility Tab */}
      {activeTab === "wdc" && (
        <div className="space-y-6">
          <div className="text-center mb-6">
            <h2
              className="text-xl font-bold mb-2"
              style={{ color: "var(--text)" }}
            >
              Who Can Still Win the Championship?
            </h2>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Based on maximum possible points with{" "}
              {Math.max(totalRounds - data.lastUpdatedRound, 0)} rounds remaining
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.wdcPossibility.map((w) => {
              const leaderPts = data.drivers[0]?.points || 0;
              const deficit = leaderPts - w.currentPoints;
              return (
                <div
                  key={w.driver}
                  className="card p-5 relative overflow-hidden"
                  style={
                    w.canStillWin
                      ? { border: "1px solid rgba(0, 210, 190, 0.3)" }
                      : { opacity: 0.6 }
                  }
                >
                  <div
                    className="absolute top-0 left-0 w-full h-1"
                    style={{ background: w.teamColor }}
                  />
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p
                        className="font-black text-lg"
                        style={{ color: "var(--text)" }}
                      >
                        {w.driver}
                      </p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                        {w.team}
                      </p>
                    </div>
                    {w.canStillWin ? (
                      <span
                        className="px-3 py-1 rounded-full text-xs font-bold"
                        style={{
                          background: "rgba(0, 210, 190, 0.15)",
                          color: "#00D2BE",
                        }}
                      >
                        IN CONTENTION
                      </span>
                    ) : (
                      <span
                        className="px-3 py-1 rounded-full text-xs font-bold"
                        style={{
                          background: "var(--bg-surface)",
                          color: "var(--text-muted)",
                        }}
                      >
                        ELIMINATED
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-center">
                    <div className="metric-card">
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                        Current
                      </p>
                      <p
                        className="font-black text-lg"
                        style={{ color: "var(--text)" }}
                      >
                        {w.currentPoints}
                      </p>
                    </div>
                    <div className="metric-card">
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                        Max Possible
                      </p>
                      <p
                        className="font-black text-lg"
                        style={{
                          color: w.canStillWin
                            ? "#00D2BE"
                            : "var(--text-muted)",
                        }}
                      >
                        {w.maxPossiblePoints}
                      </p>
                    </div>
                  </div>
                  {deficit > 0 && (
                    <p
                      className="text-xs text-center mt-3"
                      style={{ color: "var(--text-muted)" }}
                    >
                      {deficit} points behind leader
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
