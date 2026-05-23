"use client";

import { motion } from "framer-motion";
import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import HUDPanel from "@/components/ui/HUDPanel";
import AnimatedNumber from "@/components/ui/AnimatedNumber";
import { useReducedMotion } from "@/lib/useReducedMotion";

interface HUDHeaderProps {
  round: number;
  name: string;
  country: string;
  circuit: string;
  date: string;
  sprint?: boolean;
  liveLabel?: string;
  liveBadgeVariant?: "default" | "live" | "positive" | "negative" | "muted" | "info" | "outline";
  weather?: {
    temperatureC?: number;
    rainProbability?: number;
    humidity?: number | null;
    windSpeedKmh?: number | null;
    weatherDescription?: string | null;
  };
}

function pickWeatherGlyph(rain: number | undefined, desc: string | null | undefined): string {
  const r = rain ?? 0;
  const d = (desc || "").toLowerCase();
  if (r > 70 || d.includes("thunder")) return "⛈";
  if (r > 35 || d.includes("rain")) return "🌧";
  if (d.includes("cloud")) return "⛅";
  if (d.includes("clear") || d.includes("sun")) return "☀";
  return "🌤";
}

export default function HUDHeader({
  round,
  name,
  country,
  circuit,
  date,
  sprint,
  liveLabel,
  liveBadgeVariant = "live",
  weather,
}: HUDHeaderProps) {
  const reduced = useReducedMotion();

  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="mb-6"
    >
      <HUDPanel
        kicker={`Round ${round}`}
        title={
          <span className="flex items-center gap-3">
            <CountryFlag country={country} size={36} />
            <span>{name}</span>
          </span>
        }
        rightSlot={
          <div className="flex flex-wrap items-center gap-2 justify-end">
            {sprint && <Badge variant="info">Sprint Weekend</Badge>}
            {liveLabel && <Badge variant={liveBadgeVariant}>{liveLabel}</Badge>}
          </div>
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-4 gap-0 -mx-5 sm:-mx-6 px-5 sm:px-6">
          <div className="row-spec md:border-b-0 md:pr-6">
            <p className="eyebrow mb-2">Circuit</p>
            <p className="title-md">{circuit}</p>
            <p className="body-sm text-[color:var(--muted)] mt-2 font-mono">{date}</p>
          </div>
          {weather && (
            <>
              <div className="row-spec md:border-b-0 md:px-6">
                <p className="eyebrow mb-2">Temp</p>
                <div className="flex items-baseline gap-2">
                  {weather.temperatureC != null ? (
                    <>
                      <AnimatedNumber value={weather.temperatureC} decimals={0} variant="default" />
                      <span className="body-sm text-[color:var(--muted)]">°C</span>
                    </>
                  ) : (
                    <span className="title-md text-[color:var(--muted)]">—</span>
                  )}
                </div>
              </div>
              <div className="row-spec md:border-b-0 md:px-6">
                <p className="eyebrow mb-2">Rain</p>
                <div className="flex items-baseline gap-2">
                  {weather.rainProbability != null ? (
                    <>
                      <AnimatedNumber value={weather.rainProbability} decimals={0} variant="default" />
                      <span className="body-sm text-[color:var(--muted)]">%</span>
                    </>
                  ) : (
                    <span className="title-md text-[color:var(--muted)]">—</span>
                  )}
                </div>
              </div>
              <div className="row-spec md:border-b-0 md:pl-6 flex flex-col">
                <p className="eyebrow mb-2">Sky</p>
                <span className="text-2xl" aria-hidden>
                  {pickWeatherGlyph(weather.rainProbability, weather.weatherDescription)}
                </span>
                {weather.weatherDescription && (
                  <span className="eyebrow truncate">{weather.weatherDescription}</span>
                )}
              </div>
            </>
          )}
        </div>
      </HUDPanel>
    </motion.div>
  );
}
