"use client";

// Race Night — the interactive centerpiece. Runs the Prism Cup race engine
// (src/lib/sim.ts, a TS port of the Python simulator) entirely client-side:
// pick a circuit, optionally back a racer, drop the flag, and watch the
// per-lap item chaos play out as an animated event feed + live position
// tower ending in a podium reveal. Batch mode runs 100 races and charts
// live win rates to show how weight class and track hazard shift the odds.

import { useEffect, useMemo, useState } from "react";
import { Flag, Repeat, Zap } from "lucide-react";

import { runBatch, simulateRace, type BatchResult, type SimFrame } from "@/lib/sim";
import { ITEMS, RACERS, RACERS_BY_ID, TRACKS, TRACKS_BY_ID } from "@/lib/simConfig";

const ROW_H = 36;

const KIND_COLOR: Record<string, string> = {
  grid: "var(--muted)",
  lap: "var(--muted)",
  boost: "#FFB84D",
  comet: "#FFB84D",
  seeker: "var(--accent-prism-bright)",
  block: "var(--success)",
  shield: "var(--success)",
  spin: "var(--accent-negative)",
  tempest: "#5AC8FF",
  swap: "var(--body)",
  hook: "var(--body)",
  fizzle: "var(--muted-soft)",
  finish: "var(--accent-podium-1)",
};

const WEIGHT_LETTER: Record<string, string> = { light: "L", medium: "M", heavy: "H" };

function frameDelay(frame: SimFrame): number {
  if (frame.kind === "lap" || frame.kind === "grid") return 950;
  if (frame.kind === "finish") return 500;
  return 640;
}

