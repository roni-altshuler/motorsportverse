import type { Metadata } from "next";

import StandingsView from "@/components/StandingsView";
import { getPointsProgression, getWecData } from "@/lib/wecData";

export const metadata: Metadata = {
  title: "Standings — RaceIQ WEC",
  description:
    "FIA WEC championship standings by class — Hypercar and LMGT3 points, wins, podiums, per-round progression, and the mathematical title race.",
};

export default function Page() {
  const data = getWecData();
  const progression = getPointsProgression();
  return (
    <StandingsView
      classes={data.classes}
      standings={data.standings}
      championship={data.championship}
      progression={progression}
    />
  );
}
