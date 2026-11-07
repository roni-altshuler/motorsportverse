"use client";

import { useEffect, useRef, useState } from "react";
import { ROLLING_DAYS, type TimelinePoint } from "@/lib/trackRecord";

const pct = (value: number) => `${value.toFixed(1)}%`;
const dateLabel = (date: string) => new Date(`${date}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

export default function WinnerTimeline({ points, comparison }: { points: TimelinePoint[]; comparison: boolean }) {
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
    <div className="flex flex-wrap gap-4 text-sm mb-3"><span style={{ color: "var(--viz-model, currentColor)" }}>● Cumulative {comparison ? "winner matches" : "accuracy"}</span><span style={{ color: "var(--viz-baseline, currentColor)" }}>┄ Recent form: {ROLLING_DAYS} calendar days</span></div>
    <div ref={chart}><svg viewBox={`0 0 ${width} 290`} role="img" aria-label={comparison ? "Historical winner matches by event date, from 0 to 100 percent" : "Winner accuracy by event date, from 0 to 100 percent"} style={{ width: "100%", height: "auto", minHeight: 180, touchAction: "pan-y" }}>
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
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Chart data table"><table className="w-full text-left text-sm"><caption className="sr-only">{comparison ? "Cumulative and rolling historical winner matches by event date" : "Cumulative and rolling verified pre-race winner accuracy by event date"}</caption><thead><tr>{["Event date", comparison ? "Cumulative matches / comparisons" : "Cumulative correct / settled", comparison ? "Recent matches / comparisons" : "Recent correct / settled", "Recent window", "Recorded model version"].map(h => <th key={h} scope="col" className="p-3">{h}</th>)}</tr></thead><tbody>{points.map(p => <tr key={p.date}><th scope="row" className="p-3 whitespace-nowrap">{dateLabel(p.date)}</th><td className="p-3">{p.correct}/{p.settled} ({pct(p.accuracy)})</td><td className="p-3">{p.recentCorrect}/{p.recentSettled} ({pct(p.recentAccuracy)})</td><td className="p-3 whitespace-nowrap">{p.windowStart}–{p.windowEnd}</td><td className="p-3">{p.versions.join(", ") || "Not recorded"}</td></tr>)}</tbody></table></div>
    </details>
  </>;
}
