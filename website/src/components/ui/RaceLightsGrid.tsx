"use client";

import { useEffect, useMemo, useState } from "react";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { cn } from "./cn";

interface RaceLightsGridProps {
  /** Panels (1-5). Each panel shows 4 red bulbs. */
  panels?: number;
  /** Bulbs per panel. */
  bulbsPerPanel?: number;
  /** Ms between each panel lighting up. */
  stepMs?: number;
  /** Ms the lights stay on before "all off" fires. */
  holdMs?: number;
  /** Fire when "all off" transition completes. */
  onSequenceComplete?: () => void;
  autoPlay?: boolean;
  /** sessionStorage key to skip after first play. Set to null to always play. */
  skipKey?: string | null;
  className?: string;
}

type Phase = "idle" | "lighting" | "hold" | "out" | "done";

export function RaceLightsGrid({
  panels = 5,
  bulbsPerPanel = 4,
  stepMs = 700,
  holdMs = 900,
  onSequenceComplete,
  autoPlay = true,
  skipKey = "lights-out-played",
  className,
}: RaceLightsGridProps) {
  const reduced = useReducedMotion();
  const [litCount, setLitCount] = useState(0);
  const [phase, setPhase] = useState<Phase>("idle");

  const alreadyPlayed = useMemo(() => {
    if (!skipKey || typeof window === "undefined") return false;
    return window.sessionStorage.getItem(skipKey) === "1";
  }, [skipKey]);

  useEffect(() => {
    if (!autoPlay) return;

    if (reduced || alreadyPlayed) {
      setLitCount(0);
      setPhase("done");
      onSequenceComplete?.();
      return;
    }

    setPhase("lighting");
    const timers: ReturnType<typeof setTimeout>[] = [];
    for (let i = 1; i <= panels; i++) {
      timers.push(
        setTimeout(() => {
          setLitCount(i);
          if (i === panels) setPhase("hold");
        }, stepMs * i),
      );
    }
    timers.push(
      setTimeout(() => {
        setLitCount(0);
        setPhase("out");
      }, stepMs * panels + holdMs),
    );
    timers.push(
      setTimeout(() => {
        setPhase("done");
        if (skipKey && typeof window !== "undefined") {
          window.sessionStorage.setItem(skipKey, "1");
        }
        onSequenceComplete?.();
      }, stepMs * panels + holdMs + 250),
    );
    return () => timers.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      role="img"
      aria-label="Race start lights"
      aria-live="polite"
      className={cn("lights-out-grid", className)}
      data-phase={phase}
    >
      {Array.from({ length: panels }).map((_, panelIdx) => {
        const lit = panelIdx < litCount;
        return (
          <div key={panelIdx} className="lights-out-panel">
            {Array.from({ length: bulbsPerPanel }).map((_, bulbIdx) => (
              <span
                key={bulbIdx}
                className={cn("lights-out-bulb", lit && "on")}
                aria-hidden
              />
            ))}
          </div>
        );
      })}
    </div>
  );
}

export default RaceLightsGrid;
