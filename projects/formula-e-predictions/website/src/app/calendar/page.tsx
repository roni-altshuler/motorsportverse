import type { Metadata } from "next";

import CalendarPage from "@/components/CalendarPage";
import { getFEData } from "@/lib/fedata";

export const metadata: Metadata = { title: "Calendar — RaceIQ Formula E" };

export default function Page() {
  const data = getFEData();
  return (
    <CalendarPage
      season={data.season}
      totalRounds={data.totalRounds}
      completedRounds={data.completedRounds}
      calendar={data.calendar}
    />
  );
}
