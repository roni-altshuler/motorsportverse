import Link from "next/link";
import type { RaceCalendarEntry, RoundData } from "@/types";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { resolveDriverHeadshot } from "@/lib/headshots";
import { getGridBaseline } from "@/lib/gridBaseline";

/** A compact readout of observed results and the independent forecast records. */
export default function HeldRaceOverview({
  data,
  race,
}: {
  data: RoundData;
  race: RaceCalendarEntry;
}) {
  const actuals = Object.entries(data.actualResults ?? {}).sort((a, b) => a[1] - b[1]);
  const sessions = data.weekendResults?.sessions ?? [];
  const result = sessions.find((session) => session.kind === "race" && session.rows.length > 0);
  const drivers = new Map(
    sessions.flatMap((session) => session.rows).map((row) => [row.driver, row]),
  );
  const baseline = getGridBaseline(data, race);
  const withdrawn = data.publicationHold?.reason === "event-mismatch";

  return (
    <section
      aria-label="Race overview"
      className="border border-[var(--hairline)] bg-[var(--surface-soft)]"
    >
      <div className="grid sm:grid-cols-[1.2fr_1fr]">
        <div className="p-4 sm:p-5">
          <h2 className="eyebrow text-[var(--muted)] mb-3">
            {actuals.length ? "Recorded race result" : "Race result"}
          </h2>
          {actuals.length ? (
            <ol aria-label="Observed race leaders" className="divide-y divide-[var(--hairline)]">
              {actuals.slice(0, 3).map(([driver, position]) => {
                const row = drivers.get(driver);
                const resultRow = result?.rows.find((entry) => entry.driver === driver);
                return (
                  <li
                    key={driver}
                    className="grid grid-cols-[1.5rem_minmax(0,1fr)_auto] items-center gap-3 py-2"
                  >
                    <span className="font-mono text-xs text-[var(--muted)]">P{position}</span>
                    <div className="flex items-center gap-2 min-w-0">
                      {row && (
                        <DriverPortrait
                          headshotUrl={resolveDriverHeadshot(driver)}
                          driver={driver}
                          driverFullName={row.driverFullName}
                          team={row.team}
                          teamColor={row.teamColor}
                          size={32}
                        />
                      )}
                      <div className="min-w-0">
                        <Link
                          href={`/driver/${driver}`}
                          className="body-sm hover:underline focus-visible:outline-2 focus-visible:outline-offset-4"
                        >
                          {row?.driverFullName || driver}
                        </Link>
                        {row?.team && <p className="text-xs text-[var(--muted)]">{row.team}</p>}
                      </div>
                    </div>
                    <span className="font-mono text-xs text-[var(--muted)]">
                      {resultRow?.position === position
                        ? resultRow.time || resultRow.gap || ""
                        : ""}
                    </span>
                  </li>
                );
              })}
            </ol>
          ) : (
            <p className="body-sm text-[var(--muted)] py-3">
              No race classification is recorded in this round yet.
            </p>
          )}
          {actuals.length > 0 && result && (
            <a
              href={`#${result.key}`}
              className="link-bugatti inline-flex min-h-11 items-center text-sm"
            >
              Full race result →
            </a>
          )}
        </div>
        <div className="border-t sm:border-t-0 sm:border-l border-[var(--hairline)] p-4 sm:p-5">
          <dl className="space-y-4">
            <div>
              <dt className="eyebrow text-[var(--muted)] mb-2">Model forecast</dt>
              <dd className="body-md text-[var(--warning)]">
                {withdrawn ? "Withheld" : "Unavailable"}
              </dd>
              <dd className="body-sm text-[var(--muted)] mt-1">
                {withdrawn
                  ? "Excluded from model accuracy."
                  : "No pre-race model forecast recorded."}
              </dd>
            </div>
            <div>
              <dt className="eyebrow text-[var(--muted)] mb-2">Sealed grid baseline</dt>
              <dd className="body-sm">
                {baseline
                  ? `${baseline.artifact.winnerPick.driverFullName} · P1 starter`
                  : "Not available for this event"}
              </dd>
              {baseline && (
                <dd className="text-xs text-[var(--muted)] mt-1">
                  Pre-race grid order · no win probabilities
                </dd>
              )}
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}
