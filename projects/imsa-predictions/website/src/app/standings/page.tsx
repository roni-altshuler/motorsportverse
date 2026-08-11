import type { Metadata } from "next";

import StandingsView from "@/components/StandingsView";
import { getPointsProgression, getImsaData } from "@/lib/imsaData";

export const metadata: Metadata = {
  title: "Standings — RaceIQ IMSA",
  description:
    "IMSA championship standings by class — GTP, LMP2, GTD PRO and GTD points, wins, podiums, per-round progression, and the mathematical title race.",
};

export default function Page() {
  const data = getImsaData();
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
