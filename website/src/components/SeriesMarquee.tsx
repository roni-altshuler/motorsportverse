"use client";

import Image from "next/image";

import { Marquee } from "@/components/magicui/marquee";

export interface SeriesItem {
  key: string;
  sport: string;
  icon?: string;
  accent?: string;
  maturity: string;
}

export function SeriesMarquee({ items }: { items: SeriesItem[] }) {
  return (
    <div className="relative">
      <Marquee pauseOnHover className="[--duration:38s] [--gap:1.25rem]">
        {items.map((s) => (
          <div
            key={s.key}
            className="flex items-center gap-3 rounded-[var(--radius-pill)] border border-[var(--hairline)] bg-[var(--surface)]/70 px-5 py-3 backdrop-blur"
            style={{ ["--team-color" as string]: s.accent || "var(--accent)" }}
          >
            {s.icon && <Image src={s.icon} alt="" width={26} height={26} className="h-[26px] w-[26px]" />}
            <span className="whitespace-nowrap font-display text-sm font-semibold tracking-wide text-[var(--ink)]">
              RaceIQ {s.sport}
            </span>
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: `var(--maturity-${s.maturity})` }}
              aria-hidden
            />
          </div>
        ))}
      </Marquee>
      {/* edge fades */}
      <div className="pointer-events-none absolute inset-y-0 left-0 w-24 bg-gradient-to-r from-[var(--canvas)] to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-24 bg-gradient-to-l from-[var(--canvas)] to-transparent" />
    </div>
  );
}
