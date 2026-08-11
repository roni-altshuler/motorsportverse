import type { Metadata } from "next";

import PredictionsView from "@/components/PredictionsView";
import { getWecData } from "@/lib/wecData";

export const metadata: Metadata = {
  title: "Next-round forecast — RaceIQ WEC",
  description:
    "Win and podium probabilities for the next FIA WEC round, by class — the full Hypercar and LMGT3 grid with each car's predicted finishing order.",
};

export default function Page() {
  const data = getWecData();
  return <PredictionsView next={data.nextPrediction} classes={data.classes} />;
}
