import type { Metadata } from "next";

import CalendarPage from "@/components/CalendarPage";
import { getWrcData } from "@/lib/wrcData";

export const metadata: Metadata = { title: "Calendar — RaceIQ WRC" };

export default function Page() {
  const data = getWrcData();
  return (
    <CalendarPage
      season={data.season}
      totalRounds={data.totalRounds}
      completedRounds={data.completedRounds}
      calendar={data.calendar}
    />
  );
}
