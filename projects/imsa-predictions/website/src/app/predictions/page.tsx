import type { Metadata } from "next";

import PredictionsView from "@/components/PredictionsView";
import { getImsaData } from "@/lib/imsaData";

export const metadata: Metadata = {
  title: "Next-round forecast — RaceIQ IMSA",
  description:
    "Win and podium probabilities for the next IMSA round, by class — the full GTP, LMP2, GTD PRO and GTD grid with each car's predicted finishing order.",
};

export default function Page() {
  const data = getImsaData();
  return <PredictionsView next={data.nextPrediction} classes={data.classes} />;
}
