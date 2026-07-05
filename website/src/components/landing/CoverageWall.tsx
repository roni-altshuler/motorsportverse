"use client";

/**
 * CoverageWall — every racing series in the registry as a premium tile wall.
 *
 * One tile per sport: brand icon, series name, and an honest maturity state
 * (teal live dot = production, amber pulse = experimental, blueprint blue =
 * in development). Live products deep-link to their dashboards; scaffolds
 * link to their in-app architecture preview. Data arrives via props from the
 * server page (never imports the fs-based registry loader).
 */

import Image from "next/image";
import Link from "next/link";
import { motion } from "framer-motion";

import { asset } from "@/lib/asset";
import { fadeUp, staggerContainer } from "@/lib/motion";
import { useReveal } from "@/lib/useReveal";
import type { Maturity } from "@/types/registry";

export interface CoverageItem {
  slug: string;
  sport: string;
  icon?: string;
  accent: string;
  maturity: Maturity;
  /** External product URL — present only for live (production/experimental) series. */
  website?: string;
}

const STATE: Record<
  string,
  { label: string; hint: string; colorVar: string; pulse: boolean }
> = {
  production: {
    label: "Live",
    hint: "Open dashboard",
    colorVar: "var(--maturity-production)",
    pulse: true,
  },
  experimental: {
    label: "Experimental",
    hint: "Open dashboard",
    colorVar: "var(--maturity-experimental)",
    pulse: true,
  },
  "in-development": {
    label: "In development",
    hint: "Architecture preview",
    colorVar: "var(--maturity-in-development)",
    pulse: false,
  },
};

export function CoverageWall({ items }: { items: CoverageItem[] }) {
  const { ref, shown } = useReveal();

  if (!items.length) {
    return (
      <p className="card-premium p-8 text-center text-sm text-[var(--ink-dim)]">
        The series registry is empty — check back after the next build.
      </p>
    );
  }

  return (
    <motion.div
      ref={ref}
      variants={staggerContainer}
      initial="hidden"
      animate={shown ? "visible" : "hidden"}
      className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4"
    >
      {items.map((it, i) => (
        <WallTile key={it.slug} item={it} index={i} />
      ))}
    </motion.div>
  );
}

function WallTile({ item, index }: { item: CoverageItem; index: number }) {
  const state = STATE[item.maturity] ?? STATE["in-development"];
  const live =
    (item.maturity === "production" || item.maturity === "experimental") && !!item.website;

  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <span
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[var(--radius-md)] border"
          style={{
            borderColor: `color-mix(in srgb, ${item.accent} 30%, var(--line))`,
            background: `color-mix(in srgb, ${item.accent} 9%, transparent)`,
          }}
        >
          {item.icon ? (
            <Image
              src={asset(item.icon)}
              alt=""
              width={26}
              height={26}
              className={`h-[26px] w-[26px] ${live ? "" : "opacity-80"}`}
            />
          ) : (
            <span className="text-xs font-bold" style={{ color: item.accent }}>
              {item.sport.slice(0, 2).toUpperCase()}
            </span>
          )}
        </span>
        {live ? (
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden
            className="mt-1 text-[var(--ink-dim)] transition-colors group-hover:text-[var(--ink)]"
          >
            <path
              d="M7 17 17 7M9 7h8v8"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        ) : (
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden
            className="mt-1 text-[var(--ink-dim)] transition-colors group-hover:text-[var(--ink)]"
          >
            <path
              d="M5 12h14M13 6l6 6-6 6"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </div>

      <h3
        className={`mt-4 font-display text-base font-semibold leading-tight ${
          live ? "text-[var(--ink)]" : "text-[var(--ink-muted)]"
        }`}
      >
        {item.sport}
      </h3>

      <p className="mt-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.16em]">
        {state.pulse ? (
          <span
            className="live-dot !h-1.5 !w-1.5"
            style={{ ["--dot-color" as string]: state.colorVar }}
            aria-hidden
          />
        ) : (
          <span
            className="inline-block h-1.5 w-1.5 rounded-full border"
            style={{ borderColor: state.colorVar }}
            aria-hidden
          />
        )}
        <span style={{ color: state.colorVar }}>{state.label}</span>
      </p>

      {/* hover hint — kept in flow (fades in) so tiles never jump */}
      <p className="mt-1.5 text-[11px] text-[var(--ink-dim)] opacity-0 transition-opacity duration-300 group-hover:opacity-100">
        {state.hint} {live ? "↗" : "→"}
      </p>
    </>
  );

  const className = "group card-premium card-pop relative block p-4 sm:p-5";
  const style = { ["--team-color" as string]: item.accent };

  return (
    <motion.div variants={fadeUp} custom={index * 0.4}>
      {live ? (
        <a
          href={item.website}
          target="_blank"
          rel="noreferrer"
          className={className}
          style={style}
          aria-label={`${item.sport} — live forecasts (opens the product site)`}
        >
          {body}
        </a>
      ) : (
        <Link
          href={`/projects/${item.slug}`}
          className={className}
          style={style}
          aria-label={`${item.sport} — in development, view the architecture preview`}
        >
          {body}
        </Link>
      )}
    </motion.div>
  );
}
