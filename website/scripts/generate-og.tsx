/**
 * generate-og.tsx
 *
 * Renders 1200x630 Open Graph images for the F1 Predictions site.
 *
 *   - public/og/default.png             site-wide fallback
 *   - public/og/round_NN.png            one per round (1..totalRounds)
 *
 * Reads input from public/data/season.json and public/data/rounds/round_NN.json.
 * Runs during the `prebuild` npm script via tsx, so PNGs are regenerated
 * before each `next build`.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";

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
        "F1 Predictions"
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
        "f1-predictions"
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
        "F1 Predictions"
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
        "AI and machine-learning powered race forecasts, championship standings, pit-strategy simulations, and value-finder bets for every Grand Prix."
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
          "Race predictions * Standings * Accuracy * Value bets"
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
        "f1-predictions"
      )
    )
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

async function main(): Promise<void> {
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  const seasonFile = path.join(DATA_DIR, "season.json");
  const season = JSON.parse(fs.readFileSync(seasonFile, "utf-8")) as SeasonData;

  console.log(
    `[og] Generating Open Graph images for ${season.totalRounds} rounds + default`
  );

  // Default card
  const defaultStart = Date.now();
  const defaultSize = await renderPng(
    buildDefaultCard(season.season),
    path.join(OUT_DIR, "default.png")
  );
  console.log(
    `[og]   default.png        ${(defaultSize / 1024).toFixed(1)} KB  ${Date.now() - defaultStart}ms`
  );

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
    console.log(
      `[og]   round_${pad2(entry.round)}.png      ${(size / 1024)
        .toFixed(1)
        .padStart(5)} KB  ${Date.now() - t0}ms  ${entry.name}${
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
