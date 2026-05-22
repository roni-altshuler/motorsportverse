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
        scanlines
        cornerNotch
        intensity="strong"
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
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <p className="hud-kicker mb-1">Circuit</p>
            <p className="text-lg font-bold">{circuit}</p>
            <p className="text-sm text-[color:var(--text-muted)] mt-1 font-mono">{date}</p>
          </div>
          {weather && (
            <>
              <div className="md:col-span-2 grid grid-cols-3 gap-3">
                <div className="hud-frame p-3">
                  <p className="hud-kicker mb-1">Temp</p>
                  <div className="flex items-baseline gap-2">
                    {weather.temperatureC != null ? (
                      <>
                        <AnimatedNumber value={weather.temperatureC} decimals={0} variant="default" />
                        <span className="text-sm text-[color:var(--text-muted)]">°C</span>
                      </>
                    ) : (
                      <span className="text-lg text-[color:var(--text-muted)]">—</span>
                    )}
                  </div>
                </div>
                <div className="hud-frame p-3">
                  <p className="hud-kicker mb-1">Rain</p>
                  <div className="flex items-baseline gap-2">
                    {weather.rainProbability != null ? (
                      <>
                        <AnimatedNumber value={weather.rainProbability} decimals={0} variant="default" />
                        <span className="text-sm text-[color:var(--text-muted)]">%</span>
                      </>
                    ) : (
                      <span className="text-lg text-[color:var(--text-muted)]">—</span>
                    )}
                  </div>
                </div>
                <div className="hud-frame p-3 flex flex-col">
                  <p className="hud-kicker mb-1">Sky</p>
                  <span className="text-2xl" aria-hidden>
                    {pickWeatherGlyph(weather.rainProbability, weather.weatherDescription)}
                  </span>
                  {weather.weatherDescription && (
                    <span className="text-[10px] text-[color:var(--text-muted)] truncate">
                      {weather.weatherDescription}
                    </span>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </HUDPanel>
    </motion.div>
  );
}
