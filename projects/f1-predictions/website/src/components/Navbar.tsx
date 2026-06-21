"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "framer-motion";
import { ChevronDown, Github, Menu, X } from "lucide-react";

import { SeasonData, SeasonTrackerData } from "@/types";
import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import { ShimmerButton } from "@/components/magicui/shimmer-button";
import {
  fetchSeasonData,
  fetchSeasonTrackerData,
  getRoundLifecycle,
  getRoundStatusMeta,
} from "@/lib/data";
import { useSeason } from "@/lib/SeasonProvider";
import SeasonSwitcher from "@/components/SeasonSwitcher";

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";
const GITHUB_URL = "https://github.com/roni-altshuler/f1_predictions";

interface AccuracySummary {
  accuracyPct: number;
  roundsWithActual: number;
}

function useAccuracySummary(base: string): AccuracySummary | null {
  const [summary, setSummary] = useState<AccuracySummary | null>(null);
  useEffect(() => {
    fetch(`${base}/gp_accuracy_report.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d?.overallAccuracy) {
          setSummary(null);
          return;
        }
        setSummary({
          // Headline = podium-weighted (60/40) exact-position accuracy.
          accuracyPct: d.overallAccuracy.seasonAccuracyPct ?? 0,
          roundsWithActual: d.overallAccuracy.roundsWithActual ?? 0,
        });
      })
      .catch(() => {});
  }, [base]);
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
  const [standingsOpen, setStandingsOpen] = useState(false);
  const [standingsAnchor, setStandingsAnchor] = useState<"left" | "right">("left");
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [tracker, setTracker] = useState<SeasonTrackerData | null>(null);
  const [utilityHidden, setUtilityHidden] = useState(false);
  const racesRef = useRef<HTMLDivElement>(null);
  const standingsRef = useRef<HTMLDivElement>(null);
  const racesCloseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const standingsCloseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { basePath, year, index } = useSeason();
  const accuracy = useAccuracySummary(basePath);
  const { scrollY } = useScroll();

  // Append ?season=<year> to in-app links when viewing a non-current season so
  // deep links land on the right archive.
  const withSeason = (href: string) =>
    index && year !== index.current ? `${href}${href.includes("?") ? "&" : "?"}season=${year}` : href;

  useEffect(() => {
    fetchSeasonData(basePath).then(setSeason).catch(() => setSeason(null));
    fetchSeasonTrackerData(basePath).then(setTracker).catch(() => setTracker(null));
  }, [basePath]);

  // Outside-click to close dropdowns
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (racesRef.current && !racesRef.current.contains(e.target as Node)) {
        setRacesOpen(false);
      }
      if (standingsRef.current && !standingsRef.current.contains(e.target as Node)) {
        setStandingsOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useMotionValueEvent(scrollY, "change", (latest) => {
    setUtilityHidden(latest > 80);
  });

  // Compute the Standings dropdown anchor at open time so we don't have to
  // synchronously setState from an effect (React 19 lint rule). Flips to
  // right-anchored when the menu would overflow the viewport.
  const computeStandingsAnchor = (): "left" | "right" => {
    const trigger = standingsRef.current;
    if (!trigger || typeof window === "undefined") return "left";
    const rect = trigger.getBoundingClientRect();
    return rect.left + 440 > window.innerWidth - 12 ? "right" : "left";
  };
  const openStandings = () => {
    if (standingsCloseTimerRef.current) {
      clearTimeout(standingsCloseTimerRef.current);
      standingsCloseTimerRef.current = null;
    }
    setStandingsAnchor(computeStandingsAnchor());
    setStandingsOpen(true);
  };
  const toggleStandings = () => {
    setStandingsOpen((open) => {
      if (!open) setStandingsAnchor(computeStandingsAnchor());
      return !open;
    });
  };

  // Hover-open with grace timeout for cursor travel
  const openMenu = (ref: typeof racesCloseTimerRef, setOpen: (b: boolean) => void) => {
    if (ref.current) {
      clearTimeout(ref.current);
      ref.current = null;
    }
    setOpen(true);
  };
  const scheduleClose = (ref: typeof racesCloseTimerRef, setOpen: (b: boolean) => void) => {
    if (ref.current) clearTimeout(ref.current);
    ref.current = setTimeout(() => setOpen(false), 140);
  };
  useEffect(() => () => {
    if (racesCloseTimerRef.current) clearTimeout(racesCloseTimerRef.current);
    if (standingsCloseTimerRef.current) clearTimeout(standingsCloseTimerRef.current);
  }, []);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  const actualSet = useMemo(
    () => new Set((tracker?.rounds || []).filter((round) => round.hasActual).map((round) => round.round)),
    [tracker],
  );

  // Find next upcoming round (first non-completed)
  const nextRound = useMemo(() => {
    if (!season) return null;
    const completed = new Set(season.completedRounds);
    return season.calendar.find((r) => !completed.has(r.round)) ?? season.calendar[season.calendar.length - 1];
  }, [season]);

  const navLinkBase =
    "nav-link-text px-3 lg:px-4 py-2 inline-flex items-center gap-1.5 transition-colors";

  const navLink = (href: string, label: string) => (
    <Link
      href={withSeason(href)}
      aria-current={isActive(href) ? "page" : undefined}
      className={`${navLinkBase} ${
        isActive(href)
          ? "text-[color:var(--ink)]"
          : "text-[color:var(--muted)] hover:text-[color:var(--ink)]"
      }`}
    >
      {label}
    </Link>
  );

  return (
    <nav
      className="sticky top-0 z-50"
      aria-label="Primary"
      style={{
        background: "rgba(0, 0, 0, 0.85)",
        backdropFilter: "blur(10px)",
        borderBottom: "1px solid var(--hairline)",
      }}
    >
      {/* ── Row 1: utility strip (collapses on scroll) ─────────────── */}
      <motion.div
        initial={false}
        animate={{
          height: utilityHidden ? 0 : 32,
          opacity: utilityHidden ? 0 : 1,
        }}
        transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
        className="overflow-hidden border-b border-[color:var(--hairline)]/60"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-8 flex items-center justify-end gap-2 text-[10px]">
          <SeasonSwitcher />
          {accuracy && accuracy.roundsWithActual > 0 && (
            <Link
              href="/about#methodology"
              className="eyebrow inline-flex items-center gap-1.5 px-2 py-0.5 border transition-colors hover:text-[color:var(--ink)]"
              style={{
                borderColor:
                  accuracy.accuracyPct >= 80
                    ? "var(--accent-f1-red-soft)"
                    : accuracy.accuracyPct < 60
                      ? "rgba(212,160,23,0.4)"
                      : "var(--hairline)",
                color: "var(--muted)",
              }}
              title={`Season podium & points accuracy ${accuracy.accuracyPct.toFixed(1)}% across ${accuracy.roundsWithActual} completed round(s)`}
            >
              <span
                className="inline-block w-1.5 h-1.5 rounded-full"
                style={{
                  background:
                    accuracy.accuracyPct >= 80 ? "var(--accent-f1-red)" : "var(--muted)",
                }}
              />
              {accuracy.accuracyPct.toFixed(0)}% · {accuracy.roundsWithActual}R
            </Link>
          )}
          {process.env.NODE_ENV === "development" && (
            <Link
              href="/design-system"
              className="eyebrow px-2 py-0.5 hover:text-[color:var(--ink)] text-[color:var(--muted)] transition-colors"
            >
              Design System
            </Link>
          )}
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="eyebrow inline-flex items-center gap-1 px-2 py-0.5 hover:text-[color:var(--ink)] text-[color:var(--muted)] transition-colors"
            aria-label="GitHub repository"
          >
            <Github className="w-3 h-3" />
            <span className="hidden sm:inline">GitHub</span>
          </a>
        </div>
      </motion.div>

      {/* ── Row 2: primary nav ─────────────────────────────────────── */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center h-14 gap-2 sm:gap-4">
          {/* mobile trigger */}
          <button
            onClick={() => setMobileOpen(true)}
            className="md:hidden inline-flex items-center justify-center w-9 h-9 -ml-1.5"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5 text-[color:var(--ink)]" />
          </button>

          {/* wordmark */}
          <Link href="/" className="flex items-center gap-2 group shrink-0" aria-label="RaceIQ home">
            <span
              className="inline-block w-1.5 h-6"
              style={{ background: "var(--accent-f1-red)", boxShadow: "var(--glow-live)" }}
              aria-hidden
            />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`${BASE_PATH}/brand/raceiq-f1-mark.svg`}
              alt="RaceIQ F1"
              className="h-7 w-auto"
              style={{ filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.4))" }}
            />
            <span className="wordmark">RaceIQ</span>
          </Link>

          {/* primary nav cluster (desktop) */}
          <div className="hidden md:flex items-center gap-0 ml-4">
            {navLink("/", "Home")}

            {/* Races dropdown */}
            <div
              ref={racesRef}
              className="relative"
              onMouseEnter={() => openMenu(racesCloseTimerRef, setRacesOpen)}
              onMouseLeave={() => scheduleClose(racesCloseTimerRef, setRacesOpen)}
            >
              <button
                onClick={() => setRacesOpen((open) => !open)}
                onFocus={() => openMenu(racesCloseTimerRef, setRacesOpen)}
                aria-haspopup="menu"
                aria-expanded={racesOpen}
                className={`${navLinkBase} ${
                  isActive("/race") || isActive("/calendar")
                    ? "text-[color:var(--ink)]"
                    : "text-[color:var(--muted)] hover:text-[color:var(--ink)]"
                }`}
              >
                Races
                <ChevronDown
                  className={`w-3 h-3 transition-transform ${racesOpen ? "rotate-180" : ""}`}
                />
              </button>
              <AnimatePresence>
                {racesOpen && season && (
                  <motion.div
                    role="menu"
                    data-lenis-prevent
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.14, ease: [0.16, 1, 0.3, 1] }}
                    className="dropdown-menu absolute top-full left-0 mt-1 w-80 max-h-[70vh] overflow-y-auto overscroll-contain"
                    style={{ scrollbarGutter: "stable" }}
                  >
                    <div className="p-2">
                      <Link
                        href={withSeason("/calendar")}
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
                            href={withSeason(`/race/${race.round}`)}
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
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Standings dropdown */}
            <div
              ref={standingsRef}
              className="relative"
              onMouseEnter={openStandings}
              onMouseLeave={() => scheduleClose(standingsCloseTimerRef, setStandingsOpen)}
            >
              <button
                onClick={toggleStandings}
                onFocus={openStandings}
                aria-haspopup="menu"
                aria-expanded={standingsOpen}
                className={`${navLinkBase} ${
                  isActive("/standings")
                    ? "text-[color:var(--ink)]"
                    : "text-[color:var(--muted)] hover:text-[color:var(--ink)]"
                }`}
              >
                Standings
                <ChevronDown
                  className={`w-3 h-3 transition-transform ${standingsOpen ? "rotate-180" : ""}`}
                />
              </button>
              <AnimatePresence>
                {standingsOpen && (
                  <motion.div
                    role="menu"
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.14, ease: [0.16, 1, 0.3, 1] }}
                    className={`dropdown-menu absolute top-full mt-1 p-3 w-[min(440px,calc(100vw-1.5rem))] ${
                      standingsAnchor === "right" ? "right-0" : "left-0"
                    }`}
                  >
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { href: withSeason("/standings?tab=drivers"), label: "Drivers", hint: "Per-driver totals" },
                        { href: withSeason("/standings?tab=constructors"), label: "Constructors", hint: "Team-by-team" },
                        { href: withSeason("/standings?tab=wdc"), label: "Who Can Still Win", hint: "Mathematical title race" },
                      ].map((item) => (
                        <Link
                          key={item.href}
                          href={item.href}
                          onClick={() => setStandingsOpen(false)}
                          role="menuitem"
                          className="block p-3 transition-colors hover:bg-[color:var(--surface-elevated)] border border-transparent hover:border-[color:var(--hairline)]"
                        >
                          <p className="title-sm text-[color:var(--ink)]">{item.label}</p>
                          <p className="caption-uppercase mt-1 text-[10px] tracking-[0.14em]">
                            {item.hint}
                          </p>
                        </Link>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {navLink("/accuracy", "Accuracy")}
            {navLink("/about", "About")}
          </div>

          <div className="flex-1" />

          {/* CTA */}
          {nextRound && (
            <Link
              href={withSeason(`/race/${nextRound.round}`)}
              className="hidden sm:block"
              aria-label={`Next race: ${nextRound.name}`}
            >
              <ShimmerButton
                background="var(--accent-f1-red)"
                shimmerColor="rgba(255,255,255,0.9)"
                borderRadius="9999px"
                className="button-label h-9 !py-0 !px-4 text-[12px]"
              >
                Next Race →
              </ShimmerButton>
            </Link>
          )}
        </div>
      </div>

      {/* ── Mobile drawer ─────────────────────────────────────────── */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/60"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
              aria-hidden
            />
            <motion.aside
              className="fixed top-0 right-0 bottom-0 z-50 w-[320px] max-w-[88vw] bg-[color:var(--canvas)] border-l border-[color:var(--hairline)] overflow-y-auto"
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
              role="dialog"
              aria-label="Mobile navigation"
            >
              <div className="flex items-center justify-between px-5 py-4 border-b border-[color:var(--hairline)]">
                <span className="wordmark">Menu</span>
                <button
                  onClick={() => setMobileOpen(false)}
                  aria-label="Close menu"
                  className="inline-flex items-center justify-center w-9 h-9"
                >
                  <X className="w-5 h-5 text-[color:var(--ink)]" />
                </button>
              </div>

              <nav className="flex flex-col gap-0 py-2">
                {[
                  { href: "/", label: "Home" },
                  { href: withSeason("/calendar"), label: "Season Calendar" },
                  { href: withSeason("/standings"), label: "Standings" },
                  { href: "/accuracy", label: "Accuracy" },
                  { href: "/about", label: "About" },
                ].map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={isActive(item.href) ? "page" : undefined}
                    onClick={() => setMobileOpen(false)}
                    className={`nav-link-text px-5 py-4 row-spec transition-colors ${
                      isActive(item.href)
                        ? "text-[color:var(--ink)]"
                        : "text-[color:var(--muted)]"
                    }`}
                  >
                    {item.label}
                  </Link>
                ))}

                {nextRound && (
                  <div className="px-5 pt-4">
                    <Link href={withSeason(`/race/${nextRound.round}`)} onClick={() => setMobileOpen(false)}>
                      <ShimmerButton
                        background="var(--accent-f1-red)"
                        shimmerColor="rgba(255,255,255,0.9)"
                        borderRadius="9999px"
                        className="w-full button-label h-10 !py-0 !px-4 text-[12px]"
                      >
                        Next Race → {nextRound.name}
                      </ShimmerButton>
                    </Link>
                  </div>
                )}

                {season && season.completedRounds.length > 0 && (
                  <div className="pt-4">
                    <p className="eyebrow px-5 pt-4 pb-2">Race Status</p>
                    {season.calendar
                      .filter((r) => season.completedRounds.includes(r.round) || actualSet.has(r.round))
                      .map((race) => (
                        <Link
                          key={race.round}
                          href={withSeason(`/race/${race.round}`)}
                          onClick={() => setMobileOpen(false)}
                          className="px-5 py-3 row-spec text-sm flex items-center gap-2 justify-between font-serif transition-colors hover:text-[color:var(--ink)]"
                          style={{ color: "var(--body)" }}
                        >
                          <span className="flex items-center gap-2">
                            <CountryFlag country={race.country} size={18} />
                            {race.name}
                          </span>
                          <Badge
                            variant={
                              TONE_TO_BADGE_VARIANT[
                                getRoundStatusMeta(
                                  getRoundLifecycle(
                                    race,
                                    season.completedRounds.includes(race.round),
                                    actualSet.has(race.round),
                                  ),
                                ).tone as StatusTone
                              ] ?? "default"
                            }
                          >
                            {
                              getRoundStatusMeta(
                                getRoundLifecycle(
                                  race,
                                  season.completedRounds.includes(race.round),
                                  actualSet.has(race.round),
                                ),
                              ).shortLabel
                            }
                          </Badge>
                        </Link>
                      ))}
                  </div>
                )}
              </nav>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </nav>
  );
}
