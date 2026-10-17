import type { Metadata } from "next";
import * as fs from "node:fs";
import * as path from "node:path";
import { Suspense } from "react";
import AccuracyDashboardPage from "@/components/AccuracyDashboardPage";
import CalibrationPanel from "@/components/CalibrationPanel";
import HistoricalBacktestPanel from "@/components/accuracy/HistoricalBacktestPanel";
import { getCalibrationSummary } from "@/lib/calibration";
import { EvidencePanel } from "@/components/ui/EvidencePanel";
import { getEvidence } from "@/lib/evidence";

// ---------------------------------------------------------------------------
// Metadata only. Read at build time (static export) so the share card + the
// description reflect the live "called X of Y winners" headline. The page body
// below is unchanged — AccuracyDashboardPage is owned elsewhere.
// ---------------------------------------------------------------------------
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";
const ACCURACY_DATA_DIR = path.join(process.cwd(), "public", "data");

function readAccuracyJson<T>(file: string): T | null {
  try {
    return JSON.parse(
      fs.readFileSync(path.join(ACCURACY_DATA_DIR, file), "utf-8"),
    ) as T;
  } catch {
    return null;
  }
}

function buildAccuracyMeta(): { title: string; description: string } {
  const season = readAccuracyJson<{ season?: number }>("season.json");
  return {
    title: `F1 ${season?.season ?? new Date().getFullYear()} Historical Evaluation`,
    description: "Saved historical winner comparisons, position errors and podium/points ranking scores. Original pre-race publication timing is not verified here; see the Model track record for eligible winner picks.",
  };
}

const { title: ACCURACY_TITLE, description: ACCURACY_DESC } =
  buildAccuracyMeta();
const OG_ACCURACY = `${BASE_PATH}/og/accuracy.png`;

export const metadata: Metadata = {
  title: ACCURACY_TITLE,
  description: ACCURACY_DESC,
  alternates: { canonical: "/accuracy" },
  openGraph: {
    type: "website",
    title: ACCURACY_TITLE,
    description: ACCURACY_DESC,
    url: "/accuracy",
    images: [
      {
        url: OG_ACCURACY,
        width: 1200,
        height: 630,
        alt: `${ACCURACY_TITLE} — season scorecard`,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: ACCURACY_TITLE,
    description: ACCURACY_DESC,
    images: [OG_ACCURACY],
  },
};

export default function Page() {
  const calibrationSummary = getCalibrationSummary();

  return (
    <>
      <EvidencePanel evidence={getEvidence()} className="mb-10" />
      <Suspense
        fallback={
          <div className="min-h-[60vh] flex items-center justify-center">
            <div
              className="loading-pulse text-lg"
              style={{ color: "var(--text-muted)" }}
            >
              Loading accuracy data...
            </div>
          </div>
        }
      >
        <AccuracyDashboardPage />
      </Suspense>

      <section
        aria-labelledby="historical-heading"
        className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-12"
      >
        <h2
          id="historical-heading"
          className="section-heading"
          style={{ marginBottom: "1rem" }}
        >
          Historical Evaluation
        </h2>
        <HistoricalBacktestPanel />
      </section>

      <section
        aria-labelledby="calibration-heading"
        className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-12"
      >
        <h2
          id="calibration-heading"
          className="section-heading"
          style={{ marginBottom: "1rem" }}
        >
          Forecast Calibration
        </h2>
        <CalibrationPanel summary={calibrationSummary} />
      </section>
    </>
  );
}
