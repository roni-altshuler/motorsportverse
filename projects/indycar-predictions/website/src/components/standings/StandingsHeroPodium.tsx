"use client";

import type { DriverStanding } from "@/types/indycar";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { TeamColorBar } from "@/components/ui/TeamColorBar";
import { teamColor as teamColorFor } from "@/lib/teams";

interface StandingsHeroPodiumProps {
  drivers: DriverStanding[];
}

/**
 * Three-card hero row for P1/P2/P3 in the drivers tab (port of the RaceIQ F1
 * StandingsHeroPodium). Dark `var(--surface-card)` surface for every card, a
 * thin podium-1 accent strip + "Championship Leader" pill on P1, leader visually
 * centred (P2 left, P1 middle, P3 right). Adapted to the FE DriverStanding shape
 * (`code`/`name` rather than `driver`/`driverFullName`).
 */
export default function StandingsHeroPodium({ drivers }: StandingsHeroPodiumProps) {
  const podium = drivers.slice(0, 3);
  if (podium.length === 0) return null;
  const [first, second, third] = podium;
  const order: { d: DriverStanding | undefined; rank: 1 | 2 | 3 }[] = [
    { d: second, rank: 2 },
    { d: first, rank: 1 },
    { d: third, rank: 3 },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 lg:gap-6 mb-12">
      {order.map(({ d, rank }) =>
        d ? <PodiumCard key={d.code} driver={d} rank={rank} /> : <span key={rank} />,
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
  const color = driver.teamColor || teamColorFor(driver.team);

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
            driver={driver.code}
            driverFullName={driver.name}
            team={driver.team}
            teamColor={color}
            headshotUrl={driver.headshotUrl}
            size={isP1 ? 84 : 64}
          />
          <div className="min-w-0 flex-1">
            <p className="caption-uppercase text-[10px] tracking-[0.18em] truncate">
              {driver.code}
            </p>
            <p className="display-md [font-weight:700] text-[color:var(--ink)] !text-[34px] !leading-none mt-1 truncate">
              {driver.name}
            </p>
            <div className="flex items-center gap-2 mt-2">
              <TeamColorBar teamColor={color} team={driver.team} size="sm" />
              <span className="caption-uppercase text-[10px] tracking-[0.18em] truncate">
                {driver.team}
              </span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 w-full pt-3 border-t border-[color:var(--hairline)]">
          <div>
            <p className="eyebrow text-[10px]">Pts</p>
            <p className="font-mono tabular-nums text-[22px] text-[color:var(--ink)] [font-weight:700]">
              <NumberTicker value={driver.points} />
            </p>
          </div>
          <div>
            <p className="eyebrow text-[10px]">Wins</p>
            <p className="font-mono tabular-nums text-[22px] text-[color:var(--ink)]">
              <NumberTicker value={driver.wins} />
            </p>
          </div>
          <div>
            <p className="eyebrow text-[10px]">Podiums</p>
            <p className="font-mono tabular-nums text-[22px] text-[color:var(--ink)]">
              <NumberTicker value={driver.podiums} />
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
