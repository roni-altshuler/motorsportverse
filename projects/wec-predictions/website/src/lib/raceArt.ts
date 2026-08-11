/**
 * Circuit photography mapping — WEC.
 *
 * Per project convention, race art MUST be REAL aerial circuit photography of
 * the ACTUAL venue (NOT SVG diagrams, NOT logos, NOT generic country
 * landscapes). A round with no verified, correct photograph simply falls back
 * to the styled gradient placeholder — that is the correct, honest choice, not
 * a wrong image.
 *
 * There is currently no curated, curl-verified aerial photograph mapped for any
 * 2026 WEC round, so EVERY round resolves to the gradient fallback card. To add
 * a round: source a real, correctly-attributed aerial photo of that exact
 * circuit, `curl -I` the resolved URL to confirm HTTP 200 (image/jpeg), and only
 * then add it below keyed by the calendar venue `key`.
 */

interface RaceArt {
  src: string;
  credit: string;
}

const RACE_ART: Record<string, RaceArt> = {};

const ALIASES: Record<string, string> = {};

/**
 * Pick the curated aerial photo for a given venue `key`. Returns null when no
 * verified photo exists (callers fall back to a styled placeholder rather than a
 * wrong image, per project convention).
 */
export function getRaceArt(key: string | null | undefined): {
  src: string;
  credit: string;
} | null {
  if (!key) return null;
  const normalised = key.toLowerCase().replace(/\s+/g, "-");
  const resolved = RACE_ART[normalised] ?? RACE_ART[ALIASES[normalised] ?? ""];
  return resolved ?? null;
}
