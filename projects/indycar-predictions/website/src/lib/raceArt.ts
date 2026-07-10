/**
 * Race photography mapping — one curated aerial venue photo per IndyCar
 * venue, keyed by the calendar's venue `key` strings (as emitted by the
 * export: indianapolis-motor-speedway, barber-motorsports-park, ...).
 * The Speedway hosts two rounds (the road course and the 500); keying by
 * venue means both resolve the same facility aerial.
 *
 * Sourcing: Wikimedia Commons. Per project convention, race art MUST be
 * aerial venue photography (NOT SVG layout diagrams, NOT logos, NOT generic
 * landscapes). Venues with no verified aerial on Commons (the street rounds —
 * St. Petersburg, Arlington, Long Beach, Detroit, Markham, Washington — plus
 * Phoenix, Road America, Mid-Ohio, Nashville Superspeedway, Portland,
 * Milwaukee, Laguna Seca) are DELIBERATELY absent — the calendar falls back
 * to the styled gradient card rather than ever showing a wrong or non-aerial
 * image.
 *
 * Every URL below was verified for this map on 2026-07-10 (`curl -I` → HTTP
 * 200, image/jpeg), and the uncertain candidates were downloaded and visually
 * confirmed to be aerials. To swap an image, search Commons, `curl -I` the
 * candidate, and eyeball it before committing — guessed Wikimedia thumbnail
 * filenames almost always 404.
 *
 * Consumed via CSS background-image (NOT next/image), so the hostname does not
 * need to be in next.config.ts `remotePatterns`.
 */

interface RaceArt {
  src: string;
  credit: string;
}

const RACE_ART: Record<string, RaceArt> = {
  // R4 — Barber Motorsports Park · aerial photo (visually verified)
  "barber-motorsports-park": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Barber_Motorsports_Park_Aerial_%2834804699780%29.jpg/1280px-Barber_Motorsports_Park_Aerial_%2834804699780%29.jpg",
    credit: "Barber Motorsports Park aerial · Wikimedia Commons",
  },
  // R6 — IMS Road Course · the facility aerial shows the infield road course
  "indianapolis-motor-speedway-road-course": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/3/35/Indianapolis_Motor_Speedway_Aerial_August_2018.jpg/1280px-Indianapolis_Motor_Speedway_Aerial_August_2018.jpg",
    credit: "Indianapolis Motor Speedway aerial · Wikimedia Commons",
  },
  // R7 — Indianapolis Motor Speedway (the 500) · aerial photo
  "indianapolis-motor-speedway": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/3/35/Indianapolis_Motor_Speedway_Aerial_August_2018.jpg/1280px-Indianapolis_Motor_Speedway_Aerial_August_2018.jpg",
    credit: "Indianapolis Motor Speedway aerial · Wikimedia Commons",
  },
  // R9 — World Wide Technology Raceway (Gateway) · aerial photo
  "world-wide-technology-raceway": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cc/World_Wide_Technology_Raceway%2C_aerial_view%2C_June_2023_%28cropped%29.jpg/500px-World_Wide_Technology_Raceway%2C_aerial_view%2C_June_2023_%28cropped%29.jpg",
    credit: "World Wide Technology Raceway aerial · Wikimedia Commons",
  },
};

// A few name aliases, so resolution still works if a future export uses the
// round `name` or a slightly different key spelling.
const ALIASES: Record<string, string> = {
  barber: "barber-motorsports-park",
  indy: "indianapolis-motor-speedway",
  "indy-500": "indianapolis-motor-speedway",
  indianapolis: "indianapolis-motor-speedway",
  "ims-road-course": "indianapolis-motor-speedway-road-course",
  gateway: "world-wide-technology-raceway",
  "wwt-raceway": "world-wide-technology-raceway",
};

/**
 * Pick the curated aerial photo for a given round `key`. Returns null when no
 * curated photo exists (the calendar falls back to a styled placeholder rather
 * than a non-aerial image, per project convention).
 */
export function getRaceArt(key: string | null | undefined): {
  src: string;
  credit: string;
} | null {
  if (!key) return null;
  const normalised = key.toLowerCase().replace(/\s+/g, "-");
  const resolved = RACE_ART[normalised] ?? RACE_ART[ALIASES[normalised] ?? ""];
  return resolved ?? null;
}
