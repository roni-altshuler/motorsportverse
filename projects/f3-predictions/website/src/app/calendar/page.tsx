import type { Metadata } from "next";

import CalendarPage from "@/components/CalendarPage";
import { getF3Data } from "@/lib/f3data";

export const metadata: Metadata = { title: "Calendar — RaceIQ F3" };

export default function Page() {
  const data = getF3Data();
  return (
    <CalendarPage
      season={data.season}
      totalRounds={data.totalRounds}
      completedRounds={data.completedRounds}
      calendar={data.calendar}
    />
  );
}
