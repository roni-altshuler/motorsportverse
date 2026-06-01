"use client";

import { Crown, GitCompare, TrendingUp, Trophy } from "lucide-react";

import { BentoCard, BentoGrid } from "@/components/magicui/bento-grid";
import { NumberTicker } from "@/components/magicui/number-ticker";
import TeamColorBar from "@/components/ui/TeamColorBar";
import DriverPortrait from "@/components/standings/DriverPortrait";
import type { DriverStanding } from "@/types";

interface ChampionshipKPIsProps {
  drivers: DriverStanding[];
}

/**
 * Championship-state KPI strip. Replaces the previous HUDPanel row with a
 * 4-cell BentoGrid:
 *   1. Championship leader (large, BorderBeam in F1-red)
 *   2. Gap to P2
 *   3. Biggest mover (recent points jump)
 *   4. Total wins by leader (small badge cell)
 */
export default function ChampionshipKPIs({ drivers }: ChampionshipKPIsProps) {
  if (!drivers || drivers.length === 0) return null;
  const leader = drivers[0];
  const runner = drivers[1];
  const gap = runner ? leader.points - runner.points : 0;
  const closingIn = gap > 0 && gap < 25;

  const mover = drivers
    .filter((d) => d.pointsHistory.length >= 2)
    .map((d) => {
      const last = d.pointsHistory[d.pointsHistory.length - 1] ?? 0;
      const prev = d.pointsHistory[d.pointsHistory.length - 2] ?? 0;
      return { ...d, jump: last - prev };
    })
    .sort((a, b) => b.jump - a.jump)[0];

  return (
    <BentoGrid className="grid-cols-2 md:grid-cols-4 auto-rows-[12rem] gap-3 sm:gap-4 mb-8">
      {/* Championship leader — restrained dark surface, same visual language as
          the Podium-Hits cell below: thin team-color bar under the driver code,
          no glow, no team-color background fill. */}
      <BentoCard
        className="col-span-2 row-span-1"
        data-team={leader.team}
      >
        <div className="flex h-full flex-col justify-between p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <p className="eyebrow">Championship Leader</p>
            <Crown className="w-4 h-4 text-[color:var(--accent-podium-1)]" />
          </div>
          <div className="flex items-end justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-3">
                <DriverPortrait
                  driver={leader.driver}
                  driverFullName={leader.driverFullName}
                  team={leader.team}
                  teamColor={leader.teamColor}
                  headshotUrl={leader.headshotUrl}
                  size={40}
                />
                <p className="display-md [font-weight:700] text-[color:var(--ink)] !text-[34px] !leading-none truncate">
                  {leader.driverFullName ?? leader.driver}
                </p>
              </div>
              <TeamColorBar
                teamColor={leader.teamColor}
                team={leader.team}
                variant="solid"
                size="sm"
                className="mt-2"
              />
              <p className="caption-uppercase text-[10px] mt-2 tracking-[0.18em] text-[color:var(--muted)] truncate">
                {leader.team}
              </p>
            </div>
            <p className="font-mono font-tabular text-[42px] [font-weight:700] text-[color:var(--ink)] leading-none shrink-0">
              <NumberTicker value={leader.points} />
              <span className="text-base text-[color:var(--muted)] ml-1.5">pts</span>
            </p>
          </div>
        </div>
      </BentoCard>

      {/* Gap to P2 */}
      <BentoCard className="col-span-1 row-span-1">
        <div className="flex h-full flex-col justify-between p-5">
          <div className="flex items-center justify-between">
            <p className="eyebrow">Gap to P2</p>
            <GitCompare className="w-4 h-4 text-[color:var(--muted)]" />
          </div>
          <div>
            <p
              className="font-mono font-tabular text-[42px] [font-weight:700] leading-none"
              style={{
                color: closingIn
                  ? "var(--accent-f1-red)"
                  : "var(--ink)",
              }}
            >
              <NumberTicker value={gap} />
              <span className="text-base text-[color:var(--muted)] ml-1.5">pts</span>
            </p>
            <p className="caption-uppercase text-[10px] mt-2 tracking-[0.18em] text-[color:var(--muted)] truncate">
              {closingIn
                ? "Within a race weekend"
                : runner
                  ? `vs ${runner.driverFullName ?? runner.driver}`
                  : "—"}
            </p>
          </div>
        </div>
      </BentoCard>

      {/* Biggest mover */}
      <BentoCard className="col-span-1 row-span-1" data-team={mover?.team}>
        <div className="flex h-full flex-col justify-between p-5">
          <div className="flex items-center justify-between">
            <p className="eyebrow">Biggest Mover</p>
            <TrendingUp className="w-4 h-4 text-[color:var(--accent-podium-1)]" />
          </div>
          {mover ? (
            <div>
              <div className="flex items-center gap-2">
                <DriverPortrait
                  driver={mover.driver}
                  driverFullName={mover.driverFullName}
                  team={mover.team}
                  teamColor={mover.teamColor}
                  headshotUrl={mover.headshotUrl}
                  size={28}
                />
                <p className="display-md [font-weight:700] text-[color:var(--ink)] !text-[28px] !leading-none truncate">
                  {mover.driverFullName ?? mover.driver}
                </p>
              </div>
              <p className="caption-uppercase text-[10px] mt-2 tracking-[0.18em] text-[color:var(--muted)]">
                +<NumberTicker value={mover.jump} /> pts last round
              </p>
            </div>
          ) : (
            <p className="body-sm text-[color:var(--muted)]">awaiting next round</p>
          )}
        </div>
      </BentoCard>

      {/* Leader wins */}
      <BentoCard className="col-span-2 md:col-span-1 row-span-1">
        <div className="flex h-full flex-col justify-between p-5" data-team={leader.team}>
          <div className="flex items-center justify-between">
            <p className="eyebrow">Wins · {leader.driverFullName ?? leader.driver}</p>
            <Trophy className="w-4 h-4 text-[color:var(--accent-podium-1)]" />
          </div>
          <div>
            <p className="font-mono font-tabular text-[42px] [font-weight:700] text-[color:var(--ink)] leading-none">
              <NumberTicker value={leader.wins} />
            </p>
            <p className="caption-uppercase text-[10px] mt-2 tracking-[0.18em] text-[color:var(--muted)]">
              {leader.podiums} podium{leader.podiums !== 1 ? "s" : ""} so far
            </p>
          </div>
        </div>
      </BentoCard>

      {/* Spacer/aux cell for md+: extends grid to 3 rows visually balanced */}
      <BentoCard className="hidden md:block md:col-span-2 row-span-1">
        <div className="flex h-full flex-col justify-between p-5">
          <p className="eyebrow">Field Spread</p>
          <div>
            <p className="display-md [font-weight:700] text-[color:var(--ink)] !text-[26px] !leading-none">
              {drivers.length > 1
                ? `${drivers[0].points - drivers[drivers.length - 1].points} pts`
                : "—"}
            </p>
            <p className="caption-uppercase text-[10px] mt-2 tracking-[0.18em] text-[color:var(--muted)]">
              P1 to last on the grid
            </p>
          </div>
        </div>
      </BentoCard>

      {/* Sprint-points share placeholder cell */}
      <BentoCard className="hidden md:block md:col-span-2 row-span-1">
        <div className="flex h-full flex-col justify-between p-5">
          <p className="eyebrow">Podium Hits · Top 3</p>
          <div className="flex items-end gap-5">
            {drivers.slice(0, 3).map((d, i) => (
              <div key={d.driver} className="flex-1" data-team={d.team}>
                <p className="caption-uppercase text-[10px] mb-1 tracking-[0.18em] text-[color:var(--muted)]">
                  P{i + 1}
                </p>
                <p className="font-mono font-tabular text-[28px] [font-weight:700] text-[color:var(--ink)] leading-none">
                  <NumberTicker value={d.podiums} />
                </p>
                <TeamColorBar
                  teamColor={d.teamColor}
                  team={d.team}
                  variant="solid"
                  size="sm"
                  className="mt-2"
                />
              </div>
            ))}
          </div>
        </div>
      </BentoCard>
    </BentoGrid>
  );
}
