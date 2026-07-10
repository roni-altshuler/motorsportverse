"use client";

import Link from "next/link";
import { Trophy, Flag, TrendingUp, Gauge, Percent } from "lucide-react";

import type {
  CalendarRound,
  DriverStanding,
  TeamStanding,
  TitleOdds,
  SeasonAccuracy,
} from "@/types/indycar";
import { BentoCard, BentoGrid } from "@/components/magicui/bento-grid";
import { NumberTicker } from "@/components/magicui/number-ticker";
import TeamColorBar from "@/components/ui/TeamColorBar";
import DriverPortrait from "@/components/standings/DriverPortrait";

interface ChampionshipBentoProps {
  driverStandings: DriverStanding[];
  teamStandings: TeamStanding[];
  championship: TitleOdds[];
  nextRace: CalendarRound | null;
  roundsRemaining: number;
  totalRounds: number;
  seasonAccuracy?: SeasonAccuracy;
  roundsCompleted: number;
}

/**
 * Bento mosaic snapshot of the IndyCar championship state. Ported from
 * RaceIQ F1's ChampionshipBento. FE has no sprint format (so the "sprints
 * remaining" tile becomes a title-odds tile sourced from the driver
 * championship odds). The accuracy tile uses the season podium hit-rate, since
 * FE has no single headline accuracy percentage like F1.
 */
