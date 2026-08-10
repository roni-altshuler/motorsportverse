/**
 * Race photography mapping — one curated aerial circuit photo per MotoGP venue.
 *
 * Keyed by the MotoGP calendar's venue `key` strings (as emitted by the export).
 * Per project convention, race art MUST be REAL aerial circuit photography of
 * the ACTUAL venue (NOT SVG layout diagrams, NOT logos, NOT generic country
 * landscapes, and NEVER a different track's photo). A venue with no verified
 * aerial simply falls back to the styled gradient placeholder — that is the
 * correct, honest choice, not a wrong image.
 *
 * Sourcing: Wikimedia Commons. Every URL below was `curl -I`-verified to return
 * HTTP 200 (image/jpeg) against the ACTUAL MotoGP venue before committing.
 * MotoGP shares only a handful of circuits with the F1/F3 calendars
 * (Barcelona-Catalunya, Silverstone, Red Bull Ring); the rest are MotoGP-only
 * tracks (COTA, Sachsenring, Phillip Island here), and every other venue falls
 * back to the gradient card. To add a venue: query
 *   https://en.wikipedia.org/api/rest_v1/page/media-list/<title>
 * for an aerial JPG and `curl -I` the resolved thumburl before committing —
 * guessed Wikimedia thumbnail filenames almost always 404.
 *
 * Consumed via CSS background-image (NOT next/image), so the hostname does not
 * need to be in next.config.ts `remotePatterns`.
 */

interface RaceArt {
  src: string;
  credit: string;
}

const RACE_ART: Record<string, RaceArt> = {
  // R3 — Circuit of the Americas (Austin) · SkySat aerial
  "circuit-of-the-americas": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/Circuit_of_the_Americas%2C_April_22%2C_2018_SkySat_%28cropped2%29.jpg/1280px-Circuit_of_the_Americas%2C_April_22%2C_2018_SkySat_%28cropped2%29.jpg",
    credit: "Circuit of the Americas aerial · Planet Labs / Wikimedia Commons",
  },
  // R6 — Circuit de Barcelona-Catalunya · SkySat aerial
  "circuit-de-barcelona-catalunya": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Circuit_de_Barcelona-Catalunya%2C_April_19%2C_2018_SkySat_%28cropped%29.jpg/1280px-Circuit_de_Barcelona-Catalunya%2C_April_19%2C_2018_SkySat_%28cropped%29.jpg",
    credit: "Circuit de Barcelona-Catalunya aerial · Planet Labs / Wikimedia Commons",
  },
  // R11 — Sachsenring · aerial photo (view from the south-west)
  sachsenring: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Aerial_image_of_Sachsenring_%28view_from_the_southwest%29.jpg/1280px-Aerial_image_of_Sachsenring_%28view_from_the_southwest%29.jpg",
    credit: "Sachsenring aerial · Wikimedia Commons",
  },
  // R12 — Silverstone Circuit · SkySat aerial
  "silverstone-circuit": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Silverstone_Circuit%2C_July_2%2C_2018_SkySat_%28cropped%29.jpg/1280px-Silverstone_Circuit%2C_July_2%2C_2018_SkySat_%28cropped%29.jpg",
    credit: "Silverstone Circuit aerial · Planet Labs / Wikimedia Commons",
  },
  // R15 — Red Bull Ring (Spielberg) · official aerial photo
  "red-bull-ring-spielberg": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cb/Luftaufnahme_%28c%29Red_Bull_Ring.jpg/1280px-Luftaufnahme_%28c%29Red_Bull_Ring.jpg",
    credit: "Red Bull Ring aerial · Wikimedia Commons",
  },
  // R18 — Phillip Island Grand Prix Circuit · aerial photo
  "phillip-island": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Phillip_Island_Aerial_View.jpg/1280px-Phillip_Island_Aerial_View.jpg",
    credit: "Phillip Island Circuit aerial · Wikimedia Commons",
  },
};

// A few name/country aliases so resolution still works if a future export uses
// the round `name` or a slightly different key spelling for a mapped venue.
const ALIASES: Record<string, string> = {
  austin: "circuit-of-the-americas",
  cota: "circuit-of-the-americas",
  barcelona: "circuit-de-barcelona-catalunya",
  catalunya: "circuit-de-barcelona-catalunya",
  silverstone: "silverstone-circuit",
  spielberg: "red-bull-ring-spielberg",
  "red-bull-ring": "red-bull-ring-spielberg",
  "phillip-island-grand-prix-circuit": "phillip-island",
};

/**
 * Pick the curated aerial photo for a given venue `key`. Returns null when no
 * verified photo exists (the calendar falls back to a styled placeholder rather
 * than a non-aerial or wrong-venue image, per project convention).
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
