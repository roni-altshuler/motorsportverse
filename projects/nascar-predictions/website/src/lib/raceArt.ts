/**
 * Race photography mapping — one curated aerial venue photo per NASCAR Cup
 * venue, keyed by the calendar's venue `key` strings (as emitted by the
 * export: daytona-international-speedway, talladega-superspeedway, ...).
 * Several venues host two rounds (Daytona, Atlanta, Talladega, Kansas,
 * Las Vegas, ...); keying by venue means both rounds resolve the same photo.
 *
 * Sourcing: Wikimedia Commons. Superspeedways photograph spectacularly from
 * the air (the whole tri-oval fits one frame) — Talladega, Daytona (USGS
 * orthophoto), Atlanta, Kansas, Las Vegas, Pocono, Indianapolis, Gateway all
 * have genuine aerials; COTA inherits the Planet Labs SkySat satellite frame
 * from the F1 production map. Per project convention, race art MUST be aerial
 * venue photography (NOT SVG layout diagrams, NOT logos, NOT generic
 * landscapes). Venues with no verified aerial on Commons (Bristol's best shot
 * is an in-bowl grandstand photo; Darlington, Martinsville, Phoenix, Richmond,
 * Sonoma, Watkins Glen, Homestead, Michigan, Texas, Nashville, Chicagoland,
 * North Wilkesboro, Iowa, New Hampshire, San Diego street) are DELIBERATELY
 * absent — the calendar falls back to the styled gradient card rather than
 * ever showing a wrong or non-aerial image.
 *
 * Every URL below was verified for this map on 2026-07-08 (`curl -I` → HTTP
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
  // R1 + R26 — Daytona International Speedway · USGS orthophoto (true aerial)
  "daytona-international-speedway": {
    src: "https://upload.wikimedia.org/wikipedia/commons/d/d8/DaytonaInternationalSpeedwayAerial.jpg",
    credit: "Daytona International Speedway aerial · USGS / Wikimedia Commons",
  },
  // R2 + R20 — Atlanta Motor Speedway · aerial photo
  "atlanta-motor-speedway": {
    src: "https://upload.wikimedia.org/wikipedia/commons/f/fe/Atlanta_Motor_Speedway_aerial_2006.jpg",
    credit: "Atlanta Motor Speedway aerial · Wikimedia Commons",
  },
  // R3 — Circuit of The Americas · SkySat satellite aerial (F1 production map)
  "circuit-of-the-americas": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/Circuit_of_the_Americas%2C_April_22%2C_2018_SkySat_%28cropped2%29.jpg/1280px-Circuit_of_the_Americas%2C_April_22%2C_2018_SkySat_%28cropped2%29.jpg",
    credit: "Circuit of The Americas aerial · Planet Labs / Wikimedia Commons",
  },
  // R5 + R31 — Las Vegas Motor Speedway · aerial photo
  "las-vegas-motor-speedway": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/LasVegasMotorSpeedwayAerialViewNov2018.jpg/1280px-LasVegasMotorSpeedwayAerialViewNov2018.jpg",
    credit: "Las Vegas Motor Speedway aerial · Wikimedia Commons",
  },
  // R9 + R30 — Kansas Speedway · aerial photo
  "kansas-speedway": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/Kansas_Speedway_Aerial.jpg/1280px-Kansas_Speedway_Aerial.jpg",
    credit: "Kansas Speedway aerial · Wikimedia Commons",
  },
  // R10 + R34 — Talladega Superspeedway · aerial photo (visually verified)
  "talladega-superspeedway": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/TalladegaSuperspeedway2-2.jpg/1280px-TalladegaSuperspeedway2-2.jpg",
    credit: "Talladega Superspeedway aerial · Wikimedia Commons",
  },
  // R16 — Pocono Raceway (the Tricky Triangle) · aerial photo
  "pocono-raceway": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Pocono_Raceway_aerial_2018.jpg/1280px-Pocono_Raceway_aerial_2018.jpg",
    credit: "Pocono Raceway aerial · Wikimedia Commons",
  },
  // R22 — Indianapolis Motor Speedway · aerial photo
  "indianapolis-motor-speedway": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/3/35/Indianapolis_Motor_Speedway_Aerial_August_2018.jpg/1280px-Indianapolis_Motor_Speedway_Aerial_August_2018.jpg",
    credit: "Indianapolis Motor Speedway aerial · Wikimedia Commons",
  },
  // R28 — World Wide Technology Raceway (Gateway) · aerial photo
  "world-wide-technology-raceway": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cc/World_Wide_Technology_Raceway%2C_aerial_view%2C_June_2023_%28cropped%29.jpg/500px-World_Wide_Technology_Raceway%2C_aerial_view%2C_June_2023_%28cropped%29.jpg",
    credit: "World Wide Technology Raceway aerial · Wikimedia Commons",
  },
};

// A few name aliases, so resolution still works if a future export uses the
// round `name` or a slightly different key spelling.
const ALIASES: Record<string, string> = {
  daytona: "daytona-international-speedway",
  atlanta: "atlanta-motor-speedway",
  cota: "circuit-of-the-americas",
  "circuit-of-the-americas-austin": "circuit-of-the-americas",
  "las-vegas": "las-vegas-motor-speedway",
  kansas: "kansas-speedway",
  talladega: "talladega-superspeedway",
  pocono: "pocono-raceway",
  indianapolis: "indianapolis-motor-speedway",
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
