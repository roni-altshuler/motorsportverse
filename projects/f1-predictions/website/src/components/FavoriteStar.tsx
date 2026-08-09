"use client";

/**
 * FavoriteStar — a subtle star toggle that stars/un-stars a driver.
 *
 * Client-only: the favourite state lives in `localStorage` via `@/lib/favorites`
 * and is read through `useIsFavorite` (a `useSyncExternalStore` binding with a
 * stable server snapshot), so it is safe under the static export and never
 * mismatches on hydration. Starred = filled champagne star; otherwise a faint
 * outline that warms up on hover.
 *
 * It stops click propagation + prevents default so it can sit safely inside a
 * clickable row or an anchor without triggering navigation.
 */

import { toggleFavorite, useIsFavorite } from "@/lib/favorites";

interface FavoriteStarProps {
  /** Driver 3-letter code (e.g. "VER"). */
  code: string;
  /** Human name for the accessible label; falls back to the code. */
  driverName?: string;
  /** Star size in pixels. */
  size?: number;
  className?: string;
}

export default function FavoriteStar({
  code,
  driverName,
  size = 16,
  className = "",
}: FavoriteStarProps) {
  const favorite = useIsFavorite(code);
  const who = driverName ?? code;
  const label = favorite
    ? `Remove ${who} from your favourites`
    : `Add ${who} to your favourites`;

  return (
    <button
      type="button"
      aria-pressed={favorite}
      aria-label={label}
      title={label}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleFavorite(code);
      }}
      className={
        "inline-flex items-center justify-center align-middle shrink-0 " +
        "rounded-full p-1 transition-colors focus:outline-none " +
        "focus-visible:ring-1 focus-visible:ring-[color:var(--accent-podium-1)] " +
        (favorite
          ? "text-[color:var(--accent-podium-1)]"
          : "text-[color:var(--muted)] hover:text-[color:var(--accent-podium-1)]") +
        (className ? ` ${className}` : "")
      }
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill={favorite ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth={favorite ? 1.5 : 1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        focusable="false"
      >
        <polygon points="12 2.5 15.09 8.76 22 9.77 17 14.64 18.18 21.52 12 18.27 5.82 21.52 7 14.64 2 9.77 8.91 8.76 12 2.5" />
      </svg>
    </button>
  );
}
