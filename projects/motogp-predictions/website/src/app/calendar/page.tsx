import PublicationHoldNotice from "@/components/PublicationHoldNotice";
import { getPublicationHold } from "@/lib/publication";
import type { Metadata } from "next";

import CalendarPage from "@/components/CalendarPage";
import { getMotogpData } from "@/lib/motogpData";

const pageHold = getPublicationHold();
export const metadata: Metadata = pageHold ? { title: "MotoGP publication withheld", description: pageHold.message } : { title: "Calendar — RaceIQ MotoGP" };

export default function Page() {
  const publicationHold = getPublicationHold();
  if (publicationHold) return <PublicationHoldNotice hold={publicationHold} />;
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
