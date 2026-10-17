"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ROLLING_DAYS, selectRecords, summarize, winnerTimeline, type TimelinePoint, type TrackRecordData, type WinnerRecord } from "@/lib/trackRecord";

const pct = (value: number) => `${value.toFixed(1)}%`;
const dateLabel = (date: string) => new Date(`${date}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const STATUS = { scored: "Scored", pending: "Pending", missing: "Missing record", held: "Withheld", unverified: "Timing unverified", incomplete: "Incomplete record" };
const surface = { background: "var(--bg-surface, var(--panel))", border: "1px solid var(--border, var(--line))", borderRadius: 12, padding: "clamp(16px, 3vw, 28px)" };
function name(row: WinnerRecord, id: string | null) { return id === null ? "Not recorded" : row.positions.find(p => p.id === id)?.name ?? id; }

function Timeline({ points }: { points: TimelinePoint[] }) {
  const [selection, setSelection] = useState<number | null>(null);
  const chart = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(650);
  useEffect(() => {
    const element = chart.current;
    if (!element) return;
    const resize = () => setWidth(Math.max(240, element.getBoundingClientRect().width));
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const selected = Math.max(0, Math.min(selection ?? points.length - 1, points.length - 1));
  const point = points[selected];
  const first = Date.parse(`${points[0].date}T00:00:00Z`), last = Date.parse(`${points[points.length - 1].date}T00:00:00Z`);
  const span = Math.max(last - first, 86_400_000);
  const left = 48, right = width - 16, plotWidth = right - left;
  const x = (date: string) => points.length === 1 ? (left + right) / 2 : left + (Date.parse(`${date}T00:00:00Z`) - first) / span * plotWidth;
  const dateTicks = width < 450 ? [0, 1] : [0, 0.5, 1];
  const y = (value: number) => 244 - value * 2.1;
  const path = (key: "accuracy" | "recentAccuracy") => points.map(p => `${x(p.date)},${y(p[key])}`).join(" ");
  return <>
    <div className="flex flex-wrap gap-4 text-sm mb-3"><span style={{ color: "var(--viz-model, currentColor)" }}>● Cumulative accuracy</span><span style={{ color: "var(--viz-baseline, currentColor)" }}>┄ Recent form: {ROLLING_DAYS} calendar days</span></div>
    <div ref={chart}><svg viewBox={`0 0 ${width} 290`} role="img" aria-label="Winner accuracy by event date, from 0 to 100 percent" style={{ width: "100%", height: "auto", minHeight: 180, touchAction: "pan-y" }}>
      {[0, 25, 50, 75, 100].map(value => <g key={value}><line x1={left} x2={right} y1={y(value)} y2={y(value)} stroke="currentColor" opacity="0.15" /><text x={left - 8} y={y(value) + 4} textAnchor="end" fill="currentColor" fontSize="13">{value}%</text></g>)}
      <polyline points={path("accuracy")} fill="none" stroke="var(--viz-model, currentColor)" strokeWidth="3" />
      <polyline points={path("recentAccuracy")} fill="none" stroke="var(--viz-baseline, currentColor)" strokeDasharray="6 5" strokeWidth="2" />
      {points.map((p, i) => p.versions.length && p.versions.join() !== points[i - 1]?.versions.join() ? <g key={`version:${p.date}`}><title>{`Recorded model version: ${p.versions.join(", ")}`}</title><line x1={x(p.date)} x2={x(p.date)} y1="28" y2="244" stroke="currentColor" strokeDasharray="2 5" opacity="0.3" /><text x={x(p.date)} y="20" textAnchor="middle" fill="currentColor" fontSize="12">V</text></g> : null)}
      {points.map((p, i) => <circle key={p.date} cx={x(p.date)} cy={y(p.accuracy)} r={selected === i ? 6 : 4} fill="var(--viz-model, currentColor)" onPointerDown={() => setSelection(i)}><title>{`${dateLabel(p.date)}: ${p.correct}/${p.settled} cumulative; ${p.recentCorrect}/${p.recentSettled} in ${p.windowStart}–${p.windowEnd}`}</title></circle>)}
      {dateTicks.map(fraction => {
        const time = first + (last - first) * fraction;
        return <text key={fraction} x={left + plotWidth * fraction} y="274" textAnchor={fraction === 0 ? "start" : fraction === 1 ? "end" : "middle"} fill="currentColor" fontSize="12">{dateLabel(new Date(time).toISOString().slice(0, 10))}</text>;
      })}
    </svg></div>
    {points.some(p => p.versions.length) ? <p className="text-sm">V marks recorded model-version metadata; full labels are in the date table.</p> : null}
    <label className="block text-sm" htmlFor="winner-date">Inspect event date</label>
    <input id="winner-date" aria-label="Inspect event date" aria-valuetext={`${dateLabel(point.date)}: cumulative ${point.correct}/${point.settled}; recent ${point.recentCorrect}/${point.recentSettled}, ${point.windowStart}–${point.windowEnd}`} aria-describedby="winner-point-detail" type="range" min="0" max={points.length - 1} value={selected} onChange={e => setSelection(Number(e.target.value))} style={{ width: "100%", minHeight: 44, accentColor: "var(--viz-model, currentColor)" }} />
    <p id="winner-point-detail" aria-live="polite" className="text-sm" data-testid="point-detail"><strong>{dateLabel(point.date)}</strong> · Cumulative {point.correct}/{point.settled} ({pct(point.accuracy)}) · Recent {point.recentCorrect}/{point.recentSettled} ({pct(point.recentAccuracy)}), {dateLabel(point.windowStart)}–{dateLabel(point.windowEnd)}.</p>
    <details className="mt-5"><summary className="cursor-pointer py-3">All chart dates and counts</summary>
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Chart data table"><table className="w-full text-left text-sm"><caption className="sr-only">Cumulative and rolling winner accuracy by event date</caption><thead><tr>{["Event date", "Cumulative correct / settled", "Recent correct / settled", "Recent window", "Recorded model version"].map(h => <th key={h} scope="col" className="p-3">{h}</th>)}</tr></thead><tbody>{points.map(p => <tr key={p.date}><th scope="row" className="p-3 whitespace-nowrap">{dateLabel(p.date)}</th><td className="p-3">{p.correct}/{p.settled} ({pct(p.accuracy)})</td><td className="p-3">{p.recentCorrect}/{p.recentSettled} ({pct(p.recentAccuracy)})</td><td className="p-3 whitespace-nowrap">{p.windowStart}–{p.windowEnd}</td><td className="p-3">{p.versions.join(", ") || "Not recorded"}</td></tr>)}</tbody></table></div>
    </details>
  </>;
}

export default function WinnerTrackRecord({ data, season, onSeasonChange }: {
  data: TrackRecordData; season: number; onSeasonChange: (season: number) => void;
}) {
  const [scopeChoice, setScopeChoice] = useState("");
  const seasons = [...new Set([data.currentSeason, ...data.records.map(r => r.season)])].filter(year => year > 0).sort((a, b) => b - a);
  const scopes = [...new Map(data.records.filter(r => r.season === season).map(r => [r.scope, r.scopeLabel])).entries()];
  const scope = scopes.some(([key]) => key === scopeChoice) ? scopeChoice : scopes[0]?.[0] ?? "";
  const rows = selectRecords(data.records, season, scope), summary = summarize(data.records, season, scope);
  const points = winnerTimeline(data.records, season, scope);
  const counts = (status: WinnerRecord["status"]) => rows.filter(r => r.status === status).length;
  const period = rows.flatMap(r => r.date ? [r.date] : []).sort();
  const evaluationHref = `/accuracy${season === data.currentSeason ? "" : `?season=${season}`}`;
  return <div style={{ maxWidth: 1120, margin: "0 auto", padding: "40px 16px 80px", color: "var(--text, var(--ink))", overflowWrap: "anywhere" }}>
    <header className="mb-8"><p className="eyebrow">{data.label} · Pre-race winner picks</p><h1 className="text-4xl sm:text-5xl font-bold mt-2 mb-3">Model track record</h1><p className="max-w-3xl">Did the model pick the race winner? Follow the original picks, settled results and changes over time.</p></header>
    <div className="flex flex-wrap gap-4 mb-6">
      <label className="text-sm">Season <select aria-label="Track record season" value={season} onChange={e => onSeasonChange(Number(e.target.value))} className="ml-2 p-3 rounded" style={{ background: "var(--bg-surface, var(--panel))", color: "inherit", border: "1px solid var(--border, var(--line))" }}>{!seasons.includes(season) ? <option value={season}>{season} — unavailable</option> : null}{seasons.map(year => <option key={year} value={year}>{year}</option>)}</select></label>
      <label className="text-sm">Race / class <select aria-label="Race or class" value={scope} onChange={e => setScopeChoice(e.target.value)} className="ml-2 p-3 rounded" style={{ background: "var(--bg-surface, var(--panel))", color: "inherit", border: "1px solid var(--border, var(--line))" }}>{scopes.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
    </div>
    <section aria-label="Winner accuracy" style={surface}>
      <p className="eyebrow">Correct race-winner picks · {season} · {scopes.find(([key]) => key === scope)?.[1] ?? "No records"}</p>
      <p className="text-5xl sm:text-6xl font-bold my-4" data-testid="winner-headline">{summary.accuracy === null ? "Not yet scored" : pct(summary.accuracy)}</p>
      <p className="text-lg"><strong>{summary.correct} correct / {summary.settled} eligible settled races</strong></p>
      <p className="text-sm mt-3">{period.length ? `${dateLabel(period[0])}–${dateLabel(period[period.length - 1])}. ` : "No dated events available. "}Saved-data review as of {data.asOf}.</p>
      <p className="text-sm mt-3">{counts("pending")} pending · {counts("missing")} missing records · {counts("held")} withheld · {counts("unverified")} timing unverified · {counts("incomplete")} incomplete</p>
      <p className="text-sm mt-4 max-w-3xl">One pick per race: the original classification’s unique P1. A correct pick matches the unique P1 in the actual result. Only calendar-matched, dated, settled races with a verifiable original pre-race model record count. Missing, ambiguous, withheld and unverified records stay outside the denominator.</p>
      {summary.accuracy === null ? <p className="text-sm mt-3">There is no eligible winner score yet. Saved comparisons below do not establish pre-race publication.</p> : null}
    </section>
    <section aria-label="Accuracy over time" className="mt-6" style={surface}>
      <h2 className="text-2xl font-bold mb-3">Accuracy over time</h2>
      <p className="text-sm mb-5">Cumulative correct picks / all eligible settled races in this season and race or class. Recent form uses the same records in the trailing {ROLLING_DAYS} calendar days, including the selected date; its denominator can vary. Equal-date races enter together. Lines join observed values without smoothing.</p>
      {points.length ? <Timeline key={`${season}:${scope}`} points={points} /> : <p className="py-8">No eligible dated results to plot yet. The first scored race will start the timeline.</p>}
      <p className="text-sm mt-4">Model versions appear only when saved in the original forecast metadata. A version label does not establish why accuracy changed.</p>
    </section>
    <section aria-label="Every pick and result" className="mt-8">
      <h2 className="text-2xl font-bold mb-2">Every pick and result</h2><p className="text-sm mb-5">All calendar events and saved snapshots for this selection, including exclusions. Open a record to inspect every saved position.</p>
      {!rows.length ? <p>No saved records for this season and race or class.</p> : <div className="grid gap-4">{rows.map(row => <article key={row.id} style={surface} data-testid="winner-record">
        <div className="flex flex-wrap justify-between gap-2"><h3 className="font-bold">R{row.round} · {row.event}</h3><span className="text-sm">{row.date ? dateLabel(row.date) : "Date not recorded"}</span></div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 my-4"><p><span className="text-sm block">Model winner pick</span><strong>{name(row, row.predictedWinner)}</strong></p><p><span className="text-sm block">Actual winner</span><strong>{name(row, row.actualWinner)}</strong></p><p><span className="text-sm block">Scoring status</span><strong>{row.status === "scored" ? row.correct ? "Correct" : "Miss" : STATUS[row.status]}</strong></p></div>
        <p className="text-sm">{row.reason}</p>
        <details className="mt-3"><summary className="cursor-pointer py-3">All recorded positions and source</summary><p className="text-sm mb-3">Result/snapshot: {row.source}. {row.publication ? `Original forecast published ${row.publication}.` : "Original pre-race publication not verified."} Model version: {row.modelVersion ?? "Not recorded"}.</p>
          {row.forecastSource ? <p className="text-sm mb-3"><a className="underline" href={`https://raw.githubusercontent.com/roni-altshuler/motorsportverse/${row.sourceCommit}/projects/${data.series}-predictions/website/public/data/${row.forecastSource}`}>Original forecast: {row.forecastSource}</a>. SHA256: {row.forecastSha256}. Source commit: {row.sourceCommit}. <a href={row.publicationEvent ?? undefined} className="underline">Audited publication record</a>. Receipt: forecast_receipts.json.</p> : null}
          {row.positions.length ? <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={`R${row.round} recorded positions`}><table className="w-full text-sm text-left"><caption className="sr-only">Saved prediction and actual result positions</caption><thead><tr><th scope="col" className="p-2">Driver / entry</th><th scope="col" className="p-2">Predicted</th><th scope="col" className="p-2">Actual</th></tr></thead><tbody>{row.positions.map(p => <tr key={p.id}><th scope="row" className="p-2">{p.name}</th><td className="p-2">{p.predicted ?? "Not recorded"}</td><td className="p-2">{p.actual ?? "Not recorded"}</td></tr>)}</tbody></table></div> : <p>No classification positions saved.</p>}
        </details>
      </article>)}</div>}
    </section>
    <aside className="mt-8" style={surface}><h2 className="text-xl font-bold mb-2">Historical evaluations are separate</h2><p className="text-sm">Position RMSE measures finishing-position error. The podium/points blend measures ranking overlap. Neither is the percentage of race winners picked correctly. Historical replays and snapshots without original publication evidence do not enter this track record.</p>{data.series === "f2" ? <p className="text-sm mt-2">F2’s walk-forward evaluation is a retrospective replay of completed rounds, not an immutable record of forecasts published before each race.</p> : null}<Link href={evaluationHref} className="inline-block underline py-3">Historical evaluation and position errors →</Link></aside>
  </div>;
}
