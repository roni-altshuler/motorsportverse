"use client";
import type { Transition } from "framer-motion";
import { cn } from "@/components/ui/cn";
interface BorderBeamProps {
  size?: number;
  duration?: number;
  delay?: number;
  colorFrom?: string;
  colorTo?: string;
  className?: string;
  reverse?: boolean;
  initialOffset?: number;
  borderRadius?: number;
  transition?: Transition;
}
/** Static accent outline. Motion props are accepted for existing callers. */
export function BorderBeam({
  className,
  size = 1,
  colorFrom = "#E10600",
  borderRadius = 0,
}: BorderBeamProps) {
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0", className)}
      style={{ borderRadius, borderWidth: size, borderStyle: "solid", borderColor: colorFrom }}
    />
  );
}
