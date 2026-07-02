/**
 * Race photography mapping — one curated aerial circuit photo per F3 round.
 *
 * F3 shares the F1 race weekends and circuits, so this is a direct port of the
 * RaceIQ F1 raceArt map (src/lib/raceArt.ts), re-keyed to the F3 calendar's
 * venue `key` strings (as emitted by the F3 export: sakhir, jeddah, melbourne,
 * imola, monaco, catalunya, spielberg, silverstone, hungaroring, spa, monza,
 * baku, yas-marina).
 *
 * Sourcing: Wikimedia Commons. Where possible, the "SkySat" satellite aerials
 * (Planet Labs, 2018) — the closest free analog to official race-page hero
 * photography. Per project convention, race art MUST be aerial circuit
 * photography (NOT SVG layout diagrams, NOT logos, NOT generic country
 * landscapes).
 *
 * Every URL is inherited verbatim from the RaceIQ F1 production map, where each
 * was curl-verified to return HTTP 200 (image/jpeg). To swap an image, query
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
  // R1 — Bahrain International Circuit (Sakhir) · SkySat aerial
  sakhir: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/Bahrain_International_Circuit%2C_November_2%2C_2017_SkySat_%28cropped%29.jpg/1280px-Bahrain_International_Circuit%2C_November_2%2C_2017_SkySat_%28cropped%29.jpg",
    credit: "Bahrain International Circuit aerial · Planet Labs / Wikimedia Commons",
  },
  // R2 — Jeddah Corniche Circuit
  jeddah: {
    src: "https://upload.wikimedia.org/wikipedia/commons/4/44/Jeddah.circuit.jpg",
    credit: "Jeddah Corniche Circuit · Wikimedia Commons",
  },
  // R3 — Albert Park Circuit (Melbourne) · SkySat aerial
  melbourne: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Melbourne_Grand_Prix_Circuit%2C_March_22%2C_2018_SkySat_%28cropped%29.jpg/1280px-Melbourne_Grand_Prix_Circuit%2C_March_22%2C_2018_SkySat_%28cropped%29.jpg",
    credit: "Albert Park aerial · Planet Labs / Wikimedia Commons",
  },
  // R4 — Imola (Autodromo Enzo e Dino Ferrari) · aerial poster shot
  imola: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fc/Autodromo_aerea_poster.jpg/1280px-Autodromo_aerea_poster.jpg",
    credit: "Imola aerial · Wikimedia Commons",
  },
  // 2026 R3 — Circuit Gilles-Villeneuve (Montréal) · SkySat aerial
  montreal: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/Circuit_Gilles-Villeneuve%2C_May_29%2C_2018_SkySat_%28cropped%29.jpg/1280px-Circuit_Gilles-Villeneuve%2C_May_29%2C_2018_SkySat_%28cropped%29.jpg",
    credit: "Circuit Gilles-Villeneuve aerial · Planet Labs / Wikimedia Commons",
  },
  // R5 — Circuit de Monaco · SkySat aerial
  monaco: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Circuit_de_Monaco%2C_April_1%2C_2018_SkySat_%28cropped%29.jpg/500px-Circuit_de_Monaco%2C_April_1%2C_2018_SkySat_%28cropped%29.jpg",
    credit: "Circuit de Monaco aerial · Planet Labs / Wikimedia Commons",
  },
  // R6 — Circuit de Barcelona-Catalunya · SkySat aerial
  catalunya: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Circuit_de_Barcelona-Catalunya%2C_April_19%2C_2018_SkySat_%28cropped%29.jpg/1280px-Circuit_de_Barcelona-Catalunya%2C_April_19%2C_2018_SkySat_%28cropped%29.jpg",
    credit: "Circuit de Barcelona-Catalunya aerial · Planet Labs / Wikimedia Commons",
  },
  // R7 — Red Bull Ring (Spielberg) · official aerial photo
  spielberg: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cb/Luftaufnahme_%28c%29Red_Bull_Ring.jpg/1280px-Luftaufnahme_%28c%29Red_Bull_Ring.jpg",
    credit: "Red Bull Ring aerial · Wikimedia Commons",
  },
  // R8 — Silverstone Circuit · SkySat aerial
  silverstone: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Silverstone_Circuit%2C_July_2%2C_2018_SkySat_%28cropped%29.jpg/1280px-Silverstone_Circuit%2C_July_2%2C_2018_SkySat_%28cropped%29.jpg",
    credit: "Silverstone Circuit aerial · Planet Labs / Wikimedia Commons",
  },
  // R9 — Hungaroring · SkySat aerial
  hungaroring: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/a/aa/Hungaroring%2C_April_28%2C_2018_SkySat_%28cropped%29.jpg/500px-Hungaroring%2C_April_28%2C_2018_SkySat_%28cropped%29.jpg",
    credit: "Hungaroring aerial · Planet Labs / Wikimedia Commons",
  },
  // R10 — Circuit de Spa-Francorchamps · SkySat aerial
  spa: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/Circuit_de_Spa-Francorchamps%2C_April_22%2C_2018_SkySat_%28cropped%29.jpg/1280px-Circuit_de_Spa-Francorchamps%2C_April_22%2C_2018_SkySat_%28cropped%29.jpg",
    credit: "Spa-Francorchamps aerial · Planet Labs / Wikimedia Commons",
  },
  // R11 — Autodromo Nazionale Monza · SkySat aerial
  monza: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Autodromo_Nazionale_Monza%2C_April_22%2C_2018_SkySat_%28cropped%29.jpg/1280px-Autodromo_Nazionale_Monza%2C_April_22%2C_2018_SkySat_%28cropped%29.jpg",
    credit: "Monza aerial · Planet Labs / Wikimedia Commons",
  },
  // R12 — Baku City Circuit · SkySat aerial
  baku: {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Baku_City_Circuit%2C_April_9%2C_2018_SkySat.jpg/1280px-Baku_City_Circuit%2C_April_9%2C_2018_SkySat.jpg",
    credit: "Baku City Circuit aerial · Planet Labs / Wikimedia Commons",
  },
  // R13 — Yas Marina Circuit (Abu Dhabi) · SkySat aerial
  "yas-marina": {
    src: "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/Yas_Marina_Circuit%2C_October_12%2C_2018_SkySat_%28cropped%29.jpg/1280px-Yas_Marina_Circuit%2C_October_12%2C_2018_SkySat_%28cropped%29.jpg",
    credit: "Yas Marina Circuit aerial · Planet Labs / Wikimedia Commons",
  },
};

// A few country/name aliases, so resolution still works if a future export uses
// the round `name` or a slightly different key spelling.
const ALIASES: Record<string, string> = {
  bahrain: "sakhir",
  "saudi-arabia": "jeddah",
  saudi: "jeddah",
  australia: "melbourne",
  canada: "montreal",
  "emilia-romagna": "imola",
  spain: "catalunya",
  barcelona: "catalunya",
  austria: "spielberg",
  "great-britain": "silverstone",
  britain: "silverstone",
  hungary: "hungaroring",
  belgium: "spa",
  italy: "monza",
  azerbaijan: "baku",
  "abu-dhabi": "yas-marina",
  uae: "yas-marina",
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
