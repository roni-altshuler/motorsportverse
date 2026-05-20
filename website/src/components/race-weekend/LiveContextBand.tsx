"use client";

/**
 * Race-weekend live context band (B-P1.1).
 *
 * Sticky strip rendered just below the navbar on / and /race/[round]
 * during race-weekend windows.  Shows: countdown to next session, current
 * weather snapshot at the circuit, data-freshness indicator.
 *
 * Visibility rules (kept lenient so visitors see context even outside the
 * narrow Thu-Sun race window):
 *   - liveRound present → always render
 *   - nextRound within 14 days → render
 *   - otherwise → null
 */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import {
  fetchSeasonData,
  fetchSeasonTrackerData,
  fetchWeatherData,
  formatDateTime,
  getCurrentRaceContext,
} from "@/lib/data";
import type { RaceCalendarEntry, SeasonData, WeatherData } from "@/types";

const MS_PER_DAY = 24 * 60 * 60 * 1000;
const SHOW_BAND_WITHIN_DAYS = 14;

function formatCountdown(targetIso: string, now: Date): string {
  const target = new Date(targetIso).getTime();
  const ms = target - now.getTime();
  if (ms <= 0) return "Live · in progress";
  const days = Math.floor(ms / MS_PER_DAY);
  const hours = Math.floor((ms % MS_PER_DAY) / (60 * 60 * 1000));
  const mins = Math.floor((ms % (60 * 60 * 1000)) / (60 * 1000));
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

function weatherForRound(
  weather: WeatherData | null,
  gpKey: string,
): { rainProbability: number; temperatureC: number; description: string; source: string } | null {
  if (!weather) return null;
  // weather.json has either a `forecasts` map keyed by gpKey, or a flat structure.
  const candidate =
    (weather as unknown as { forecasts?: Record<string, unknown> }).forecasts?.[gpKey];
  if (!candidate || typeof candidate !== "object") return null;
  const w = candidate as Record<string, unknown>;
  return {
    rainProbability: typeof w.rain_probability === "number" ? (w.rain_probability as number) : 0,
    temperatureC: typeof w.temperature_c === "number" ? (w.temperature_c as number) : 22,
    description:
      typeof w.weather_description === "string" ? (w.weather_description as string) : "—",
    source: typeof w.source === "string" ? (w.source as string) : "static",
  };
}

export default function LiveContextBand() {
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [tracker, setTracker] = useState<Awaited<ReturnType<typeof fetchSeasonTrackerData>>>(null);
  const [now, setNow] = useState<Date>(() => new Date());

  // Re-tick the countdown every 30s so it stays accurate while open.
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    fetchSeasonData().then(setSeason).catch(() => {});
    fetchWeatherData().then(setWeather).catch(() => {});
    fetchSeasonTrackerData().then(setTracker).catch(() => {});
  }, []);

  const featuredRace: RaceCalendarEntry | null = useMemo(() => {
    if (!season) return null;
    const actuals = (tracker?.rounds || [])
      .filter((r) => r.hasActual)
      .map((r) => r.round);
    const ctx = getCurrentRaceContext(season, actuals, now);
    return ctx.liveRound ?? ctx.nextRound;
  }, [season, tracker, now]);

  if (!season || !featuredRace) return null;
  const raceDate = new Date(featuredRace.date);
  const daysUntil = Math.ceil((raceDate.getTime() - now.getTime()) / MS_PER_DAY);
  if (daysUntil > SHOW_BAND_WITHIN_DAYS && daysUntil >= 0) return null;

  const isLive = daysUntil <= 0;
  const weatherSnap = weatherForRound(weather, featuredRace.gpKey);
  const lastUpdated = tracker?.generatedAt ?? null;

  return (
    <div
      className="sticky top-[64px] z-40 border-b backdrop-blur-xl"
      style={{
        background: "color-mix(in srgb, var(--surface) 78%, transparent)",
        borderColor: "var(--border)",
      }}
      aria-label="Race-weekend live context"
    >
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-2 text-sm sm:px-6 lg:px-8">
        <Link
          href={`/race/${featuredRace.round}`}
          className="group inline-flex items-center gap-2 font-semibold text-[color:var(--text-primary)] hover:text-[color:var(--accent-live)]"
        >
          <CountryFlag country={featuredRace.country} size={20} />
          <span className="hidden sm:inline">
            R{featuredRace.round} · {featuredRace.name}
          </span>
          <span className="sm:hidden">R{featuredRace.round}</span>
        </Link>

        <Badge variant={isLive ? "live" : "info"} className="font-mono font-tabular text-[10px]">
          {isLive ? "LIVE" : formatCountdown(featuredRace.date, now)}
        </Badge>

        {weatherSnap && (
          <div className="flex items-center gap-2 text-[color:var(--text-secondary)]">
            <span aria-hidden>🌡️</span>
            <span className="font-mono font-tabular">
              {weatherSnap.temperatureC.toFixed(0)}°C
            </span>
            <span aria-hidden>💧</span>
            <span className="font-mono font-tabular">
              {(weatherSnap.rainProbability * 100).toFixed(0)}%
            </span>
            <span className="hidden text-[color:var(--text-muted)] md:inline">
              · {weatherSnap.description}
            </span>
          </div>
        )}

        <div className="ml-auto flex items-center gap-2 text-[color:var(--text-muted)]">
          <span
            className="inline-block h-1.5 w-1.5 rounded-full bg-[color:var(--accent-positive)]"
            aria-hidden
          />
          <span className="hidden sm:inline">
            {lastUpdated ? `Updated ${formatDateTime(lastUpdated)}` : "Live data"}
          </span>
          <span className="sm:hidden">Live</span>
        </div>
      </div>
    </div>
  );
}
