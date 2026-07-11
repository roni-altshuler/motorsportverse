"use client";

// The centerpiece — a client-side race simulator. Pick a venue, drop the
// green flag, and watch the season's personalities play out lap by lap in an
// animated event feed, ending in a podium reveal. "Run 100 races" Monte
// Carlos the same venue live in the browser and charts win probability.
// Everything happens client-side: no fs, no fetches, just sim.ts.

import { useEffect, useMemo, useRef, useState } from "react";

import { simulateRace, winProbabilities } from "@/lib/sim";
import type { FeedEvent, SimRace, WinProb } from "@/lib/sim";
import type { CharacterCard, VenueCard } from "@/types/data";

const TICK_MS = 340;

type Phase = "idle" | "running" | "finished";

export default function RaceDay({
  characters,
  venues,
}: {
  characters: CharacterCard[];
  venues: VenueCard[];
}) {
  const [venueSlug, setVenueSlug] = useState(venues[0]?.slug ?? "");
  const [phase, setPhase] = useState<Phase>("idle");
  const [race, setRace] = useState<SimRace | null>(null);
  const [shown, setShown] = useState(0);
  const [probs, setProbs] = useState<WinProb[] | null>(null);
  const [probVenue, setProbVenue] = useState<string | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const venue = useMemo(
    () => venues.find((v) => v.slug === venueSlug) ?? venues[0],
    [venues, venueSlug]
  );

  const stopTicker = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  useEffect(() => stopTicker, []);

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [shown]);

  const startRace = () => {
    if (!venue) return;
    stopTicker();
    const seed = (Date.now() ^ (Math.random() * 0xffffffff)) >>> 0;
    const next = simulateRace(characters, venue, seed);
    setRace(next);
    setShown(1);
    setPhase("running");
    timerRef.current = setInterval(() => {
      setShown((n) => {
        if (n + 1 >= next.events.length) {
          stopTicker();
          setPhase("finished");
          return next.events.length;
        }
        return n + 1;
      });
    }, TICK_MS);
  };

  const skipToFlag = () => {
    if (!race) return;
    stopTicker();
    setShown(race.events.length);
    setPhase("finished");
  };

  const runHundred = () => {
    if (!venue) return;
    const seed = (Date.now() ^ 0x5f3759df) >>> 0;
    setProbs(winProbabilities(characters, venue, 100, seed));
    setProbVenue(venue.name);
  };

  const events: FeedEvent[] = race ? race.events.slice(0, shown) : [];
  const podium = phase === "finished" && race ? race.results.slice(0, 3) : null;
  const maxWins = probs ? Math.max(1, ...probs.map((p) => p.wins)) : 1;

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
      <div>
        {/* Venue picker */}
        <p className="eyebrow mb-3">Choose your battleground</p>
        <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Venue picker">
          {venues.map((v) => (
            <button
              key={v.slug}
              type="button"
              className={`venue-chip${v.slug === venue?.slug ? " active" : ""}`}
              onClick={() => setVenueSlug(v.slug)}
            >
              {v.name}
            </button>
          ))}
        </div>
        {venue && <p className="body-sm mb-5 text-[color:var(--muted)]">{venue.blurb}</p>}

        <div className="mb-6 flex flex-wrap items-center gap-3">
          <button type="button" className="btn-valley btn-valley-accent" onClick={startRace}>
            {phase === "idle" ? "Start the race" : "Race again"}
          </button>
          {phase === "running" && (
            <button type="button" className="btn-valley" onClick={skipToFlag}>
              Skip to the flag
            </button>
          )}
          <button type="button" className="btn-valley" onClick={runHundred}>
            Run 100 races
          </button>
        </div>

        {/* Event feed */}
        <div className="feed-shell">
          <div className="flex items-center gap-3 border-b border-[color:var(--hairline)] px-4 py-3">
            {phase === "running" ? <span className="live-dot" aria-hidden /> : null}
            <span className="mono-label">
              {phase === "idle" && "Waiting for the green flag"}
              {phase === "running" && `Live from ${venue?.name}`}
              {phase === "finished" && `Full race classification — ${venue?.name}`}
            </span>
          </div>
          <div ref={feedRef} className="max-h-[340px] overflow-y-auto" aria-live="polite">
            {events.length === 0 ? (
              <p className="body-sm px-4 py-8 text-[color:var(--muted)]">
                Twelve engines idling. Pick a venue, press the button, and let the valley decide.
              </p>
            ) : (
              events.map((e, i) => (
                <div key={i} className="feed-item" data-tone={e.tone}>
                  <span className="feed-lap">{e.lap === 0 ? "grid" : `Lap ${e.lap}`}</span>
                  <span className="feed-text">{e.text}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Podium reveal */}
        {podium && (
          <div className="mt-6">
            <p className="eyebrow eyebrow-accent mb-3">The podium</p>
            <div className="grid grid-cols-3 gap-3">
              {[podium[1], podium[0], podium[2]].map((r, col) =>
                r ? (
                  <div
                    key={r.slug}
                    className={`podium-slot${col === 1 ? " -translate-y-2" : ""}`}
                    data-step={col === 1 ? "1" : col === 0 ? "2" : "3"}
                    style={{ animationDelay: `${col === 1 ? 400 : col === 0 ? 150 : 0}ms` }}
                  >
                    <span className={`position-badge p${r.position}`}>P{r.position}</span>
                    <p className="title-sm mt-3">{r.name}</p>
                    <p className="mono-label mt-1">#{r.number}</p>
                    <p className="body-sm mt-2 text-[color:var(--muted)]">
                      {r.position === 1
                        ? `${r.lapsLed} laps led`
                        : r.gapSeconds != null
                          ? `+${r.gapSeconds.toFixed(1)}s`
                          : "classified"}
                    </p>
                  </div>
                ) : null
              )}
            </div>
            {race && race.results.some((r) => r.dnf) && (
              <p className="body-sm mt-4 text-[color:var(--muted)]">
                Towed home:{" "}
                {race.results
                  .filter((r) => r.dnf)
                  .map((r) => `${r.name} (${r.dnfReason})`)
                  .join(" · ")}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Win-probability panel */}
      <aside>
        <p className="eyebrow mb-3">Win probability — computed in your browser</p>
        <div className="card p-5">
          {probs ? (
            <>
              <p className="mono-label mb-4">100 simulated races · {probVenue}</p>
              <div>
                {probs.map((p) => (
                  <div key={p.slug} className="prob-row" style={{ "--racer-color": p.color } as React.CSSProperties}>
                    <span className="body-sm truncate text-[color:var(--body-strong)]">{p.name}</span>
                    <div className="prob-track">
                      <div className="prob-fill" style={{ width: `${(p.wins / maxWins) * 100}%` }} />
                    </div>
                    <span className="mono-label text-right font-tabular">{p.pct}%</span>
                  </div>
                ))}
              </div>
              <p className="body-sm mt-4 text-[color:var(--muted)]">
                Same personalities, same venue, one hundred alternate Sundays.
              </p>
            </>
          ) : (
            <p className="body-sm py-6 text-[color:var(--muted)]">
              Press <span className="font-mono text-[12px] uppercase tracking-widest">Run 100 races</span>{" "}
              and watch a hundred alternate afternoons resolve into odds. Showboats look great in
              one race — a hundred races tell on them.
            </p>
          )}
        </div>
      </aside>
    </div>
  );
}
