"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSeason } from "@/lib/SeasonProvider";
import type { TrackRecordData } from "@/lib/trackRecord";
import WinnerTrackRecord from "@/components/ui/WinnerTrackRecord";

export default function SeasonWinnerTrackRecord({ data }: { data: TrackRecordData }) {
  const { year, setYear } = useSeason();
  return <WinnerTrackRecord data={data} season={year} onSeasonChange={setYear} />;
}

export function HistoricalEvaluationNotice() {
  const pathname = usePathname();
  const { year } = useSeason();
  if (!pathname?.replace(/\/$/, "").endsWith("/accuracy")) return null;
  return <aside aria-label="Historical evaluation scope" style={{ maxWidth: 1120, margin: "24px auto", padding: "20px 16px", border: "1px solid var(--border, var(--line))", color: "var(--text, var(--ink))" }}>
    <p className="font-bold">Historical evaluation</p>
    <p className="text-sm mt-2">These saved comparisons and replays do not verify original pre-race publication. Winner percentages here are retrospective; position error and podium/points scores measure other aspects of the ranking.</p>
    <Link href={`/track-record?season=${year}`} className="inline-block underline py-3">Open the pre-race winner track record →</Link>
  </aside>;
}
