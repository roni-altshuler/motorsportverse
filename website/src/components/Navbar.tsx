"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useTheme } from "./ThemeProvider";
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

// Shared with HomePage — keep the legacy status-pill tone → Badge variant
// mapping centralised so the rest of the codebase can migrate piecewise.
const TONE_TO_BADGE_VARIANT = {
  red: "negative",
  green: "positive",
  amber: "live",
  slate: "muted",
} as const;
type StatusTone = keyof typeof TONE_TO_BADGE_VARIANT;

export default function Navbar() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [racesOpen, setRacesOpen] = useState(false);
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [tracker, setTracker] = useState<SeasonTrackerData | null>(null);
  const racesRef = useRef<HTMLDivElement>(null);

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

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  const navLink = (href: string, label: string) => (
    <Link
      href={href}
      aria-current={isActive(href) ? "page" : undefined}
      className={`px-4 py-2 text-sm font-semibold tracking-wide transition-colors rounded-lg ${
        isActive(href)
          ? "text-[color:var(--accent-live)]"
          : "text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
      }`}
    >
      {label}
    </Link>
  );

  const navLinkWithBadge = (href: string, label: string, badge: string) => (
    <Link
      href={href}
      aria-current={isActive(href) ? "page" : undefined}
      className={`px-4 py-2 text-sm font-semibold tracking-wide transition-colors rounded-lg inline-flex items-center gap-2 ${
        isActive(href)
          ? "text-[color:var(--accent-live)]"
          : "text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
      }`}
    >
      {label}
      <Badge variant="live" className="px-1.5 py-0 text-[9px] leading-tight">
        {badge}
      </Badge>
    </Link>
  );

  const actualSet = new Set((tracker?.rounds || []).filter((round) => round.hasActual).map((round) => round.round));

  // Compact accuracy chip — fetches gp_accuracy_report.json once and
  // surfaces "Accuracy 53.4% · N rounds" so visitors always know how the
  // model has been performing.  Replaces the standalone /accuracy nav
  // link per the 2026-05 redesign.
  const accuracySummary = useAccuracySummary();

  return (
    <nav
      className="sticky top-0 z-50 border-b"
      aria-label="Primary"
      style={{
        background: "var(--bg)",
        borderColor: "var(--border)",
      }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center font-black text-sm tracking-tighter group-hover:scale-105 transition-transform shadow-lg"
              style={{
                background: "var(--accent-live)",
                color: "var(--accent-live-fg)",
                boxShadow: "0 8px 24px color-mix(in srgb, var(--accent-live) 22%, transparent)",
              }}
            >
              F1
            </div>
            <div className="hidden sm:block">
              <p className="text-sm font-bold leading-tight" style={{ color: "var(--text)" }}>
                {season?.season ?? DEFAULT_SEASON_YEAR} PREDICTIONS
              </p>
              <p className="text-[10px] uppercase tracking-widest leading-tight" style={{ color: "var(--text-muted)" }}>
                AI-Powered Forecasts
              </p>
            </div>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-1">
            {navLink("/", "Home")}

            {/* Races Dropdown */}
            <div ref={racesRef} className="relative">
              <button
                onClick={() => setRacesOpen(!racesOpen)}
                className={`px-4 py-2 text-sm font-semibold tracking-wide transition-colors rounded-lg inline-flex items-center gap-1.5 ${
                  isActive("/race") || isActive("/calendar")
                    ? "text-f1-red"
                    : "text-[var(--text-muted)] hover:text-[var(--text)]"
                }`}
              >
                Races
                <svg className={`w-3 h-3 transition-transform ${racesOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {racesOpen && season && (
                <div className="dropdown-menu absolute top-full left-0 mt-2 w-80 max-h-[70vh] overflow-y-auto">
                  <div className="p-2">
                    <Link
                      href="/calendar"
                      className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-bold transition-colors hover:bg-[var(--bg-card-hover)]"
                      style={{ color: "var(--text)" }}
                    >
                      <span className="text-f1-red text-base">📅</span>
                      Full Season Calendar
                    </Link>
                    <div className="h-px my-1" style={{ background: "var(--border)" }} />
                    {season.calendar.map((race) => {
                      const completed = season.completedRounds.includes(race.round);
                      const statusMeta = getRoundStatusMeta(
                        getRoundLifecycle(race, completed, actualSet.has(race.round)),
                      );
                      return (
                        <Link
                          key={race.round}
                          href={`/race/${race.round}`}
                          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors hover:bg-[var(--bg-card-hover)]"
                          style={{ color: "var(--text)" }}
                        >
                          <CountryFlag country={race.country} size={20} />
                          <span className="flex-1 truncate">{race.name}</span>
                          <span className="text-xs shrink-0" style={{ color: "var(--text-muted)" }}>R{race.round}</span>
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

            {navLinkWithBadge("/value", "Value Finder", "NEW")}
            {navLink("/standings", "Standings")}
            {navLink("/about", "About")}

            {/* Accuracy chip — replaces the standalone /accuracy nav link */}
            {accuracySummary && accuracySummary.roundsWithActual > 0 && (
              <Link
                href="/about#methodology"
                className="ml-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-mono font-tabular transition-colors"
                style={{
                  borderColor: "var(--border)",
                  color: "var(--text-muted)",
                }}
                title={`Season accuracy ${accuracySummary.accuracyPct.toFixed(1)}% across ${accuracySummary.roundsWithActual} completed round(s)`}
              >
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-[color:var(--accent-positive)]" aria-hidden />
                {accuracySummary.accuracyPct.toFixed(0)}% · {accuracySummary.roundsWithActual}R
              </Link>
            )}

            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              className="ml-3 p-2 rounded-lg transition-colors text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--glass-bg)]"
              aria-label="Toggle theme"
            >
              {theme === "dark" ? (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
              )}
            </button>
          </div>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden p-2 rounded-lg text-[var(--text-muted)]"
            aria-label="Toggle menu"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              {mobileOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="md:hidden py-4 border-t" style={{ borderColor: "var(--border)" }}>
            <div className="flex flex-col gap-1">
              {[
                { href: "/", label: "Home" },
                { href: "/calendar", label: "Season Calendar" },
                { href: "/value", label: "Value Finder", badge: "NEW" },
                { href: "/standings", label: "Standings" },
                { href: "/about", label: "About" },
              ].map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-4 py-3 text-sm font-semibold rounded-lg transition-colors flex items-center gap-2 ${
                    isActive(item.href) ? "text-f1-red bg-[rgba(225,6,0,0.08)]" : "text-[var(--text-muted)]"
                  }`}
                >
                  {item.label}
                  {item.badge && (
                    <span
                      className="px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wider"
                      style={{
                        background: "rgba(225, 6, 0, 0.18)",
                        color: "#E10600",
                        border: "1px solid rgba(225, 6, 0, 0.35)",
                        letterSpacing: "0.08em",
                      }}
                    >
                      {item.badge}
                    </span>
                  )}
                </Link>
              ))}
              {/* Completed races in mobile */}
              {season && season.completedRounds.length > 0 && (
                <>
                  <div className="h-px my-2" style={{ background: "var(--border)" }} />
                  <p className="px-4 py-1 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Race Status</p>
                  {season.calendar
                    .filter((r) => season.completedRounds.includes(r.round) || actualSet.has(r.round))
                    .map((race) => (
                      <Link
                        key={race.round}
                        href={`/race/${race.round}`}
                        className="px-4 py-2 text-sm flex items-center gap-2 justify-between transition-colors hover:text-f1-red"
                        style={{ color: "var(--text)" }}
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
              <div className="h-px my-2" style={{ background: "var(--border)" }} />
              <button
                onClick={toggleTheme}
                className="px-4 py-3 text-sm font-semibold text-left rounded-lg transition-colors text-[var(--text-muted)]"
              >
                {theme === "dark" ? "☀️ Light Mode" : "🌙 Dark Mode"}
              </button>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
