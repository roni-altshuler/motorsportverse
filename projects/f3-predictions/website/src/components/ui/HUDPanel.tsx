"use client";

import * as React from "react";
import { cn } from "./cn";

interface HUDPanelProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  title?: React.ReactNode;
  kicker?: React.ReactNode;
  rightSlot?: React.ReactNode;
  /** No-op in Bugatti redesign; kept for prop compatibility. */
  scanlines?: boolean;
  /** No-op in Bugatti redesign; kept for prop compatibility. */
  cornerNotch?: boolean;
  /** No-op in Bugatti redesign; kept for prop compatibility. */
  intensity?: "subtle" | "strong";
  bodyClassName?: string;
}

/**
 * Bugatti redesign: gutted HUD wrapper. The decorative scanlines, corner
 * notch and HUD-frame box-shadow are gone. The component now renders a flat
 * surface-card panel with a hairline header divider. Props are accepted but
 * ignored so call sites keep compiling.
 */
export function HUDPanel({
  title,
  kicker,
  rightSlot,
  className,
  bodyClassName,
  children,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  scanlines,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  cornerNotch,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  intensity,
  ...rest
}: HUDPanelProps) {
  return (
    <div
      {...rest}
      className={cn(
        "border border-[color:var(--hairline)] bg-[color:var(--surface-card)] rounded-none",
        className,
      )}
    >
      {(title || kicker || rightSlot) && (
        <header className="flex flex-wrap items-start justify-between gap-3 px-5 sm:px-6 pt-5 pb-3 border-b border-[color:var(--hairline)]">
          <div className="min-w-0">
            {kicker && <p className="eyebrow mb-1">{kicker}</p>}
            {title && <h3 className="title-md">{title}</h3>}
          </div>
          {rightSlot && <div className="flex-shrink-0">{rightSlot}</div>}
        </header>
      )}
      <div className={cn("p-5 sm:p-6", bodyClassName)}>{children}</div>
    </div>
  );
}

export default HUDPanel;
