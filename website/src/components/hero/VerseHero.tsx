"use client";

/**
 * VerseHero — the flagship WebGL hero ("the verse").
 *
 * Loading + degradation strategy (per the static-export + a11y contract):
 *   - The WebGL canvas (VerseCanvas) is loaded via next/dynamic with
 *     ssr:false, so it never participates in `next build` / static export.
 *   - It only mounts after a capability check: WebGL2 present, viewport wide
 *     enough, not a coarse-pointer/low-core device, and not prefers-reduced-
 *     motion. Otherwise the layered CSS gradient + hairline grid backdrop is
 *     shown alone — a fully static, premium fallback.
 *   - Even when active, the canvas sits behind a static gradient wash so the
 *     foreground copy is always legible and the first paint is never blank.
 */

import dynamic from "next/dynamic";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { asset } from "@/lib/asset";

const VerseCanvas = dynamic(() => import("./VerseCanvas"), { ssr: false });

interface VerseHeroProps {
  nodeColors: string[];
  stats: { value: string; label: string }[];
}

export function VerseHero({ nodeColors, stats }: VerseHeroProps) {
  // "off" until we've confirmed the client can/should run WebGL.
  const [mode, setMode] = useState<"static" | "webgl" | "reduced">("static");

  useEffect(() => {
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    const evaluate = () => {
      if (mql.matches) {
        setMode("reduced");
        return;
      }
      const wideEnough = window.innerWidth >= 768;
      const finePointer = window.matchMedia("(pointer: fine)").matches;
      const cores = navigator.hardwareConcurrency ?? 4;
      let webglOk = false;
      try {
        const c = document.createElement("canvas");
        webglOk = !!c.getContext("webgl2");
      } catch {
        webglOk = false;
      }
      if (webglOk && wideEnough && finePointer && cores >= 4) {
        setMode("webgl");
      } else {
        setMode("static");
      }
    };
    evaluate();
    mql.addEventListener("change", evaluate);
    window.addEventListener("resize", evaluate, { passive: true });
    return () => {
      mql.removeEventListener("change", evaluate);
      window.removeEventListener("resize", evaluate);
    };
  }, []);

  return (
    <section className="relative isolate overflow-hidden">
      {/* Static, always-present backdrop (the fallback + the legibility base). */}
      <div className="pointer-events-none absolute inset-0 -z-20">
        <div className="bg-grid bg-grid-fade absolute inset-0 opacity-[0.5]" />
        <div
          className="absolute inset-0"
          style={{ background: "var(--mesh-1)" }}
          aria-hidden
        />
      </div>

      {/* WebGL verse — only when the client opted in. */}
      {mode === "webgl" && (
        <div className="pointer-events-none absolute inset-0 -z-10">
          <div className="absolute left-1/2 top-[42%] h-[120%] w-[120%] -translate-x-1/2 -translate-y-1/2">
            <VerseCanvas nodeColors={nodeColors} />
          </div>
          {/* vignette so text stays crisp over the field */}
          <div
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(70% 60% at 50% 38%, transparent 0%, var(--canvas) 92%)",
            }}
          />
        </div>
      )}

      <div className="shell relative flex flex-col items-center pt-28 pb-24 text-center sm:pt-36">
        {/* live ecosystem pill */}
        <div className="glass mb-10 inline-flex items-center gap-2.5 rounded-full px-3.5 py-1.5 text-xs text-[var(--ink-muted)]">
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
        <dl className="mt-16 grid w-full max-w-3xl grid-cols-2 overflow-hidden rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--glass)] backdrop-blur-xl sm:grid-cols-4">
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
