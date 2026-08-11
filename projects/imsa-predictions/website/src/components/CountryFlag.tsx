"use client";

import Image from "next/image";

/**
 * CountryFlag — renders a flag image from flagcdn.com instead of emoji
 * (emoji flags render as two-letter abbreviations on Windows). Ported from
 * RaceIQ F1, extended with the country-name strings the IMSA export emits (the
 * IMSA calendar hosts).
 */
const COUNTRY_CODES: Record<string, string> = {
  // IMSA calendar hosts (2026 + common rounds) — a North-American series.
  "United States": "us",
  USA: "us",
  Canada: "ca",
  Mexico: "mx",
  // Retained for archived / cross-series rounds.
  Italy: "it",
  Belgium: "be",
  France: "fr",
  Brazil: "br",
  Japan: "jp",
  "United Kingdom": "gb",
  "Great Britain": "gb",
  Portugal: "pt",
  Spain: "es",
  Germany: "de",
};

interface CountryFlagProps {
  country: string | null | undefined;
  size?: number;
  className?: string;
}

export default function CountryFlag({ country, size = 24, className = "" }: CountryFlagProps) {
  const code = country ? COUNTRY_CODES[country] : undefined;

  if (!code) {
    return (
      <span
        className={className}
        style={{ fontSize: size * 0.8, lineHeight: 1 }}
        role="img"
        aria-label={`${country ?? "Race"} flag`}
      >
        🏁
      </span>
    );
  }

  return (
    <Image
      src={`https://flagcdn.com/w80/${code}.png`}
      width={size}
      height={Math.round(size * 0.75)}
      alt={`${country} flag`}
      className={`inline-block object-cover rounded-sm ${className}`}
      style={{ width: size, height: Math.round(size * 0.75) }}
      loading="lazy"
      unoptimized
    />
  );
}

export { COUNTRY_CODES };
