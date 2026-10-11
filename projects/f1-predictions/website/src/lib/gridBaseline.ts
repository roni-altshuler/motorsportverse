import sealed from "../../public/data/baselines/2026_round_17_f994d9796f18.json";
import record from "../../public/data/baselines/2026_round_17.json";
import type {
  GridBaselineArtifact,
  GridBaselineReceipt,
  RaceCalendarEntry,
  RoundData,
} from "@/types";
import { artifactTimestamp } from "./predictionFreshness";

export const GRID_BASELINE_SHA256 =
  "f994d9796f18458398c2733e48ab27a984cff51aa57874323d1aa61f6cde0c58";
const ORIGINAL_SEAL_TIME = "2026-10-11T06:53:07.672909Z";

/** Select only this independent sealed stream, and hide it if official inputs change. */
export function getGridBaseline(
  data: RoundData,
  race: RaceCalendarEntry,
  artifact: GridBaselineArtifact = sealed as GridBaselineArtifact,
  receipt: GridBaselineReceipt = record as GridBaselineReceipt,
): { artifact: GridBaselineArtifact; receipt: GridBaselineReceipt } | null {
  const times = [
    artifact.inputCutoff,
    artifact.generatedAt,
    receipt.sourceRecheckedAt,
    receipt.stagedAt,
    artifact.raceStartUtc,
  ].map(artifactTimestamp);
  if (times.some((t) => t.state !== "known")) return null;
  const [cutoff, generated, checked, staged, start] = times.map((t) =>
    t.state === "known" ? t.epoch : NaN,
  );
  if (!(cutoff <= generated && generated <= checked && checked <= staged && staged < start))
    return null;
  if (
    artifact.forecastKind !== "official_grid_baseline" ||
    receipt.forecastKind !== artifact.forecastKind ||
    artifact.status !== "sealed_review_only" ||
    artifact.probabilities !== null ||
    artifact.modelPromotion !== false ||
    artifact.publicationHoldReleased !== false ||
    receipt.publicationHoldReleased !== false ||
    receipt.modelForecastChanged !== false ||
    receipt.graded !== false ||
    receipt.evaluationStream !== "baselines/official_grid" ||
    receipt.artifactSha256 !== GRID_BASELINE_SHA256 ||
    receipt.baselineId !== `2026:17:official_grid:${GRID_BASELINE_SHA256}` ||
    artifact.generatedAt !== ORIGINAL_SEAL_TIME ||
    receipt.sealedAt !== artifact.generatedAt ||
    artifact.season !== 2026 ||
    artifact.round !== 17 ||
    receipt.season !== artifact.season ||
    receipt.round !== artifact.round ||
    race.round !== artifact.round ||
    data.round !== artifact.round ||
    race.gpKey !== "Singapore" ||
    data.gpKey !== race.gpKey ||
    artifact.name !== race.name ||
    data.name !== race.name ||
    artifact.circuit !== race.circuit ||
    data.circuit !== race.circuit ||
    data.date !== race.date ||
    race.date !== "2026-10-11" ||
    race.raceStartUtc !== artifact.raceStartUtc
  )
    return null;
  const grid = data.weekendResults?.sessions.find(
    (s) => s.key === "startingGrid" && s.status === "official",
  );
  if (
    !grid ||
    grid.sourceUrl !== receipt.sourceUrls.startingGrid ||
    grid.rows.length !== 22 ||
    artifact.classification.length !== 22
  )
    return null;
  const positions = new Map(grid.rows.map((r) => [r.driver, r.position]));
  const expected = new Set(artifact.classification.map((r) => r.driver));
  if (
    positions.size !== 22 ||
    expected.size !== 22 ||
    artifact.classification.some(
      (r, i) =>
        r.predictedPosition !== i + 1 ||
        r.officialGridPosition !== i + 1 ||
        positions.get(r.driver) !== i + 1,
    )
  )
    return null;
  if (artifact.winnerPick.driver !== artifact.classification[0].driver) return null;
  return { artifact, receipt };
}

export function gridBaselineArtifactUrl(receipt: GridBaselineReceipt): string {
  return `${process.env.NEXT_PUBLIC_BASE_PATH || ""}/data/baselines/${receipt.artifactFile}`;
}
