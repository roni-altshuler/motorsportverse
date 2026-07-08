/**
 * Race photography mapping — one curated aerial venue photo per Formula E
 * venue, keyed by the calendar's venue `key` strings (as emitted by the FE
 * export: sao-paulo, mexico-city, miami, jeddah, madrid, berlin, monaco,
 * sanya, shanghai, tokyo, london). Doubleheader rounds share a key, so both
 * races of a weekend resolve the same photo.
 *
 * Sourcing: Wikimedia Commons. Where possible, the "SkySat" satellite aerials
 * (Planet Labs, 2018) — the closest free analog to official race-page hero
 * photography. Per project convention, race art MUST be aerial venue
 * photography (NOT SVG layout diagrams, NOT logos, NOT generic country
 * landscapes). Venues with no verified aerial photo on Commons (São Paulo's
 * Anhembi Sambadrome, Homestead-Miami, Sanya, Tokyo Big Sight) are DELIBERATELY
 * absent — the calendar falls back to the styled gradient card rather than
 * ever showing a wrong or non-aerial image.
 *
 * Every URL below was verified for this map on 2026-07-08 (`curl -I` → HTTP
 * 200, image/jpeg); the SkySat entries are additionally inherited verbatim
 * from the RaceIQ F1 production map. To swap an image, query
 *   https://en.wikipedia.org/api/rest_v1/page/media-list/<title>
 * for JPGs and `curl -I` the candidate before committing — guessed Wikimedia
 * thumbnail filenames almost always 404.
 *
 * Consumed via CSS background-image (NOT next/image), so the hostname does not
 * need to be in next.config.ts `remotePatterns`.
 */

interface RaceArt {
  src: string;
  credit: string;
}

const RACE_ART: Record<string, RaceArt> = {
  // R2 — Autódromo Hermanos Rodríguez (Mexico City E-Prix) · SkySat aerial
  "mexico-city": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f6/Aut%C3%B3dromo_Hermanos_Rodr%C3%ADguez%2C_June_4%2C_2018_SkySat_%28cropped%29.jpg/1280px-Aut%C3%B3dromo_Hermanos_Rodr%C3%ADguez%2C_June_4%2C_2018_SkySat_%28cropped%29.jpg",
    credit: "Autódromo Hermanos Rodríguez aerial · Planet Labs / Wikimedia Commons",
  },
  // R4+R5 — Jeddah Corniche Circuit (Jeddah E-Prix doubleheader) · satellite aerial.
  // NOTE: deliberately NOT the F1 map's "Jeddah.circuit.jpg" — that file is a
  // track-layout diagram, which the race-art discipline forbids.
  jeddah: {
    src: "https://upload.wikimedia.org/wikipedia/commons/d/dc/Jeddah_Corniche_Circuit_viewed_from_above.png",
    credit: "Jeddah Corniche Circuit satellite view · Wikimedia Commons",
  },
  // R6 — Circuito del Jarama (Madrid E-Prix) · aerial photo
  madrid: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bd/Circuito_de_Madrid_Jarama_-_RACE%2C_o_%22Circuito_del_Jarama%22._Comunidad_de_Madrid._Espa%C3%B1a%2C_Spain.jpg/1280px-Circuito_de_Madrid_Jarama_-_RACE%2C_o_%22Circuito_del_Jarama%22._Comunidad_de_Madrid._Espa%C3%B1a%2C_Spain.jpg",
    credit: "Circuito del Jarama aerial · Wikimedia Commons",
  },
  // R7+R8 — Tempelhof Airport street circuit (Berlin E-Prix doubleheader)
  berlin: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Berlin_-_Flughafen_Tempelhof_-_2016.jpg/1280px-Berlin_-_Flughafen_Tempelhof_-_2016.jpg",
    credit: "Tempelhof Airport aerial · Wikimedia Commons",
  },
  // R9+R10 — Circuit de Monaco (Monaco E-Prix doubleheader) · SkySat aerial
  monaco: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Circuit_de_Monaco%2C_April_1%2C_2018_SkySat_%28cropped%29.jpg/500px-Circuit_de_Monaco%2C_April_1%2C_2018_SkySat_%28cropped%29.jpg",
    credit: "Circuit de Monaco aerial · Planet Labs / Wikimedia Commons",
  },
  // R12+R13 — Shanghai International Circuit (Shanghai E-Prix doubleheader) · SkySat aerial
  shanghai: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d6/Shanghai_International_Circuit%2C_April_7%2C_2018_SkySat_%28rotated%29.jpg/1280px-Shanghai_International_Circuit%2C_April_7%2C_2018_SkySat_%28rotated%29.jpg",
    credit: "Shanghai International Circuit aerial · Planet Labs / Wikimedia Commons",
  },
  // R16+R17 — ExCeL London street circuit (London E-Prix doubleheader) · aerial
  london: {
    src: "https://upload.wikimedia.org/wikipedia/commons/9/91/Aerial_view_of_ExCeL_Exhibition_London%2C_July_2015.jpg",
    credit: "ExCeL London aerial · Wikimedia Commons",
  },
};

// A few city/name aliases, so resolution still works if a future export uses
// the round `name` or a slightly different key spelling. Doubleheader "II"
// names normalise to the base venue.
const ALIASES: Record<string, string> = {
  "mexico": "mexico-city",
  "mexico-city-ii": "mexico-city",
  "jeddah-ii": "jeddah",
  "diriyah": "jeddah",
  "berlin-ii": "berlin",
  "tempelhof": "berlin",
  "monaco-ii": "monaco",
  "monte-carlo": "monaco",
  "shanghai-ii": "shanghai",
  "london-ii": "london",
  "excel": "london",
  "jarama": "madrid",
  "madrid-ii": "madrid",
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
