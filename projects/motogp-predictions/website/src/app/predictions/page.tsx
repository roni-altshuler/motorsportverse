import PublicationHoldNotice from "@/components/PublicationHoldNotice";
import { getPublicationHold } from "@/lib/publication";
import type { Metadata } from "next";

import PredictionsRedirect from "@/components/PredictionsRedirect";
import { getMotogpData } from "@/lib/motogpData";

// The F1 flagship has no standalone /predictions route — the next-round forecast
// lives on the home page and race-detail page. This route is kept only as a
// redirect to the next round (structural 1-of-1 mimic; no dead inbound links).
const pageHold = getPublicationHold();
export const metadata: Metadata = pageHold ? { title: "MotoGP publication withheld", description: pageHold.message } : {
  title: "Predictions — RaceIQ MotoGP",
  robots: { index: false, follow: true },
};

export default function PredictionsPage() {
  const publicationHold = getPublicationHold();
  if (publicationHold) return <PublicationHoldNotice hold={publicationHold} />;
  const data = getMotogpData();
  return <PredictionsRedirect round={data.nextPrediction?.round ?? null} />;
}
