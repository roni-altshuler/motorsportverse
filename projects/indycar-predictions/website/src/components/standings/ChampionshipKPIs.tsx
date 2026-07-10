"use client";

import { Crown, GitCompare, Flag, Target } from "lucide-react";

import { BentoCard, BentoGrid } from "@/components/magicui/bento-grid";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { TeamColorBar } from "@/components/ui/TeamColorBar";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { teamColor as teamColorFor } from "@/lib/teams";
import type { DriverStanding, SeasonAccuracy, TitleOdds } from "@/types/indycar";

interface ChampionshipKPIsProps {
  drivers: DriverStanding[];
  championship: TitleOdds[];
  roundsRemaining: number;
  seasonAccuracy?: SeasonAccuracy;
}

/**
 * Championship-state KPI strip (port of the RaceIQ F1 ChampionshipKPIs bento).
 * Adapted to IndyCar: cells are championship leader (with title odds), gap to P2,
 * rounds remaining, leader wins, field spread, and a forecast-accuracy cell
 * sourced from seasonAccuracy. Tech-stack-scrubbed copy throughout.
 */
export default function ChampionshipKPIs({
  drivers,
  championship,
  roundsRemaining,
  seasonAccuracy,
}: ChampionshipKPIsProps) {
  if (!drivers || drivers.length === 0) return null;
  const leader = drivers[0];
  const runner = drivers[1];
  const gap = runner ? leader.points - runner.points : 0;
  const closingIn = gap > 0 && gap < 25;
  const leaderColor = leader.teamColor || teamColorFor(leader.team);
  const leaderOdds = championship.find((c) => c.code === leader.code);

  const meanErr = seasonAccuracy?.meanPositionError;
  const podiumRate = seasonAccuracy?.podiumHitRate;

  return (
    <BentoGrid className="grid-cols-2 md:grid-cols-4 auto-rows-[12rem] gap-3 sm:gap-4 mb-8">
      {/* Championship leader */}
      <BentoCard className="col-span-2 row-span-1" data-team={leader.team}>
        <div className="flex h-full flex-col justify-between p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <p className="eyebrow">Championship Leader</p>
            <Crown className="w-4 h-4 text-[color:var(--accent-podium-1)]" />
          </div>
          <div className="flex items-end justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-3">
                <DriverPortrait
                  driver={leader.code}
                  driverFullName={leader.name}
                  team={leader.team}
                  teamColor={leaderColor}
                  headshotUrl={leader.headshotUrl}
                  size={40}
                />
                <p className="display-md [font-weight:700] text-[color:var(--ink)] !text-[30px] !leading-none truncate">
                  {leader.name}
                </p>
              </div>
              <TeamColorBar
                teamColor={leaderColor}
                team={leader.team}
                variant="solid"
                size="sm"
                className="mt-2"
              />
              <p className="caption-uppercase text-[10px] mt-2 tracking-[0.18em] text-[color:var(--muted)] truncate">
                {leader.team}
                {leaderOdds ? ` · ${(leaderOdds.pTitle * 100).toFixed(0)}% title odds` : ""}
              </p>
            </div>
            <p className="font-mono tabular-nums text-[42px] [font-weight:700] text-[color:var(--ink)] leading-none shrink-0">
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
              className="font-mono tabular-nums text-[42px] [font-weight:700] leading-none"
              style={{ color: closingIn ? "var(--accent)" : "var(--ink)" }}
            >
              <NumberTicker value={gap} />
              <span className="text-base text-[color:var(--muted)] ml-1.5">pts</span>
            </p>
            <p className="caption-uppercase text-[10px] mt-2 tracking-[0.18em] text-[color:var(--muted)] truncate">
              {closingIn ? "Within a weekend" : runner ? `vs ${runner.name}` : "—"}
            </p>
          </div>
        </div>
      </BentoCard>

      {/* Rounds remaining */}
      <BentoCard className="col-span-1 row-span-1">
        <div className="flex h-full flex-col justify-between p-5">
          <div className="flex items-center justify-between">
            <p className="eyebrow">Rounds Left</p>
            <Flag className="w-4 h-4 text-[color:var(--accent-podium-1)]" />
          </div>
          <div>
            <p className="font-mono tabular-nums text-[42px] [font-weight:700] text-[color:var(--ink)] leading-none">
              <NumberTicker value={roundsRemaining} />
            </p>
            <p className="caption-uppercase text-[10px] mt-2 tracking-[0.18em] text-[color:var(--muted)]">
              still to run this season
            </p>
          </div>
        </div>
      </BentoCard>

      {/* Field spread */}
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

      {/* Forecast accuracy — sourced from seasonAccuracy */}
      <BentoCard className="hidden md:block md:col-span-2 row-span-1">
        <div className="flex h-full flex-col justify-between p-5">
          <div className="flex items-center justify-between">
            <p className="eyebrow">Forecast Accuracy</p>
            <Target className="w-4 h-4 text-[color:var(--accent-podium-1)]" />
          </div>
          <div className="flex items-end gap-8">
            <div>
              <p className="font-mono tabular-nums text-[28px] [font-weight:700] text-[color:var(--ink)] leading-none">
                {podiumRate != null ? `${Math.round(podiumRate * 100)}%` : "—"}
              </p>
              <p className="caption-uppercase text-[10px] mt-1 tracking-[0.18em] text-[color:var(--muted)]">
                Podium hit rate
              </p>
            </div>
            <div>
              <p className="font-mono tabular-nums text-[28px] [font-weight:700] text-[color:var(--ink)] leading-none">
                {meanErr != null ? meanErr.toFixed(1) : "—"}
              </p>
              <p className="caption-uppercase text-[10px] mt-1 tracking-[0.18em] text-[color:var(--muted)]">
                Avg. position error
              </p>
            </div>
          </div>
        </div>
      </BentoCard>
    </BentoGrid>
  );
}
