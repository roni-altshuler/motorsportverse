"use client";

import { motion } from "framer-motion";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { DURATIONS, EASE } from "@/lib/motion";
import { cn } from "./cn";

interface TeamColorBarProps {
  teamColor: string;
  team?: string;
  variant?: "solid" | "gradient" | "glow";
  orientation?: "vertical" | "horizontal";
  size?: "sm" | "md" | "lg";
  className?: string;
  animate?: "draw" | "pulse" | "none";
  style?: React.CSSProperties;
}

const SIZE: Record<NonNullable<TeamColorBarProps["size"]>, { short: string; long: string }> = {
  sm: { short: "w-1", long: "h-4" },
  md: { short: "w-1.5", long: "h-8" },
  lg: { short: "w-2.5", long: "h-12" },
};

export function TeamColorBar({
  teamColor,
  team,
  variant = "solid",
  orientation = "vertical",
  size = "md",
  className,
  animate = "none",
  style,
}: TeamColorBarProps) {
  const reduced = useReducedMotion();
  const sz = SIZE[size];
  const shortSide = orientation === "vertical" ? sz.short : sz.long.replace("h-", "w-");
  const longSide = orientation === "vertical" ? sz.long : sz.short.replace("w-", "h-");

  const background =
    variant === "gradient"
      ? `linear-gradient(${orientation === "vertical" ? "180deg" : "90deg"}, ${teamColor} 0%, ${teamColor}33 100%)`
      : teamColor;

  const boxShadow =
    variant === "glow"
      ? `0 0 12px ${teamColor}, 0 0 24px ${teamColor}66`
      : undefined;

  const initial =
    animate === "draw" && !reduced
      ? orientation === "vertical"
        ? { scaleY: 0 }
        : { scaleX: 0 }
      : false;
  const animateTo =
    animate === "draw" && !reduced
      ? { scaleY: 1, scaleX: 1 }
      : false;

  return (
    <motion.span
      aria-hidden
      data-team={team}
      className={cn(
        "inline-block rounded-full flex-shrink-0",
        shortSide,
        longSide,
        animate === "pulse" && !reduced && "animate-pulse",
        className,
      )}
      style={{
        background,
        boxShadow,
        transformOrigin: orientation === "vertical" ? "top center" : "left center",
        "--team-color": teamColor,
        ...style,
      } as React.CSSProperties}
      initial={initial}
      animate={animateTo}
      transition={{ duration: DURATIONS.base, ease: EASE.pit }}
    />
  );
}

export default TeamColorBar;
