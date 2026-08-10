import type { Metadata } from "next";

import CalendarPage from "@/components/CalendarPage";
import { getMotogpData } from "@/lib/motogpData";

export const metadata: Metadata = { title: "Calendar — RaceIQ MotoGP" };

export default function Page() {
  const data = getMotogpData();
  return (
    <CalendarPage
      season={data.season}
      totalRounds={data.totalRounds}
      completedRounds={data.completedRounds}
      calendar={data.calendar}
    />
  );
}
