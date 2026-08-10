"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";

import ShareButton from "@/components/ShareButton";

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
import { useSeasonWrcData } from "@/lib/wrcClient";
import { teamColor as teamColorFor } from "@/lib/teams";
import type {
  DriverStanding,
  WrcData,
  SeasonAccuracy,
  ManufacturerStanding,
  TitleOdds,
} from "@/types/wrc";

type Tab = "drivers" | "teams" | "wdc";

function parseTab(value: string | null): Tab {
  if (value === "teams" || value === "wdc") return value;
  if (value === "manufacturers") return "teams";
  if (value === "whocanwin") return "wdc";
  return "drivers";
}

export interface StandingsPageProps {
  season: number;
  completedRounds: number;
  totalRounds: number;
  lastUpdatedRound: number;
  drivers: DriverStanding[];
  manufacturers: ManufacturerStanding[];
  championship: TitleOdds[];
  seasonAccuracy?: SeasonAccuracy;
  rounds: number[];
  driverSeries: ProgressionSeries[];
}

export default function StandingsPage(props: StandingsPageProps) {
  return (
    <Suspense fallback={null}>
      <StandingsPageInner {...props} />
    </Suspense>
  );
}

// Rebuild the props the server page bakes at build time, from an archived
// season's wrc.json (client-side). Uses each crew row's exported pointsHistory —
// the same fallback the server page's series builder uses. Manufacturers carry
// no history, so there is no manufacturer progression series to rebuild.
function propsFromSeasonData(data: WrcData): StandingsPageProps {
  const TOP_DRIVERS = 6;
  const projByCode: Record<string, number> = {};
  for (const c of data.championship) {
    projByCode[c.code] = c.projMean;
  }
  const rounds = data.calendar.filter((c) => c.completed).map((c) => c.round);
  const driverSeries: ProgressionSeries[] = data.driverStandings
    .slice(0, TOP_DRIVERS)
    .map((d) => ({
      key: d.code,
      label: d.code,
      color: d.teamColor || teamColorFor(d.team),
      history: d.pointsHistory ?? [],
      projectedTotal: projByCode[d.code] ?? d.points,
    }))
    .filter((s) => s.history.length > 0);
  return {
    season: data.season,
    completedRounds: data.completedRounds,
    totalRounds: data.totalRounds,
    lastUpdatedRound: data.lastUpdatedRound ?? data.completedRounds,
    drivers: data.driverStandings,
    manufacturers: data.manufacturerStandings,
    championship: data.championship,
    seasonAccuracy: data.seasonAccuracy,
    rounds,
    driverSeries,
  };
}

function StandingsPageInner(baked: StandingsPageProps) {
  // Multi-season: baked props carry the CURRENT season (static export); an
  // archived season selected via the SeasonSwitcher overlays them client-side.
  const { data: seasonData, isArchived } = useSeasonWrcData();
  const {
    season,
    completedRounds,
    totalRounds,
    lastUpdatedRound,
    drivers,
    manufacturers,
    championship,
    seasonAccuracy,
    rounds,
    driverSeries,
  } = isArchived && seasonData ? propsFromSeasonData(seasonData) : baked;
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
            size={18}
          />
          <span style={{ color: "var(--text)" }}>{d.code}</span>
        </span>
      ))}
    </div>
  );

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 section-bugatti">
      <div className="mb-16 text-center">
        <p className="eyebrow mb-4">WRC · Championship</p>
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
        <ShareButton
          title={`${season} WRC Championship Standings`}
          text={`See who's winning the ${season} WRC title — full crew & manufacturer standings, plus who can still take it.`}
          className="mt-6 justify-center"
        />
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
            { key: "drivers" as Tab, label: "Crews", href: "/standings?tab=drivers" },
            { key: "teams" as Tab, label: "Manufacturers", href: "/standings?tab=teams" },
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

      {/* Crews tab */}
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

      {/* Manufacturers tab — WRC publishes only current manufacturer points
          (no wins, podiums, history or projection), so this is a clean points
          standings: the points-share lanes plus a rank/manufacturer/points table. */}
      {activeTab === "teams" && (
        <div className="space-y-8">
          <div className="space-y-3">
            <h3 className="section-heading">Manufacturers — Points Share</h3>
            <ConstructorsForecastLanes teams={manufacturers} />
          </div>

          <TeamsTable teams={manufacturers} />
        </div>
      )}

      {/* Who can still win tab — crews only (manufacturers have no projection) */}
      {activeTab === "wdc" && (
        <div className="space-y-10">
          {rounds.length > 0 && driverSeries.length > 0 && (
            <div className="card p-6">
              <h3 className="section-heading">Crews — Points Projection</h3>
              <ProgressionChart
                series={driverSeries}
                rounds={rounds}
                totalRounds={totalRounds}
                legend={driverLegend}
              />
            </div>
          )}
          <WhoCanWinLanes championship={championship} remainingRounds={remainingRounds} />
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
        <table className="w-full text-sm" aria-label="Crew championship standings">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {[
                { label: "POS", sort: "ascending" as const },
                { label: "", sort: undefined },
                { label: "", sort: undefined },
                { label: "CREW", sort: undefined },
                { label: "MANUFACTURER", sort: undefined },
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
                    <Link
                      href={`/driver/${d.code}`}
                      aria-label={`${d.name} driver profile`}
                      className="inline-block transition-opacity hover:opacity-80"
                    >
                      <DriverPortrait
                        driver={d.code}
                        driverFullName={d.name}
                        team={d.team}
                        teamColor={color}
                        size={40}
                      />
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/driver/${d.code}`}
                      className="group inline-flex items-baseline transition-colors hover:text-[color:var(--accent)]"
                    >
                      <span className="font-bold text-[color:var(--ink)] group-hover:text-[color:var(--accent)]">
                        {d.code}
                      </span>
                      <span className="ml-2 text-xs hidden sm:inline text-[color:var(--text-muted)]">
                        {d.name}
                      </span>
                    </Link>
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

function TeamsTable({ teams }: { teams: ManufacturerStanding[] }) {
  const maxPts = teams[0]?.points || 1;
  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm" aria-label="Manufacturer championship standings">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {[
                { label: "POS", sort: "ascending" as const },
                { label: "", sort: undefined },
                { label: "MANUFACTURER", sort: undefined },
                { label: "PTS", sort: "descending" as const },
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
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <span className="font-black text-lg font-mono tabular-nums text-[color:var(--ink)]">
                        <NumberTicker value={t.points} />
                      </span>
                      <div className="hidden sm:block progress-bar w-24 h-1.5">
                        <div
                          className="progress-bar-fill"
                          style={{ width: `${(t.points / maxPts) * 100}%`, background: color }}
                        />
                      </div>
                    </div>
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
