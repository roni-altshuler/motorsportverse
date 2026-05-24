"use client";

import Link from "next/link";
import { Trophy, Wrench, Flag, TrendingUp, Gauge } from "lucide-react";

import { RaceCalendarEntry, SeasonData, StandingsData } from "@/types";
import { BentoCard, BentoGrid } from "@/components/magicui/bento-grid";
import { NumberTicker } from "@/components/magicui/number-ticker";
import TeamColorBar from "@/components/ui/TeamColorBar";

interface ChampionshipBentoProps {
  standings: StandingsData;
  season: SeasonData;
  nextRace: RaceCalendarEntry | null;
  accuracyPct?: number | null;
  roundsCompleted: number;
}

const MS_PER_DAY = 24 * 60 * 60 * 1000;

function countdownDays(targetIso: string): number {
  const ms = new Date(targetIso).getTime() - Date.now();
  return Math.max(0, Math.floor(ms / MS_PER_DAY));
}

/**
 * Bento mosaic snapshot of the championship state. Replaces the dual
 * PaddockWall block at the bottom of the home page.
 */
export default function ChampionshipBento({
  standings,
  season,
  nextRace,
  accuracyPct,
  roundsCompleted,
}: ChampionshipBentoProps) {
  const driverLeader = standings.drivers[0];
  const constructorLeader = standings.constructors[0];
  const sprintRounds = season.calendar.filter((r) => r.sprint);
  const sprintsRemaining = sprintRounds.filter((r) =>
    !season.completedRounds.includes(r.round),
  ).length;
  const days = nextRace ? countdownDays(nextRace.date) : null;

  // pick a "biggest mover" — driver whose recent points jump is largest
  const mover = standings.drivers
    .filter((d) => d.pointsHistory.length >= 2)
    .map((d) => {
      const last = d.pointsHistory[d.pointsHistory.length - 1] ?? 0;
      const prev = d.pointsHistory[d.pointsHistory.length - 2] ?? 0;
      return { driver: d.driver, team: d.team, teamColor: d.teamColor, jump: last - prev };
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
            <Link href="/standings?tab=drivers" className="link-bugatti button-label text-[11px]">
              All →
            </Link>
          </div>
          <ol className="flex-1 flex flex-col gap-3 mt-1">
            {standings.drivers.slice(0, 5).map((d) => (
              <li
                key={d.driver}
                className="flex items-center gap-3 py-1.5 border-b border-[color:var(--hairline)] last:border-0"
                data-team={d.team}
              >
                <span className="position-badge points w-9 shrink-0 text-center">
                  {d.position}
                </span>
                <TeamColorBar teamColor={d.teamColor} team={d.team} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="title-sm text-[color:var(--ink)] truncate">
                    {d.driverFullName ?? d.driver}
                  </p>
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

      {/* Constructors top 3 — 2x1 */}
      <BentoCard className="col-span-2 row-span-1 md:col-span-2 md:row-span-1">
        <div className="flex h-full flex-col p-5">
          <div className="flex items-baseline justify-between mb-2">
            <div>
              <p className="eyebrow mb-1">Constructors</p>
              <h3 className="title-md text-[color:var(--ink)]">Team Standings</h3>
            </div>
            <Link href="/standings?tab=constructors" className="link-bugatti button-label text-[11px]">
              All →
            </Link>
          </div>
          <div className="flex-1 grid grid-cols-3 gap-2 items-end">
            {standings.constructors.slice(0, 3).map((t, i) => (
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

      {/* Next race countdown — 1x1 */}
      <BentoCard className="col-span-1 row-span-1 relative overflow-hidden">
        <div className="flex h-full flex-col justify-between p-5">
          <Flag className="w-5 h-5 text-[color:var(--accent-f1-red)]" />
          <div>
            <p className="eyebrow mb-1">Next Race</p>
            {nextRace ? (
              <>
                <p className="display-sm text-[color:var(--ink)] !text-[28px] !tracking-tight">
                  {days !== null && days > 0 ? (
                    <>
                      <NumberTicker value={days} className="font-mono" />
                      <span className="text-base text-[color:var(--muted)] ml-1">days</span>
                    </>
                  ) : (
                    "this weekend"
                  )}
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

      {/* Forecast accuracy — 1x1 */}
      <BentoCard className="col-span-1 row-span-1">
        <div className="flex h-full flex-col justify-between p-5">
          <Gauge className="w-5 h-5 text-[color:var(--success)]" />
          <div>
            <p className="eyebrow mb-1">Forecast Accuracy</p>
            <p className="display-sm text-[color:var(--ink)] !text-[28px] !tracking-tight">
              {typeof accuracyPct === "number" ? (
                <>
                  <NumberTicker value={accuracyPct} decimalPlaces={0} className="font-mono" />
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
                <p className="display-sm text-[color:var(--ink)] !text-[28px]">{mover.driver}</p>
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

      {/* Sprints remaining — 1x1 */}
      <BentoCard className="col-span-1 row-span-1">
        <div className="flex h-full flex-col justify-between p-5">
          <Wrench className="w-5 h-5 text-[color:var(--warning)]" />
          <div>
            <p className="eyebrow mb-1">Sprint Weekends</p>
            <p className="display-sm text-[color:var(--ink)] !text-[28px] !tracking-tight">
              <NumberTicker value={sprintsRemaining} className="font-mono" />
              <span className="text-base text-[color:var(--muted)] ml-1">left</span>
            </p>
            <p className="caption-uppercase text-[10px] mt-1 tracking-[0.16em] text-[color:var(--muted)]">
              of {sprintRounds.length} scheduled
            </p>
          </div>
        </div>
      </BentoCard>

      {/* Championship leader card — 2x1 */}
      <BentoCard className="col-span-2 row-span-1">
        <div className="flex h-full flex-col p-5" data-team={driverLeader?.team}>
          <div className="flex items-baseline justify-between mb-1">
            <p className="eyebrow">Championship Leader</p>
            <Trophy className="w-4 h-4 text-[color:var(--accent-podium-1)]" />
          </div>
          {driverLeader ? (
            <div className="flex flex-1 items-end gap-4">
              <TeamColorBar teamColor={driverLeader.teamColor} team={driverLeader.team} />
              <div className="flex-1 min-w-0">
                <p className="display-sm text-[color:var(--ink)] !text-[26px] truncate">
                  {driverLeader.driverFullName ?? driverLeader.driver}
                </p>
                <p className="caption-uppercase text-[10px] tracking-[0.16em] text-[color:var(--muted)] truncate">
                  {driverLeader.team} · {constructorLeader?.team ?? "—"} leads constructors
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
    </BentoGrid>
  );
}
