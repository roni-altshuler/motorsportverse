"use client";

import { useEffect, useId, useRef, useState } from "react";
import { loadSchematic, type CircuitSchematic, type ExplorerReview } from "@/lib/circuitExplorer";
import { useReducedMotion } from "@/lib/useReducedMotion";

/** Shared shell: only the caller's explicitly reviewed event gets a launch button. */
export default function CircuitExplorer({ review, basePath = "" }: {
  review: ExplorerReview | null;
  basePath?: string;
}) {
  if (!review) return null;
  return <CircuitExplorerView key={`${basePath}:${JSON.stringify(review)}`} review={review} basePath={basePath} />;
}

function CircuitExplorerView({ review, basePath }: { review: ExplorerReview; basePath: string }) {
  const id = useId();
  const reduced = useReducedMotion();
  const root = useRef<HTMLElement>(null);
  const hotspots = useRef<Array<HTMLButtonElement | null>>([]);
  const mounted = useRef(true);
  const [open, setOpen] = useState(false);
  const [schematic, setSchematic] = useState<CircuitSchematic | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState(0);
  const [tour, setTour] = useState(false);
  const [inView, setInView] = useState(false);
  const [pageVisible, setPageVisible] = useState(() => typeof document === "undefined" || !document.hidden);
  const running = tour && open && inView && pageVisible && !reduced;

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  useEffect(() => {
    const update = () => setPageVisible(!document.hidden);
    document.addEventListener("visibilitychange", update);
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting && entry.intersectionRatio >= 0.15), { threshold: 0.15 });
    if (root.current) observer.observe(root.current);
    return () => { observer.disconnect(); document.removeEventListener("visibilitychange", update); };
  }, []);
  useEffect(() => {
    if (!running || !schematic) return;
    const timer = setInterval(() => setSelected(current => {
      const index = schematic.corners.findIndex(corner => corner.number === current);
      return schematic.corners[(index + 1) % schematic.corners.length].number;
    }), 6000);
    return () => clearInterval(timer);
  }, [running, schematic]);

  async function reveal() {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (schematic || loading) return;
    setLoading(true); setFailed(false);
    try {
      const result = await loadSchematic(review, basePath);
      if (mounted.current) { setSchematic(result); setSelected(result.corners[0].number); }
    } catch { if (mounted.current) setFailed(true); }
    finally { if (mounted.current) setLoading(false); }
  }
  function select(number: number) { setSelected(number); setTour(false); }
  const corner = schematic?.corners.find(entry => entry.number === selected);

  return (
    <section ref={root} className="border border-[color:var(--hairline)] bg-[color:var(--surface-soft)]" aria-label={`${review.title} circuit explorer`}>
      <button
        type="button" onClick={reveal} aria-expanded={open} aria-controls={`${id}-body`}
        className="flex min-h-20 w-full items-center justify-between gap-4 px-5 py-5 text-left hover:bg-[color:var(--surface-card)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--ink)]"
      >
        <span><span className="eyebrow block text-[color:var(--muted)]">Venue guide</span><span className="title-md mt-1 block">Explore {review.title}</span></span>
        <span aria-hidden="true" className="font-mono text-xl text-[color:var(--accent)]">{open ? "−" : "+"}</span>
      </button>
      <div id={`${id}-body`} hidden={!open}>
        {loading && <p role="status" className="body-sm border-t border-[color:var(--hairline)] p-5">Loading circuit schematic…</p>}
        {failed && <p role="status" className="body-sm border-t border-[color:var(--hairline)] p-5">Circuit explorer unavailable. Close and reopen to retry.</p>}
        {schematic && (
          <div className="border-t border-[color:var(--hairline)]">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--hairline)] px-5 py-4">
              <div><p className="eyebrow">{schematic.totalCorners} turns · {schematic.corners.length} highlights</p><p className="body-sm mt-1 text-[color:var(--muted)]">Schematic checked against {review.event.season} references</p></div>
              {!reduced && <button type="button" aria-pressed={tour} onClick={() => setTour(value => !value)} className="min-h-11 border border-[color:var(--hairline-strong)] px-4 py-2 font-mono text-xs focus-visible:outline-2 focus-visible:outline-offset-2">{tour ? "Pause tour" : "Tour highlights"}</button>}
            </div>
            <div className="grid lg:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
              <div className="p-6 sm:p-8">
                <div className="relative" data-circuit-map="schematic" data-tour-state={running ? "running" : tour && !reduced ? "paused" : "static"} style={{ aspectRatio: `${schematic.asset.width}/${schematic.asset.height}` }}>
                  {/* Licensed artwork stays intact; the overlay supplies only reviewed highlights. */}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={`${basePath}${schematic.asset.path}`} alt={`${review.title} circuit schematic, ${schematic.totalCorners} numbered turns`} width={schematic.asset.width} height={schematic.asset.height} className="h-full w-full object-contain" />
                  {schematic.corners.map((entry, index) => (
                    <button key={entry.number} type="button" ref={element => { hotspots.current[index] = element; }}
                      aria-label={`Show Turn ${entry.number}: ${entry.name}`} aria-pressed={selected === entry.number} aria-controls={`${id}-corner`}
                      onClick={() => select(entry.number)} onKeyDown={event => {
                        const next = event.key === "Home" ? 0 : event.key === "End" ? schematic.corners.length - 1
                          : ["ArrowRight", "ArrowDown"].includes(event.key) ? (index + 1) % schematic.corners.length
                          : ["ArrowLeft", "ArrowUp"].includes(event.key) ? (index + schematic.corners.length - 1) % schematic.corners.length : null;
                        if (next !== null) { event.preventDefault(); select(schematic.corners[next].number); hotspots.current[next]?.focus(); }
                      }}
                      className="absolute flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--ink)]"
                      style={{ left: `${entry.x * 100}%`, top: `${entry.y * 100}%` }}>
                      <span aria-hidden="true" className="flex h-7 w-7 items-center justify-center rounded-full border-2 font-mono text-xs font-bold" style={{ background: selected === entry.number ? "var(--accent)" : "var(--surface-card)", color: selected === entry.number ? "var(--accent-ink)" : "var(--ink)", borderColor: "var(--ink)" }}>{entry.number}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="border-t border-[color:var(--hairline)] p-5 lg:border-l lg:border-t-0 sm:p-7">
                <p className="eyebrow mb-4 text-[color:var(--muted)]">Choose a corner</p>
                <ol className="space-y-2">{schematic.corners.map(entry => <li key={entry.number}><button type="button" aria-pressed={selected === entry.number} aria-controls={`${id}-corner`} onClick={() => select(entry.number)} className="flex min-h-12 w-full items-center gap-4 border px-4 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2" style={{ borderColor: selected === entry.number ? "var(--accent)" : "var(--hairline)" }}><span className="font-mono text-sm text-[color:var(--muted)]">T{String(entry.number).padStart(2, "0")}</span><span className="body-sm">{entry.name}</span></button></li>)}</ol>
                <div id={`${id}-corner`} aria-live="polite" className="mt-6 border-t border-[color:var(--hairline)] pt-5">
                  {corner && <><p className="eyebrow text-[color:var(--accent)]">Turn {corner.number}</p><h3 className="title-md mt-2">{corner.name}</h3><p className="body-sm mt-3 text-[color:var(--body)]">{corner.description}</p></>}
                </div>
                <p className="body-sm mt-6 text-[color:var(--muted)]">Select a marker or use the list. Arrow keys move between map highlights.</p>
              </div>
            </div>
            <footer className="space-y-2 border-t border-[color:var(--hairline)] px-5 py-5 text-[color:var(--muted)]">
              <p className="body-sm">{schematic.disclaimer}</p>
              <p className="body-sm"><a href={schematic.source.page} className="underline">{schematic.source.title}</a> by {schematic.source.creator} · <a href={schematic.license.url} className="underline">CC BY-SA 4.0</a>. {schematic.modifications} No endorsement by the creator, circuit or Formula 1 is implied.</p>
              <p className="body-sm">References: {schematic.references.map((reference, index) => <span key={reference.url}>{index ? " · " : ""}<a href={reference.url} className="underline">{reference.purpose}</a></span>)}. Checked {schematic.checkedAt}.</p>
            </footer>
          </div>
        )}
      </div>
    </section>
  );
}
