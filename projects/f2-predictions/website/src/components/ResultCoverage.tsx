"use client";

import Link from "next/link";
import { resultCoverage, type CoverageRound } from "@/lib/resultCoverage";
import { useCoverageClock } from "@/lib/useCoverageClock";

function utcDate(value?: string) {
  const date = value ? new Date(value) : null;
  return date && Number.isFinite(date.getTime())
    ? date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    : "Unknown";
}

export default function ResultCoverage({ calendar, generatedAt, asOf }: {
  calendar: CoverageRound[];
  generatedAt?: string;
  asOf: string;
}) {
  const now = useCoverageClock(asOf);
  const coverage = resultCoverage(calendar, now);
  const behind = coverage.pastDue.length > 0;
  const empty = calendar.length === 0;
  const title = empty ? "No result coverage published" : behind ? "Result coverage is behind" : coverage.unknown.length
    ? "Result coverage needs review" : "Published result coverage";

  return (
    <section aria-label="Result coverage" className="mt-8 overflow-hidden rounded-[4px] border border-[color:var(--hairline)] bg-[color:var(--surface)]">
      <div className={`border-l-4 p-5 sm:p-6 ${behind || empty || coverage.unknown.length ? "border-[color:var(--warning)]" : "border-[color:var(--accent)]"}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-xl uppercase tracking-wide">{title}</h2>
          <span className="font-mono text-xs text-[color:var(--muted)]">AS OF {utcDate(now).toUpperCase()} UTC</span>
        </div>
        <dl className="mt-5 grid grid-cols-2 gap-x-5 gap-y-4 sm:grid-cols-3">
          <div><dt className="text-xs text-[color:var(--muted)]">Rounds imported</dt><dd className="mt-1 font-mono text-xl">{empty ? "—" : coverage.imported.length}<span className="text-sm text-[color:var(--muted)]"> {empty ? "" : `/ ${calendar.length}`}</span></dd></div>
          <div><dt className="text-xs text-[color:var(--muted)]">Latest imported result</dt><dd className="mt-1 text-sm font-medium">{coverage.latest ? `R${coverage.latest.round} · ${coverage.latest.name}` : "None yet"}</dd></div>
          <div><dt className="text-xs text-[color:var(--muted)]">Dataset exported</dt><dd className="mt-1 text-sm font-medium">{utcDate(generatedAt)} UTC</dd></div>
        </dl>
        <p className="mt-4 text-sm leading-relaxed text-[color:var(--body-strong)]">
          {empty ? "The season calendar is unavailable, so result coverage cannot be assessed. " : ""}
          {behind ? `${coverage.pastDue.length} scheduled ${coverage.pastDue.length === 1 ? "round is" : "rounds are"} past due and ${coverage.pastDue.length === 1 ? "has" : "have"} no imported result. ` : ""}
          {coverage.unknown.length ? `${coverage.unknown.length} unimported ${coverage.unknown.length === 1 ? "round has" : "rounds have"} an unverified date. ` : ""}
          {behind ? "Standings and forecasts reflect the available snapshot. " : ""}
          Source availability has not been verified here. Export time is not a source freshness check.
        </p>
        {behind && (
          <details className="mt-4 text-sm">
            <summary className="w-fit cursor-pointer rounded py-1 font-medium underline decoration-[color:var(--hairline)] underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[color:var(--accent)]">View past-due rounds</summary>
            <ul className="mt-3 flex flex-wrap gap-2" aria-label="Past-due rounds">
              {coverage.pastDue.map((round) => <li key={round.round}><Link href={`/race/${round.round}`} className="inline-block border border-[color:var(--hairline)] px-3 py-2 text-xs transition-colors hover:border-[color:var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]">R{round.round} · {round.name}</Link></li>)}
            </ul>
          </details>
        )}
      </div>
    </section>
  );
}
