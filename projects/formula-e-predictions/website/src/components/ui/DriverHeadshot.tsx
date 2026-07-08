"use client";

import { useState } from "react";

// Driver portrait with a designed fallback: if /headshots/<CODE>.webp is missing
// (the common case until portraits are added) we render a team-coloured initials
// avatar instead of a broken image — the same graceful pattern RaceIQ F1 uses.
export function DriverHeadshot({
  code,
  teamColor,
  size = 40,
}: {
  code: string;
  teamColor: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  const base = process.env.NEXT_PUBLIC_BASE_PATH || "";

  if (failed) {
    return (
      <span
        aria-hidden
        className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
        style={{
          width: size,
          height: size,
          fontSize: size * 0.34,
          background: `conic-gradient(from 210deg, ${teamColor}, color-mix(in srgb, ${teamColor} 55%, #000))`,
        }}
      >
        {code.slice(0, 3)}
      </span>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`${base}/headshots/${code}.webp`}
      alt={code}
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
      className="shrink-0 rounded-full object-cover"
      style={{ width: size, height: size, border: `1.5px solid ${teamColor}` }}
    />
  );
}