export default function ChampionshipBento({
  driverStandings,
  teamStandings,
  championship,
  nextRace,
  roundsRemaining,
  totalRounds,
  seasonAccuracy,
  roundsCompleted,
}: ChampionshipBentoProps) {
  const driverLeader = driverStandings[0];
  const constructorLeader = teamStandings[0];
  const titleFavourite = championship[0];

  const podiumHitPct =
    seasonAccuracy?.podiumHitRate != null
      ? seasonAccuracy.podiumHitRate * 100
      : null;

  // Biggest mover — driver whose most-recent round points jump is largest.
  const mover = driverStandings
    .filter((d) => (d.pointsHistory?.length ?? 0) >= 2)
    .map((d) => {
      const h = d.pointsHistory ?? [];
      const last = h[h.length - 1] ?? 0;
      const prev = h[h.length - 2] ?? 0;
      return {
        code: d.code,
        name: d.name,
        team: d.team,
        teamColor: d.teamColor,
        jump: last - prev,
      };
    })
    .sort((a, b) => b.jump - a.jump)[0];

  return (
    <BentoGrid className="grid-cols-2 md:grid-cols-4 auto-rows-[12rem] gap-3 sm:gap-4">
      {/* Drivers top 5 — 2x2 */}
      <BentoCard className="col-span-2 row-span-2 md:col-span-2 md:row-span-2 h-full">
        <div className="flex h-full flex-col p-6">
          <div className="flex items-baseline justify-between mb-4">
            <div>
              <p className="eyebrow mb-1">Championship</p>
              <h3 className="title-md text-[color:var(--ink)]">Drivers · Top 5</h3>
            </div>
            <Link
              href="/standings?tab=drivers"
              className="link-bugatti button-label text-[11px]"
            >
              All →
            </Link>
          </div>
          <ol className="flex-1 flex flex-col gap-3 mt-1">
            {driverStandings.slice(0, 5).map((d) => (
              <li
                key={d.code}
                className="flex items-center gap-3 py-1.5 border-b border-[color:var(--hairline)] last:border-0"
                data-team={d.team}
              >
                <span className="position-badge points w-9 shrink-0 text-center">
                  {d.position}
                </span>
                <DriverPortrait
                  driver={d.code}
                  driverFullName={d.name}
                  team={d.team}
                  teamColor={d.teamColor}
                  size={28}
                />
                <TeamColorBar teamColor={d.teamColor ?? "var(--accent)"} team={d.team} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="title-sm text-[color:var(--ink)] truncate">{d.name}</p>
                  <p className="caption-uppercase text-[10px] tracking-[0.16em] text-[color:var(--muted)] truncate">
                    {d.team}
                  </p>
                </div>
                <span className="font-mono text-base font-tabular text-[color:var(--ink)] shrink-0">
                  <NumberTicker value={d.points} />
                </span>
              </li>
            ))}
          </ol>
        </div>
      </BentoCard>

      {/* Teams top 3 — 2x1 */}
      <BentoCard className="col-span-2 row-span-1 md:col-span-2 md:row-span-1">
        <div className="flex h-full flex-col p-5">
          <div className="flex items-baseline justify-between mb-2">
            <div>
              <p className="eyebrow mb-1">Teams</p>
              <h3 className="title-md text-[color:var(--ink)]">Team Standings</h3>
            </div>
            <Link
              href="/standings?tab=teams"
              className="link-bugatti button-label text-[11px]"
            >
              All →
            </Link>
          </div>
          <div className="flex-1 grid grid-cols-3 gap-2 items-end">
            {teamStandings.slice(0, 3).map((t, i) => (
              <div
                key={t.team}
                data-team={t.team}
                className="border-l-2 pl-3 py-1"
                style={{ borderColor: t.teamColor || "var(--ink)" }}
              >
                <p className="caption-uppercase text-[9px] mb-0.5">P{i + 1}</p>
                <p className="title-sm text-[color:var(--ink)] truncate">{t.team}</p>
                <p className="font-mono text-lg font-tabular text-[color:var(--ink)]">
                  <NumberTicker value={t.points} />
                </p>
              </div>
            ))}
          </div>
        </div>
      </BentoCard>

      {/* Next round — 1x1 */}
      <BentoCard className="col-span-1 row-span-1 relative overflow-hidden">
        <div className="flex h-full flex-col justify-between p-5">
          <Flag className="w-5 h-5 text-[color:var(--accent-f1-red)]" />
          <div>
            <p className="eyebrow mb-1">Next Round</p>
            {nextRace ? (
              <>
                <p className="display-sm text-[color:var(--ink)] !text-[26px] !tracking-tight truncate">
                  R{nextRace.round}
                </p>
                <p className="caption-uppercase text-[10px] mt-1 tracking-[0.16em] truncate">
                  {nextRace.name}
                </p>
              </>
            ) : (
              <p className="title-sm text-[color:var(--muted)]">Season finale</p>
            )}
          </div>
        </div>
      </BentoCard>

      {/* Podium accuracy — 1x1 */}
      <BentoCard className="col-span-1 row-span-1">
        <div className="flex h-full flex-col justify-between p-5">
          <Gauge className="w-5 h-5 text-[color:var(--success)]" />
          <div>
            <p className="eyebrow mb-1">Podium Accuracy</p>
            <p className="display-sm text-[color:var(--ink)] !text-[28px] !tracking-tight">
              {podiumHitPct != null ? (
                <>
                  <NumberTicker value={podiumHitPct} decimalPlaces={0} className="font-mono" />
                  <span className="text-base text-[color:var(--muted)] ml-0.5">%</span>
                </>
              ) : (
                "—"
              )}
            </p>
            <p className="caption-uppercase text-[10px] mt-1 tracking-[0.16em] text-[color:var(--muted)]">
              {roundsCompleted} rounds graded
            </p>
          </div>
        </div>
      </BentoCard>

      {/* Biggest mover — 1x1 */}
      <BentoCard className="col-span-1 row-span-1">
        <div className="flex h-full flex-col justify-between p-5" data-team={mover?.team}>
          <TrendingUp className="w-5 h-5 text-[color:var(--accent-podium-1)]" />
          <div>
            <p className="eyebrow mb-1">Biggest Mover</p>
            {mover ? (
              <>
                <div className="flex items-center gap-2">
                  <DriverPortrait
                    driver={mover.code}
                    driverFullName={mover.name}
                    team={mover.team}
                    teamColor={mover.teamColor}
                    size={28}
                  />
                  <p className="display-sm text-[color:var(--ink)] !text-[24px] truncate">
                    {mover.name}
                  </p>
                </div>
                <p className="caption-uppercase text-[10px] mt-1 tracking-[0.16em] text-[color:var(--muted)]">
                  +<NumberTicker value={mover.jump} /> pts last round
                </p>
              </>
            ) : (
              <p className="title-sm text-[color:var(--muted)]">awaiting next round</p>
            )}
          </div>
        </div>
      </BentoCard>

      {/* Title odds (favourite) — 1x1 */}
      <BentoCard className="col-span-1 row-span-1">
        <div className="flex h-full flex-col justify-between p-5" data-team={titleFavourite?.team}>
          <Percent className="w-5 h-5 text-[color:var(--accent)]" />
          <div>
            <p className="eyebrow mb-1">Title Favourite</p>
            {titleFavourite ? (
              <>
                <p className="display-sm text-[color:var(--ink)] !text-[28px] !tracking-tight">
                  <NumberTicker value={titleFavourite.pTitle * 100} decimalPlaces={0} className="font-mono" />
                  <span className="text-base text-[color:var(--muted)] ml-0.5">%</span>
                </p>
                <p className="caption-uppercase text-[10px] mt-1 tracking-[0.16em] text-[color:var(--muted)] truncate">
                  {titleFavourite.name}
                </p>
              </>
            ) : (
              <p className="title-sm text-[color:var(--muted)]">—</p>
            )}
          </div>
        </div>
      </BentoCard>

      {/* Championship leader — 2x1 */}
      <BentoCard className="col-span-2 row-span-1">
        <div className="flex h-full flex-col p-5" data-team={driverLeader?.team}>
          <div className="flex items-baseline justify-between mb-1">
            <p className="eyebrow">Championship Leader</p>
            <Trophy className="w-4 h-4 text-[color:var(--accent-podium-1)]" />
          </div>
          {driverLeader ? (
            <div className="flex flex-1 items-end gap-4">
              <DriverPortrait
                driver={driverLeader.code}
                driverFullName={driverLeader.name}
                team={driverLeader.team}
                teamColor={driverLeader.teamColor}
                size={28}
              />
              <TeamColorBar teamColor={driverLeader.teamColor ?? "var(--accent)"} team={driverLeader.team} />
              <div className="flex-1 min-w-0">
                <p className="display-sm text-[color:var(--ink)] !text-[24px] truncate">
                  {driverLeader.name}
                </p>
                <p className="caption-uppercase text-[10px] tracking-[0.16em] text-[color:var(--muted)] truncate">
                  {driverLeader.team} · {constructorLeader?.team ?? "—"} leads teams
                </p>
              </div>
              <p className="font-mono text-[36px] font-tabular text-[color:var(--ink)] leading-none">
                <NumberTicker value={driverLeader.points} />
              </p>
            </div>
          ) : (
            <p className="title-sm text-[color:var(--muted)]">awaiting first result</p>
          )}
        </div>
      </BentoCard>

      {/* Projection band — full-width footnote on the favourite */}
      {titleFavourite && (
        <BentoCard className="col-span-2 md:col-span-4 row-span-1 !auto-rows-min">
          <div className="flex h-full flex-col justify-center p-5">
            <p className="eyebrow mb-1">Projected Final Points · {titleFavourite.name}</p>
            <div className="flex items-baseline gap-3">
              <p className="font-mono text-[32px] font-tabular text-[color:var(--ink)] leading-none">
                <NumberTicker value={titleFavourite.projMean} decimalPlaces={0} />
              </p>
              <p className="body-sm text-[color:var(--muted)]">
                projected ({titleFavourite.projP10.toFixed(0)}–{titleFavourite.projP90.toFixed(0)} range) ·{" "}
                {titleFavourite.currentPoints} pts now · {roundsRemaining} of {totalRounds} rounds left
              </p>
            </div>
          </div>
        </BentoCard>
      )}
    </BentoGrid>
  );
}
