import type { Metadata } from "next";
import Link from "next/link";

import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { getWecData } from "@/lib/wecData";

export const metadata: Metadata = {
  title: "Calendar — RaceIQ WEC",
  description:
    "The FIA World Endurance Championship season calendar — every round from the 6-hour races to the 24 Hours of Le Mans, with completed and upcoming status.",
};

export default function Page() {
  const data = getWecData();
  const next = data.nextPrediction;
  const remaining =
    data.championship[data.classes[0]?.key ?? ""]?.remainingRounds ?? null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <header className="mb-8">
        <p className="eyebrow mb-2">Season {data.season}</p>
        <h1 className="display-lg">Calendar</h1>
        <p className="body-md mt-3 max-w-2xl text-[color:var(--muted)]">
          The endurance season runs from the 6-hour rounds to the 24 Hours of Le Mans, the crown
          jewel. Completed rounds link through to their predicted-vs-actual classification.
        </p>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {data.calendar.map((r) => (
          <Link key={r.round} href={`/round/${r.round}`}>
            <Card
              interactive
              className={`p-5 h-full ${r.isLeMans ? "podium-leader-card" : ""}`}
            >
              {r.isLeMans && <div className="podium-leader-accent" />}
              <div className="flex items-center justify-between mb-4">
                <span className="eyebrow">Round {r.round}</span>
                {r.isLeMans ? (
                  <Badge
                    variant="live"
                    className="!text-[color:var(--accent-podium-1)] !border-[color:var(--accent-podium-1)]"
                  >
                    24 Hours
                  </Badge>
                ) : (
                  <Badge variant="positive">Completed</Badge>
                )}
              </div>
              <div className="flex items-center gap-3">
                <CountryFlag country={r.country} size={40} />
                <div className="min-w-0">
                  <h2 className="title-md truncate">{r.name}</h2>
                  <p className="text-[12px] text-[color:var(--muted)] truncate">
                    {r.place}
                    {r.country ? ` · ${r.country}` : ""}
                  </p>
                </div>
              </div>
              {r.isLeMans && (
                <p className="mt-4 pt-3 border-t border-[color:var(--hairline)] body-sm text-[color:var(--muted)]">
                  The 24-hour endurance classic — the biggest points and the season&rsquo;s defining
                  test of car and crew.
                </p>
              )}
            </Card>
          </Link>
        ))}

        {next && (
          <Link href="/predictions">
            <Card interactive className="p-5 h-full border-dashed">
              <div className="flex items-center justify-between mb-4">
                <span className="eyebrow">Round {next.round}</span>
                <Badge variant="live">Next · forecast</Badge>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-3xl" aria-hidden>
                  🏁
                </span>
                <div className="min-w-0">
                  <h2 className="title-md truncate">{next.place}</h2>
                  <p className="text-[12px] text-[color:var(--muted)]">Forecast ready — view predictions</p>
                </div>
              </div>
            </Card>
          </Link>
        )}
      </div>

      {remaining != null && remaining > 0 && (
        <p className="mt-8 text-[12px] text-[color:var(--muted-soft)] max-w-2xl">
          {data.completedRounds} round{data.completedRounds === 1 ? "" : "s"} completed ·{" "}
          {remaining} still to run this season. Upcoming venues are added to the calendar as the
          schedule is confirmed.
        </p>
      )}
    </div>
  );
}
