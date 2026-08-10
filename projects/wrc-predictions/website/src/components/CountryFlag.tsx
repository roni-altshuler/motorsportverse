"use client";

import Image from "next/image";

/**
 * CountryFlag — renders a flag image from flagcdn.com instead of emoji
 * (emoji flags render as two-letter abbreviations on Windows). Ported from
 * RaceIQ F1, extended with the country-name strings the WRC export emits
 * (the 2026 rally calendar hosts).
 */
const COUNTRY_CODES: Record<string, string> = {
  // 2026 WRC calendar hosts.
  Monaco: "mc",
  Sweden: "se",
  Kenya: "ke",
  Croatia: "hr",
  Spain: "es",
  Portugal: "pt",
  Japan: "jp",
  Greece: "gr",
  Estonia: "ee",
  Finland: "fi",
  Paraguay: "py",
  Chile: "cl",
  Italy: "it",
  "Saudi Arabia": "sa",
  // A few extra common host names kept for resilience.
  France: "fr",
  Germany: "de",
  Belgium: "be",
  Poland: "pl",
  Latvia: "lv",
  "United Kingdom": "gb",
  "Great Britain": "gb",
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
