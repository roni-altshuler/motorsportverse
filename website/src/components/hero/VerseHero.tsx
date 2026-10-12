"use client";

/** Static hero surfaces with a finite entrance; no ambient layers or loops. */

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
      <div className="shell relative flex flex-col items-center pt-28 pb-24 text-center sm:pt-36">
        {/* live ecosystem pill */}
        <motion.div
          {...rise(0)}
          className="liquid-glass mb-10 inline-flex items-center gap-2.5 rounded-full px-3.5 py-1.5 text-xs text-[var(--ink-muted)]"
        >
          <span className="live-dot" />
          <span className="font-mono tracking-wide whitespace-nowrap">
            {stats[0]?.value ?? "—"} series · {stats[1]?.value ?? "—"} live
            products
          </span>
          <span className="hidden text-[var(--ink-dim)] sm:inline">·</span>
          <span className="hidden sm:inline">one shared core</span>
        </motion.div>

        <motion.div {...rise(0.08)}>
          <Image
            src={asset("/brand/motorsportverse-logo.png")}
            alt="MotorsportVerse"
            width={1217}
            height={414}
            priority
            className="h-auto w-full max-w-[520px] drop-shadow-[0_8px_50px_rgba(231,16,47,0.28)]"
          />
        </motion.div>

        <motion.h1
          {...rise(0.16)}
          className="display mt-9 max-w-4xl text-[length:var(--text-hero)]"
        >
          <span className="text-gradient">Prediction infrastructure</span>
          <br />
          <span className="hero-sheen">for every racing series.</span>
        </motion.h1>

        <motion.p {...rise(0.24)} className="lead mt-7 max-w-2xl text-balance">
          One open-source core powering live forecasts for every racing series.
        </motion.p>

        <motion.div
          {...rise(0.32)}
          className="mt-10 flex flex-wrap items-center justify-center gap-3"
        >
          <Link
            href="/projects"
            className="btn-accent px-6 py-3 text-sm font-semibold"
          >
            Explore projects
          </Link>
          <Link
            href="/docs"
            className="btn-ghost px-6 py-3 text-sm font-semibold"
          >
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
                i > 0
                  ? "border-t border-[var(--line)] sm:border-l sm:border-t-0"
                  : ""
              }`}
            >
              <dd className="font-display text-4xl font-bold text-[var(--ink)]">
                {s.value}
              </dd>
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
          <span
            className="block h-7 w-[1.5px] rounded-full"
            style={{
              background: "linear-gradient(180deg, var(--accent), transparent)",
            }}
          />
        </motion.div>
      </div>
    </section>
  );
}
