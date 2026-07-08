// Pure, fs-free track-type helpers — safe to import from client components.
// NASCAR's four track archetypes drive the calendar badges, the narrative
// framing and the calibration strata (superspeedway / intermediate / short / road).

import type { TrackType } from "@/types/nascar";

export const TRACK_TYPE_LABEL: Record<TrackType, string> = {
  superspeedway: "Superspeedway",
  intermediate: "Intermediate",
  short: "Short Track",
  road: "Road Course",
};

/** Short badge label (calendar chips). */
export function trackTypeLabel(t: TrackType | undefined | null): string {
  return t ? TRACK_TYPE_LABEL[t] ?? t : "Oval";
}

/** One-line racing character used by narrative surfaces. */
export const TRACK_TYPE_BLURB: Record<TrackType, string> = {
  superspeedway:
    "pack racing in the draft — anyone in the lead pack can win, and one wrong move collects half the field",
  intermediate:
    "the aero-dependent 1.5-mile style that decides most Cup weekends — clean air and pit execution rule",
  short:
    "beating and banging at close quarters — track position and restarts matter more than raw pace",
  road:
    "left AND right turns — braking zones, tire management and racecraft separate the field",
};

/** Sum of the advertised stage laps, when the export ships them. */
export function totalLaps(stageLaps: number[] | undefined | null): number | null {
  if (!stageLaps || stageLaps.length === 0) return null;
  return stageLaps.reduce((a, b) => a + b, 0);
}
