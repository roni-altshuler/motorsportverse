"use client";

import HUDPanel from "@/components/ui/HUDPanel";
import AnimatedNumber from "@/components/ui/AnimatedNumber";
import TeamColorBar from "@/components/ui/TeamColorBar";
import type { DriverStanding } from "@/types";

interface ChampionshipKPIsProps {
  drivers: DriverStanding[];
}

export default function ChampionshipKPIs({ drivers }: ChampionshipKPIsProps) {
  if (!drivers || drivers.length === 0) return null;
  const leader = drivers[0];
  const runner = drivers[1];
  const gap = runner ? leader.points - runner.points : 0;
  const closingIn = gap > 0 && gap < 25;

  // "Biggest mover" — driver with the most points scored this round
  // (we use round-by-round delta if available, else fallback to highest podiums)
  type WithDelta = DriverStanding & { lastRoundPoints?: number };
  const mover = drivers
    .map((d) => d as WithDelta)
    .sort((a, b) => (b.lastRoundPoints ?? b.podiums) - (a.lastRoundPoints ?? a.podiums))[0];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
      <HUDPanel
        kicker="Championship Leader"
        intensity="strong"
      >
        <div className="flex items-center gap-3 mb-2">
          <TeamColorBar teamColor={leader.teamColor} team={leader.team} variant="gradient" size="lg" />
          <div className="flex-1">
            <p className="text-2xl font-black tracking-tight">{leader.driver}</p>
            <p className="text-xs text-[color:var(--text-muted)]">{leader.team}</p>
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <AnimatedNumber value={leader.points} variant="huge" />
          <span className="text-sm text-[color:var(--text-muted)]">pts</span>
        </div>
      </HUDPanel>

      <HUDPanel kicker="Gap to P2" intensity="strong">
        <div className="flex items-baseline gap-2 mb-2">
          <AnimatedNumber
            value={gap}
            variant="huge"
            className={closingIn ? "text-[color:var(--accent-live)]" : "text-[color:var(--text-primary)]"}
          />
          <span className="text-sm text-[color:var(--text-muted)]">pts</span>
        </div>
        <p className="text-xs text-[color:var(--text-muted)]">
          {closingIn ? "Closing in — within a race weekend" : runner ? `vs ${runner.driver}` : "—"}
        </p>
      </HUDPanel>

      {mover && (
        <HUDPanel kicker="Biggest Mover" intensity="strong">
          <div className="flex items-center gap-3 mb-2">
            <TeamColorBar teamColor={mover.teamColor} team={mover.team} variant="gradient" size="lg" />
            <div className="flex-1">
              <p className="text-2xl font-black tracking-tight">{mover.driver}</p>
              <p className="text-xs text-[color:var(--text-muted)]">
                {mover.podiums} podium{mover.podiums !== 1 ? "s" : ""} · {mover.wins} win{mover.wins !== 1 ? "s" : ""}
              </p>
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <AnimatedNumber value={mover.points} variant="default" />
            <span className="text-sm text-[color:var(--text-muted)]">total pts</span>
          </div>
        </HUDPanel>
      )}
    </div>
  );
}
