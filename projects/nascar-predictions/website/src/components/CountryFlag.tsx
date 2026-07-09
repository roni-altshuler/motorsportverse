"use client";

import Image from "next/image";

/**
 * CountryFlag — renders a flag image from flagcdn.com instead of emoji
 * (emoji flags render as two-letter abbreviations on Windows). Ported from
 * RaceIQ F1, extended with the country-name strings the NASCAR export emits
 * (e.g. "United Kingdom", "UAE").
 */
const COUNTRY_CODES: Record<string, string> = {
  Australia: "au",
  China: "cn",
  Japan: "jp",
  Bahrain: "bh",
  "Saudi Arabia": "sa",
  Miami: "us",
  "Emilia Romagna": "it",
  "Emilia-Romagna": "it",
  Monaco: "mc",
  Spain: "es",
  Madrid: "es",
  Canada: "ca",
  Austria: "at",
  "Great Britain": "gb",
  "United Kingdom": "gb",
  Belgium: "be",
  Hungary: "hu",
  Netherlands: "nl",
  Italy: "it",
  Azerbaijan: "az",
  Singapore: "sg",
  "United States": "us",
  Mexico: "mx",
  Brazil: "br",
  "Las Vegas": "us",
  Qatar: "qa",
  "Abu Dhabi": "ae",
  UAE: "ae",
  "United Arab Emirates": "ae",
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
