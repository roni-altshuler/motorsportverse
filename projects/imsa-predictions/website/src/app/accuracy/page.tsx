import type { Metadata } from "next";

import AccuracyView, {
  type ForwardEvalSummary,
  type RoundAccuracyRow,
} from "@/components/AccuracyView";
import {
  allRoundNumbers,
  getCalibrationSummary,
  getForwardEvalSeason,
  getRound,
  getImsaData,
} from "@/lib/imsaData";
import type { SeasonAccuracyStat } from "@/types/imsa";

export const metadata: Metadata = {
  title: "Accuracy — RaceIQ IMSA",
  description:
    "How the RaceIQ IMSA forecasts have scored against real results — overall and per class, round by round, measured honestly with no cherry-picking.",
};

export default function Page() {
  const data = getImsaData();
  const calibration = getCalibrationSummary();
  const forwardEval = getForwardEvalSeason();

  const overall: SeasonAccuracyStat =
    data.seasonAccuracy?.overall ?? {
      roundsScored: 0,
      meanPositionError: null,
      podiumHitRate: null,
      winnerHitRate: null,
    };
  const byClass = data.seasonAccuracy?.byClass ?? {};

  // Per-round, per-class accuracy from the completed round files.
  const perRound: Record<string, RoundAccuracyRow[]> = {};
  for (const r of allRoundNumbers()) {
    const detail = getRound(r);
    if (!detail || !detail.completed) continue;
    const cal = data.calendar.find((c) => c.round === r);
    for (const block of detail.classes) {
      if (!block.accuracy) continue;
      (perRound[block.key] ??= []).push({
        round: r,
        name: cal?.name ?? detail.place,
        n: block.accuracy.n,
        mpe: block.accuracy.mean_position_error ?? null,
        podiumHits: block.accuracy.podium_hits ?? 0,
        exact: block.accuracy.exact_matches ?? 0,
        within3: block.accuracy.within_3 ?? 0,
        winnerHit: block.accuracy.winner_hit ?? false,
      });
    }
  }

  // Honest model-vs-baselines summary (only when forward_eval is published).
  const BASELINE_LABELS: Record<string, string> = {
    lastRace: "Last-race form",
    seasonForm: "Season form",
  };
  let forwardEvalSummary: ForwardEvalSummary | null = null;
  if (forwardEval?.modelVsBaselines) {
    const mvb = forwardEval.modelVsBaselines;
    forwardEvalSummary = {
      classRoundsScored: forwardEval.classRoundsScored ?? overall.roundsScored,
      model: mvb.modelWinPodiumBrier,
      baselines: Object.entries(mvb.vs).map(([key, v]) => ({
        key,
        label: BASELINE_LABELS[key] ?? key,
        value: v.baselineWinPodiumBrier,
        delta: v.delta,
        notWorse: v.notWorse,
      })),
    };
  }

  return (
    <AccuracyView
      classes={data.classes}
      overall={overall}
      byClass={byClass}
      perRound={perRound}
      calibration={calibration}
      forwardEval={forwardEvalSummary}
    />
  );
}
