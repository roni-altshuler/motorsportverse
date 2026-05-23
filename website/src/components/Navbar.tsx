"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { SeasonData, SeasonTrackerData } from "@/types";
import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import { fetchSeasonData, fetchSeasonTrackerData, getRoundLifecycle, getRoundStatusMeta } from "@/lib/data";
import { DEFAULT_SEASON_YEAR } from "@/lib/season";

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

interface AccuracySummary {
  accuracyPct: number;
  roundsWithActual: number;
}

function useAccuracySummary(): AccuracySummary | null {
  const [summary, setSummary] = useState<AccuracySummary | null>(null);
  useEffect(() => {
    fetch(`${BASE_PATH}/data/gp_accuracy_report.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d?.overallAccuracy) return;
        setSummary({
          accuracyPct: d.overallAccuracy.seasonAccuracyPct ?? 0,
          roundsWithActual: d.overallAccuracy.roundsWithActual ?? 0,
        });
      })
      .catch(() => {});
  }, []);
  return summary;
}

const TONE_TO_BADGE_VARIANT = {
  red: "negative",
  green: "positive",
  amber: "live",
  slate: "muted",
} as const;
type StatusTone = keyof typeof TONE_TO_BADGE_VARIANT;

export default function Navbar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [racesOpen, setRacesOpen] = useState(false);
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [tracker, setTracker] = useState<SeasonTrackerData | null>(null);
  const racesRef = useRef<HTMLDivElement>(null);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetchSeasonData().then(setSeason).catch(() => {});
    fetchSeasonTrackerData().then(setTracker).catch(() => {});
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (racesRef.current && !racesRef.current.contains(e.target as Node)) {
        setRacesOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Close-on-hover-out uses a small grace timeout so the cursor can travel
  // between the trigger button and the dropdown body without the menu
  // collapsing under it.
  const openRacesMenu = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    setRacesOpen(true);
  };
  const scheduleRacesClose = () => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    closeTimerRef.current = setTimeout(() => setRacesOpen(false), 140);
  };
  useEffect(() => () => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
  }, []);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  const navLink = (href: string, label: string) => (
    <Link
      href={href}
      aria-current={isActive(href) ? "page" : undefined}
      className={`nav-link-text px-4 py-2 transition-colors ${
        isActive(href)
          ? "text-[color:var(--ink)]"
          : "text-[color:var(--muted)] hover:text-[color:var(--ink)]"
      }`}
    >
      {label}
    </Link>
  );

  const actualSet = new Set((tracker?.rounds || []).filter((round) => round.hasActual).map((round) => round.round));

  const accuracySummary = useAccuracySummary();

  const seasonYear = season?.season ?? DEFAULT_SEASON_YEAR;

  return (
    <nav
      className="sticky top-0 z-50"
      aria-label="Primary"
      style={{
        background: "rgba(0, 0, 0, 0.85)",
        borderBottom: "1px solid var(--hairline)",
      }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-3 items-center h-14">
          {/* Left: MENU label (mobile hamburger) + desktop nav cluster */}
          <div className="flex items-center gap-1 justify-start">
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="md:hidden nav-link-text px-3 py-2 text-[color:var(--ink)]"
              aria-label="Toggle menu"
            >
              {mobileOpen ? "CLOSE" : "MENU"}
            </button>

            <div className="hidden md:flex items-center gap-0">
              {navLink("/", "Home")}

              <div
                ref={racesRef}
                className="relative"
                onMouseEnter={openRacesMenu}
                onMouseLeave={scheduleRacesClose}
              >
                <button
                  onClick={() => setRacesOpen((open) => !open)}
                  onFocus={openRacesMenu}
                  aria-haspopup="menu"
                  aria-expanded={racesOpen}
                  className={`nav-link-text px-4 py-2 inline-flex items-center gap-1.5 transition-colors ${
                    isActive("/race") || isActive("/calendar")
                      ? "text-[color:var(--ink)]"
                      : "text-[color:var(--muted)] hover:text-[color:var(--ink)]"
                  }`}
                >
                  Races
                  <svg className={`w-3 h-3 transition-transform ${racesOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {racesOpen && season && (
                  <div
                    role="menu"
                    data-lenis-prevent
                    className="dropdown-menu absolute top-full left-0 mt-2 w-80 max-h-[70vh] overflow-y-auto overscroll-contain"
                    style={{ scrollbarGutter: "stable" }}
                  >
                    <div className="p-2">
                      <Link
                        href="/calendar"
                        onClick={() => setRacesOpen(false)}
                        className="nav-link-text flex items-center gap-3 px-3 py-2.5 text-[color:var(--ink)] transition-colors hover:bg-[color:var(--surface-elevated)]"
                      >
                        Full Season Calendar
                      </Link>
                      <div className="h-px my-1" style={{ background: "var(--hairline)" }} />
                      {season.calendar.map((race) => {
                        const completed = season.completedRounds.includes(race.round);
                        const statusMeta = getRoundStatusMeta(
                          getRoundLifecycle(race, completed, actualSet.has(race.round)),
                        );
                        return (
                          <Link
                            key={race.round}
                            href={`/race/${race.round}`}
                            onClick={() => setRacesOpen(false)}
                            role="menuitem"
                            className="flex items-center gap-3 px-3 py-2 text-sm font-serif transition-colors hover:bg-[color:var(--surface-elevated)]"
                            style={{ color: "var(--body)" }}
                          >
                            <CountryFlag country={race.country} size={20} />
                            <span className="flex-1 truncate">{race.name}</span>
                            <span className="eyebrow shrink-0">R{race.round}</span>
                            <Badge variant={TONE_TO_BADGE_VARIANT[statusMeta.tone as StatusTone] ?? "default"}>
                              {statusMeta.shortLabel}
                            </Badge>
                          </Link>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {navLink("/standings", "Standings")}
              {navLink("/about", "About")}
            </div>
          </div>

          {/* Center: wordmark */}
          <Link href="/" className="flex items-center justify-center gap-2 group">
            <span className="wordmark">F1 {seasonYear} PREDICTIONS</span>
          </Link>

          {/* Right: accuracy chip */}
          <div className="flex items-center justify-end">
            {accuracySummary && accuracySummary.roundsWithActual > 0 && (
              <Link
                href="/about#methodology"
                className="eyebrow inline-flex items-center gap-1.5 px-3 py-1 border transition-colors hover:text-[color:var(--ink)]"
                style={{
                  borderColor: "var(--hairline)",
                  color: "var(--muted)",
                }}
                title={`Season accuracy ${accuracySummary.accuracyPct.toFixed(1)}% across ${accuracySummary.roundsWithActual} completed round(s)`}
              >
                {accuracySummary.accuracyPct.toFixed(0)}% · {accuracySummary.roundsWithActual}R
              </Link>
            )}
          </div>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="md:hidden py-4 border-t" style={{ borderColor: "var(--hairline)" }}>
            <div className="flex flex-col gap-0">
              {[
                { href: "/", label: "Home" },
                { href: "/calendar", label: "Season Calendar" },
                { href: "/standings", label: "Standings" },
                { href: "/about", label: "About" },
              ].map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={isActive(item.href) ? "page" : undefined}
                  onClick={() => setMobileOpen(false)}
                  className={`nav-link-text px-4 py-3 row-spec transition-colors ${
                    isActive(item.href)
                      ? "text-[color:var(--ink)]"
                      : "text-[color:var(--muted)]"
                  }`}
                >
                  {item.label}
                </Link>
              ))}
              {season && season.completedRounds.length > 0 && (
                <>
                  <p className="eyebrow px-4 pt-4 pb-2">Race Status</p>
                  {season.calendar
                    .filter((r) => season.completedRounds.includes(r.round) || actualSet.has(r.round))
                    .map((race) => (
                      <Link
                        key={race.round}
                        href={`/race/${race.round}`}
                        onClick={() => setMobileOpen(false)}
                        className="px-4 py-3 row-spec text-sm flex items-center gap-2 justify-between font-serif transition-colors hover:text-[color:var(--ink)]"
                        style={{ color: "var(--body)" }}
                      >
                        <span className="flex items-center gap-2">
                          <CountryFlag country={race.country} size={18} />
                          {race.name}
                        </span>
                        <Badge variant={TONE_TO_BADGE_VARIANT[getRoundStatusMeta(getRoundLifecycle(race, season.completedRounds.includes(race.round), actualSet.has(race.round))).tone as StatusTone] ?? "default"}>
                          {getRoundStatusMeta(getRoundLifecycle(race, season.completedRounds.includes(race.round), actualSet.has(race.round))).shortLabel}
                        </Badge>
                      </Link>
                    ))}
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
