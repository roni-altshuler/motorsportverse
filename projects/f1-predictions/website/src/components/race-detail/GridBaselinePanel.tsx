import Link from "next/link";
import type { RaceCalendarEntry, RoundData } from "@/types";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { resolveDriverHeadshot } from "@/lib/headshots";
import { getGridBaseline, gridBaselineArtifactUrl } from "@/lib/gridBaseline";
import { artifactTimestamp } from "@/lib/predictionFreshness";

function SourceIcon({ download = false }: { download?: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={download ? "M12 3v12m-5-5 5 5 5-5M5 17v4h14v-4" : "M7 17 17 7M7 7h10v10"} />
    </svg>
  );
}

export default function GridBaselinePanel({
  data,
  race,
  compact = false,
}: {
  data: RoundData;
  race: RaceCalendarEntry;
  compact?: boolean;
}) {
  const selected = getGridBaseline(data, race);
  if (!selected) return null;
  const { artifact, receipt } = selected;
  const top = artifact.classification.slice(0, 3);
  return (
    <section
      aria-label="Official-grid baseline"
      className="mt-8 border border-[var(--hairline)] bg-[var(--surface-soft)] p-5 sm:p-8"
    >
      <header className="flex flex-wrap items-baseline justify-between gap-3 border-b border-[var(--hairline)] pb-4">
        <h2 className="eyebrow text-[var(--link)]">Official-grid baseline</h2>
        <span className="font-mono text-xs text-[var(--muted)]">Singapore · R17</span>
      </header>
      <div className="grid gap-7 py-6 sm:grid-cols-[1.3fr_1fr]">
        <div className="flex items-center gap-4 min-w-0">
          <DriverPortrait
            headshotUrl={resolveDriverHeadshot(top[0].driver)}
            driver={top[0].driver}
            driverFullName={top[0].driverFullName}
            team={top[0].team}
            teamColor="#3671C6"
            size={64}
          />
          <div className="min-w-0">
            <p className="eyebrow text-[var(--muted)] mb-2">Winner pick · starts P01</p>
            <h3 className="display-sm break-words">{top[0].driverFullName}</h3>
            <p className="body-sm mt-2 text-[var(--muted)]">{top[0].team}</p>
          </div>
        </div>
        <ol
          start={2}
          className="divide-y divide-[var(--hairline)] border-y border-[var(--hairline)]"
        >
          {top.slice(1).map((row) => (
            <li key={row.driver} className="flex items-center gap-4 py-4">
              <span className="font-mono text-sm text-[var(--muted)]">
                P0{row.predictedPosition}
              </span>
              <div>
                <p className="body-md">{row.driverFullName}</p>
                <p className="text-xs text-[var(--muted)] mt-1">{row.team}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
      <p className="body-md max-w-3xl">
        This simple forecast follows the official final starting grid. No win probability is
        assigned; weather, strategy and retirements are not modelled.
      </p>
      <p className="body-sm mt-3 text-[var(--muted)]">
        The model forecast remains withheld. This baseline has its own record and is excluded from
        model accuracy.
      </p>
      <dl className="grid gap-4 mt-6 pt-5 border-t border-[var(--hairline)] sm:grid-cols-2">
        <div>
          <dt className="eyebrow text-[var(--muted)] mb-2">Baseline sealed</dt>
          <dd className="font-mono text-xs leading-6">
            {artifactTimestamp(artifact.generatedAt).label}
          </dd>
        </div>
        <div>
          <dt className="eyebrow text-[var(--muted)] mb-2">Official grid rechecked</dt>
          <dd className="font-mono text-xs leading-6">
            {artifactTimestamp(receipt.sourceRecheckedAt).label}
          </dd>
        </div>
      </dl>
      <div className="mt-5 flex flex-wrap gap-x-6 gap-y-3">
        <Link
          href={compact ? "/race/17#startingGrid" : "#startingGrid"}
          className="link-bugatti text-sm"
        >
          Full final grid →
        </Link>
        <a
          href={receipt.sourceUrls.startingGrid}
          target="_blank"
          rel="noopener noreferrer"
          className="link-bugatti text-sm inline-flex items-center gap-1"
        >
          Official starting grid <SourceIcon />
        </a>
      </div>
      <details className="mt-6 border-t border-[var(--hairline)] pt-4">
        <summary className="cursor-pointer body-sm text-[var(--muted)]">
          Source and sealed record
        </summary>
        <p className="body-sm text-[var(--muted)] mt-3">
          Qualifying and the final grid are separate facts. Russell qualified sixth and starts 21st
          after a power-unit penalty. The baseline was sealed before the race; later source checks
          do not change its original timestamp.
        </p>
        <div className="flex flex-wrap gap-x-6 gap-y-3 mt-4">
          <a
            href={receipt.sourceUrls.qualifying}
            target="_blank"
            rel="noopener noreferrer"
            className="link-bugatti text-sm inline-flex items-center gap-1"
          >
            Official qualifying <SourceIcon />
          </a>
          <a href={gridBaselineArtifactUrl(receipt)} className="link-bugatti text-sm inline-flex items-center gap-1">
            Sealed baseline JSON <SourceIcon download />
          </a>
        </div>
      </details>
    </section>
  );
}
