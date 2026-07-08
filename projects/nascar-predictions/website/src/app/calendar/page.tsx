import type { Metadata } from "next";

import CalendarPage from "@/components/CalendarPage";
import { getNascarData } from "@/lib/nascardata";

export const metadata: Metadata = { title: "Calendar — RaceIQ NASCAR" };

export default function Page() {
  const data = getNascarData();
  return (
    <CalendarPage
      season={data.season}
      totalRounds={data.totalRounds}
      completedRounds={data.completedRounds}
      calendar={data.calendar}
    />
  );
}
