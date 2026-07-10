import type { Metadata } from "next";

import CalendarPage from "@/components/CalendarPage";
import { getIndycarData } from "@/lib/indycardata";

export const metadata: Metadata = { title: "Calendar — RaceIQ Indy" };

export default function Page() {
  const data = getIndycarData();
  return (
    <CalendarPage
      season={data.season}
      totalRounds={data.totalRounds}
      completedRounds={data.completedRounds}
      calendar={data.calendar}
    />
  );
}
