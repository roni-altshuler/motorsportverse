"use client";

import * as React from "react";
import { cn } from "./cn";

interface HUDPanelProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  title?: React.ReactNode;
  kicker?: React.ReactNode;
  rightSlot?: React.ReactNode;
  scanlines?: boolean;
  cornerNotch?: boolean;
  intensity?: "subtle" | "strong";
  bodyClassName?: string;
}

/**
 * Telemetry-style frame around a section.  Optional scanline overlay,
 * optional corner-notch clip-path, optional kicker + title bar.
 * Intentionally a presentational wrapper — pages decide what goes
 * inside.
 */
export function HUDPanel({
  title,
  kicker,
  rightSlot,
  scanlines = false,
  cornerNotch = false,
  intensity = "subtle",
  className,
  bodyClassName,
  children,
  ...rest
}: HUDPanelProps) {
  return (
    <div
      {...rest}
      className={cn(
        "hud-frame",
        intensity === "strong" && "hud-frame-strong",
        cornerNotch && "hud-corner-notch",
        scanlines && "scanline-overlay",
        className,
      )}
    >
      {(title || kicker || rightSlot) && (
        <header className="flex flex-wrap items-start justify-between gap-3 px-5 sm:px-6 pt-5 pb-3 border-b border-[color:var(--border)]">
          <div className="min-w-0">
            {kicker && <p className="hud-kicker mb-1">{kicker}</p>}
            {title && (
              <h3 className="text-lg sm:text-xl font-black tracking-tight text-[color:var(--text-primary)]">
                {title}
              </h3>
            )}
          </div>
          {rightSlot && <div className="flex-shrink-0">{rightSlot}</div>}
        </header>
      )}
      <div className={cn("p-5 sm:p-6", bodyClassName)}>{children}</div>
    </div>
  );
}

export default HUDPanel;
