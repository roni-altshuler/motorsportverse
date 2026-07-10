// Pure, fs-free track-type helpers — safe to import from client components.
// IndyCar's three track archetypes drive the calendar badges, the narrative
// framing and the calibration strata (oval / road / street). The model rates
// oval and road/street ability separately — the coarser `trackGroup` names
// which of the two surface ratings drove a round.

import type { TrackGroup, TrackType } from "@/types/indycar";

export const TRACK_TYPE_LABEL: Record<TrackType, string> = {
  oval: "Oval",
  road: "Road Course",
  street: "Street Circuit",
};

/** Short badge label (calendar chips). */
export function trackTypeLabel(t: TrackType | undefined | null): string {
  return t ? TRACK_TYPE_LABEL[t] ?? t : "Road Course";
}

/** One-line racing character used by narrative surfaces. */
export const TRACK_TYPE_BLURB: Record<TrackType, string> = {
  oval:
    "flat-out in traffic at 220 mph — pack dynamics, tire falloff and pit cycles decide it, and one wrong move collects the pack",
  road:
    "permanent road-course racing — braking zones, tire management and racecraft separate the field",
  street:
    "temporary walls with zero margin — track position rules, and cautions can reshuffle everything",
};

/** Label for the coarser surface family the model rates separately. */
export const TRACK_GROUP_LABEL: Record<TrackGroup, string> = {
  oval: "Oval",
  road_street: "Road / Street",
};

export function trackGroupLabel(g: TrackGroup | undefined | null): string {
  return g ? TRACK_GROUP_LABEL[g] ?? g : "Road / Street";
}
