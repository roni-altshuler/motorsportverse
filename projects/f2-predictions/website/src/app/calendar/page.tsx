import type { Metadata } from "next";

import CalendarPage from "@/components/CalendarPage";
import { getF2Data } from "@/lib/f2data";

export const metadata: Metadata = { title: "Calendar — RaceIQ F2" };

export default function Page() {
  const data = getF2Data();
  return (
    <CalendarPage
      season={data.season}
      totalRounds={data.totalRounds}
      completedRounds={data.completedRounds}
      calendar={data.calendar}
    />
  );
}
