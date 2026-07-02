/**
 * Reduced-motion helpers — pure functions usable in both client and server
 * contexts. Ported verbatim from RaceIQ F1.
 */
export function withReducedMotion<T>(reduced: boolean, full: T, fallback: T): T {
  return reduced ? fallback : full;
}

export function reducedDuration(reduced: boolean, full: number, fallback: number = 0.001): number {
  return reduced ? fallback : full;
}
