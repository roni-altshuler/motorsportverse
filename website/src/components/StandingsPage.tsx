"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { StandingsData, SeasonData, ChampionshipForecast } from "@/types";
import {
  fetchStandingsData,
  fetchSeasonData,
  fetchChampionshipForecast,
  formatDateTime,
} from "@/lib/data";
import { getSeasonYear } from "@/lib/season";
import StandingsChart from "@/components/charts/StandingsChart";
import DriverBadge from "@/components/standings/DriverBadge";
import ChampionshipKPIs from "@/components/standings/ChampionshipKPIs";
import StandingsHeroPodium from "@/components/standings/StandingsHeroPodium";
import DriverPortrait from "@/components/standings/DriverPortrait";
import TeamBadge from "@/components/standings/TeamBadge";
import WhoCanWinLanes from "@/components/standings/WhoCanWinLanes";
import ConstructorsForecastLanes from "@/components/standings/ConstructorsForecastLanes";
import { NumberTicker } from "@/components/magicui/number-ticker";
import LoadingTire from "@/components/ui/LoadingTire";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { motion } from "framer-motion";

type Tab = "drivers" | "constructors" | "wdc";

function parseTab(value: string | null): Tab {
  if (value === "constructors" || value === "wdc") {
    return value;
  }
  return "drivers";
}

function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "Updated recently";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "Updated recently";
  const delta = Math.max(0, Date.now() - then);
  const m = Math.round(delta / 60000);
  if (m < 1) return "Updated just now";
  if (m < 60) return `Updated ${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `Updated ${h}h ago`;
  const d = Math.round(h / 24);
  return `Updated ${d}d ago`;
}

export default function StandingsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [data, setData] = useState<StandingsData | null>(null);
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [forecast, setForecast] = useState<ChampionshipForecast | null>(null);
  const [error, setError] = useState(false);
  const activeTab = parseTab(searchParams.get("tab"));

  useEffect(() => {
    fetchStandingsData().then(setData).catch(() => setError(true));
    fetchSeasonData().then(setSeason).catch(() => {});
    fetchChampionshipForecast().then(setForecast).catch(() => {});
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
        <div className="data-freshness-status">
          <span className="data-freshness-dot" aria-hidden />
          <span className="data-freshness-eyebrow">Data Freshness · Live</span>
          <span className="data-freshness-note">Standings sync with the latest official classification</span>
        </div>
        <div className="data-freshness-meta">
          <span>{formatRelativeTime(data.lastUpdated)}</span>
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
          {/* ━━━ HERO PODIUM — F1.com signature 3-card row with portraits ━━━ */}
          <StandingsHeroPodium drivers={data.drivers} />

          {/* ━━━ Compact 4-up grid of P4–P8 ━━━ */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {data.drivers.slice(3, 8).map((d, i) => (
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
                headshotUrl={d.headshotUrl}
              />
            ))}
          </div>

          {completedRounds.length > 0 && (
            <div className="card p-6">
              <h3 className="section-heading">Points Progression</h3>
              <StandingsChart
                data={data.drivers.slice(0, 10)}
                rounds={completedRounds}
                totalRounds={totalRounds}
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
                      { label: "", sort: undefined },
                      { label: "DRIVER", sort: undefined },
                      { label: "TEAM", sort: undefined },
                      // The table is pre-sorted by points descending — surface
                      // that via aria-sort so screen-reader users know.
                      { label: "PTS", sort: "descending" as const },
                      { label: "WINS", sort: undefined },
                      { label: "PODIUMS", sort: undefined },
                    ].map((h, idx) => (
                      <th
                        key={`${h.label}-${idx}`}
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
                        <td className="px-2 py-2">
                          <DriverPortrait
                            driver={d.driver}
                            driverFullName={d.driverFullName}
                            team={d.team}
                            teamColor={d.teamColor}
                            headshotUrl={d.headshotUrl}
                            size={40}
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
                          <span className="inline-flex items-center gap-2">
                            <TeamBadge team={d.team} teamColor={d.teamColor} size={26} />
                            <span>{d.team}</span>
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <span
                              className="font-black text-lg font-mono font-tabular"
                              style={{ color: "var(--text)" }}
                            >
                              <NumberTicker value={d.points} />
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
                <div
                  key={c.team}
                  data-team={c.team}
                  className="card hover-lift-premium p-5 relative overflow-hidden"
                  style={{
                    background:
                      "color-mix(in srgb, var(--team-color, var(--surface-card)) 6%, var(--surface-card))",
                  }}
                >
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
                      className="text-2xl font-black font-mono font-tabular"
                      style={{ color: "var(--text)" }}
                    >
                      <NumberTicker value={c.points} /> pts
                    </span>
                  </div>
                  <div className="flex items-start gap-4 mb-3">
                    <TeamBadge
                      team={c.team}
                      teamColor={c.teamColor}
                      size={84}
                      variant="card"
                    />
                    <div className="min-w-0 flex-1">
                      <h3
                        className="font-bold text-lg [font-family:var(--font-display)] uppercase tracking-[0.05em] mb-1"
                        style={{ color: "var(--text)" }}
                      >
                        {c.team}
                      </h3>
                      <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                        {c.drivers.join(" • ")}
                      </p>
                    </div>
                  </div>
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

      {/* Title race outlook — WDC + WCC side-by-side so users can
          compare driver vs team championship races on the same page. */}
      {activeTab === "wdc" && (
        <ErrorBoundary label="WhoCanWinLanes">
          <div className="space-y-10">
            <WhoCanWinLanes standings={data} forecast={forecast} />
            <div>
              <h2 className="display-md mb-2">Constructors Title Race</h2>
              <p className="body-md text-[color:var(--text-muted)] max-w-2xl mb-6">
                Driver projections aggregated by team. Mercedes vs Ferrari vs
                McLaren over the {forecast?.remainingRounds ?? 0} remaining
                round{forecast?.remainingRounds === 1 ? "" : "s"}.
              </p>
              <ConstructorsForecastLanes forecast={forecast} />
            </div>
          </div>
        </ErrorBoundary>
      )}
    </div>
  );
}
