"use client";

import { DriverStanding } from "@/types";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { NumberTicker } from "@/components/magicui/number-ticker";
import TeamColorBar from "@/components/ui/TeamColorBar";

interface StandingsHeroPodiumProps {
  drivers: DriverStanding[];
}

/**
 * Three-card hero row for P1/P2/P3 in the drivers tab. Mirrors the race-detail
 * Race Podium visual language: dark `var(--surface-card)` surface for every
 * card, a thin champagne accent strip + "Championship Leader" pill on P1,
 * no team-color gradient backdrop, no BorderBeam. Same shape as PodiumPredictionTrio.
 */
export default function StandingsHeroPodium({ drivers }: StandingsHeroPodiumProps) {
  const podium = drivers.slice(0, 3);
  if (podium.length === 0) return null;
  const [first, second, third] = podium;
  // Render with the leader visually centered (P2 left, P1 middle, P3 right)
  const order: { d: DriverStanding | undefined; rank: 1 | 2 | 3 }[] = [
    { d: second, rank: 2 },
    { d: first, rank: 1 },
    { d: third, rank: 3 },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 lg:gap-6 mb-12">
      {order.map(({ d, rank }) =>
        d ? <PodiumCard key={d.driver} driver={d} rank={rank} /> : <span key={rank} />,
      )}
    </div>
  );
}

function PodiumCard({ driver, rank }: { driver: DriverStanding; rank: 1 | 2 | 3 }) {
  const tintToken =
    rank === 1
      ? "var(--accent-podium-1)"
      : rank === 2
        ? "var(--accent-podium-2)"
        : "var(--accent-podium-3)";
  const isP1 = rank === 1;

  return (
    <div
      data-team={driver.team}
      className={`relative overflow-hidden border border-[color:var(--hairline)] bg-[color:var(--surface-card)] rounded-[var(--radius-card)] hover-lift-premium${
        isP1 ? " podium-card-p1 podium-leader-card" : ""
      }`}
    >
      {isP1 && (
        <>
          <span aria-hidden className="podium-leader-accent" />
          <span className="podium-leader-pill" aria-label="Championship leader">
            Championship Leader
          </span>
        </>
      )}
      <div className="p-5 sm:p-7 flex flex-col items-start gap-4">
        <div className="flex items-center w-full">
          <span
            className="position-badge"
            style={{
              color: tintToken,
              borderColor: tintToken,
              minWidth: 38,
              height: 32,
              fontSize: 14,
              letterSpacing: "0.10em",
            }}
          >
            P{rank}
          </span>
        </div>

        <div className="flex items-center gap-4 w-full">
          <DriverPortrait
            driver={driver.driver}
            driverFullName={driver.driverFullName}
            team={driver.team}
            teamColor={driver.teamColor}
            headshotUrl={driver.headshotUrl}
            size={isP1 ? 84 : 64}
          />
          <div className="min-w-0 flex-1">
            <p className="caption-uppercase text-[10px] tracking-[0.18em] truncate">
              {driver.driverFullName ?? driver.driver}
            </p>
            <p className="display-md [font-weight:700] text-[color:var(--ink)] !text-[34px] !leading-none mt-1">
              {driver.driver}
            </p>
            <div className="flex items-center gap-2 mt-2">
              <TeamColorBar teamColor={driver.teamColor} team={driver.team} size="sm" />
              <span className="caption-uppercase text-[10px] tracking-[0.18em] truncate">
                {driver.team}
              </span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 w-full pt-3 border-t border-[color:var(--hairline)]">
          <div>
            <p className="eyebrow text-[10px]">Pts</p>
            <p className="font-mono font-tabular text-[22px] text-[color:var(--ink)] [font-weight:700]">
              <NumberTicker value={driver.points} />
            </p>
          </div>
          <div>
            <p className="eyebrow text-[10px]">Wins</p>
            <p className="font-mono font-tabular text-[22px] text-[color:var(--ink)]">
              <NumberTicker value={driver.wins} />
            </p>
          </div>
          <div>
            <p className="eyebrow text-[10px]">Podiums</p>
            <p className="font-mono font-tabular text-[22px] text-[color:var(--ink)]">
              <NumberTicker value={driver.podiums} />
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
