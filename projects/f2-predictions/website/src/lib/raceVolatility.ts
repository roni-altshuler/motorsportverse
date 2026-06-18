/**
 * Per-race volatility scoring (F2).
 *
 * Each driver in a round's classification carries a finish-range
 * (`finishRangeLow`, `finishRangeHigh`) representing how wide the model's
 * per-driver position interval is. Tight intervals across the front of the
 * grid signal a high-confidence forecast; wide intervals signal a chaotic
 * race outlook (reverse-grid sprint shuffle, fresh roster, wet circuit, …).
 *
 * We collapse those per-driver widths into one scalar in [0, 1] by averaging
 * the top-N widths and normalising against a reference width chosen to match
 * the bucketing thresholds below:
 *
 *   - score < 0.33  → "high confidence"    (tight front-end)
 *   - 0.33..0.66    → "moderate volatility"
 *   - score > 0.66  → "chaotic race"
 *
 * Wording is intentionally model-agnostic — never any internal terminology.
 * This is a pure, fs-free helper so client components can import it directly.
 */

import type { ClassificationEntry } from "@/types/f2";

const REF_WIDTH = 4; // width of 4 positions ≈ "fully volatile" for the score=1 anchor
const TOP_N = 6;

export type VolatilityBucket = "high" | "moderate" | "chaotic";

export interface RaceVolatility {
  /** Normalised score in [0, 1]. Higher = more volatile. */
  score: number;
  bucket: VolatilityBucket;
  /** Short user-facing label, free of any modelling jargon. */
  label: string;
  /** One-line explanation suitable for a chip tooltip. */
  description: string;
  /** Number of drivers actually used in the aggregate. */
  samples: number;
}

const BUCKET_LABEL: Record<VolatilityBucket, string> = {
  high: "High Confidence",
  moderate: "Moderate Volatility",
  chaotic: "Chaotic Race",
};

const BUCKET_DESCRIPTION: Record<VolatilityBucket, string> = {
  high: "Tight forecast across the front of the grid — small spread between predicted and likely finishing positions.",
  moderate: "Some uncertainty up front — the predicted order has wiggle room and a few drivers could swap places.",
  chaotic: "Wide range of plausible outcomes across the front of the grid — expect surprises.",
};

function bucketFor(score: number): VolatilityBucket {
  if (score < 0.33) return "high";
  if (score < 0.66) return "moderate";
  return "chaotic";
}

/**
 * Compute a per-race volatility scalar from the top-N drivers' prediction
 * intervals. Returns `null` when the classification is empty or has no range
 * data populated.
 */
export function computeRaceVolatility(
  classification: ClassificationEntry[] | null | undefined,
): RaceVolatility | null {
  if (!classification || classification.length === 0) return null;

  const sorted = [...classification].sort((a, b) => a.position - b.position);
  const head = sorted.slice(0, TOP_N);

  const widths: number[] = [];
  for (const c of head) {
    if (typeof c.finishRangeLow === "number" && typeof c.finishRangeHigh === "number") {
      widths.push(Math.max(0, c.finishRangeHigh - c.finishRangeLow));
    }
  }

  if (widths.length === 0) return null;

  const meanWidth = widths.reduce((a, b) => a + b, 0) / widths.length;
  // Normalise. Clamp at 1 so very chaotic races don't blow past the scale.
  const score = Math.min(1, Math.max(0, meanWidth / REF_WIDTH));
  const bucket = bucketFor(score);

  return {
    score,
    bucket,
    label: BUCKET_LABEL[bucket],
    description: BUCKET_DESCRIPTION[bucket],
    samples: widths.length,
  };
}
