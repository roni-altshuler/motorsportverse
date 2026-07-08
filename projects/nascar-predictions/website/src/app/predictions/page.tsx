import type { Metadata } from "next";

import PredictionsRedirect from "@/components/PredictionsRedirect";
import { getNascarData } from "@/lib/nascardata";

// The F1 flagship has no standalone /predictions route — the next-round forecast
// lives on the home page and race-detail page. This route is kept only as a
// redirect to the next round (structural 1-of-1 mimic; no dead inbound links).
export const metadata: Metadata = {
  title: "Predictions — RaceIQ NASCAR",
  robots: { index: false, follow: true },
};

export default function PredictionsPage() {
  const data = getNascarData();
  return <PredictionsRedirect round={data.nextPrediction?.round ?? null} />;
}
