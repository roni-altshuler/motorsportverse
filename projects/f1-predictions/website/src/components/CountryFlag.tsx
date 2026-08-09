"use client";

import Image from "next/image";

/**
 * CountryFlag — renders a flag image from flagcdn.com instead of emoji
 * (emoji flags render as two-letter abbreviations on Windows).
 *
 * Usage:
 *   <CountryFlag country="Australia" size={24} />
 *   <CountryFlag country="Monaco" size={32} className="rounded" />
 *   <CountryFlag countryCode="GB" country="British" size={20} />   // driver nationality
 *
 * `countryCode` (ISO 3166-1, alpha-2 or alpha-3) takes precedence over the
 * `country` name lookup when supplied — handy for driver-nationality data where
 * the label is an adjective ("British") that wouldn't match the name map.
 * flagcdn only serves alpha-2, so alpha-3 inputs are mapped down defensively;
 * an unresolvable code renders nothing rather than a broken image.
 */

// Map GP keys / country names → ISO 3166-1 alpha-2 codes
const COUNTRY_CODES: Record<string, string> = {
  Australia: "au",
  China: "cn",
  Japan: "jp",
  Bahrain: "bh",
  "Saudi Arabia": "sa",
  Miami: "us",
  "Emilia Romagna": "it",
  Monaco: "mc",
  Spain: "es",
  Madrid: "es",
  Canada: "ca",
  Austria: "at",
  "Great Britain": "gb",
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
};

// ISO 3166-1 alpha-3 → alpha-2, covering the nationalities that turn up on an
// F1 grid (flagcdn only serves alpha-2). Extend as new nationalities appear.
const ALPHA3_TO_ALPHA2: Record<string, string> = {
  ARG: "ar",
  AUS: "au",
  AUT: "at",
  BEL: "be",
  BRA: "br",
  CAN: "ca",
  CHE: "ch",
  CHN: "cn",
  DEU: "de",
  DNK: "dk",
  ESP: "es",
  FIN: "fi",
  FRA: "fr",
  GBR: "gb",
  ITA: "it",
  JPN: "jp",
  MCO: "mc",
  MEX: "mx",
  NLD: "nl",
  NZL: "nz",
  POL: "pl",
  RUS: "ru",
  SWE: "se",
  THA: "th",
  USA: "us",
};

/** Normalise an ISO code (alpha-2 or alpha-3) to a flagcdn alpha-2 code. */
function resolveCountryCode(raw: string): string | null {
  const trimmed = raw.trim();
  if (trimmed.length === 2) return trimmed.toLowerCase();
  if (trimmed.length === 3) return ALPHA3_TO_ALPHA2[trimmed.toUpperCase()] ?? null;
  return null;
}

interface CountryFlagProps {
  /** GP key or country name / nationality (e.g. "Australia", "British") */
  country: string;
  /** ISO 3166-1 code (alpha-2 or alpha-3). Overrides the `country` name lookup. */
  countryCode?: string | null;
  /** Image width in pixels (height auto-scales to aspect ratio) */
  size?: number;
  /** Additional CSS classes */
  className?: string;
}

export default function CountryFlag({
  country,
  countryCode,
  size = 24,
  className = "",
}: CountryFlagProps) {
  const code = countryCode
    ? resolveCountryCode(countryCode) ?? COUNTRY_CODES[country]
    : COUNTRY_CODES[country];

  if (!code) {
    // Fallback: checkered flag emoji for unknown countries
    return (
      <span
        className={className}
        style={{ fontSize: size * 0.8, lineHeight: 1 }}
        role="img"
        aria-label={`${country} flag`}
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
