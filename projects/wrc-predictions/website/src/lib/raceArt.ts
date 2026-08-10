/**
 * Rally photography mapping — WRC.
 *
 * Per project convention, race art MUST be REAL aerial/stage photography of the
 * ACTUAL rally (NOT SVG diagrams, NOT logos, NOT generic country landscapes, and
 * NEVER a circuit photo — rally rounds are run over public special stages, not
 * fixed circuits). A rally with no verified, correct photograph simply falls
 * back to the styled gradient placeholder — that is the correct, honest choice,
 * not a wrong image.
 *
 * There is currently no curated, curl-verified stage photograph mapped for any
 * 2026 WRC round, so EVERY rally resolves to the gradient fallback card. To add
 * a rally: source a real, correctly-attributed stage/aerial photo of that exact
 * event, `curl -I` the resolved URL to confirm HTTP 200 (image/jpeg), and only
 * then add it below keyed by the calendar venue `key`.
 */

interface RaceArt {
  src: string;
  credit: string;
}

const RACE_ART: Record<string, RaceArt> = {};

const ALIASES: Record<string, string> = {};

/**
 * Pick the curated stage photo for a given venue `key`. Returns null when no
 * verified photo exists (the calendar falls back to a styled placeholder rather
 * than a non-stage or wrong-rally image, per project convention).
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
