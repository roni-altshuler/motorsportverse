/**
 * Skeleton — a placeholder that reserves the REAL layout's box.
 *
 * A skeleton of the wrong shape is a layout shift with extra steps. Give it the
 * dimensions the loaded content will have, not a generic grey rectangle.
 *
 * The shimmer is a plain opacity pulse rather than a travelling gradient,
 * because gradients are out on the series sites (DESIGN.md §9) and because the
 * global `prefers-reduced-motion` block flattens it to a static tint without
 * needing a per-component branch.
 */
import * as React from "react";
import { cn } from "./cn";

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-testid="skeleton"
      aria-hidden="true"
      className={cn(
        "animate-pulse bg-[color:var(--surface-elevated)]",
        className,
      )}
      {...props}
    />
  );
}

/** A skeleton table: `rows` × `columns`, matching a standings board's box. */
export function SkeletonTable({
  rows = 8,
  columns = 4,
  className,
}: {
  rows?: number;
  columns?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2", className)} data-testid="skeleton-table">
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex gap-3">
          {Array.from({ length: columns }).map((_, columnIndex) => (
            <Skeleton
              key={columnIndex}
              className={cn(
                "h-4",
                // The first column is the name column on every board here, so
                // the skeleton is wider there — a uniform grid reflows on load.
                columnIndex === 0 ? "flex-[2]" : "flex-1",
              )}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
