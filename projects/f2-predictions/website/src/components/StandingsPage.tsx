"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";

import ProgressionChart, {
  type ProgressionSeries,
} from "@/components/charts/ProgressionChart";
import DriverBadge from "@/components/standings/DriverBadge";
import TeamBadge from "@/components/standings/TeamBadge";
import DriverPortrait from "@/components/standings/DriverPortrait";
import StandingsHeroPodium from "@/components/standings/StandingsHeroPodium";
import ChampionshipKPIs from "@/components/standings/ChampionshipKPIs";
import WhoCanWinLanes from "@/components/standings/WhoCanWinLanes";
import ConstructorsForecastLanes from "@/components/standings/ConstructorsForecastLanes";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { teamColor as teamColorFor } from "@/lib/teams";
import type {
  DriverStanding,
  SeasonAccuracy,
  TeamStanding,
  TitleOdds,
} from "@/types/f2";

type Tab = "drivers" | "teams" | "wdc";

function parseTab(value: string | null): Tab {
  if (value === "teams" || value === "wdc") return value;
  if (value === "constructors") return "teams";
  if (value === "whocanwin") return "wdc";
  return "drivers";
}

export interface StandingsPageProps {
  season: number;
  completedRounds: number;
  totalRounds: number;
  lastUpdatedRound: number;
  drivers: DriverStanding[];
  teams: TeamStanding[];
  championship: TitleOdds[];
  seasonAccuracy?: SeasonAccuracy;
  rounds: number[];
  driverSeries: ProgressionSeries[];
  teamSeries: ProgressionSeries[];
}

export default function StandingsPage(props: StandingsPageProps) {
  return (
    <Suspense fallback={null}>
      <StandingsPageInner {...props} />
    </Suspense>
  );
}

