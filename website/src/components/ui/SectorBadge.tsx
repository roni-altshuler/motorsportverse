import { cn } from "./cn";

type SectorColor = "green" | "yellow" | "purple" | "neutral";

interface SectorBadgeProps {
  sector?: 1 | 2 | 3;
  color: SectorColor;
  time?: string;
  ariaLabel?: string;
  className?: string;
}

const COLOR_CLASS: Record<SectorColor, string> = {
  green: "sector-green",
  yellow: "sector-yellow",
  purple: "sector-purple",
  neutral: "sector-neutral",
};

export function SectorBadge({ sector, color, time, ariaLabel, className }: SectorBadgeProps) {
  return (
    <span
      aria-label={ariaLabel ?? `Sector ${sector ?? ""} ${color}${time ? ` ${time}` : ""}`}
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full font-mono text-[11px] uppercase tabular-nums tracking-[0.18em]",
        COLOR_CLASS[color],
        className,
      )}
    >
      {sector !== undefined && <span className="opacity-70">S{sector}</span>}
      {time && <span>{time}</span>}
    </span>
  );
}

export default SectorBadge;
