import PublicationHoldNotice from "@/components/PublicationHoldNotice";
import { getPublicationHold } from "@/lib/publication";
import SeasonWinnerTrackRecord from "@/components/SeasonWinnerTrackRecord";
import { loadTrackRecord } from "@/lib/trackRecordData";

const pageHold = getPublicationHold();
export const metadata = pageHold ? { title: "MotoGP publication withheld", description: pageHold.message } : { title: "Model winner track record", description: "Historical saved winner comparisons and separately verified pre-race picks, with settled results, date coverage and running records." };

export default function TrackRecordPage() {
  const publicationHold = getPublicationHold();
  if (publicationHold) return <PublicationHoldNotice hold={publicationHold} />;
  return <SeasonWinnerTrackRecord data={loadTrackRecord("motogp")} />;
}
