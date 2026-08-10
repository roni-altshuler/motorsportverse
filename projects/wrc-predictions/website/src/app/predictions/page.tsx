import type { Metadata } from "next";

import PredictionsRedirect from "@/components/PredictionsRedirect";
import { getWrcData } from "@/lib/wrcData";

// There is no standalone /predictions route — the next-rally forecast lives on
// the home page and the rally-detail page. This route is kept only as a redirect
// to the next round (structural mimic; no dead inbound links).
export const metadata: Metadata = {
  title: "Rally Predictions — RaceIQ WRC",
  robots: { index: false, follow: true },
};

export default function PredictionsPage() {
  const data = getWrcData();
  return <PredictionsRedirect round={data.nextPrediction?.round ?? null} />;
}
