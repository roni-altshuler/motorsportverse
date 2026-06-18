import type { Metadata } from "next";

import PredictionsRedirect from "@/components/PredictionsRedirect";
import { getF2Data } from "@/lib/f2data";

// The F1 flagship has no standalone /predictions route — the next-round forecast
// lives on the home page and race-detail page. This route is kept only as a
// redirect to the next round (structural 1-of-1 mimic; no dead inbound links).
export const metadata: Metadata = {
  title: "Predictions — RaceIQ F2",
  robots: { index: false, follow: true },
};

export default function PredictionsPage() {
  const data = getF2Data();
  return <PredictionsRedirect round={data.nextPrediction?.round ?? null} />;
}
