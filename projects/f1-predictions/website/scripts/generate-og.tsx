/**
 * generate-og.tsx
 *
 * Renders 1200x630 Open Graph share cards for the RaceIQ site, plus the PWA
 * icon set:
 *
 *   - public/og/default.png             site-wide fallback
 *   - public/og/round_NN.png            race prediction card, one per round
 *   - public/og/theatre_NN.png          race-replay ("theatre") card, one per round
 *   - public/og/standings.png           championship title-race card
 *   - public/og/accuracy.png            "called X of Y winners" season scorecard
 *   - public/icons/icon-192.png         PWA / favicon (any)
 *   - public/icons/icon-512.png         PWA (any)
 *   - public/icons/maskable-512.png     PWA adaptive icon (maskable, safe-zone padded)
 *   - public/icons/apple-touch-icon.png iOS home-screen icon (180x180, opaque)
 *
 * Reads input from public/data/season.json, public/data/rounds/round_NN.json,
 * public/data/standings.json and public/data/gp_accuracy_report.json. The icon
 * set is composited from src/app/icon.png (the 256x256 brand mark).
 *
 * Runs during the `prebuild` npm script via tsx, so every asset is regenerated
 * before each `next build`.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import sharp from "sharp";

// -----------------------------------------------------------------------------
// Paths
// -----------------------------------------------------------------------------
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");
const PUBLIC_DIR = path.join(ROOT, "public");
const DATA_DIR = path.join(PUBLIC_DIR, "data");
const ROUNDS_DIR = path.join(DATA_DIR, "rounds");
const OUT_DIR = path.join(PUBLIC_DIR, "og");
const ICONS_DIR = path.join(PUBLIC_DIR, "icons");
const APP_ICON_SRC = path.join(ROOT, "src", "app", "icon.png");

// -----------------------------------------------------------------------------
// Types (kept inline to avoid coupling to src/types so the script can run
// standalone without TS path-mapping)
// -----------------------------------------------------------------------------
interface CalendarEntry {
  round: number;
  name: string;
  circuit: string;
  date: string;
  country: string;
  gpKey: string;
}

interface DriverInfo {
  code: string;
  fullName: string;
  team: string;
  teamColor: string;
}

interface SeasonData {
  season: number;
  totalRounds: number;
  calendar: CalendarEntry[];
  drivers: DriverInfo[];
}

interface ClassificationEntry {
  position: number;
  driver: string;
  driverFullName: string;
  team: string;
  teamColor: string;
}

interface RoundData {
  round: number;
  name: string;
  date: string;
  circuit: string;
  classification: ClassificationEntry[];
}

interface StandingsDriver {
  position: number;
  driver: string;
  driverFullName: string;
  team: string;
  teamColor: string;
  points: number;
  wins: number;
}

interface StandingsConstructor {
  position: number;
  team: string;
  teamColor: string;
  points: number;
  wins: number;
}

interface StandingsData {
  lastUpdatedRound?: number;
  drivers: StandingsDriver[];
  constructors: StandingsConstructor[];
}

interface AccuracyOverall {
  seasonWinnerHits?: number;
  roundsWithActual?: number;
  seasonWinnerHitPct?: number;
  seasonPodiumAccuracyPct?: number;
  seasonPointsAccuracyPct?: number;
  seasonAccuracyPctClassified?: number;
  seasonAccuracyPct?: number;
}

interface AccuracyReport {
  overallAccuracy?: AccuracyOverall;
}

// -----------------------------------------------------------------------------
// Country code mapping (mirrors src/components/CountryFlag.tsx)
// -----------------------------------------------------------------------------
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
  Madrid: "es",
};

// -----------------------------------------------------------------------------
// Fonts
// -----------------------------------------------------------------------------
function loadFont(weight: 400 | 600 | 800): Buffer {
  // @fontsource/inter ships per-weight WOFF files. Satori accepts WOFF.
  const file = path.join(
    ROOT,
    "node_modules",
    "@fontsource",
    "inter",
    "files",
    `inter-latin-${weight}-normal.woff`
  );
  return fs.readFileSync(file);
}

const FONT_REGULAR = loadFont(400);
const FONT_SEMI = loadFont(600);
const FONT_BOLD = loadFont(800);

const SATORI_FONTS = [
  { name: "Inter", data: FONT_REGULAR, weight: 400 as const, style: "normal" as const },
  { name: "Inter", data: FONT_SEMI, weight: 600 as const, style: "normal" as const },
  { name: "Inter", data: FONT_BOLD, weight: 800 as const, style: "normal" as const },
];

// -----------------------------------------------------------------------------
// Flag image cache (downloaded once per country during build)
// -----------------------------------------------------------------------------
const flagCache = new Map<string, string | null>();

async function getFlagDataUrl(country: string): Promise<string | null> {
  const code = COUNTRY_CODES[country];
  if (!code) return null;
  if (flagCache.has(code)) return flagCache.get(code) ?? null;
  try {
    const res = await fetch(`https://flagcdn.com/w320/${code}.png`);
    if (!res.ok) {
      flagCache.set(code, null);
      return null;
    }
    const buf = Buffer.from(await res.arrayBuffer());
    const dataUrl = `data:image/png;base64,${buf.toString("base64")}`;
    flagCache.set(code, dataUrl);
    return dataUrl;
  } catch {
    flagCache.set(code, null);
    return null;
  }
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------
function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

function formatDateLong(iso: string): string {
  // iso = "2026-03-08"
  const [y, m, d] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

// Stripped-down React.createElement-style object. Satori accepts these as
// "JSX" nodes when its custom jsx is not configured.
// We use plain objects to avoid pulling in React for a build-time script.
type Node = {
  type: string;
  props: { children?: unknown; style?: Record<string, unknown> } & Record<string, unknown>;
};

function h(
  type: string,
  props: Record<string, unknown> | null,
  ...children: unknown[]
): Node {
  const flat = children
    .flat(Infinity)
    .filter((c) => c !== null && c !== undefined && c !== false);
  const node: Node = {
    type,
    props: {
      ...(props ?? {}),
    },
  };
  // Only set children when we actually have content. Satori treats an empty
  // array as "has children" and then rejects a <div> that lacks display:flex.
  if (flat.length === 1) {
    node.props.children = flat[0];
  } else if (flat.length > 1) {
    node.props.children = flat;
  }
  return node;
}

// -----------------------------------------------------------------------------
// Layout
// -----------------------------------------------------------------------------
const BG = "#0a0a0a";
const PANEL = "#141414";
const F1_RED = "#E10600";
const TEXT = "#ffffff";
const MUTED = "#9ca3af";

// A right-pointing "play" triangle as an SVG data URI. Satori's CSS
// transparent-border triangle hack renders as a filled box, so we embed an
// SVG <img> instead (verified to rasterize correctly through resvg).
const PLAY_GLYPH =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 100 100'><polygon points='34,22 34,78 82,50' fill='#ffffff'/></svg>",
  );

function pctLabel(v: number | undefined): string {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  return `${Math.round(v)}%`;
}

function buildRaceCard(opts: {
  round: number;
  season: number;
  name: string;
  circuit: string;
  date: string;
  country: string;
  flagDataUrl: string | null;
  top3: { code: string; fullName: string; team: string; teamColor: string }[];
}): Node {
  const { round, season, name, circuit, date, country, flagDataUrl, top3 } = opts;

  const positionLabels = ["P1", "P2", "P3"];

  return h(
    "div",
    {
      style: {
        width: "1200px",
        height: "630px",
        display: "flex",
        flexDirection: "column",
        background: BG,
        color: TEXT,
        fontFamily: "Inter",
        position: "relative",
      },
    },
    // F1-red accent stripe at top
    h("div", {
      style: {
        width: "100%",
        height: "8px",
        background: F1_RED,
      },
    }),
    // Header row: ROUND N (2026 SEASON)
    h(
      "div",
      {
        style: {
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "32px 56px 0 56px",
        },
      },
      h(
        "div",
        {
          style: {
            display: "flex",
            alignItems: "center",
            gap: "16px",
          },
        },
        h(
          "div",
          {
            style: {
              fontSize: "18px",
              fontWeight: 800,
              letterSpacing: "6px",
              color: F1_RED,
              textTransform: "uppercase",
            },
          },
          `Round ${round}`
        ),
        h(
          "div",
          {
            style: {
              fontSize: "18px",
              fontWeight: 600,
              letterSpacing: "4px",
              color: MUTED,
              textTransform: "uppercase",
            },
          },
          `${season} Season`
        )
      ),
      h(
        "div",
        {
          style: {
            fontSize: "16px",
            fontWeight: 600,
            letterSpacing: "3px",
            color: MUTED,
            textTransform: "uppercase",
          },
        },
        "RaceIQ"
      )
    ),
    // Race name + date + country block
    h(
      "div",
      {
        style: {
          display: "flex",
          alignItems: "center",
          padding: "16px 56px 16px 56px",
          gap: "32px",
        },
      },
      flagDataUrl
        ? h("img", {
            src: flagDataUrl,
            width: 120,
            height: 80,
            style: {
              borderRadius: "8px",
              objectFit: "cover",
              boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
            },
          })
        : h(
            "div",
            {
              style: {
                width: "120px",
                height: "80px",
                background: PANEL,
                borderRadius: "8px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "14px",
                color: MUTED,
              },
            },
            country
          ),
      h(
        "div",
        {
          style: {
            display: "flex",
            flexDirection: "column",
            gap: "8px",
            flex: 1,
          },
        },
        h(
          "div",
          {
            style: {
              fontSize: "56px",
              fontWeight: 800,
              lineHeight: 1.05,
              color: TEXT,
            },
          },
          name
        ),
        h(
          "div",
          {
            style: {
              display: "flex",
              gap: "16px",
              alignItems: "center",
              fontSize: "22px",
              fontWeight: 500,
              color: MUTED,
            },
          },
          h("span", null, formatDateLong(date)),
          h("span", { style: { color: F1_RED } }, "*"),
          h("span", null, circuit)
        )
      )
    ),
    // Top-3 predicted drivers panel
    h(
      "div",
      {
        style: {
          display: "flex",
          flexDirection: "column",
          padding: "16px 56px 0 56px",
          flex: 1,
        },
      },
      h(
        "div",
        {
          style: {
            fontSize: "14px",
            fontWeight: 700,
            letterSpacing: "4px",
            color: MUTED,
            textTransform: "uppercase",
            marginBottom: "16px",
          },
        },
        top3.length > 0 ? "Predicted Podium" : "Predictions Coming Soon"
      ),
      h(
        "div",
        {
          style: {
            display: "flex",
            gap: "16px",
          },
        },
        ...top3.map((d, i) =>
          h(
            "div",
            {
              key: d.code,
              style: {
                display: "flex",
                flexDirection: "column",
                flex: 1,
                background: PANEL,
                borderRadius: "12px",
                padding: "20px 24px",
                borderLeft: `6px solid ${d.teamColor}`,
                gap: "8px",
              },
            },
            h(
              "div",
              {
                style: {
                  fontSize: "16px",
                  fontWeight: 700,
                  letterSpacing: "3px",
                  color: MUTED,
                },
              },
              positionLabels[i] ?? `P${i + 1}`
            ),
            h(
              "div",
              {
                style: {
                  fontSize: "30px",
                  fontWeight: 800,
                  color: TEXT,
                  lineHeight: 1.1,
                },
              },
              d.fullName
            ),
            h(
              "div",
              {
                style: {
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  fontSize: "16px",
                  fontWeight: 600,
                  color: MUTED,
                },
              },
              h("div", {
                style: {
                  width: "12px",
                  height: "12px",
                  borderRadius: "9999px",
                  background: d.teamColor,
                },
              }),
              h("span", null, d.team)
            )
          )
        )
      )
    ),
    // Footer
    h(
      "div",
      {
        style: {
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "20px 56px 28px 56px",
          marginTop: "auto",
        },
      },
      h(
        "div",
        {
          style: {
            fontSize: "16px",
            fontWeight: 600,
            color: MUTED,
          },
        },
        "AI-powered Formula 1 forecasts"
      ),
      h(
        "div",
        {
          style: {
            fontSize: "16px",
            fontWeight: 700,
            color: TEXT,
            letterSpacing: "2px",
          },
        },
        "raceiq"
      )
    )
  );
}

function buildDefaultCard(season: number): Node {
  return h(
    "div",
    {
      style: {
        width: "1200px",
        height: "630px",
        display: "flex",
        flexDirection: "column",
        background: BG,
        color: TEXT,
        fontFamily: "Inter",
      },
    },
    h("div", {
      style: { width: "100%", height: "8px", background: F1_RED },
    }),
    h(
      "div",
      {
        style: {
          display: "flex",
          flexDirection: "column",
          flex: 1,
          justifyContent: "center",
          padding: "0 80px",
          gap: "16px",
        },
      },
      h(
        "div",
        {
          style: {
            fontSize: "20px",
            fontWeight: 800,
            letterSpacing: "8px",
            color: F1_RED,
            textTransform: "uppercase",
          },
        },
        `${season} Season`
      ),
      h(
        "div",
        {
          style: {
            fontSize: "92px",
            fontWeight: 800,
            color: TEXT,
            lineHeight: 1.0,
          },
        },
        "RaceIQ"
      ),
      h(
        "div",
        {
          style: {
            fontSize: "32px",
            fontWeight: 500,
            color: MUTED,
            lineHeight: 1.3,
            maxWidth: "1000px",
          },
        },
        "AI and machine-learning powered race forecasts, championship standings, and pit-strategy simulations for every Grand Prix."
      )
    ),
    h(
      "div",
      {
        style: {
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 80px 48px 80px",
        },
      },
      h(
        "div",
        {
          style: {
            display: "flex",
            gap: "12px",
            alignItems: "center",
          },
        },
        h("div", {
          style: {
            width: "12px",
            height: "12px",
            borderRadius: "9999px",
            background: F1_RED,
          },
        }),
        h(
          "div",
          {
            style: { fontSize: "20px", fontWeight: 600, color: MUTED },
          },
          "Race predictions * Standings * Accuracy"
        )
      ),
      h(
        "div",
        {
          style: {
            fontSize: "20px",
            fontWeight: 700,
            color: TEXT,
            letterSpacing: "3px",
          },
        },
        "raceiq"
      )
    )
  );
}

// -----------------------------------------------------------------------------
// Shared card chrome (red stripe / header / footer) for the newer share cards
// -----------------------------------------------------------------------------
function redStripe(): Node {
  return h("div", {
    style: { width: "100%", height: "8px", background: F1_RED },
  });
}

function buildHeader(kicker: string, sub: string): Node {
  return h(
    "div",
    {
      style: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "32px 56px 0 56px",
      },
    },
    h(
      "div",
      { style: { display: "flex", alignItems: "center", gap: "16px" } },
      h(
        "div",
        {
          style: {
            fontSize: "18px",
            fontWeight: 800,
            letterSpacing: "6px",
            color: F1_RED,
            textTransform: "uppercase",
          },
        },
        kicker,
      ),
      sub
        ? h(
            "div",
            {
              style: {
                fontSize: "18px",
                fontWeight: 600,
                letterSpacing: "4px",
                color: MUTED,
                textTransform: "uppercase",
              },
            },
            sub,
          )
        : null,
    ),
    h(
      "div",
      {
        style: {
          fontSize: "16px",
          fontWeight: 600,
          letterSpacing: "3px",
          color: MUTED,
          textTransform: "uppercase",
        },
      },
      "RaceIQ",
    ),
  );
}

function buildFooter(left: string): Node {
  return h(
    "div",
    {
      style: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "20px 56px 28px 56px",
        marginTop: "auto",
      },
    },
    h(
      "div",
      { style: { fontSize: "16px", fontWeight: 600, color: MUTED } },
      left,
    ),
    h(
      "div",
      {
        style: {
          fontSize: "16px",
          fontWeight: 700,
          color: TEXT,
          letterSpacing: "2px",
        },
      },
      "raceiq",
    ),
  );
}

// -----------------------------------------------------------------------------
// Race Theatre (replay) card — one per round
// -----------------------------------------------------------------------------
function buildTheatreCard(opts: {
  round: number;
  season: number;
  name: string;
  circuit: string;
  date: string;
  country: string;
  flagDataUrl: string | null;
}): Node {
  const { round, season, name, circuit, date, country, flagDataUrl } = opts;
  return h(
    "div",
    {
      style: {
        width: "1200px",
        height: "630px",
        display: "flex",
        flexDirection: "column",
        background: BG,
        color: TEXT,
        fontFamily: "Inter",
      },
    },
    redStripe(),
    buildHeader("Race Theatre", `${season} Season`),
    h(
      "div",
      {
        style: {
          display: "flex",
          flex: 1,
          padding: "24px 56px 0 56px",
          gap: "48px",
          alignItems: "center",
        },
      },
      // Left column: race identity + replay hook
      h(
        "div",
        {
          style: {
            display: "flex",
            flexDirection: "column",
            flex: 1,
            gap: "18px",
          },
        },
        h(
          "div",
          { style: { display: "flex", alignItems: "center", gap: "20px" } },
          flagDataUrl
            ? h("img", {
                src: flagDataUrl,
                width: 88,
                height: 59,
                style: {
                  borderRadius: "6px",
                  objectFit: "cover",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
                },
              })
            : null,
          h(
            "div",
            {
              style: {
                fontSize: "16px",
                fontWeight: 700,
                letterSpacing: "3px",
                color: MUTED,
                textTransform: "uppercase",
              },
            },
            `Round ${round} · ${country}`,
          ),
        ),
        h(
          "div",
          {
            style: {
              fontSize: "60px",
              fontWeight: 800,
              lineHeight: 1.02,
              color: TEXT,
            },
          },
          name,
        ),
        h(
          "div",
          {
            style: {
              display: "flex",
              gap: "14px",
              alignItems: "center",
              fontSize: "22px",
              fontWeight: 500,
              color: MUTED,
            },
          },
          h("span", null, formatDateLong(date)),
          h("span", { style: { color: F1_RED } }, "·"),
          h("span", null, circuit),
        ),
        h(
          "div",
          {
            style: {
              display: "flex",
              alignItems: "center",
              background: F1_RED,
              color: TEXT,
              fontSize: "18px",
              fontWeight: 700,
              letterSpacing: "2px",
              textTransform: "uppercase",
              padding: "12px 22px",
              borderRadius: "9999px",
              marginTop: "4px",
              alignSelf: "flex-start",
            },
          },
          "Relive every lap",
        ),
        h(
          "div",
          { style: { fontSize: "18px", fontWeight: 500, color: MUTED } },
          "All cars on track · Live timing tower · Lap-by-lap replay",
        ),
      ),
      // Right column: play panel
      h(
        "div",
        {
          style: {
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "22px",
            width: "360px",
            height: "330px",
            background: PANEL,
            borderRadius: "20px",
          },
        },
        h(
          "div",
          {
            style: {
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "150px",
              height: "150px",
              borderRadius: "9999px",
              background: F1_RED,
              boxShadow: "0 10px 30px rgba(225,6,0,0.45)",
            },
          },
          h("img", {
            src: PLAY_GLYPH,
            width: 64,
            height: 64,
            style: { marginLeft: "10px" },
          }),
        ),
        h(
          "div",
          {
            style: {
              fontSize: "18px",
              fontWeight: 700,
              letterSpacing: "2px",
              color: MUTED,
              textTransform: "uppercase",
            },
          },
          "Watch the replay",
        ),
      ),
    ),
    buildFooter("Animated race replay · reconstructed from race data"),
  );
}

// -----------------------------------------------------------------------------
// Championship title-race card
// -----------------------------------------------------------------------------
function buildStandingsCard(opts: {
  season: number;
  round: number;
  totalRounds: number;
  leader: StandingsDriver;
  runnerUp?: StandingsDriver;
  constructorLeader?: StandingsConstructor;
}): Node {
  const { season, round, totalRounds, leader, runnerUp, constructorLeader } =
    opts;
  const gap = runnerUp ? leader.points - runnerUp.points : null;
  return h(
    "div",
    {
      style: {
        width: "1200px",
        height: "630px",
        display: "flex",
        flexDirection: "column",
        background: BG,
        color: TEXT,
        fontFamily: "Inter",
      },
    },
    redStripe(),
    buildHeader("Title Race", `${season} Season`),
    h(
      "div",
      {
        style: {
          display: "flex",
          flexDirection: "column",
          flex: 1,
          padding: "20px 56px 0 56px",
          gap: "14px",
        },
      },
      h(
        "div",
        {
          style: {
            fontSize: "16px",
            fontWeight: 700,
            letterSpacing: "4px",
            color: MUTED,
            textTransform: "uppercase",
          },
        },
        "Drivers' Championship leader",
      ),
      h(
        "div",
        {
          style: {
            fontSize: "72px",
            fontWeight: 800,
            lineHeight: 1.0,
            color: TEXT,
          },
        },
        leader.driverFullName,
      ),
      h(
        "div",
        {
          style: {
            display: "flex",
            alignItems: "center",
            gap: "10px",
            fontSize: "22px",
            fontWeight: 600,
            color: MUTED,
          },
        },
        h("div", {
          style: {
            width: "14px",
            height: "14px",
            borderRadius: "9999px",
            background: leader.teamColor,
          },
        }),
        h("span", null, leader.team),
      ),
      h(
        "div",
        { style: { display: "flex", gap: "20px", marginTop: "8px" } },
        h(
          "div",
          {
            style: {
              display: "flex",
              flexDirection: "column",
              flex: 1,
              background: PANEL,
              borderRadius: "14px",
              padding: "22px 26px",
              borderLeft: `6px solid ${leader.teamColor}`,
              gap: "6px",
            },
          },
          h(
            "div",
            {
              style: {
                fontSize: "15px",
                fontWeight: 700,
                letterSpacing: "3px",
                color: MUTED,
                textTransform: "uppercase",
              },
            },
            "Points",
          ),
          h(
            "div",
            {
              style: {
                fontSize: "48px",
                fontWeight: 800,
                color: TEXT,
                lineHeight: 1.0,
              },
            },
            `${leader.points}`,
          ),
        ),
        gap !== null
          ? h(
              "div",
              {
                style: {
                  display: "flex",
                  flexDirection: "column",
                  flex: 1,
                  background: PANEL,
                  borderRadius: "14px",
                  padding: "22px 26px",
                  borderLeft: `6px solid ${F1_RED}`,
                  gap: "6px",
                },
              },
              h(
                "div",
                {
                  style: {
                    fontSize: "15px",
                    fontWeight: 700,
                    letterSpacing: "3px",
                    color: MUTED,
                    textTransform: "uppercase",
                  },
                },
                gap > 0 ? "Leads by" : "Level on points",
              ),
              h(
                "div",
                {
                  style: {
                    fontSize: "48px",
                    fontWeight: 800,
                    color: TEXT,
                    lineHeight: 1.0,
                  },
                },
                gap > 0 ? `${gap} pts` : "0 pts",
              ),
              runnerUp
                ? h(
                    "div",
                    {
                      style: {
                        fontSize: "16px",
                        fontWeight: 600,
                        color: MUTED,
                      },
                    },
                    `over ${runnerUp.driverFullName}`,
                  )
                : null,
            )
          : null,
      ),
      constructorLeader
        ? h(
            "div",
            {
              style: {
                display: "flex",
                alignItems: "center",
                gap: "10px",
                fontSize: "20px",
                fontWeight: 600,
                marginTop: "6px",
              },
            },
            h("div", {
              style: {
                width: "12px",
                height: "12px",
                borderRadius: "9999px",
                background: constructorLeader.teamColor,
              },
            }),
            h(
              "span",
              { style: { color: MUTED } },
              `${constructorLeader.team} leads the Constructors' with ${constructorLeader.points} pts`,
            ),
          )
        : null,
    ),
    buildFooter(
      round > 0
        ? `After Round ${round} of ${totalRounds}`
        : `${season} Formula 1 championship`,
    ),
  );
}

// -----------------------------------------------------------------------------
// Season accuracy "scorecard" card — the shareable "called X of Y winners" hook
// -----------------------------------------------------------------------------
function accStatTile(label: string, value: string): Node {
  return h(
    "div",
    {
      style: {
        display: "flex",
        flexDirection: "column",
        flex: 1,
        background: PANEL,
        borderRadius: "14px",
        padding: "20px 24px",
        gap: "6px",
      },
    },
    h(
      "div",
      {
        style: {
          fontSize: "40px",
          fontWeight: 800,
          color: TEXT,
          lineHeight: 1.0,
        },
      },
      value,
    ),
    h(
      "div",
      {
        style: {
          fontSize: "15px",
          fontWeight: 700,
          letterSpacing: "2px",
          color: MUTED,
          textTransform: "uppercase",
        },
      },
      label,
    ),
  );
}

function buildAccuracyCard(opts: {
  season: number;
  overall: AccuracyOverall;
}): Node {
  const { season, overall } = opts;
  const hits = overall.seasonWinnerHits ?? 0;
  const rounds = overall.roundsWithActual ?? 0;
  return h(
    "div",
    {
      style: {
        width: "1200px",
        height: "630px",
        display: "flex",
        flexDirection: "column",
        background: BG,
        color: TEXT,
        fontFamily: "Inter",
      },
    },
    redStripe(),
    buildHeader("Season Scorecard", `${season} Season`),
    h(
      "div",
      {
        style: {
          display: "flex",
          flexDirection: "column",
          flex: 1,
          padding: "8px 56px 0 56px",
          justifyContent: "center",
          gap: "12px",
        },
      },
      h(
        "div",
        { style: { display: "flex", alignItems: "flex-end", gap: "28px" } },
        h(
          "div",
          { style: { display: "flex", alignItems: "flex-end" } },
          h(
            "span",
            {
              style: {
                fontSize: "150px",
                fontWeight: 800,
                color: TEXT,
                lineHeight: 1.0,
              },
            },
            `${hits}`,
          ),
          h(
            "span",
            {
              style: {
                fontSize: "88px",
                fontWeight: 800,
                color: MUTED,
                lineHeight: 1.0,
              },
            },
            ` / ${rounds}`,
          ),
        ),
        h(
          "div",
          {
            style: {
              display: "flex",
              flexDirection: "column",
              paddingBottom: "22px",
              gap: "2px",
            },
          },
          h(
            "div",
            {
              style: {
                fontSize: "30px",
                fontWeight: 800,
                color: F1_RED,
                letterSpacing: "2px",
                textTransform: "uppercase",
              },
            },
            "Race winners",
          ),
          h(
            "div",
            {
              style: {
                fontSize: "30px",
                fontWeight: 800,
                color: TEXT,
                letterSpacing: "2px",
                textTransform: "uppercase",
              },
            },
            "called correctly",
          ),
        ),
      ),
      h(
        "div",
        { style: { display: "flex", gap: "18px", marginTop: "18px" } },
        accStatTile("Podium accuracy", pctLabel(overall.seasonPodiumAccuracyPct)),
        accStatTile(
          "Points finishers",
          pctLabel(overall.seasonPointsAccuracyPct),
        ),
        accStatTile(
          "Finishing order",
          pctLabel(overall.seasonAccuracyPctClassified),
        ),
      ),
    ),
    buildFooter(`How the ${season} forecasts scored against real results`),
  );
}

// -----------------------------------------------------------------------------
// PWA icon set — composited from the 256x256 brand mark onto the site black.
// Uses sharp (ships transitively with Next 16, same as convert-viz-to-webp).
// -----------------------------------------------------------------------------
async function renderIcon(
  size: number,
  markRatio: number,
  outName: string,
): Promise<void> {
  const markSize = Math.round(size * markRatio);
  const mark = await sharp(APP_ICON_SRC)
    .resize(markSize, markSize, {
      fit: "contain",
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    })
    .png()
    .toBuffer();
  await sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background: { r: 10, g: 10, b: 10, alpha: 1 }, // #0a0a0a site black
    },
  })
    .composite([{ input: mark, gravity: "center" }])
    .png()
    .toFile(path.join(ICONS_DIR, outName));
}

async function generatePwaIcons(): Promise<void> {
  if (!fs.existsSync(APP_ICON_SRC)) {
    console.warn(`[og]   skipping PWA icons — source not found: ${APP_ICON_SRC}`);
    return;
  }
  if (!fs.existsSync(ICONS_DIR)) fs.mkdirSync(ICONS_DIR, { recursive: true });
  const t0 = Date.now();
  await renderIcon(192, 0.92, "icon-192.png");
  await renderIcon(512, 0.92, "icon-512.png");
  await renderIcon(512, 0.78, "maskable-512.png");
  await renderIcon(180, 0.88, "apple-touch-icon.png");
  console.log(
    `[og]   icons/ (192, 512, maskable, apple-touch)  ${Date.now() - t0}ms`,
  );
}

// -----------------------------------------------------------------------------
// Render pipeline
// -----------------------------------------------------------------------------
async function renderPng(tree: Node, outPath: string): Promise<number> {
  // satori expects a JSX-like element; our `h()` produces objects that
  // satori's React reconciler accepts at runtime.
  const svg = await satori(tree as unknown as React.ReactNode, {
    width: 1200,
    height: 630,
    fonts: SATORI_FONTS,
  });
  const resvg = new Resvg(svg, {
    background: BG,
    fitTo: { mode: "width", value: 1200 },
  });
  const png = resvg.render().asPng();
  fs.writeFileSync(outPath, png);
  return png.length;
}

function loadRound(round: number): RoundData | null {
  const file = path.join(ROUNDS_DIR, `round_${pad2(round)}.json`);
  if (!fs.existsSync(file)) return null;
  try {
    return JSON.parse(fs.readFileSync(file, "utf-8")) as RoundData;
  } catch {
    return null;
  }
}

function loadDataJson<T>(fileName: string): T | null {
  const file = path.join(DATA_DIR, fileName);
  if (!fs.existsSync(file)) return null;
  try {
    return JSON.parse(fs.readFileSync(file, "utf-8")) as T;
  } catch {
    return null;
  }
}

async function main(): Promise<void> {
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  const seasonFile = path.join(DATA_DIR, "season.json");
  const season = JSON.parse(fs.readFileSync(seasonFile, "utf-8")) as SeasonData;

  console.log(
    `[og] Generating Open Graph images for ${season.totalRounds} rounds + default`
  );

  // PWA icon set (independent of card data — do this first so icons still
  // regenerate even if a data file is missing).
  await generatePwaIcons();

  // Default card
  const defaultStart = Date.now();
  const defaultSize = await renderPng(
    buildDefaultCard(season.season),
    path.join(OUT_DIR, "default.png")
  );
  console.log(
    `[og]   default.png        ${(defaultSize / 1024).toFixed(1)} KB  ${Date.now() - defaultStart}ms`
  );

  // Championship title-race card
  const standings = loadDataJson<StandingsData>("standings.json");
  if (standings?.drivers?.length) {
    const t0 = Date.now();
    const drivers = [...standings.drivers].sort(
      (a, b) => a.position - b.position
    );
    const constructors = [...(standings.constructors ?? [])].sort(
      (a, b) => a.position - b.position
    );
    const size = await renderPng(
      buildStandingsCard({
        season: season.season,
        round: standings.lastUpdatedRound ?? 0,
        totalRounds: season.totalRounds,
        leader: drivers[0],
        runnerUp: drivers[1],
        constructorLeader: constructors[0],
      }),
      path.join(OUT_DIR, "standings.png")
    );
    console.log(
      `[og]   standings.png      ${(size / 1024).toFixed(1)} KB  ${Date.now() - t0}ms`
    );
  } else {
    console.warn("[og]   standings.png      skipped (no standings data)");
  }

  // Season accuracy scorecard ("called X of Y winners")
  const accuracy = loadDataJson<AccuracyReport>("gp_accuracy_report.json");
  if (accuracy?.overallAccuracy) {
    const t0 = Date.now();
    const size = await renderPng(
      buildAccuracyCard({
        season: season.season,
        overall: accuracy.overallAccuracy,
      }),
      path.join(OUT_DIR, "accuracy.png")
    );
    console.log(
      `[og]   accuracy.png       ${(size / 1024).toFixed(1)} KB  ${Date.now() - t0}ms`
    );
  } else {
    console.warn("[og]   accuracy.png       skipped (no accuracy data)");
  }

  // Per-round cards
  for (const entry of season.calendar) {
    const t0 = Date.now();
    const round = loadRound(entry.round);
    const flag = await getFlagDataUrl(entry.country);
    const top3 = (round?.classification ?? []).slice(0, 3).map((c) => ({
      code: c.driver,
      fullName: c.driverFullName,
      team: c.team,
      teamColor: c.teamColor,
    }));
    const size = await renderPng(
      buildRaceCard({
        round: entry.round,
        season: season.season,
        name: entry.name,
        circuit: entry.circuit,
        date: entry.date,
        country: entry.country,
        flagDataUrl: flag,
        top3,
      }),
      path.join(OUT_DIR, `round_${pad2(entry.round)}.png`)
    );
    // Race Theatre (replay) share card for the same round.
    await renderPng(
      buildTheatreCard({
        round: entry.round,
        season: season.season,
        name: entry.name,
        circuit: entry.circuit,
        date: entry.date,
        country: entry.country,
        flagDataUrl: flag,
      }),
      path.join(OUT_DIR, `theatre_${pad2(entry.round)}.png`)
    );
    console.log(
      `[og]   round_${pad2(entry.round)}.png      ${(size / 1024)
        .toFixed(1)
        .padStart(5)} KB  ${Date.now() - t0}ms  ${entry.name} (+theatre)${
        top3.length === 0 ? " (no predictions yet)" : ""
      }`
    );
  }

  console.log("[og] Done.");
}

main().catch((err) => {
  console.error("[og] Failed:", err);
  process.exit(1);
});
