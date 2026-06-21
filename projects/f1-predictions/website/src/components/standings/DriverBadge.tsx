"use client";

import { motion } from "framer-motion";
import { Card } from "@/components/ui/Card";
import AnimatedNumber from "@/components/ui/AnimatedNumber";
import TeamColorBar from "@/components/ui/TeamColorBar";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { fadeUp } from "@/lib/motion";

interface DriverBadgeProps {
  position: number;
  driver: string;
  driverFullName?: string;
  team: string;
  teamColor: string;
  points: number;
  wins?: number;
  podiums?: number;
  headshotUrl?: string | null;
  index?: number;
}

export default function DriverBadge({
  position,
  driver,
  driverFullName,
  team,
  teamColor,
  points,
  wins = 0,
  podiums = 0,
  headshotUrl,
  index = 0,
}: DriverBadgeProps) {
  const positionColor =
    position === 1
      ? "var(--hud-champagne)"
      : position === 2
      ? "var(--accent-podium-2)"
      : position === 3
      ? "var(--accent-podium-3)"
      : "var(--text-muted)";

  return (
    <motion.div
      custom={index}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "0px 0px -10% 0px" }}
      variants={fadeUp}
    >
      <Card
        surface="paddock"
        interactive
        team={team}
        teamColor={teamColor}
        className="p-4 sm:p-5 h-full"
      >
        <div className="flex items-center gap-3 mb-3">
          <span
            className="font-mono font-tabular text-3xl sm:text-4xl font-black tabular-nums"
            style={{ color: positionColor }}
          >
            {position}
          </span>
          <DriverPortrait
            driver={driver}
            driverFullName={driverFullName}
            team={team}
            teamColor={teamColor}
            headshotUrl={headshotUrl}
            size={36}
          />
          <TeamColorBar teamColor={teamColor} team={team} variant="gradient" size="md" />
          <div className="ml-auto flex flex-col items-end">
            <p className="hud-kicker">Points</p>
            <AnimatedNumber value={points} variant="default" decimals={0} />
          </div>
        </div>
        <p className="text-lg font-black tracking-tight leading-tight">{driverFullName ?? driver}</p>
        <p className="text-sm text-[color:var(--text-muted)] mt-1">{team}</p>
        <div className="flex items-center gap-3 mt-3 text-[11px] font-mono text-[color:var(--text-muted)]">
          <span>
            <span className="text-[color:var(--hud-champagne)] font-bold">{wins}</span> wins
          </span>
          <span className="opacity-60">·</span>
          <span>
            <span className="text-[color:var(--text-primary)] font-bold">{podiums}</span> podiums
          </span>
        </div>
      </Card>
    </motion.div>
  );
}
