"use client";

/**
 * ProductFilm — the end-to-end "how the engine works" demo film.
 *
 * A self-contained, looping product walkthrough rendered entirely in the
 * browser (no video file): six cinematic steps that trace a prediction from raw
 * timing data, through the ML model engine, to a self-graded result — the whole
 * pipeline, start to finish. Framed like an official product demo: player
 * chrome, a live pipeline step-strip, autoplay-on-scroll via IntersectionObserver
 * (mirrors the FireFly product film), and a frozen first frame under reduced
 * motion.
 *
 * (Drop-in seam: if a recorded MP4 is ever produced, swap <SceneStage/> for a
 * muted/loop/playsInline <video> — the chrome + step-strip stay identical.)
 */

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

const SCENE_MS = 4200;

const SCENES = [
  {
    key: "ingest",
    step: "Ingest",
    title: "Every timing feed, one schema",
    blurb: "Official lap times and decades of race archives flow into one canonical store.",
  },
  {
    key: "engine",
    step: "Model engine",
    title: "The ML engine turns pace into skill",
    blurb: "Features stream into a gradient-boosted ensemble that scores every driver's true pace.",
  },
  {
    key: "calibrate",
    step: "Calibrate",
    title: "Probabilities that tell the truth",
    blurb: "Raw model output is calibrated against history — confidence the data actually supports.",
  },
  {
    key: "simulate",
    step: "Simulate",
    title: "Thousands of races, one grid",
    blurb: "A Monte-Carlo race engine runs the weekend over and over to map every outcome.",
  },
  {
    key: "forecast",
    step: "Forecast",
    title: "A podium, with a confidence band",
    blurb: "The result: a predicted finishing order for every session, each with its own margin.",
  },
  {
    key: "grade",
    step: "Self-grade",
    title: "It scores its own homework",
    blurb: "After the race, every prediction is graded against reality — round after round.",
  },
] as const;

const ACCENT = "var(--accent)";
const TEAL = "var(--teal)";

