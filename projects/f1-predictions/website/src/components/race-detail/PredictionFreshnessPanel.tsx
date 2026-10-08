import {
  artifactTimestamp,
  compareArtifactTimes,
  qualifyingAssumption,
  weatherAssumption,
  type FreshnessInput,
  type ProbabilityMetadata,
} from "@/lib/predictionFreshness";

interface Props {
  data: FreshnessInput;
  probabilities: ProbabilityMetadata | null;
  probabilityLoading?: boolean;
  season: number;
  resultLabel?: string;
  trainingYears?: number[];
}

export default function PredictionFreshnessPanel({
  data,
  probabilities,
  probabilityLoading = false,
  season,
  resultLabel,
  trainingYears,
}: Props) {
  const ranking = artifactTimestamp(data.generatedAt);
  const identityConflict =
    !!probabilities && (probabilities.round !== data.round || probabilities.season !== season);
  const probability = artifactTimestamp(identityConflict ? undefined : probabilities?.generatedAt);
  const comparison = compareArtifactTimes(ranking, probability);
  const status = probabilityLoading
    ? "Reading probability metadata"
    : identityConflict
      ? "Probability identity conflict"
      : !probabilities
        ? "Probability export unavailable"
        : comparison.label;
  const qualifying = qualifyingAssumption(data);
  const weather = weatherAssumption(data);
  const warning = identityConflict || (!probabilityLoading && comparison.warning);
  const timestamps = [
    { title: "Ranking export", value: ranking, detail: "Timestamp stored in the ranking file." },
    {
      title: "Probability export",
      value: probability,
      detail: probabilityLoading
        ? "Reading the separate probability file."
        : identityConflict
          ? "The file identifies a different round or season; its time is not used."
          : !probabilities
            ? "The separate file could not be loaded."
            : "Timestamp stored in the probability file.",
    },
  ];
  return (
    <section
      aria-labelledby="prediction-freshness-heading"
      className="mt-5 mb-8 border border-[color:var(--hairline)] bg-[color:var(--surface-soft)]"
    >
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-[color:var(--hairline)] p-5">
        <div>
          <p className="eyebrow mb-1">Prediction context</p>
          <h3 id="prediction-freshness-heading" className="title-sm">
            Freshness &amp; Sources
          </h3>
        </div>
        <p
          role="status"
          className={`max-w-full border border-[color:var(--hairline)] px-2.5 py-1 text-xs ${warning ? "text-[color:var(--warning)]" : "text-[color:var(--muted)]"}`}
        >
          {status}
        </p>
      </header>
      <div className="p-5">
        <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          {timestamps.map(({ title, value, detail }) => (
            <div key={title} className="min-w-0">
              <dt className="eyebrow mb-2">{title}</dt>
              <dd className="font-mono text-[12px] sm:text-[13px] break-words text-[color:var(--ink)]">
                {title === "Probability export" && probabilityLoading ? (
                  "Reading metadata…"
                ) : title === "Probability export" && identityConflict ? (
                  "Identity conflict"
                ) : title === "Probability export" && !probabilities ? (
                  "Unavailable"
                ) : value.state === "known" ? (
                  <time dateTime={value.iso}>{value.label}</time>
                ) : (
                  value.label
                )}
              </dd>
              <dd className="mt-1 body-sm text-[color:var(--muted)]">
                {value.state === "invalid"
                  ? "The stored time is invalid or has no explicit timezone."
                  : detail}
              </dd>
            </div>
          ))}
        </dl>
        {!probabilityLoading && !identityConflict && probabilities && comparison.note && (
          <p className="mt-4 border-l-2 border-[color:var(--warning)] pl-3 body-sm text-[color:var(--body)]">
            {comparison.note}
          </p>
        )}
        <dl className="mt-5 grid grid-cols-1 gap-5 border-t border-[color:var(--hairline)] pt-5 sm:grid-cols-2">
          {[
            { title: "Qualifying input", ...qualifying },
            { title: "Weather input", ...weather },
          ].map(({ title, label, detail, warning }) => (
            <div key={title} className="min-w-0">
              <dt className="eyebrow mb-2">{title}</dt>
              <dd
                className={`text-sm font-semibold ${warning ? "text-[color:var(--warning)]" : "text-[color:var(--ink)]"}`}
              >
                {label}
              </dd>
              <dd className="mt-1 body-sm text-[color:var(--muted)] break-words">{detail}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-5 border-t border-[color:var(--hairline)] pt-4">
          <dl className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <dt className="eyebrow">Forecast input cutoff</dt>
            <dd className="text-sm font-semibold text-[color:var(--warning)]">Not published</dd>
          </dl>
          <p className="mt-1 body-sm text-[color:var(--muted)]">
            Export times do not establish when forecast inputs were frozen or whether both files
            used the same inputs.
          </p>
        </div>
        {(resultLabel || !!trainingYears?.length) && (
          <p className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[color:var(--muted)]">
            {resultLabel && <span>{resultLabel}</span>}
            {!!trainingYears?.length && (
              <span>
                <span className="font-mono">{trainingYears.join(", ")}</span> training data
              </span>
            )}
          </p>
        )}
      </div>
    </section>
  );
}
