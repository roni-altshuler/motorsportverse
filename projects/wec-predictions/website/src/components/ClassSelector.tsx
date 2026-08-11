"use client";

import { readableInk } from "@/lib/classes";
import type { ClassMeta } from "@/types/wec";

/**
 * ClassSelector — WEC's signature control. Endurance racing runs several classes
 * on track at once, each its own championship; every keyed-by-class surface
 * (standings, predictions, round detail) is filtered through this segmented
 * pill row. The active pill fills with the class's own colour (near-black ink
 * for the light class tints); inactive pills wear a faint tint of the same hue,
 * so the palette itself teaches the class colours.
 */
export default function ClassSelector({
  classes,
  value,
  onChange,
  size = "md",
  className = "",
  idPrefix = "class",
}: {
  classes: ClassMeta[];
  value: string;
  onChange: (key: string) => void;
  size?: "sm" | "md";
  className?: string;
  idPrefix?: string;
}) {
  const pad = size === "sm" ? "px-3 py-1.5 text-[11px]" : "px-4 py-2 text-[12px]";

  return (
    <div
      role="tablist"
      aria-label="Class"
      className={`inline-flex flex-wrap items-center gap-1.5 ${className}`}
    >
      {classes.map((c) => {
        const active = c.key === value;
        const style = active
          ? {
              background: c.color,
              borderColor: c.color,
              color: readableInk(c.color),
            }
          : {
              background: `color-mix(in oklab, ${c.color} 10%, transparent)`,
              borderColor: `color-mix(in oklab, ${c.color} 45%, transparent)`,
              color: c.color,
            };
        return (
          <button
            key={c.key}
            role="tab"
            id={`${idPrefix}-tab-${c.key}`}
            aria-selected={active}
            aria-controls={`${idPrefix}-panel-${c.key}`}
            onClick={() => onChange(c.key)}
            className={`inline-flex items-center gap-2 rounded-full border font-mono uppercase tracking-[0.16em] transition-colors ${pad}`}
            style={style}
          >
            <span
              aria-hidden
              className="inline-block rounded-full"
              style={{
                width: 8,
                height: 8,
                background: active ? readableInk(c.color) : c.color,
                opacity: active ? 0.8 : 1,
              }}
            />
            {c.label}
          </button>
        );
      })}
    </div>
  );
}