export function ProductFilm() {
  const reduce = useReducedMotion();
  const sectionRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  const [playing, setPlaying] = useState(false);

  // Autoplay only once the film scrolls into view (saves work, mirrors Firefly).
  useEffect(() => {
    const el = sectionRef.current;
    if (!el || reduce) return;
    const io = new IntersectionObserver(
      ([e]) => setPlaying(e.isIntersecting),
      { threshold: 0.3, rootMargin: "0px 0px -10% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reduce]);

  useEffect(() => {
    if (!playing || reduce) return;
    const id = setInterval(() => setActive((a) => (a + 1) % SCENES.length), SCENE_MS);
    return () => clearInterval(id);
  }, [playing, reduce]);

  const scene = SCENES[active];

  return (
    <section className="section pt-0" ref={sectionRef}>
      <div className="shell">
        <div className="mx-auto mb-10 max-w-2xl text-center">
          <h2 className="text-[length:var(--text-4xl)]">Watch the prediction engine run</h2>
          <p className="lead mt-4">
            From a raw timing feed, through the AI&nbsp;model engine, to a result that grades itself
            — the entire pipeline every project on the grid inherits, start to finish.
          </p>
        </div>

        <motion.div
          initial={reduce ? false : { opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="liquid-glass-pane relative mx-auto max-w-5xl overflow-hidden rounded-[var(--radius-xl)]"
        >
          {/* ---- player top bar ---- */}
          <div className="flex items-center justify-between gap-3 border-b border-[var(--line)] px-5 py-3">
            <div className="flex items-center gap-2.5">
              <span className="live-dot" />
              <span className="mono-label !tracking-[0.18em] text-[var(--ink-muted)]">
                MotorsportVerse — how it works
              </span>
            </div>
            <span className="font-mono text-[11px] text-[var(--ink-dim)]">
              {String(active + 1).padStart(2, "0")} / {String(SCENES.length).padStart(2, "0")}
            </span>
          </div>

          {/* ---- stage ---- */}
          <div className="relative aspect-[16/10] sm:aspect-[16/9]">
            <div className="bg-grid bg-grid-fade pointer-events-none absolute inset-0 opacity-30" />
            <AnimatePresence mode="wait">
              <motion.div
                key={scene.key}
                initial={reduce ? false : { opacity: 0, scale: 0.985 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={reduce ? undefined : { opacity: 0, scale: 1.01 }}
                transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                className="absolute inset-0 flex items-center justify-center p-6 sm:p-10"
              >
                <SceneStage which={scene.key} reduce={!!reduce} />
              </motion.div>
            </AnimatePresence>

            {/* caption */}
            <div className="absolute inset-x-0 bottom-0 p-5 sm:p-7">
              <AnimatePresence mode="wait">
                <motion.div
                  key={scene.key + "-cap"}
                  initial={reduce ? false : { opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={reduce ? undefined : { opacity: 0, y: -8 }}
                  transition={{ duration: 0.4 }}
                  className="max-w-md"
                >
                  <p className="mono-label text-[var(--accent-text)]">
                    Step {active + 1} · {scene.step}
                  </p>
                  <h3 className="title-md mt-1.5 text-[length:var(--text-xl)] text-[var(--ink)]">
                    {scene.title}
                  </h3>
                  <p className="body-sm mt-1">{scene.blurb}</p>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>

          {/* ---- scrubber ---- */}
          <div className="h-1 w-full bg-[var(--hairline)]">
            <motion.div
              key={active + (playing ? "p" : "s")}
              className="h-full"
              style={{ background: `linear-gradient(90deg, ${ACCENT}, ${TEAL})` }}
              initial={{ width: "0%" }}
              animate={{ width: playing && !reduce ? "100%" : "16%" }}
              transition={{ duration: playing && !reduce ? SCENE_MS / 1000 : 0.4, ease: "linear" }}
            />
          </div>

          {/* ---- pipeline step-strip (start → finish) ---- */}
          <div className="grid grid-cols-3 gap-px border-t border-[var(--line)] bg-[var(--line)] sm:grid-cols-6">
            {SCENES.map((s, i) => (
              <button
                key={s.key}
                onClick={() => setActive(i)}
                className="group relative flex items-center gap-2 bg-[var(--surface)] px-3 py-2.5 text-left transition-colors hover:bg-[var(--surface-2)]"
                aria-label={`Step ${i + 1}: ${s.step}`}
              >
                <span
                  className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full font-mono text-[10px] font-bold transition-all"
                  style={{
                    background: i === active ? ACCENT : "var(--surface-3)",
                    color: i === active ? "#fff" : "var(--ink-dim)",
                    boxShadow: i === active ? "0 0 12px var(--accent)" : "none",
                  }}
                >
                  {i + 1}
                </span>
                <span
                  className="truncate font-mono text-[10px] uppercase tracking-wider transition-colors"
                  style={{ color: i === active ? "var(--ink)" : "var(--ink-dim)" }}
                >
                  {s.step}
                </span>
              </button>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}

/* ============================ scenes ============================ */

function SceneStage({ which, reduce }: { which: string; reduce: boolean }) {
  switch (which) {
    case "ingest":
      return <IngestScene reduce={reduce} />;
    case "engine":
      return <EngineScene reduce={reduce} />;
    case "calibrate":
      return <CalibrateScene reduce={reduce} />;
    case "simulate":
      return <SimulateScene reduce={reduce} />;
    case "forecast":
      return <ForecastScene reduce={reduce} />;
    default:
      return <GradeScene reduce={reduce} />;
  }
}

const panel =
  "relative w-full max-w-xl rounded-[var(--radius-lg)] border border-[var(--line)] bg-[color-mix(in_srgb,var(--surface)_80%,transparent)] p-5 backdrop-blur-sm";

function IngestScene({ reduce }: { reduce: boolean }) {
  const sources = ["FastF1", "Jolpica", "Archives", "Live timing"];
  const rows = [
    ["VER", "1:18.204", "S1 ✓"],
    ["NOR", "1:18.411", "S2 ✓"],
    ["LEC", "1:18.538", "S1 ✓"],
    ["PIA", "1:18.602", "S3 ✓"],
  ];
  return (
    <div className={panel}>
      <div className="mb-4 flex flex-wrap gap-2">
        {sources.map((s, i) => (
          <motion.span
            key={s}
            initial={reduce ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.12 }}
            className="rounded-full border border-[var(--line-strong)] bg-[var(--surface-2)] px-3 py-1 font-mono text-[11px] tracking-wide text-[var(--ink-muted)]"
          >
            ↳ {s}
          </motion.span>
        ))}
      </div>
      <div className="space-y-1.5">
        {rows.map((r, i) => (
          <motion.div
            key={r[0]}
            initial={reduce ? false : { opacity: 0, x: -24 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.4 + i * 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="flex items-center justify-between rounded-md border border-[var(--line-faint)] bg-[var(--canvas-deep)] px-3 py-2 font-mono text-xs"
          >
            <span className="font-semibold text-[var(--ink)]">{r[0]}</span>
            <span className="text-[var(--ink-muted)]">{r[1]}</span>
            <span className="text-[var(--teal)]">{r[2]}</span>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function EngineScene({ reduce }: { reduce: boolean }) {
  const features = ["Quali pace", "Circuit type", "Driver form", "Tyre model", "Weather"];
  const scores = [
    ["VER", "0.94"],
    ["NOR", "0.88"],
    ["LEC", "0.85"],
  ];
  return (
    <div className={`${panel} max-w-2xl`}>
      <div className="mb-4 flex items-center justify-between">
        <span className="mono-label">ML model engine</span>
        <span className="font-mono text-[11px] text-[var(--ink-dim)]">GBR + XGB ensemble</span>
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        {/* features in */}
        <div className="space-y-1.5">
          {features.map((f, i) => (
            <motion.div
              key={f}
              initial={reduce ? false : { opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 + i * 0.1 }}
              className="rounded-md border border-[var(--line-faint)] bg-[var(--canvas-deep)] px-2.5 py-1.5 font-mono text-[11px] text-[var(--ink-muted)]"
            >
              {f}
            </motion.div>
          ))}
        </div>
        {/* engine core */}
        <div className="relative flex h-24 w-24 items-center justify-center">
          {[0, 1, 2].map((r) => (
            <motion.span
              key={r}
              className="absolute rounded-full border"
              style={{ borderColor: ACCENT, inset: r * 10 }}
              animate={reduce ? { opacity: 0.5 } : { opacity: [0.25, 0.7, 0.25], scale: [0.9, 1.05, 0.9] }}
              transition={{ duration: 2, delay: r * 0.25, repeat: reduce ? 0 : Infinity }}
            />
          ))}
          <motion.span
            className="h-9 w-9 rounded-full"
            style={{ background: `radial-gradient(circle, ${ACCENT}, var(--accent-deep))`, boxShadow: "var(--glow-accent)" }}
            animate={reduce ? undefined : { scale: [1, 1.15, 1] }}
            transition={{ duration: 1.4, repeat: Infinity }}
          />
        </div>
        {/* pace scores out */}
        <div className="space-y-1.5">
          {scores.map((s, i) => (
            <motion.div
              key={s[0]}
              initial={reduce ? false : { opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.6 + i * 0.15 }}
              className="flex items-center justify-between rounded-md border border-[var(--line)] bg-[var(--canvas-deep)] px-2.5 py-1.5 font-mono text-[11px]"
            >
              <span className="font-semibold text-[var(--ink)]">{s[0]}</span>
              <span className="text-[var(--teal)]">{s[1]}</span>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CalibrateScene({ reduce }: { reduce: boolean }) {
  const bars = [
    { name: "Win", raw: 0.62, cal: 0.44 },
    { name: "Podium", raw: 0.88, cal: 0.71 },
    { name: "Points", raw: 0.97, cal: 0.93 },
  ];
  return (
    <div className={panel}>
      <div className="mb-4 flex items-center justify-between">
        <span className="mono-label">Probability calibration</span>
        <span className="rounded-full bg-[color-mix(in_srgb,var(--teal)_18%,transparent)] px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-[var(--teal)]">
          Calibrated
        </span>
      </div>
      <div className="space-y-4">
        {bars.map((b, i) => (
          <div key={b.name}>
            <div className="mb-1 flex justify-between font-mono text-[11px] text-[var(--ink-muted)]">
              <span>{b.name}</span>
              <span className="text-[var(--ink)]">{Math.round(b.cal * 100)}%</span>
            </div>
            <div className="relative h-2.5 overflow-hidden rounded-full bg-[var(--canvas-deep)]">
              <motion.div
                className="absolute inset-y-0 left-0 rounded-full"
                style={{ background: `linear-gradient(90deg, ${ACCENT}, ${TEAL})` }}
                initial={reduce ? false : { width: `${b.raw * 100}%` }}
                animate={{ width: `${b.cal * 100}%` }}
                transition={{ delay: 0.2 + i * 0.15, duration: 1, ease: [0.22, 1, 0.36, 1] }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SimulateScene({ reduce }: { reduce: boolean }) {
  const cells = Array.from({ length: 20 });
  return (
    <div className={panel}>
      <div className="mb-4 flex items-center justify-between">
        <span className="mono-label">Monte-Carlo race engine</span>
        <span className="font-mono text-[11px] text-[var(--ink-dim)]">5,000 runs</span>
      </div>
      <div className="grid grid-cols-10 gap-1.5">
        {cells.map((_, i) => (
          <motion.div
            key={i}
            className="aspect-square rounded-[4px]"
            style={{ background: i < 3 ? ACCENT : "var(--surface-3)" }}
            initial={reduce ? false : { opacity: 0.3 }}
            animate={
              reduce ? { opacity: 1 } : { opacity: [0.3, 1, 0.5, 1], scale: [1, 1.08, 1] }
            }
            transition={{ duration: 1.4, delay: (i % 10) * 0.05, repeat: reduce ? 0 : Infinity, repeatDelay: 1 }}
          />
        ))}
      </div>
      <div className="mt-4 flex gap-2">
        {["P1", "P2", "P3"].map((p, i) => (
          <motion.div
            key={p}
            initial={reduce ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 + i * 0.15 }}
            className="flex-1 rounded-md border border-[var(--line-strong)] bg-[var(--canvas-deep)] py-2 text-center font-mono text-xs text-[var(--ink)]"
          >
            {p}
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function ForecastScene({ reduce }: { reduce: boolean }) {
  const podium = [
    { pos: "1", code: "VER", p: "41%" },
    { pos: "2", code: "NOR", p: "27%" },
    { pos: "3", code: "LEC", p: "19%" },
  ];
  return (
    <div className={`${panel} max-w-md`}>
      <div className="mb-4 mono-label">Predicted podium · next Grand Prix</div>
      <div className="space-y-2.5">
        {podium.map((d, i) => (
          <motion.div
            key={d.code}
            initial={reduce ? false : { opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.15 + i * 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="flex items-center gap-3 rounded-lg border border-[var(--line)] bg-[var(--canvas-deep)] px-3 py-2.5"
          >
            <span
              className="flex h-7 w-7 items-center justify-center rounded-md font-display text-sm font-bold"
              style={{
                background: i === 0 ? ACCENT : "var(--surface-3)",
                color: i === 0 ? "#fff" : "var(--ink)",
              }}
            >
              {d.pos}
            </span>
            <span className="font-mono text-sm font-semibold text-[var(--ink)]">{d.code}</span>
            <div className="ml-auto flex items-center gap-2">
              <div className="h-1.5 w-20 overflow-hidden rounded-full bg-[var(--surface-3)]">
                <motion.div
                  className="h-full"
                  style={{ background: ACCENT }}
                  initial={reduce ? false : { width: 0 }}
                  animate={{ width: d.p }}
                  transition={{ delay: 0.3 + i * 0.18, duration: 0.9 }}
                />
              </div>
              <span className="w-9 text-right font-mono text-xs text-[var(--ink-muted)]">{d.p}</span>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function GradeScene({ reduce }: { reduce: boolean }) {
  const pct = 87;
  const R = 52;
  const C = 2 * Math.PI * R;
  return (
    <div className={`${panel} flex max-w-md flex-col items-center text-center`}>
      <span className="mono-label mb-4">Model vs reality · season accuracy</span>
      <div className="relative h-36 w-36">
        <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
          <circle cx="60" cy="60" r={R} fill="none" stroke="var(--surface-3)" strokeWidth="8" />
          <motion.circle
            cx="60"
            cy="60"
            r={R}
            fill="none"
            stroke={TEAL}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={C}
            initial={reduce ? false : { strokeDashoffset: C }}
            animate={{ strokeDashoffset: C * (1 - pct / 100) }}
            transition={{ duration: 1.3, ease: [0.22, 1, 0.36, 1] }}
            style={{ filter: "drop-shadow(0 0 8px var(--teal))" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-3xl font-bold text-[var(--ink)]">{pct}%</span>
          <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--ink-dim)]">
            podium-weighted
          </span>
        </div>
      </div>
      <p className="body-sm mt-4 max-w-xs">
        Scored every round against the real classified result — never a number the track didn&rsquo;t
        back up.
      </p>
    </div>
  );
}
