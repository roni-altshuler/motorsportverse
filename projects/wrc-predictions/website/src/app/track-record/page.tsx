import SeasonWinnerTrackRecord from "@/components/SeasonWinnerTrackRecord";
import { loadTrackRecord } from "@/lib/trackRecordData";

export const metadata = { title: "Model winner track record", description: "Historical saved winner comparisons and separately verified pre-race picks, with settled results, date coverage and running records." };

export default function TrackRecordPage() {
  return <SeasonWinnerTrackRecord data={loadTrackRecord("wrc")} />;
}
