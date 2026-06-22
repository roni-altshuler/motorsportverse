"use client";

/**
 * VerseHero — the flagship hero.
 *
 * Sits over the site-wide SpeedField light-trail canvas. Fluid, staggered
 * entrance (framer-motion), a slow breathing glow + gentle float behind the
 * logo, an animated gradient headline, and a scroll cue — Apple/Google-grade
 * restraint over a moving background. Honors reduced motion.
 */

import { motion, useReducedMotion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";

import { asset } from "@/lib/asset";

interface VerseHeroProps {
  stats: { value: string; label: string }[];
}

const EASE = [0.22, 1, 0.36, 1] as const;

export function VerseHero({ stats }: VerseHeroProps) {
  const reduce = useReducedMotion();

  const rise = (delay: number) => ({
    initial: reduce ? false : { opacity: 0, y: 22 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.8, ease: EASE, delay },
  });

  return (
    <section className="relative isolate overflow-hidden">
      {/* Legibility vignette — soft canvas wash behind the headline so copy
          stays sharp while the light-trails show through everywhere else. */}
      <div
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(58% 52% at 50% 38%, color-mix(in srgb, var(--canvas) 72%, transparent) 0%, transparent 76%)",
        }}
        aria-hidden
      />
      {/* Breathing accent bloom behind the logo. */}
      <motion.div
        className="pointer-events-none absolute left-1/2 top-[24%] -z-10 h-[420px] w-[620px] -translate-x-1/2 rounded-full"
        style={{
          background:
            "radial-gradient(50% 50% at 50% 50%, rgba(231,16,47,0.22) 0%, transparent 70%)",
          filter: "blur(20px)",
        }}
        animate={reduce ? undefined : { opacity: [0.55, 0.9, 0.55], scale: [1, 1.06, 1] }}
        transition={{ duration: 6.5, ease: "easeInOut", repeat: Infinity }}
        aria-hidden
      />

      <div className="shell relative flex flex-col items-center pt-28 pb-24 text-center sm:pt-36">
        {/* live ecosystem pill */}
        <motion.div
          {...rise(0)}
          className="liquid-glass mb-10 inline-flex items-center gap-2.5 rounded-full px-3.5 py-1.5 text-xs text-[var(--ink-muted)]"
        >
          <span className="live-dot" />
          <span className="font-mono tracking-wide">
            {stats[0]?.value ?? "—"} projects · {stats[1]?.value ?? "—"} live
          </span>
          <span className="text-[var(--ink-dim)]">·</span>
          <span>one shared core</span>
        </motion.div>

        <motion.div
          {...rise(0.08)}
          animate={
            reduce
              ? { opacity: 1, y: 0 }
              : { opacity: 1, y: [0, -8, 0] }
          }
          transition={
            reduce
              ? { duration: 0.8, ease: EASE, delay: 0.08 }
              : {
                  opacity: { duration: 0.8, ease: EASE, delay: 0.08 },
                  y: { duration: 7, ease: "easeInOut", repeat: Infinity, delay: 0.9 },
                }
          }
        >
          <Image
            src={asset("/brand/motorsportverse-logo.png")}
            alt="MotorsportVerse"
            width={1217}
            height={414}
            priority
            className="h-auto w-full max-w-[520px] drop-shadow-[0_8px_50px_rgba(231,16,47,0.28)]"
          />
        </motion.div>

        <motion.h1 {...rise(0.16)} className="display mt-9 max-w-4xl text-[length:var(--text-hero)]">
          <span className="text-gradient">Predict every race.</span>
          <br />
          <span className="hero-sheen">One unified ecosystem.</span>
        </motion.h1>

        <motion.p {...rise(0.24)} className="lead mt-7 max-w-2xl text-balance">
          A family of open-source projects that forecast race outcomes across every category of
          motorsport — built on one shared core of calibration, simulation, and data
          infrastructure, extracted from the RaceIQ&nbsp;F1 flagship.
        </motion.p>

        <motion.div {...rise(0.32)} className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Link href="/projects" className="btn-accent px-6 py-3 text-sm font-semibold">
            Explore projects
          </Link>
          <Link href="/docs" className="btn-ghost px-6 py-3 text-sm font-semibold">
            Read the docs
          </Link>
        </motion.div>

        {/* stat strip — hairline-led, restrained */}
        <motion.dl
          {...rise(0.4)}
          className="liquid-glass mt-16 grid w-full max-w-3xl grid-cols-2 overflow-hidden rounded-[var(--radius-lg)] sm:grid-cols-4"
        >
          {stats.map((s, i) => (
            <div
              key={s.label}
              className={`px-6 py-7 text-center ${
                i > 0 ? "border-t border-[var(--line)] sm:border-l sm:border-t-0" : ""
              }`}
            >
              <dd className="font-display text-4xl font-bold text-[var(--ink)]">{s.value}</dd>
              <dt className="mono-label mt-1.5">{s.label}</dt>
            </div>
          ))}
        </motion.dl>

        {/* scroll cue */}
        <motion.div
          {...rise(0.5)}
          className="mt-14 flex flex-col items-center gap-2 text-[var(--ink-dim)]"
          aria-hidden
        >
          <span className="mono-label !text-[10px]">Scroll</span>
          <motion.span
            className="block h-7 w-[1.5px] rounded-full"
            style={{ background: "linear-gradient(180deg, var(--accent), transparent)" }}
            animate={reduce ? undefined : { scaleY: [0.5, 1, 0.5], opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 2.2, ease: "easeInOut", repeat: Infinity }}
          />
        </motion.div>
      </div>
    </section>
  );
}
