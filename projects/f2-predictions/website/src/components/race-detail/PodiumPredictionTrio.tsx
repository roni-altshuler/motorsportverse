"use client";

import { motion } from "framer-motion";

import DriverPortrait from "@/components/standings/DriverPortrait";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import TeamColorBar from "@/components/ui/TeamColorBar";
import { podiumReveal } from "@/lib/motion";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { ClassificationEntry } from "@/types/f2";

interface PodiumPredictionTrioProps {
  /** Active race tab's classification — top-3 is the predicted podium. */
  classification: ClassificationEntry[];
  /** Whether the round has run (when true and actuals exist, show official podium). */
  completed?: boolean;
}

/**
 * Predicted top-3 for the active race tab, rendered as the F1 flagship's
 * podium trio (P2 left, taller P1 centre, P3 right). When the round is
 * completed and actual finishing positions are present, it switches to the
 * official top-3 and surfaces where the model predicted each driver.
 */
export default function PodiumPredictionTrio({
  classification,
  completed = false,
}: PodiumPredictionTrioProps) {
  const reduced = useReducedMotion();

  const hasActuals =
    completed && classification.some((c) => c.actualPosition != null);

  const items = hasActuals
    ? [...classification]
        .filter((c) => c.actualPosition != null)
        .sort((a, b) => (a.actualPosition ?? 99) - (b.actualPosition ?? 99))
        .slice(0, 3)
        .map((c) => ({
          code: c.code,
          name: c.name,
          team: c.team,
          teamColor: c.teamColor,
          headshotUrl: c.headshotUrl,
          displayPosition: c.actualPosition ?? c.position,
          predictedPosition: c.position,
          pWin: c.pWin,
          finishRangeLow: c.finishRangeLow,
          finishRangeHigh: c.finishRangeHigh,
        }))
    : classification.slice(0, 3).map((c) => ({
        code: c.code,
        name: c.name,
        team: c.team,
        teamColor: c.teamColor,
        headshotUrl: c.headshotUrl,
        displayPosition: c.position,
        predictedPosition: c.position,
        pWin: c.pWin,
        finishRangeLow: c.finishRangeLow,
        finishRangeHigh: c.finishRangeHigh,
      }));

  if (items.length === 0) return null;

  // Visual ordering: P2 left, P1 (taller) centre, P3 right.
  const ordered: Array<{ entry: (typeof items)[number]; rank: 0 | 1 | 2; order: number }> = [
    { entry: items[1] ?? items[0], rank: 1, order: 0 },
    { entry: items[0], rank: 0, order: 1 },
    { entry: items[2] ?? items[0], rank: 2, order: 2 },
  ];

  return (
    <div className="mb-12">
      <div className="mb-8 flex items-baseline justify-between">
        <div>
          <p className="eyebrow mb-2">{hasActuals ? "Official Result" : "Model Forecast"}</p>
          <h3 className="display-md">{hasActuals ? "Race Podium" : "Predicted Podium"}</h3>
        </div>
        <Badge variant={hasActuals ? "positive" : "live"}>
          {hasActuals ? "Result loaded" : "Prediction published"}
        </Badge>
      </div>
      <div className="grid grid-cols-1 items-start gap-10 sm:grid-cols-3">
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
              key={`${entry.code}-${rank}`}
              custom={idx}
              initial={reduced ? "visible" : "hidden"}
              whileInView="visible"
              viewport={{ once: true, margin: "0px 0px -10% 0px" }}
              variants={podiumReveal}
              style={{ order } as React.CSSProperties}
            >
              <Card
                surface="flat"
                interactive
                team={entry.team}
                teamColor={entry.teamColor}
                className={`relative overflow-hidden p-6 sm:p-8${
                  isLeader ? " podium-leader-card" : ""
                }`}
              >
                {isLeader && (
                  <>
                    <span aria-hidden className="podium-leader-accent" />
                    <span
                      className="podium-leader-pill"
                      aria-label={hasActuals ? "Race winner" : "Projected winner"}
                    >
                      {hasActuals ? "Race Winner" : "Projected Winner"}
                    </span>
                  </>
                )}
                <div className="mb-6 flex items-center gap-3">
                  <DriverPortrait
                    driver={entry.code}
                    driverFullName={entry.name}
                    team={entry.team}
                    teamColor={entry.teamColor}
                    headshotUrl={entry.headshotUrl}
                    size={isLeader ? 72 : 56}
                  />
                  <div>
                    <span
                      className={`font-mono text-[14px] uppercase tracking-[0.18em] ${rankColor}`}
                    >
                      {label}
                    </span>
                    <div className="mt-1">
                      <TeamColorBar
                        teamColor={entry.teamColor}
                        team={entry.team}
                        variant="solid"
                        orientation="horizontal"
                        size={isLeader ? "lg" : "md"}
                        animate="draw"
                      />
                    </div>
                  </div>
                </div>
                <div className={isLeader ? "display-lg [font-weight:700]" : "display-md [font-weight:700]"}>
                  {entry.name}
                </div>
                <div className="body-sm mb-6 mt-2 text-[color:var(--muted)]">{entry.team}</div>
                {entry.pWin > 0 && (
                  <>
                    <p className="eyebrow mb-2">Win probability</p>
                    <p
                      className={`font-mono font-tabular text-[color:var(--ink)] ${
                        isLeader ? "text-[56px] leading-none [font-weight:700]" : "text-[28px]"
                      }`}
                    >
                      <NumberTicker value={entry.pWin * 100} decimalPlaces={1} />
                      <span className="ml-1 text-base text-[color:var(--muted)]">%</span>
                    </p>
                  </>
                )}
                <p className="eyebrow mt-4">
                  Range P{entry.finishRangeLow}–P{entry.finishRangeHigh}
                </p>
                {hasActuals && entry.predictedPosition !== entry.displayPosition && (
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
