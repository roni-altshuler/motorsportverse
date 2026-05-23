"use client";

import Image from "next/image";

/**
 * CountryFlag — renders a flag image from flagcdn.com instead of emoji
 * (emoji flags render as two-letter abbreviations on Windows).
 *
 * Usage:
 *   <CountryFlag country="Australia" size={24} />
 *   <CountryFlag country="Monaco" size={32} className="rounded" />
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

interface CountryFlagProps {
  /** GP key or country name (e.g. "Australia", "Great Britain", "Miami") */
  country: string;
  /** Image width in pixels (height auto-scales to aspect ratio) */
  size?: number;
  /** Additional CSS classes */
  className?: string;
}

export default function CountryFlag({
  country,
  size = 24,
  className = "",
}: CountryFlagProps) {
  const code = COUNTRY_CODES[country];

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
