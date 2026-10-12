"use client";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/components/ui/cn";
interface MarqueeProps extends ComponentPropsWithoutRef<"div"> {
  pauseOnHover?: boolean;
  vertical?: boolean;
  repeat?: number;
  reverse?: boolean;
}
/** Single-copy list. Readers scroll the items; there is no automatic loop. */
export function Marquee({ className, children, vertical = false, ...props }: MarqueeProps) {
  delete props.pauseOnHover;
  delete props.repeat;
  delete props.reverse;
  return (
    <div
      {...props}
      tabIndex={props.tabIndex ?? 0}
      role={props.role ?? "region"}
      aria-label={props["aria-label"] ?? "Browse items"}
      className={cn(
        "flex overflow-auto p-2 [--gap:1rem] [gap:var(--gap)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ink)]",
        vertical ? "flex-col" : "flex-row",
        className,
      )}
    >
      <div className={cn("flex shrink-0 [gap:var(--gap)]", vertical ? "flex-col" : "flex-row")}>
        {children}
      </div>
    </div>
  );
}
