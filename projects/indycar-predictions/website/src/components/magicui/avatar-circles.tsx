"use client";

import type { CSSProperties } from "react";

import { cn } from "@/components/ui/cn";

interface Avatar {
  imageUrl?: string;
  /** 2-3 letter initials fallback when no image. */
  initials?: string;
  /** Team color tint for the ring. */
  teamColor?: string;
  /** Click target / link. */
  href?: string;
  /** Alt for img. */
  label?: string;
}

interface AvatarCirclesProps {
  numPeople?: number;
  className?: string;
  avatars: Avatar[];
  /** Per-avatar diameter in px. Default 40. */
  size?: number;
}

/**
 * Overlapping row of circular avatars with a "+N" trailing chip when
 * numPeople is provided and larger than the avatars shown.
 */
export function AvatarCircles({
  numPeople,
  className,
  avatars,
  size = 40,
}: AvatarCirclesProps) {
  return (
    <div className={cn("z-10 flex -space-x-3 rtl:space-x-reverse", className)}>
      {avatars.map((avatar, index) => {
        const ring = avatar.teamColor ?? "var(--hairline-strong)";
        const inner = avatar.imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={index}
            src={avatar.imageUrl}
            width={size}
            height={size}
            alt={avatar.label ?? `Avatar ${index + 1}`}
            className="rounded-full object-cover"
            style={{ width: size, height: size }}
            loading="lazy"
          />
        ) : (
          <span
            className="flex items-center justify-center rounded-full bg-[var(--surface-elevated)] font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--ink)]"
            style={{ width: size, height: size }}
          >
            {avatar.initials ?? "·"}
          </span>
        );
        const ringStyle: CSSProperties = {
          boxShadow: `0 0 0 2px ${ring}, 0 0 0 4px var(--canvas)`,
          borderRadius: "9999px",
        };
        const wrapper = (
          <span key={index} className="inline-block" style={ringStyle}>
            {inner}
          </span>
        );
        return avatar.href ? (
          <a key={index} href={avatar.href} style={{ display: "inline-block" }}>
            {wrapper}
          </a>
        ) : (
          wrapper
        );
      })}
      {typeof numPeople === "number" && numPeople > avatars.length ? (
        <span
          className="flex items-center justify-center rounded-full bg-[var(--canvas)] text-[10px] font-mono uppercase tracking-[0.12em] text-[var(--ink)] ring-2 ring-[var(--hairline-strong)]"
          style={{ width: size, height: size }}
        >
          +{numPeople - avatars.length}
        </span>
      ) : null}
    </div>
  );
}
