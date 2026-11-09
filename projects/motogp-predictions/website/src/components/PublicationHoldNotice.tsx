import type { PublicationHold } from "@/lib/publication";

export default function PublicationHoldNotice({ hold }: { hold: PublicationHold }) {
  const hub = process.env.NEXT_PUBLIC_BASE_PATH?.replace(/\/projects\/motogp$/, "") || "https://roni-altshuler.github.io/motorsportverse";
  const mismatch = hold.issues.some(issue => issue.code === "event-identity-mismatch");
  return <section className="mx-auto max-w-3xl px-6 py-16" aria-labelledby="publication-title">
    <p className="eyebrow">MotoGP · {hold.season}</p>
    <h1 id="publication-title" className="font-display text-4xl mt-3 mb-6">Publication temporarily withheld</h1>
    <p className="text-lg">{hold.message}</p>
    <p className="mt-4">{mismatch ? "Results were paired with different calendar events." : "The available event coverage cannot yet be published safely."} Forecasts, standings, championship odds and performance figures are unavailable while this is corrected.</p>
    <ul className="mt-6 space-y-4">
      {hold.issues.map((issue, index) => <li key={`${issue.code}:${issue.round ?? "none"}:${index}`} className="border border-[var(--hairline)] rounded-xl p-4">
        <p className="font-bold">{issue.message}</p>
        {issue.scheduled && issue.recorded ? <p className="mt-2">
          Scheduled: {issue.scheduled.venue} · {issue.scheduled.date}.<br />
          Stored result: {issue.recorded.venue} · {issue.recorded.date}.
          {issue.matchingScheduledRounds?.length === 1 ? ` The stored event belongs to scheduled round ${issue.matchingScheduledRounds[0]}.` : ""}
        </p> : null}
      </li>)}
    </ul>
    <p className="mt-6">No missing result has been filled in, and existing forecasts have not been relabeled. Verified session inputs and supported round coverage are required before figures return.</p>
    <details className="mt-6">
      <summary className="cursor-pointer py-3">Source evidence</summary>
      <p className="text-sm break-words">Preserved snapshot: {hold.sourceSnapshot}. SHA-256: {hold.snapshotSha256}.</p>
      <ul className="mt-3 space-y-2">{hold.references.map((url, i) => <li key={url}><a className="underline inline-block py-2" href={url}>{i === 0 ? "Official MotoGP calendar" : "Official Australian Grand Prix cancellation statement"}</a></li>)}</ul>
    </details>
    <a className="inline-block underline mt-8 py-3" href={`${hub}/track-record/`}>Other MotorsportVerse track records →</a>
  </section>;
}