function StandingsPageInner({
  season,
  completedRounds,
  totalRounds,
  lastUpdatedRound,
  drivers,
  teams,
  championship,
  seasonAccuracy,
  rounds,
  driverSeries,
  teamSeries,
}: StandingsPageProps) {
  const searchParams = useSearchParams();
  const activeTab = parseTab(searchParams.get("tab"));
  const remainingRounds = Math.max(0, totalRounds - completedRounds);

  const driverLegend = (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {drivers.slice(0, driverSeries.length).map((d) => (
        <span key={d.code} className="inline-flex items-center gap-1.5">
          <DriverPortrait
            driver={d.code}
            driverFullName={d.name}
            team={d.team}
            teamColor={d.teamColor || teamColorFor(d.team)}
            headshotUrl={d.headshotUrl}
            size={18}
          />
          <span style={{ color: "var(--text)" }}>{d.code}</span>
        </span>
      ))}
    </div>
  );

  const teamLegend = (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {teamSeries.map((s) => (
        <span key={s.key} className="inline-flex items-center gap-1.5">
          <span
            className="inline-block w-3 h-3 rounded-full"
            style={{ background: s.color }}
            aria-hidden
          />
          <span style={{ color: "var(--text)" }}>{s.label}</span>
        </span>
      ))}
    </div>
  );

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 section-bugatti">
      <div className="mb-16 text-center">
        <p className="eyebrow mb-4">Formula 2 · Championship</p>
        <h1 className="display-xl mb-4">{season} Standings</h1>
        <p className="body-md text-[color:var(--body)] max-w-xl mx-auto">
          Who is winning the title — and where the season is projected to go from here.
        </p>
        <p className="body-sm text-[color:var(--muted)] mt-2">
          Updated through Round {lastUpdatedRound} of {totalRounds}
        </p>
        <div className="progress-bar w-48 mx-auto mt-6">
          <div
            className="progress-bar-fill"
            style={{ width: `${(lastUpdatedRound / totalRounds) * 100}%` }}
          />
        </div>
      </div>

      <ChampionshipKPIs
        drivers={drivers}
        championship={championship}
        roundsRemaining={remainingRounds}
        seasonAccuracy={seasonAccuracy}
      />

      {/* Tab navigation with sliding active underline */}
      <div className="flex justify-center gap-2 mb-10 relative">
        {(
          [
            { key: "drivers" as Tab, label: "Drivers", href: "/standings?tab=drivers" },
            { key: "teams" as Tab, label: "Teams", href: "/standings?tab=teams" },
            { key: "wdc" as Tab, label: "Who Can Still Win?", href: "/standings?tab=wdc" },
          ] as const
        ).map((tab) => (
          <a
            key={tab.key}
            href={tab.href}
            className={`tab-button relative ${activeTab === tab.key ? "active" : ""}`}
          >
            {tab.label}
            {activeTab === tab.key && (
              <motion.span
                layoutId="standings-underline"
                className="absolute left-3 right-3 -bottom-1 h-0.5 rounded-full"
                style={{ background: "var(--accent)", boxShadow: "0 0 10px var(--accent)" }}
              />
            )}
          </a>
        ))}
      </div>

      {/* Drivers tab */}
      {activeTab === "drivers" && (
        <div className="space-y-8">
          <StandingsHeroPodium drivers={drivers} />

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {drivers.slice(3, 8).map((d, i) => (
              <DriverBadge
                key={d.code}
                index={i}
                position={d.position}
                driver={d.code}
                driverFullName={d.name}
                team={d.team}
                teamColor={d.teamColor || teamColorFor(d.team)}
                points={d.points}
                wins={d.wins}
                podiums={d.podiums}
                headshotUrl={d.headshotUrl}
              />
            ))}
          </div>

          {rounds.length > 0 && driverSeries.length > 0 && (
            <div className="card p-6">
              <h3 className="section-heading">Points Progression</h3>
              <ProgressionChart
                series={driverSeries}
                rounds={rounds}
                totalRounds={totalRounds}
                legend={driverLegend}
              />
            </div>
          )}

          <DriversTable drivers={drivers} />
        </div>
      )}

      {/* Teams tab */}
      {activeTab === "teams" && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {teams.slice(0, 6).map((t) => {
              const maxPts = teams[0]?.points || 1;
              const color = t.teamColor || teamColorFor(t.team);
              return (
                <div
                  key={t.team}
                  data-team={t.team}
                  className="card hover-lift-premium p-5 relative overflow-hidden"
                >
                  <div
                    className="absolute top-0 left-0 w-full h-1"
                    style={{ background: color }}
                  />
                  <div className="flex items-center justify-between mb-3">
                    <span
                      className={`position-badge ${
                        t.position === 1
                          ? "p1"
                          : t.position === 2
                          ? "p2"
                          : t.position === 3
                          ? "p3"
                          : "points"
                      }`}
                    >
                      P{t.position}
                    </span>
                    <span className="text-2xl font-black font-mono tabular-nums text-[color:var(--ink)]">
                      <NumberTicker value={t.points} /> pts
                    </span>
                  </div>
                  <div className="flex items-start gap-4 mb-3">
                    <TeamBadge team={t.team} teamColor={color} size={64} variant="card" />
                    <div className="min-w-0 flex-1">
                      <h3 className="title-md mb-1 text-[color:var(--ink)]">{t.team}</h3>
                      <p className="text-sm text-[color:var(--text-muted)]">
                        {t.wins} win{t.wins !== 1 ? "s" : ""} · {t.podiums} podium
                        {t.podiums !== 1 ? "s" : ""}
                      </p>
                    </div>
                  </div>
                  <div className="progress-bar h-2">
                    <div
                      className="progress-bar-fill"
                      style={{ width: `${(t.points / maxPts) * 100}%`, background: color }}
                    />
                  </div>
                  <div className="flex justify-between mt-3 text-xs text-[color:var(--text-muted)]">
                    <span>P{t.position}</span>
                    <span>{Math.round((t.points / maxPts) * 100)}% of leader</span>
                  </div>
                </div>
              );
            })}
          </div>

          {rounds.length > 0 && teamSeries.length > 0 && (
            <div className="card p-6">
              <h3 className="section-heading">Team Points Progression</h3>
              <ProgressionChart
                series={teamSeries}
                rounds={rounds}
                totalRounds={totalRounds}
                legend={teamLegend}
              />
            </div>
          )}

          <TeamsTable teams={teams} />

          <div className="space-y-3">
            <h3 className="section-heading">Teams — Still in the Fight</h3>
            <ConstructorsForecastLanes
              teams={teams}
              remainingRounds={remainingRounds}
              completedRounds={completedRounds}
            />
          </div>
        </div>
      )}

      {/* Who can still win tab */}
      {activeTab === "wdc" && (
        <div className="space-y-10">
          {rounds.length > 0 && driverSeries.length > 0 && (
            <div className="card p-6">
              <h3 className="section-heading">Drivers — Points Projection</h3>
              <ProgressionChart
                series={driverSeries}
                rounds={rounds}
                totalRounds={totalRounds}
                legend={driverLegend}
              />
            </div>
          )}
          <WhoCanWinLanes championship={championship} remainingRounds={remainingRounds} />

          <div className="space-y-6">
            <div>
              <h2 className="display-md mb-2">Teams Title Race</h2>
              <p className="body-md text-[color:var(--text-muted)] max-w-2xl">
                Team points standings and who can still mathematically reach the leader over the{" "}
                {remainingRounds} remaining round{remainingRounds === 1 ? "" : "s"}.
              </p>
            </div>
            {rounds.length > 0 && teamSeries.length > 0 && (
              <div className="card p-6">
                <h3 className="section-heading">Teams — Points Projection</h3>
                <ProgressionChart
                  series={teamSeries}
                  rounds={rounds}
                  totalRounds={totalRounds}
                  legend={teamLegend}
                />
              </div>
            )}
            <ConstructorsForecastLanes
              teams={teams}
              remainingRounds={remainingRounds}
              completedRounds={completedRounds}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function DriversTable({ drivers }: { drivers: DriverStanding[] }) {
  const maxPts = drivers[0]?.points || 1;
  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm" aria-label="Driver championship standings">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {[
                { label: "POS", sort: "ascending" as const },
                { label: "", sort: undefined },
                { label: "", sort: undefined },
                { label: "DRIVER", sort: undefined },
                { label: "TEAM", sort: undefined },
                { label: "PTS", sort: "descending" as const },
                { label: "WINS", sort: undefined },
                { label: "PODIUMS", sort: undefined },
              ].map((h, idx) => (
                <th
                  key={`${h.label}-${idx}`}
                  scope="col"
                  aria-sort={h.sort}
                  className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider text-[color:var(--text-muted)]"
                >
                  {h.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {drivers.map((d) => {
              const color = d.teamColor || teamColorFor(d.team);
              return (
                <tr key={d.code} style={{ borderBottom: "1px solid var(--border)" }}>
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
                    <div className="w-1 h-8 rounded" style={{ backgroundColor: color }} />
                  </td>
                  <td className="px-2 py-2">
                    <DriverPortrait
                      driver={d.code}
                      driverFullName={d.name}
                      team={d.team}
                      teamColor={color}
                      headshotUrl={d.headshotUrl}
                      size={40}
                    />
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-bold text-[color:var(--ink)]">{d.code}</span>
                    <span className="ml-2 text-xs hidden sm:inline text-[color:var(--text-muted)]">
                      {d.name}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[color:var(--text-muted)]">
                    <span className="inline-flex items-center gap-2">
                      <TeamBadge team={d.team} teamColor={color} size={26} />
                      <span>{d.team}</span>
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <span className="font-black text-lg font-mono tabular-nums text-[color:var(--ink)]">
                        <NumberTicker value={d.points} />
                      </span>
                      <div className="hidden sm:block progress-bar w-24 h-1.5">
                        <div
                          className="progress-bar-fill"
                          style={{ width: `${(d.points / maxPts) * 100}%`, background: color }}
                        />
                      </div>
                    </div>
                  </td>
                  <td
                    className="px-4 py-3 text-center font-bold"
                    style={{ color: d.wins > 0 ? "var(--accent-podium-1)" : "var(--text-muted)" }}
                  >
                    {d.wins}
                  </td>
                  <td className="px-4 py-3 text-center text-[color:var(--text-muted)]">
                    {d.podiums}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TeamsTable({ teams }: { teams: TeamStanding[] }) {
  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm" aria-label="Team championship standings">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {[
                { label: "POS", sort: "ascending" as const },
                { label: "", sort: undefined },
                { label: "TEAM", sort: undefined },
                { label: "PTS", sort: "descending" as const },
                { label: "WINS", sort: undefined },
                { label: "PODIUMS", sort: undefined },
              ].map((h, idx) => (
                <th
                  key={`${h.label}-${idx}`}
                  scope="col"
                  aria-sort={h.sort}
                  className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider text-[color:var(--text-muted)]"
                >
                  {h.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {teams.map((t) => {
              const color = t.teamColor || teamColorFor(t.team);
              return (
                <tr key={t.team} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3">
                    <span
                      className={`position-badge ${
                        t.position === 1
                          ? "p1"
                          : t.position === 2
                          ? "p2"
                          : t.position === 3
                          ? "p3"
                          : "points"
                      }`}
                    >
                      {t.position}
                    </span>
                  </td>
                  <td className="px-1 py-3">
                    <div className="w-1 h-8 rounded" style={{ backgroundColor: color }} />
                  </td>
                  <td className="px-4 py-3 font-bold text-[color:var(--ink)]">
                    <span className="inline-flex items-center gap-2">
                      <TeamBadge team={t.team} teamColor={color} size={26} />
                      <span>{t.team}</span>
                    </span>
                  </td>
                  <td className="px-4 py-3 font-black text-lg text-[color:var(--ink)]">{t.points}</td>
                  <td
                    className="px-4 py-3 text-center font-bold"
                    style={{ color: t.wins > 0 ? "var(--accent-podium-1)" : "var(--text-muted)" }}
                  >
                    {t.wins}
                  </td>
                  <td className="px-4 py-3 text-center text-[color:var(--text-muted)]">
                    {t.podiums}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
