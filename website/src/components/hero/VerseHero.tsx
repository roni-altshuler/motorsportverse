/**
 * VerseHero — the flagship hero.
 *
 * Fully static and server-renderable: the animated atmosphere now comes from
 * the site-wide checkered-flag wave canvas (rendered in the root layout), so
 * the hero just sits over it. A soft radial vignette behind the copy keeps the
 * headline legible against the moving background; the wave shows through
 * everywhere else.
 */

import Image from "next/image";
import Link from "next/link";

import { asset } from "@/lib/asset";

interface VerseHeroProps {
  stats: { value: string; label: string }[];
}

export function VerseHero({ stats }: VerseHeroProps) {
  return (
    <section className="relative isolate overflow-hidden">
      {/* Legibility vignette only — transparent so the site-wide wave shows
          through, with a soft canvas wash behind the headline for contrast. */}
      <div
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(60% 55% at 50% 40%, color-mix(in srgb, var(--canvas) 70%, transparent) 0%, transparent 78%)",
        }}
        aria-hidden
      />

      <div className="shell relative flex flex-col items-center pt-28 pb-24 text-center sm:pt-36">
        {/* live ecosystem pill */}
        <div className="liquid-glass mb-10 inline-flex items-center gap-2.5 rounded-full px-3.5 py-1.5 text-xs text-[var(--ink-muted)]">
          <span className="live-dot" />
          <span className="font-mono tracking-wide">
            {stats[0]?.value ?? "—"} projects · {stats[1]?.value ?? "—"} live
          </span>
          <span className="text-[var(--ink-dim)]">·</span>
          <span>one shared core</span>
        </div>

        <Image
          src={asset("/brand/motorsportverse-logo.png")}
          alt="MotorsportVerse"
          width={1217}
          height={414}
          priority
          className="h-auto w-full max-w-[520px] drop-shadow-[0_8px_50px_rgba(231,16,47,0.28)]"
        />

        <h1 className="display mt-9 max-w-4xl text-[length:var(--text-hero)]">
          <span className="text-gradient">Predict every race.</span>
          <br />
          <span className="text-gradient-accent">One unified ecosystem.</span>
        </h1>

        <p className="lead mt-7 max-w-2xl text-balance">
          A family of open-source projects that forecast race outcomes across every category of
          motorsport — built on one shared core of calibration, simulation, and data
          infrastructure, extracted from the RaceIQ&nbsp;F1 flagship.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Link href="/projects" className="btn-accent px-6 py-3 text-sm font-semibold">
            Explore projects
          </Link>
          <Link href="/docs" className="btn-ghost px-6 py-3 text-sm font-semibold">
            Read the docs
          </Link>
        </div>

        {/* stat strip — hairline-led, restrained */}
        <dl className="liquid-glass mt-16 grid w-full max-w-3xl grid-cols-2 overflow-hidden rounded-[var(--radius-lg)] sm:grid-cols-4">
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
        </dl>
      </div>
    </section>
  );
}
