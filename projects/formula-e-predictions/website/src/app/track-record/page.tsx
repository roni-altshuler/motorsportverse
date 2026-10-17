import SeasonWinnerTrackRecord from "@/components/SeasonWinnerTrackRecord";
import { loadTrackRecord } from "@/lib/trackRecordData";

export const metadata = { title: "Model winner track record", description: "Original pre-race winner picks, settled results, coverage and accuracy over time." };

export default function TrackRecordPage() {
  return <SeasonWinnerTrackRecord data={loadTrackRecord("formula-e")} />;
}
