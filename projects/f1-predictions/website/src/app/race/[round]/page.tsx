import type { Metadata } from "next";
import * as fs from "node:fs";
import * as path from "node:path";
import RaceDetailPage from "@/components/RaceDetailPage";
import type {
  ClassificationEntry,
  RaceCalendarEntry,
  SeasonData,
} from "@/types";

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

// -------------------------------------------------------------------------
// Server-side data loading (filesystem) for metadata + JSON-LD generation.
// These run at build time only — they're not bundled into the client.
// -------------------------------------------------------------------------
const DATA_DIR = path.join(process.cwd(), "public", "data");

function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

function loadSeason(): SeasonData | null {
  try {
    return JSON.parse(
      fs.readFileSync(path.join(DATA_DIR, "season.json"), "utf-8")
    ) as SeasonData;
  } catch {
    return null;
  }
}

interface RoundFile {
  round: number;
  name: string;
  circuit: string;
  date: string;
  classification: ClassificationEntry[];
}

function loadRound(round: number): RoundFile | null {
  try {
    const file = path.join(DATA_DIR, "rounds", `round_${pad2(round)}.json`);
    if (!fs.existsSync(file)) return null;
    return JSON.parse(fs.readFileSync(file, "utf-8")) as RoundFile;
  } catch {
    return null;
  }
}

export function generateStaticParams() {
  return Array.from({ length: 24 }, (_, i) => ({
    round: String(i + 1),
  }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ round: string }>;
}): Promise<Metadata> {
  const { round: roundStr } = await params;
  const round = parseInt(roundStr, 10);
  const season = loadSeason();
  const calendarEntry: RaceCalendarEntry | undefined = season?.calendar?.find(
    (e) => e.round === round
  );
  const roundData = loadRound(round);

  const raceName = calendarEntry?.name ?? roundData?.name ?? `Round ${round}`;
  const date = calendarEntry?.date ?? roundData?.date ?? "";
  const circuit = calendarEntry?.circuit ?? roundData?.circuit ?? "";
  const seasonYear = season?.season ?? new Date().getFullYear();

  const title = `${raceName} — F1 ${seasonYear} Predictions`;
  const topThree = (roundData?.classification ?? [])
    .slice(0, 3)
    .map((c) => c.driverFullName)
    .filter(Boolean);
  const podiumText =
    topThree.length === 3
      ? `Predicted podium: ${topThree.join(", ")}.`
      : `Predictions for the ${raceName}.`;
  const description =
    `${podiumText} AI-powered Formula 1 race forecast` +
    (circuit ? ` for ${circuit}` : "") +
    (date ? ` on ${date}` : "") +
    ".";

  const ogImage = `${BASE_PATH}/og/round_${pad2(round)}.png`;
  const canonical = `/race/${round}`;

  return {
    title,
    description,
    alternates: { canonical },
    openGraph: {
      type: "article",
      title,
      description,
      url: canonical,
      images: [
        {
          url: ogImage,
          width: 1200,
          height: 630,
          alt: `${raceName} — predicted podium`,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [ogImage],
    },
  };
}

// -------------------------------------------------------------------------
// JSON-LD: schema.org SportsEvent (unlocks Google rich results).
// -------------------------------------------------------------------------
function buildSportsEventJsonLd(round: number): string | null {
  const season = loadSeason();
  const calendarEntry = season?.calendar?.find((e) => e.round === round);
  if (!calendarEntry) return null;
  const roundData = loadRound(round);

  const competitors = (roundData?.classification ?? []).map((c) => ({
    "@type": "Person",
    name: c.driverFullName,
    affiliation: {
      "@type": "SportsTeam",
      name: c.team,
    },
  }));

  const jsonLd: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "SportsEvent",
    name: calendarEntry.name,
    startDate: calendarEntry.date,
    sport: "Formula 1",
    eventStatus: calendarEntry.postponed
      ? "https://schema.org/EventPostponed"
      : "https://schema.org/EventScheduled",
    eventAttendanceMode: "https://schema.org/OfflineEventAttendanceMode",
    location: {
      "@type": "Place",
      name: calendarEntry.circuit,
      address: {
        "@type": "PostalAddress",
        addressCountry: calendarEntry.country,
      },
    },
    organizer: {
      "@type": "Organization",
      name: "Formula 1",
      url: "https://www.formula1.com",
    },
  };
  if (competitors.length > 0) {
    jsonLd.competitor = competitors;
  }
  return JSON.stringify(jsonLd);
}

export default async function Page({
  params,
}: {
  params: Promise<{ round: string }>;
}) {
  const { round } = await params;
  const roundNum = parseInt(round, 10);
  const jsonLd = buildSportsEventJsonLd(roundNum);

  return (
    <>
      {jsonLd && (
        <script
          type="application/ld+json"
          // JSON.stringify already escapes well-enough; we trust our own data.
          dangerouslySetInnerHTML={{ __html: jsonLd }}
        />
      )}
      <RaceDetailPage round={roundNum} />
    </>
  );
}
