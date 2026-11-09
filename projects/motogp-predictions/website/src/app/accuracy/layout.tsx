import { getPublicationHold } from "@/lib/publication";
import { HistoricalEvaluationNotice } from "@/components/SeasonWinnerTrackRecord";

export default function HistoricalAccuracyLayout({ children }: { children: React.ReactNode }) {
  if (getPublicationHold()) return children;
  return <><HistoricalEvaluationNotice />{children}</>;
}
