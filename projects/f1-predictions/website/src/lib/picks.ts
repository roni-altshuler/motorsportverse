/**
 * picks.ts — localStorage helpers for the "Beat the Model" pick'em game.
 *
 * A fan locks in a top-3 podium prediction for an upcoming round; we persist it
 * in the browser only (no account, no server) keyed by season + round, then
 * grade it against the official result once the race is classified.
 *
 * Everything here is SSR-safe: every read/write is guarded on `typeof window`
 * so the static export never touches localStorage during render or prerender.
 * Failures (private mode, quota, disabled storage) degrade to no-ops — the game
 * simply doesn't persist rather than crashing the page.
 */

export interface UserPodiumPick {
  /** Ordered top-3 driver codes (P1, P2, P3). May hold fewer while picking. */
  podium: string[];
  /** ISO timestamp of the last save — powers the subtle "locked in" note. */
  savedAt: string;
}

const KEY_PREFIX = "f1:pickem:v1";

function storageKey(season: number, round: number): string {
  return `${KEY_PREFIX}:${season}:${round}`;
}

/** Read the saved podium pick for a round, or null when none / unavailable. */
export function loadPodiumPick(season: number, round: number): UserPodiumPick | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(storageKey(season, round));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<UserPodiumPick>;
    if (!parsed || !Array.isArray(parsed.podium)) return null;
    // Defensively coerce to <=3 clean, de-duplicated string codes.
    const seen = new Set<string>();
    const podium = parsed.podium
      .filter((d): d is string => typeof d === "string" && d.length > 0)
      .filter((d) => (seen.has(d) ? false : (seen.add(d), true)))
      .slice(0, 3);
    return { podium, savedAt: typeof parsed.savedAt === "string" ? parsed.savedAt : "" };
  } catch {
    return null;
  }
}

/** Persist a podium pick (up to 3 driver codes, in P1→P3 order). */
export function savePodiumPick(season: number, round: number, podium: string[]): void {
  if (typeof window === "undefined") return;
  try {
    const clean = podium
      .filter((d): d is string => typeof d === "string" && d.length > 0)
      .slice(0, 3);
    const payload: UserPodiumPick = { podium: clean, savedAt: new Date().toISOString() };
    window.localStorage.setItem(storageKey(season, round), JSON.stringify(payload));
  } catch {
    /* private mode / quota — the game just doesn't persist, no crash */
  }
}

/** Remove a saved pick (used by the "Start over" affordance). */
export function clearPodiumPick(season: number, round: number): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(storageKey(season, round));
  } catch {
    /* no-op */
  }
}

/**
 * Grade a podium prediction against a target top-3 (the official result, or the
 * model's own podium) by set-membership overlap — how many of the three picked
 * drivers landed on that podium, regardless of the exact P1/P2/P3 order within
 * it. This mirrors the model's own podium-accuracy definition so a scoreline
 * like "You: 2/3 · Model: 3/3" is an apples-to-apples comparison.
 */
export function gradePodium(
  picked: string[],
  target: string[],
): { hits: number; total: number } {
  const targetSet = new Set(target.slice(0, 3));
  const seen = new Set<string>();
  let hits = 0;
  for (const d of picked.slice(0, 3)) {
    if (!seen.has(d) && targetSet.has(d)) hits += 1;
    seen.add(d);
  }
  return { hits, total: Math.min(3, targetSet.size) || 3 };
}
