// Display-name layer between raw registry identifiers and user-facing copy.
//
// The registry (an engineering artifact) names algorithms; the site must not.
// Everything user-visible goes through these maps / the scrubber so copy says
// what the models do ("calibrated probabilities", "championship simulation")
// rather than how they do it. fs-free — safe to import from client components.

/** Long-form labels for `uses_core` module identifiers. */
export const CORE_LABELS: Record<string, string> = {
  calibration: "Probability calibration",
  championship: "Championship simulation",
  standings: "Standings projection",
  elo: "Driver-skill ratings",
  conformal: "Uncertainty intervals",
  eval: "Forward evaluation",
  drift: "Drift monitoring",
  promotion: "Gated model promotion",
  leakage: "Leakage guards",
  registry: "Model registry",
  interfaces: "Predictor interfaces",
};

/** Compact chip labels for `uses_core` (cards, rails). */
export const CORE_LABELS_SHORT: Record<string, string> = {
  calibration: "calibration",
  championship: "championship sim",
  standings: "standings",
  elo: "driver skill",
  conformal: "uncertainty",
  eval: "forward eval",
  drift: "drift watch",
  promotion: "promotion",
  leakage: "leakage guards",
  registry: "model registry",
  interfaces: "interfaces",
};

/** Friendly names for registry `models` identifiers. */
export const MODEL_LABELS: Record<string, string> = {
  "quali-regression": "Qualifying-pace model",
  "plackett-luce": "Probability calibration",
  "race-simulator": "Race simulator",
  "driver-skill-elo": "Driver-skill model",
  "reverse-grid-sprint": "Reverse-grid sprint head",
  "championship-monte-carlo": "Championship simulation",
  standings: "Standings projection",
};

/** Friendly names for registry `tags`. */
export const TAG_LABELS: Record<string, string> = {
  "calibrated-probabilities": "calibrated probabilities",
  "monte-carlo": "race simulation",
  "continuous-learning": "continuous learning",
  "feeder-series": "feeder series",
  "spec-series": "spec series",
  "reverse-grid": "reverse grid",
  scaffolded: "scaffolded",
};

export const coreLabel = (k: string) => CORE_LABELS[k] ?? k;
export const coreLabelShort = (k: string) => CORE_LABELS_SHORT[k] ?? k;
export const modelLabel = (k: string) => MODEL_LABELS[k] ?? k;
export const tagLabel = (k: string) => TAG_LABELS[k] ?? k;

// Ordered replacements for free-text registry descriptions. Specific phrases
// first, then generic fallbacks, so grammar survives the rewrite.
const SCRUB: [RegExp, string][] = [
  [
    /qualifying-pace regression, Plackett[-–]Luce probability calibration, and a per-lap Monte Carlo race simulator/gi,
    "a qualifying-pace model, field-strength probability calibration, and a per-lap race simulator",
  ],
  [
    /\(Elo with rookie pooling \+ finishing history \+ optional gradient-boosted signal\)/g,
    "(rookie-aware ratings, finishing history, and an optional machine-learned signal)",
  ],
  [
    /\(Elo with rookie pooling \+ finishing history\)/g,
    "(rookie-aware ratings and finishing history)",
  ],
  [/Monte[-\s]Carlo win\/podium probabilities/gi, "simulated win/podium probabilities"],
  [/Plackett[-–]Luce/gi, "field-strength calibration"],
  [/Monte[-\s]Carlo/gi, "simulation-based"],
  [/gradient[-\s]boosted/gi, "machine-learned"],
  [/XGBoost|\bXGB\b/g, "machine-learned"],
  [/isotonic/gi, "calibrated"],
  [/\bElo\b/g, "driver-skill ratings"],
  // Grammar repair for template-generated registry text ("a IndyCar ...").
  [/\ba (IndyCar|IMSA)\b/g, "an $1"],
];

/** Strip algorithm names from user-facing registry text. */
export function scrubTech(text?: string): string {
  if (!text) return "";
  let out = text;
  for (const [re, sub] of SCRUB) out = out.replace(re, sub);
  return out;
}

/** The canonical "what a scaffold inherits" story, in registry `uses_core` keys. */
export const CORE_CAPABILITIES: { key: string; label: string; blurb: string }[] = [
  { key: "calibration", label: "Probability calibration", blurb: "Raw pace in, honest win/podium probabilities out." },
  { key: "championship", label: "Championship simulation", blurb: "Season projections over every remaining round." },
  { key: "standings", label: "Standings projection", blurb: "Points math and title permutations, solved once." },
  { key: "eval", label: "Forward evaluation", blurb: "Every forecast graded against the real result." },
  { key: "drift", label: "Drift monitoring", blurb: "Alerts when the model and the sport diverge." },
  { key: "leakage", label: "Leakage guards", blurb: "Prior-rounds-only discipline, enforced at the boundary." },
];
