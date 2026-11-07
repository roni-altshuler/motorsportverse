"use client";

import Link from "next/link";
import { useState } from "react";
import WinnerTimeline from "./WinnerTimeline";
import { ROLLING_DAYS, recordView, selectRecords, summarize, winnerTimeline, type RecordBasis, type RecordStatus, type TrackRecordData, type WinnerRecord } from "@/lib/trackRecord";

const pct = (value: number) => `${value.toFixed(1)}%`;
const dateLabel = (date: string) => new Date(`${date}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const STATUS = { compared: "Compared", scored: "Scored", pending: "Pending", missing: "Missing record", held: "Withheld", unverified: "Unverified record", incomplete: "Incomplete record" };
const surface = { background: "var(--bg-surface, var(--panel))", border: "1px solid var(--border, var(--line))", borderRadius: 12, padding: "clamp(16px, 3vw, 28px)" };
function name(row: Pick<WinnerRecord, "positions">, id: string | null) { return id === null ? "Not recorded" : row.positions.find(p => p.id === id)?.name ?? id; }
function outcome(status: RecordStatus | "compared", correct: boolean | null) {
  if (status === "compared") return correct ? "Winner match" : "Different winner";
  if (status === "scored") return correct ? "Correct" : "Miss";
  return STATUS[status];
}

export default function WinnerTrackRecord({ data, season, onSeasonChange }: {
  data: TrackRecordData; season: number; onSeasonChange: (season: number) => void;
}) {
  const [basis, setBasis] = useState<RecordBasis>("comparison");
  const comparison = basis === "comparison";
  const [scopeChoice, setScopeChoice] = useState("");
  const seasons = [...new Set([data.currentSeason, ...data.records.map(r => r.season)])].filter(year => year > 0).sort((a, b) => b - a);
  const scopes = [...new Map(data.records.filter(r => r.season === season).map(r => [r.scope, r.scopeLabel])).entries()];
  const scope = scopes.some(([key]) => key === scopeChoice) ? scopeChoice : scopes[0]?.[0] ?? "";
  const rows = selectRecords(data.records, season, scope), summary = summarize(data.records, season, scope, basis);
  const points = winnerTimeline(data.records, season, scope, basis);
  const verified = summarize(data.records, season, scope);
  const dated = points.at(-1)?.settled ?? 0;
  const undated = summary.settled - dated;
  const counts = (status: RecordStatus | "compared") => rows.filter(r => recordView(r, basis).status === status).length;
  const evaluationHref = `/accuracy${season === data.currentSeason ? "" : `?season=${season}`}`;
  return <div style={{ maxWidth: 1120, margin: "0 auto", padding: "40px 16px 80px", color: "var(--text, var(--ink))", overflowWrap: "anywhere" }}>
    <header className="mb-8"><p className="eyebrow">{data.label} · {comparison ? "Historical saved comparisons" : "Verified pre-race winner picks"}</p><h1 className="text-4xl sm:text-5xl font-bold mt-2 mb-3">Winner record</h1><p className="max-w-3xl">Review winner picks, recorded results and changes over time. Historical saved comparisons and verified pre-race forecasts have separate records.</p></header>
    <div className="flex flex-wrap gap-4 mb-6">
      <label className="text-sm">Record basis <select aria-label="Record basis" value={basis} onChange={e => setBasis(e.target.value === "verified" ? "verified" : "comparison")} className="ml-2 p-3 rounded" style={{ background: "var(--bg-surface, var(--panel))", color: "inherit", border: "1px solid var(--border, var(--line))" }}><option value="comparison">Saved comparisons · historical</option><option value="verified">Verified pre-race forecasts</option></select></label>
      <label className="text-sm">Season <select aria-label="Track record season" value={season} onChange={e => onSeasonChange(Number(e.target.value))} className="ml-2 p-3 rounded" style={{ background: "var(--bg-surface, var(--panel))", color: "inherit", border: "1px solid var(--border, var(--line))" }}>{!seasons.includes(season) ? <option value={season}>{season} — unavailable</option> : null}{seasons.map(year => <option key={year} value={year}>{year}</option>)}</select></label>
      <label className="text-sm">Race / class <select aria-label="Race or class" value={scope} onChange={e => setScopeChoice(e.target.value)} className="ml-2 p-3 rounded" style={{ background: "var(--bg-surface, var(--panel))", color: "inherit", border: "1px solid var(--border, var(--line))" }}>{scopes.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
    </div>
    <section aria-label={comparison ? "Historical winner comparison" : "Verified winner accuracy"} style={surface}>
      <p className="eyebrow">{comparison ? "Historical winner matches" : "Correct pre-race winner picks"} · {season} · {scopes.find(([key]) => key === scope)?.[1] ?? "No records"}</p>
      <p className="text-5xl sm:text-6xl font-bold my-4" data-testid="winner-headline">{summary.accuracy === null ? comparison ? "No settled comparisons" : "Not yet scored" : pct(summary.accuracy)}</p>
      <p className="text-lg"><strong>{comparison ? `${summary.correct} winner matches / ${summary.settled} settled comparisons` : `${summary.correct} correct / ${summary.settled} eligible settled races`}</strong></p>
      <p className="text-sm mt-3">Saved-data review as of {data.asOf}.</p>
      <p className="text-sm mt-3">{counts("pending")} pending · {counts("missing")} missing records · {counts("held")} withheld · {counts("unverified")} unverified records · {counts("incomplete")} incomplete</p>
      <p className="text-sm mt-4 max-w-3xl">{comparison ? "A winner match compares the unique P1 in a saved classification with the unique P1 in its settled recorded result. Snapshots may have been generated or updated after the event; this percentage does not establish pre-race prediction performance. Held, synthetic, ambiguous and unsettled records are excluded." : "One pick per race: the original classification’s unique P1. Only calendar-matched, dated, settled races with a verified original pre-race model record count. Missing, ambiguous, withheld and unverified records stay outside the denominator."}</p>
      {comparison ? <p className="text-sm mt-3" data-testid="verified-coverage">Verified pre-race record: {verified.accuracy !== null ? `${verified.correct}/${verified.settled} correct (${pct(verified.accuracy)})` : "Not yet scored · no eligible original-publication records"}.</p> : summary.accuracy === null ? <p className="text-sm mt-3">There is no eligible winner score yet. Saved comparisons do not establish pre-race publication.</p> : null}
    </section>
    <section aria-label="Accuracy over time" className="mt-6" style={surface}>
      <h2 className="text-2xl font-bold mb-3">{comparison ? "Historical winner matches over time" : "Pre-race accuracy over time"}</h2>
      <p className="text-sm mb-5">{comparison ? "Cumulative winner matches among dated saved comparisons" : "Cumulative correct picks among eligible dated pre-race forecasts"} in this season and race or class. Recent form uses the same dated records in the trailing {ROLLING_DAYS} calendar days, including the selected date; its denominator can vary. Equal-date races enter together. Lines join observed values without smoothing.</p>
      <p className="text-sm mb-4" data-testid="dated-coverage">{dated} dated of {summary.settled} eligible {comparison ? "comparisons" : "races"} · {undated} undated. Undated comparisons are excluded from this chart and recent form.</p>
      {points.length ? <WinnerTimeline key={`${basis}:${season}:${scope}`} points={points} comparison={comparison} /> : <p className="py-8">{undated ? "The settled comparisons have no recorded event dates, so no chronological timeline or recent-form rate can be shown." : "No eligible dated results to plot yet."}</p>}
      <p className="text-sm mt-4">Model versions appear only when saved in the selected record’s metadata. A version label does not establish why accuracy changed.</p>
    </section>
    <section aria-label="Every pick and result" className="mt-8">
      <h2 className="text-2xl font-bold mb-2">Every pick and result</h2><p className="text-sm mb-5">All calendar events and saved snapshots for this selection, including exclusions. Open a record to inspect every saved position.</p>
      {!rows.length ? <p>No saved records for this season and race or class.</p> : <div className="grid gap-4">{rows.map(row => { const view = recordView(row, basis); return <article key={row.id} style={surface} data-testid="winner-record">
        <div className="flex flex-wrap justify-between gap-2"><h3 className="font-bold">R{row.round} · {row.event}</h3><span className="text-sm">{row.date ? dateLabel(row.date) : "Date not recorded"}</span></div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 my-4"><p><span className="text-sm block">{comparison ? "Saved winner pick" : "Original model winner pick"}</span><strong>{name(view, view.predictedWinner)}</strong></p><p><span className="text-sm block">Actual winner</span><strong>{name(view, view.actualWinner)}</strong></p><p><span className="text-sm block">{comparison ? "Comparison status" : "Scoring status"}</span><strong>{outcome(view.status, view.correct)}</strong></p></div>
        <p className="text-sm">{view.reason}</p>
        <details className="mt-3"><summary className="cursor-pointer py-3">All recorded positions and source</summary><p className="text-sm mb-3">Result/snapshot: {row.source}. {comparison ? "Historical saved comparison; original publication timing is not established by this snapshot." : row.publication ? `Original forecast published ${row.publication}.` : "Original pre-race publication not verified."} Model version: {view.modelVersion ?? "Not recorded"}.</p>
          {!comparison && row.forecastSource ? <p className="text-sm mb-3"><a className="underline" href={`https://raw.githubusercontent.com/roni-altshuler/motorsportverse/${row.sourceCommit}/projects/${data.series}-predictions/website/public/data/${row.forecastSource}`}>Original forecast: {row.forecastSource}</a>. SHA256: {row.forecastSha256}. Source commit: {row.sourceCommit}. <a href={row.publicationEvent ?? undefined} className="underline">Audited publication record</a>. Receipt: forecast_receipts.json.</p> : null}
          {view.positions.length ? <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={`R${row.round} recorded positions`}><table className="w-full text-sm text-left"><caption className="sr-only">Saved prediction and actual result positions</caption><thead><tr><th scope="col" className="p-2">Driver / entry</th><th scope="col" className="p-2">Predicted</th><th scope="col" className="p-2">Actual</th></tr></thead><tbody>{view.positions.map(p => <tr key={p.id}><th scope="row" className="p-2">{p.name}</th><td className="p-2">{p.predicted ?? "Not recorded"}</td><td className="p-2">{p.actual ?? "Not recorded"}</td></tr>)}</tbody></table></div> : <p>No classification positions saved.</p>}
        </details>
      </article>; })}</div>}
    </section>
    <aside className="mt-8" style={surface}><h2 className="text-xl font-bold mb-2">Podium and finishing-order measures</h2><p className="text-sm">Position RMSE measures finishing-position error. The podium/points blend measures ranking overlap. Neither is the percentage of race winners picked correctly. Historical replays and snapshots without original publication evidence do not enter the verified pre-race record.</p>{data.series === "f2" ? <p className="text-sm mt-2">F2’s walk-forward evaluation is a retrospective replay of completed rounds, not an immutable record of forecasts published before each race.</p> : null}<Link href={evaluationHref} className="inline-block underline py-3">Historical evaluation and position errors →</Link></aside>
  </div>;
}
