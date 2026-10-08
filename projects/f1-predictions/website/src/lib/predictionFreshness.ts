import type { ProbabilityRoundData, RoundData } from "@/types";

export type FreshnessInput = Pick<
  RoundData,
  | "round"
  | "generatedAt"
  | "qualifyingDataAvailable"
  | "gridProvenance"
  | "dataFreshness"
  | "weatherData"
>;
export type ProbabilityMetadata = Pick<ProbabilityRoundData, "round" | "season" | "generatedAt">;

type Timestamp =
  | { state: "known"; iso: string; epoch: number; label: string }
  | { state: "missing" | "invalid"; label: string };

const text = (value: unknown) => (typeof value === "string" ? value.trim() : "");

/** An export timestamp must identify an instant. Never guess a local timezone
 * or allow Date.parse to silently roll an impossible calendar date forward. */
export function artifactTimestamp(value: unknown): Timestamp {
  if (value == null || value === "") return { state: "missing", label: "Not published" };
  const raw = text(value);
  if (typeof value === "string" && !raw) return { state: "missing", label: "Not published" };
  const parts = raw.match(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$/,
  );
  if (!parts) return { state: "invalid", label: "Invalid timestamp" };
  const [, y, mo, d, h, mi, s] = parts;
  const calendar = new Date(`${y}-${mo}-${d}T00:00:00Z`);
  const epoch = Date.parse(raw);
  if (
    !Number.isFinite(epoch) ||
    calendar.getUTCFullYear() !== Number(y) ||
    calendar.getUTCMonth() + 1 !== Number(mo) ||
    calendar.getUTCDate() !== Number(d) ||
    Number(h) > 23 ||
    Number(mi) > 59 ||
    Number(s) > 59
  )
    return { state: "invalid", label: "Invalid timestamp" };
  const date = new Date(epoch);
  return {
    state: "known",
    iso: date.toISOString(),
    epoch,
    label:
      new Intl.DateTimeFormat("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hourCycle: "h23",
        timeZone: "UTC",
      }).format(date) + " UTC",
  };
}

export function compareArtifactTimes(ranking: Timestamp, probability: Timestamp) {
  if (ranking.state === "invalid" || probability.state === "invalid") {
    return { label: "Timestamp needs review", warning: true, note: null };
  }
  if (ranking.state !== "known" || probability.state !== "known") {
    return { label: "Incomplete time metadata", warning: false, note: null };
  }
  if (ranking.epoch === probability.epoch) {
    return { label: "Matching export times", warning: false, note: null };
  }
  return {
    label: "Different export times",
    warning: true,
    note:
      ranking.epoch < probability.epoch
        ? "The ranking export is older. A later probability export does not establish refreshed rankings or inputs."
        : "The probability export is older. A later ranking export does not establish refreshed probabilities or inputs.",
  };
}

export function qualifyingAssumption(data: FreshnessInput) {
  const source = text(data.dataFreshness?.qualifyingSource);
  const estimated =
    /estimate|synthetic|static/i.test(source) || data.gridProvenance === "estimated";
  const verified = data.gridProvenance === "real-quali-verified";
  if (
    (verified && estimated) ||
    (data.qualifyingDataAvailable === true && estimated) ||
    (data.qualifyingDataAvailable === false && (verified || /fastf1/i.test(source)))
  )
    return {
      label: "Conflicting qualifying metadata",
      detail: "The recorded availability and source disagree.",
      warning: true,
    };
  if (estimated || data.qualifyingDataAvailable === false) {
    return {
      label: "Estimated qualifying",
      detail: "This ranking does not record actual qualifying input.",
      warning: true,
    };
  }
  if (data.qualifyingDataAvailable === true || verified) {
    return {
      label: verified ? "Verified grid recorded" : "Qualifying data recorded",
      detail: source ? `Recorded source: ${source}.` : "Source not recorded.",
      warning: false,
    };
  }
  return {
    label: "Qualifying input unverified",
    detail: source
      ? `Recorded source: ${source}; availability not recorded.`
      : "Availability and source not recorded.",
    warning: true,
  };
}

export function weatherAssumption(data: FreshnessInput) {
  const declared = text(data.dataFreshness?.weatherSource);
  const recorded = text(data.weatherData?.source);
  const normalize = (s: string) => s.toLowerCase().replace(/^cached$/, "cache");
  if (declared && recorded && normalize(declared) !== normalize(recorded)) {
    return {
      label: "Conflicting weather metadata",
      detail: `Recorded sources: ${declared} and ${recorded}.`,
      warning: true,
    };
  }
  const source = declared || recorded;
  if (normalize(source) === "static")
    return {
      label: "Static weather estimate",
      detail: "This ranking uses an estimated weather input.",
      warning: true,
    };
  if (normalize(source) === "api")
    return {
      label: "API weather recorded",
      detail: "Its input observation time is not published here.",
      warning: false,
    };
  if (normalize(source) === "cache")
    return {
      label: "Cached weather recorded",
      detail: "The cached input's age is not published here.",
      warning: true,
    };
  return {
    label: "Weather input unverified",
    detail: source ? `Recorded source: ${source}.` : "Source not recorded.",
    warning: true,
  };
}
