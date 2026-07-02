"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/Card";
import TeamColorBar from "@/components/ui/TeamColorBar";
import { Badge } from "@/components/ui/Badge";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { resolveDriverHeadshot } from "@/lib/headshots";
import { podiumReveal } from "@/lib/motion";
import type { ClassificationEntry } from "@/types";

interface PodiumPredictionTrioProps {
  classification: ClassificationEntry[];
  /** When official actual results exist, render the actual top-3 here and label "Official"; else label "Predicted". */
  actualPodium?: Array<{
    driver: string;
    team?: string;
    teamColor?: string;
    position: number;
    headshotUrl?: string | null;
  }>;
}

export default function PodiumPredictionTrio({
  classification,
  actualPodium,
}: PodiumPredictionTrioProps) {
  const reduced = useReducedMotion();
  const isOfficial = !!actualPodium && actualPodium.length >= 3;
  // Scroll-reveal failsafe: whileInView can miss in headless/full-page
  // renders and unusual viewports — never leave the podium invisible.
  const [revealFailsafe, setRevealFailsafe] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setRevealFailsafe(true), 1200);
    return () => clearTimeout(t);
  }, []);

  const items = isOfficial
    ? actualPodium!.slice(0, 3).map((a) => {
        const pred = classification.find((c) => c.driver === a.driver);
        return {
          driver: a.driver,
          driverFullName: pred?.driverFullName ?? a.driver,
          team: a.team || pred?.team || "—",
          teamColor: a.teamColor || pred?.teamColor || "var(--accent-live)",
          position: a.position,
          predictedPosition: pred?.position ?? null,
          winProbability: pred?.winProbability ?? null,
          finishRangeLow: pred?.finishRangeLow ?? null,
          finishRangeHigh: pred?.finishRangeHigh ?? null,
          headshotUrl: resolveDriverHeadshot(a.driver, a.headshotUrl ?? pred?.headshotUrl),
        };
      })
    : classification.slice(0, 3).map((c) => ({
        driver: c.driver,
        driverFullName: c.driverFullName,
        team: c.team,
        teamColor: c.teamColor,
        position: c.position,
        predictedPosition: c.position,
        winProbability: c.winProbability ?? null,
        finishRangeLow: c.finishRangeLow ?? null,
        finishRangeHigh: c.finishRangeHigh ?? null,
        headshotUrl: resolveDriverHeadshot(c.driver, c.headshotUrl),
      }));

  // Visual ordering: P2 left, P1 (taller) centre, P3 right.
  const ordered: Array<{
    entry: (typeof items)[number];
    rank: 0 | 1 | 2;
    order: number;
  }> = [
    { entry: items[1] ?? items[0], rank: 1, order: 0 },
    { entry: items[0], rank: 0, order: 1 },
    { entry: items[2] ?? items[0], rank: 2, order: 2 },
  ];

  return (
    <div className="mb-12">
      <div className="flex items-baseline justify-between mb-8">
        <div>
          <p className="eyebrow mb-2">{isOfficial ? "Official Result" : "Model Forecast"}</p>
          <h3 className="display-md">{isOfficial ? "Race Podium" : "Predicted Podium"}</h3>
        </div>
        <Badge variant={isOfficial ? "positive" : "live"}>
          {isOfficial ? "Result loaded" : "Prediction published"}
        </Badge>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-10 items-start">
        {ordered.map(({ entry, rank, order }, idx) => {
          if (!entry) return null;
          const isLeader = rank === 0;
          const label = rank === 0 ? "P1" : rank === 1 ? "P2" : "P3";
          const rankColor =
            rank === 0
              ? "text-[color:var(--accent-podium-1)]"
              : rank === 1
                ? "text-[color:var(--accent-podium-2)]"
                : "text-[color:var(--accent-podium-3)]";
          return (
            <motion.div
              key={`${entry.driver}-${rank}`}
              custom={idx}
              initial={reduced ? "visible" : "hidden"}
              whileInView="visible"
              animate={reduced || revealFailsafe ? "visible" : undefined}
              viewport={{ once: true, margin: "0px 0px -10% 0px" }}
              variants={podiumReveal}
              style={{ order } as React.CSSProperties}
            >
              <Card
                surface="flat"
                interactive
                team={entry.team}
                teamColor={entry.teamColor}
                className={`p-6 sm:p-8 relative overflow-hidden${
                  isLeader ? " podium-leader-card" : ""
                }`}
              >
                {isLeader && (
                  <>
                    <span aria-hidden className="podium-leader-accent" />
                    <span
                      className="podium-leader-pill"
                      aria-label={isOfficial ? "Race winner" : "Projected winner"}
                    >
                      {isOfficial ? "Race Winner" : "Projected Winner"}
                    </span>
                  </>
                )}
                <div className="flex items-center gap-3 mb-6">
                  <DriverPortrait
                    driver={entry.driver}
                    driverFullName={entry.driverFullName}
                    team={entry.team}
                    teamColor={entry.teamColor}
                    headshotUrl={entry.headshotUrl}
                    size={isLeader ? 72 : 56}
                  />
                  <div>
                    <span
                      className={`font-mono uppercase tracking-[0.18em] text-[14px] ${rankColor}`}
                    >
                      {label}
                    </span>
                    <div className="mt-1">
                      <TeamColorBar
                        teamColor={entry.teamColor}
                        team={entry.team}
                        variant="solid"
                        size={isLeader ? "lg" : "md"}
                        animate="draw"
                      />
                    </div>
                  </div>
                </div>
                <div
                  className={
                    isLeader ? "display-lg [font-weight:700]" : "display-md [font-weight:700]"
                  }
                >
                  {entry.driverFullName ?? entry.driver}
                </div>
                <div className="body-sm text-[color:var(--muted)] mt-2 mb-6">{entry.team}</div>
                {entry.winProbability != null && entry.winProbability > 0 && (
                  <>
                    <p className="eyebrow mb-2">Win probability</p>
                    <p
                      className={`font-mono font-tabular text-[color:var(--ink)] ${
                        isLeader ? "text-[56px] leading-none [font-weight:700]" : "text-[28px]"
                      }`}
                    >
                      <NumberTicker value={entry.winProbability} decimalPlaces={1} />
                      <span className="text-[color:var(--muted)] text-base ml-1">%</span>
                    </p>
                  </>
                )}
                {entry.finishRangeLow != null && entry.finishRangeHigh != null && (
                  <p className="eyebrow mt-4">
                    Range P{entry.finishRangeLow}–P{entry.finishRangeHigh}
                  </p>
                )}
                {isOfficial &&
                  entry.predictedPosition != null &&
                  entry.predictedPosition !== entry.position && (
                    <p className="eyebrow mt-2 text-[color:var(--link)]">
                      Predicted P{entry.predictedPosition}
                    </p>
                  )}
              </Card>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
