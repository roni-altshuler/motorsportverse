import type { RaceCalendarEntry, RoundData } from "@/types";
import { artifactTimestamp } from "@/lib/predictionFreshness";

export default function PublicationNotice({
  data,
  race,
}: {
  data: RoundData;
  race: RaceCalendarEntry;
}) {
  const hold = data.publicationHold;
  if (!hold) return null;
  const withdrawn = hold.reason === "event-mismatch";
  return (
    <aside
      aria-label="Publication review"
      className="border border-[var(--hairline)] bg-[var(--surface-soft)] p-5 sm:p-8"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--hairline)] pb-4">
        <p className="eyebrow text-[var(--warning)]">
          {withdrawn ? "Forecast withheld" : "Result without a forecast"}
        </p>
        <span className="font-mono text-xs text-[var(--muted)]">
          R{String(race.round).padStart(2, "0")} / {race.circuit}
        </span>
      </div>
      <h2 className="display-sm mt-5 mb-3">
        {withdrawn ? "This forecast needs a fresh start" : "An honest gap in the record"}
      </h2>
      <p className="body-md max-w-3xl text-[var(--body)]">{hold.message}</p>
      <dl className="mt-6 grid gap-5 sm:grid-cols-3 border-t border-[var(--hairline)] pt-5">
        <div>
          <dt className="eyebrow mb-2">Race result</dt>
          <dd className="body-sm">
            {data.actualResults ? "Verified classification available" : "No verified race result"}
          </dd>
        </div>
        <div>
          <dt className="eyebrow mb-2">Forecast grade</dt>
          <dd className="body-sm">
            {withdrawn
              ? "Withdrawn · excluded from accuracy"
              : "Unavailable · no pre-race forecast"}
          </dd>
        </div>
        <div>
          <dt className="eyebrow mb-2">Source checked</dt>
          <dd className="font-mono text-xs leading-6 text-[var(--muted)]">
            {artifactTimestamp(hold.reviewedAt).label}
          </dd>
        </div>
      </dl>
      {race.raceStartUtc && (
        <p className="mt-5 font-mono text-sm">
          Lights out · {artifactTimestamp(race.raceStartUtc).label} · 20:00 Singapore
        </p>
      )}
      {hold.originalForecast && (
        <p className="mt-4 body-sm text-[var(--muted)]">
          Original forecast preserved from{" "}
          {artifactTimestamp(hold.originalForecast.generatedAt).label}. A calendar correction does
          not turn it into a forecast for another race.
        </p>
      )}
      <a
        href={hold.sourceUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="link-bugatti inline-block mt-5"
      >
        Official event and session schedule ↗
      </a>
    </aside>
  );
}