export default function RaceNight() {
  const [trackId, setTrackId] = useState(TRACKS[0].id);
  const [favoriteId, setFavoriteId] = useState<string | null>(null);
  const [frames, setFrames] = useState<SimFrame[] | null>(null);
  const [step, setStep] = useState(0);
  const [running, setRunning] = useState(false);
  const [batch, setBatch] = useState<BatchResult | null>(null);

  const track = TRACKS_BY_ID[trackId];
  const finished = frames !== null && !running && step === frames.length - 1 && step > 0;
  const currentOrder = frames ? frames[Math.min(step, frames.length - 1)].order : null;

  useEffect(() => {
    if (!running || !frames) return;
    if (step >= frames.length - 1) {
      setRunning(false);
      return;
    }
    const t = setTimeout(() => setStep((s) => s + 1), frameDelay(frames[step + 1]));
    return () => clearTimeout(t);
  }, [running, frames, step]);

  const dropFlag = () => {
    const seed = Math.floor(Math.random() * 2 ** 31);
    const result = simulateRace(trackId, seed);
    setBatch(null);
    setFrames(result.frames);
    setStep(0);
    setRunning(true);
  };

  const runHundred = () => {
    setFrames(null);
    setRunning(false);
    setStep(0);
    setBatch(runBatch(trackId, 100));
  };

  const feed = useMemo(() => {
    if (!frames) return [];
    const upto = frames.slice(0, step + 1);
    return upto.slice(-9).reverse();
  }, [frames, step]);

  const podium = finished && frames ? frames[frames.length - 1].order.slice(0, 3) : null;
  const favoriteFinish =
    finished && frames && favoriteId
      ? frames[frames.length - 1].order.indexOf(favoriteId) + 1
      : null;
  const maxWins = batch ? Math.max(1, ...batch.rows.map((r) => r.wins)) : 1;

  return (
    <section id="race-night" className="section-bugatti" style={{ background: "var(--surface-soft)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <p className="eyebrow mb-3" style={{ color: "var(--accent-prism-bright)" }}>
          Interactive · Runs in your browser
        </p>
        <h2 className="display-lg mb-4">Race Night</h2>
        <p className="body-md max-w-2xl mb-10">
          The same engine that simulated the season, ported to your browser.
          Pick a circuit, back a racer if you dare, and drop the flag — Seeker
          Orbs, Static Shields and boost-pad chains included. Or run a hundred
          races and watch the odds settle live.
        </p>

        {/* ── Controls ─────────────────────────────────────────────── */}
        <div className="card p-6 mb-8">
          <p className="mono-label mb-3">Circuit</p>
          <div className="flex flex-wrap gap-2 mb-6">
            {TRACKS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTrackId(t.id)}
                aria-pressed={t.id === trackId}
                className="nav-link-text px-3 py-2 border transition-colors"
                style={{
                  borderColor: t.id === trackId ? "var(--accent-prism)" : "var(--hairline)",
                  color: t.id === trackId ? "var(--ink)" : "var(--muted)",
                  background: t.id === trackId ? "var(--accent-prism-soft)" : "transparent",
                }}
              >
                {t.name}
                <span className="ml-2" style={{ color: "var(--accent-prism-bright)" }}>
                  {"⌁".repeat(t.hazard)}
                </span>
              </button>
            ))}
          </div>

          <p className="mono-label mb-3">Back a racer (optional)</p>
          <div className="flex flex-wrap gap-2 mb-6">
            {RACERS.map((r) => (
              <button
                key={r.id}
                onClick={() => setFavoriteId((f) => (f === r.id ? null : r.id))}
                aria-pressed={r.id === favoriteId}
                className="nav-link-text px-3 py-2 border inline-flex items-center gap-2 transition-colors"
                style={{
                  borderColor: r.id === favoriteId ? r.color : "var(--hairline)",
                  color: r.id === favoriteId ? "var(--ink)" : "var(--muted)",
                }}
              >
                <span
                  className="inline-block w-2 h-2 rounded-full"
                  style={{ background: r.color }}
                />
                {r.short}
                <span style={{ color: "var(--muted-soft)" }}>{WEIGHT_LETTER[r.weightClass]}</span>
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <button className="btn-prism" onClick={dropFlag} disabled={running}>
              <Flag className="w-4 h-4" />
              {running ? "Racing…" : "Drop the flag"}
            </button>
            <button className="btn-bugatti" onClick={runHundred} disabled={running}>
              <Repeat className="w-4 h-4" />
              Run 100 races
            </button>
            <span className="caption-uppercase">
              {track.laps} laps · hazard {track.hazard}/5 · boost pads{" "}
              {Math.round(track.boostPadDensity * 100)}%
            </span>
          </div>
        </div>

        {/* ── Live race: event feed + position tower ───────────────── */}
        {frames && currentOrder && (
          <div className="grid grid-cols-1 md:grid-cols-[1fr_300px] gap-6 mb-8">
            <div className="card p-5 min-h-[380px]">
              <p className="mono-label mb-4">
                Live feed — {track.name}
              </p>
              <ul className="flex flex-col gap-2.5">
                {feed.map((f, i) => {
                  const globalIndex = step - i;
                  return (
                    <li
                      key={globalIndex}
                      className={`flex items-start gap-3 ${i === 0 ? "feed-item" : ""}`}
                      style={{ opacity: i === 0 ? 1 : Math.max(0.35, 1 - i * 0.09) }}
                    >
                      <span
                        className="position-badge shrink-0"
                        style={{ color: KIND_COLOR[f.kind] ?? "var(--muted)" }}
                      >
                        {f.kind === "grid" ? "GRID" : f.kind === "finish" ? "FIN" : `L${f.lap}`}
                      </span>
                      <span
                        className="mt-1 w-2 h-2 rounded-full shrink-0"
                        style={{ background: KIND_COLOR[f.kind] ?? "var(--muted)" }}
                      />
                      <span className="body-sm" style={{ color: i === 0 ? "var(--body-strong)" : "var(--body)" }}>
                        {f.text}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>

            <div className="card p-5">
              <p className="mono-label mb-4">Position tower</p>
              <div className="relative" style={{ height: RACERS.length * ROW_H }}>
                {RACERS.map((r) => {
                  const idx = currentOrder.indexOf(r.id);
                  const isFav = r.id === favoriteId;
                  return (
                    <div
                      key={r.id}
                      className="tower-row flex items-center gap-2 pr-1"
                      style={{ transform: `translateY(${idx * ROW_H}px)`, height: ROW_H }}
                    >
                      <span
                        className="font-mono text-[11px] w-6 text-right font-tabular"
                        style={{
                          color: idx === 0 ? "var(--accent-podium-1)" : "var(--muted)",
                        }}
                      >
                        P{idx + 1}
                      </span>
                      <span className="w-1 self-stretch my-1" style={{ background: r.color }} />
                      <span
                        className="font-mono text-[12px] tracking-wide uppercase truncate"
                        style={{
                          color: isFav ? "var(--accent-prism-bright)" : "var(--body-strong)",
                        }}
                      >
                        {r.short}
                        {isFav ? " ◆" : ""}
                      </span>
                      <span className="ml-auto caption-uppercase" style={{ fontSize: 10 }}>
                        {WEIGHT_LETTER[r.weightClass]}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* ── Podium reveal ─────────────────────────────────────────── */}
        {podium && (
          <div className="podium-reveal mb-8">
            {favoriteId && favoriteFinish !== null && (
              <div
                className={`mb-6 px-5 py-4 text-center ${
                  favoriteFinish <= 3 ? "celebrate-band prism-trim" : "card"
                }`}
              >
                {favoriteFinish <= 3 ? (
                  <p className="title-md" style={{ color: "var(--accent-podium-1)" }}>
                    Your pick podiums! {RACERS_BY_ID[favoriteId].name} finishes P{favoriteFinish}
                  </p>
                ) : (
                  <p className="body-md" style={{ color: "var(--muted)" }}>
                    {RACERS_BY_ID[favoriteId].name} comes home P{favoriteFinish}. The Seeker
                    Orbs were not on your side tonight.
                  </p>
                )}
              </div>
            )}
            <div className="grid grid-cols-3 gap-4 items-end max-w-2xl mx-auto">
              {[podium[1], podium[0], podium[2]].map((rid, col) => {
                const place = col === 1 ? 1 : col === 0 ? 2 : 3;
                const r = RACERS_BY_ID[rid];
                return (
                  <div
                    key={rid}
                    className={`card p-5 text-center ${place === 1 ? "prism-trim" : ""}`}
                    style={{ marginTop: place === 1 ? 0 : 24 }}
                  >
                    <p className={`display-sm podium-${place}`}>P{place}</p>
                    <p className="title-sm mt-2" style={{ color: "var(--ink)" }}>
                      {r.name}
                    </p>
                    <p className="caption-uppercase mt-1">{r.vibe}</p>
                    <span className="mt-3 stat-bar block">
                      <span
                        className="stat-bar-fill block"
                        style={{ width: "100%", background: r.color }}
                      />
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Batch mode: live win-rate bars ────────────────────────── */}
        {batch && (
          <div className="card p-6 mb-8">
            <div className="flex items-center gap-2 mb-1">
              <Zap className="w-4 h-4" style={{ color: "var(--accent-prism-bright)" }} />
              <p className="title-sm" style={{ color: "var(--ink)" }}>
                {batch.races} races at {track.name}
              </p>
            </div>
            <p className="body-sm mb-6" style={{ color: "var(--muted)" }}>
              Win rate per racer. Hazard {track.hazard}/5
              {track.hazard >= 4
                ? " — a chaos circuit: items and storms flatten the field, so long shots cash."
                : track.hazard <= 2
                  ? " — a clean circuit: raw stats decide more, favourites stay favourites."
                  : " — items still bite, but pace mostly holds."}{" "}
              Heavies shrug off hits; lights live and die by the launch.
            </p>
            <div className="flex flex-col gap-2.5">
              {batch.rows.map((row) => {
                const r = RACERS_BY_ID[row.racerId];
                return (
                  <div key={row.racerId} className="grid grid-cols-[130px_1fr_110px] items-center gap-3">
                    <span
                      className="font-mono text-[11px] uppercase tracking-wide truncate"
                      style={{
                        color:
                          row.racerId === favoriteId
                            ? "var(--accent-prism-bright)"
                            : "var(--body-strong)",
                      }}
                    >
                      {r.short} <span style={{ color: "var(--muted-soft)" }}>{WEIGHT_LETTER[r.weightClass]}</span>
                    </span>
                    <span className="stat-bar" style={{ height: 8 }}>
                      <span
                        className="stat-bar-fill block h-full"
                        style={{ width: `${(row.wins / maxWins) * 100}%`, background: r.color }}
                      />
                    </span>
                    <span className="font-mono text-[11px] font-tabular text-right" style={{ color: "var(--muted)" }}>
                      {row.wins}% win · {row.podiums}% pod
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Item legend ───────────────────────────────────────────── */}
        <details className="deep-dive-section">
          <summary className="deep-dive-summary">The item table</summary>
          <div className="deep-dive-body deep-dive-section-body grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-4">
            {ITEMS.map((item) => (
              <div key={item.id}>
                <p className="title-sm" style={{ color: "var(--ink)" }}>
                  {item.name}{" "}
                  <span
                    className="caption-uppercase ml-1"
                    style={{
                      color:
                        item.rarity === "rare"
                          ? "var(--accent-prism-bright)"
                          : item.rarity === "uncommon"
                            ? "var(--warning)"
                            : "var(--muted)",
                    }}
                  >
                    {item.rarity}
                  </span>
                </p>
                <p className="body-sm mt-1" style={{ color: "var(--muted)" }}>
                  {item.effect}
                </p>
              </div>
            ))}
            <p className="body-sm sm:col-span-2 lg:col-span-3 pt-2 hairline-divider-top" style={{ color: "var(--muted-soft)" }}>
              Draws are position-weighted: the back of the field pulls the
              equalisers. Front-runners mostly get to defend.
            </p>
          </div>
        </details>
      </div>
    </section>
  );
}
