"use client";

/**
 * ProductFilm — the end-to-end "how the engine works" product film.
 *
 * Plays the Remotion-rendered MP4 (authored in /remotion, synced to
 * public/film/) which walks the prediction engine from raw timing data, through
 * the ML model engine, to a self-graded result. Autoplays on scroll-in (muted /
 * loop / playsInline — mirrors the FireFly product film). Under reduced motion
 * or before JS, the poster frame shows instead.
 *
 * The film carries its own player chrome, captions, and pipeline step-strip
 * (baked into the render), so this component is just a framed, cinematic player.
 */

import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { asset } from "@/lib/asset";

const FILM = asset("/film/motorsportverse-engine.mp4");
const POSTER = asset("/film/engine-poster.png");

const STEPS = ["Ingest", "Model engine", "Calibrate", "Simulate", "Forecast", "Self-grade"];

export function ProductFilm() {
  const reduce = useReducedMotion();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [started, setStarted] = useState(false);

  // Begin playback only when the film scrolls into view (saves bandwidth on
  // visitors who never reach it). Once started it loops; we don't pause on
  // scroll-away. Honors reduced motion by never autoplaying.
  useEffect(() => {
    const v = videoRef.current;
    if (!v || reduce) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          v.play().then(() => setStarted(true)).catch(() => {});
          io.disconnect();
        }
      },
      { threshold: 0.35, rootMargin: "0px 0px -8% 0px" },
    );
    io.observe(v);
    return () => io.disconnect();
  }, [reduce]);

  return (
    <section className="section pt-0">
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
          className="liquid-glass-pane relative mx-auto max-w-5xl overflow-hidden rounded-[var(--radius-xl)] p-2 sm:p-3"
        >
          <div className="relative overflow-hidden rounded-[var(--radius-lg)]">
            {reduce ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={POSTER} alt="MotorsportVerse prediction-engine walkthrough" className="block w-full" />
            ) : (
              <video
                ref={videoRef}
                src={FILM}
                poster={POSTER}
                muted
                loop
                playsInline
                preload="metadata"
                controls={false}
                aria-label="MotorsportVerse product film — how the prediction engine works, from raw timing data to a self-graded result."
                className="block w-full"
              />
            )}
            {/* faint live badge while the film plays */}
            <div
              className={`pointer-events-none absolute right-4 top-4 flex items-center gap-2 rounded-full border border-[var(--line-strong)] bg-[color-mix(in_srgb,var(--canvas)_70%,transparent)] px-3 py-1 backdrop-blur-sm transition-opacity duration-500 ${
                started ? "opacity-100" : "opacity-0"
              }`}
            >
              <span className="live-dot" />
              <span className="mono-label !text-[10px] text-[var(--ink-muted)]">Product film</span>
            </div>
          </div>
        </motion.div>

        {/* pipeline summary under the player */}
        <div className="mx-auto mt-6 flex max-w-5xl flex-wrap items-center justify-center gap-x-2 gap-y-2 px-2">
          {STEPS.map((s, i) => (
            <span key={s} className="flex items-center gap-2">
              <span className="mono-label !text-[10px] text-[var(--ink-muted)]">
                <span className="text-[var(--accent-text)]">{String(i + 1).padStart(2, "0")}</span> {s}
              </span>
              {i < STEPS.length - 1 && <span className="text-[var(--ink-dim)]">→</span>}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
