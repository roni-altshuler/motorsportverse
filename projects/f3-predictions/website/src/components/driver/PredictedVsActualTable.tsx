"use client";

/**
 * PredictedVsActualTable — per-race predicted finishing position vs the
 * classified result for one driver.
 *
 * F3 runs two scored races per round, so each round contributes up to two rows
 * (reversed-grid sprint + merit feature). Predicted position comes from that
 * race's `classification`; the actual position + base points are distilled
 * upstream into `DriverRaceResult`. Only races with an official result are
 * shown, and each row links through to the full race page. Ported from the
 * RaceIQ F1 flagship and adapted to F3's dual-race weekend.
 */
import Link from "next/link";
import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import type { DriverRaceResult } from "@/lib/driverData";

interface Props {
  results: DriverRaceResult[];
}

/** Colour a predicted-vs-actual delta: green if the driver beat the call. */
function deltaColor(delta: number): string {
  if (delta < 0) return "var(--accent-positive, var(--success))";
  if (delta > 0) return "var(--muted)";
  return "var(--ink)";
}

export default function PredictedVsActualTable({ results }: Props) {
  const rows = results.filter((r) => r.completed);

  if (rows.length === 0) {
    return (
      <div className="body-sm text-[color:var(--muted)] py-8 text-center">
        No race results to compare yet this season.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left">
            {["Round", "Race", "Pred.", "Actual", "Δ", "Pts"].map((h, i) => (
              <th
                key={h}
                className={`eyebrow pb-2 border-b border-[color:var(--hairline)] ${
                  i >= 2 && i <= 4 ? "text-center" : ""
                } ${i === 5 ? "text-right" : ""}`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const hasDelta =
              r.predictedPosition != null && r.actualPosition != null;
            const delta = hasDelta
              ? r.actualPosition! - r.predictedPosition!
              : null;
            return (
              <tr
                key={`${r.round}-${r.raceType}`}
                className="border-b border-[color:var(--hairline)] last:border-0 hover:bg-[color:var(--surface-elevated)] transition-colors"
              >
                <td className="py-2.5 font-tabular text-[color:var(--muted)]">
                  <Link
                    href={`/race/${r.round}`}
                    className="hover:text-[color:var(--ink)] transition-colors"
                  >
                    R{r.round}
                  </Link>
                </td>
                <td className="py-2.5">
                  <Link
                    href={`/race/${r.round}`}
                    className="flex items-center gap-2 min-w-0 hover:opacity-80 transition-opacity"
                  >
                    <CountryFlag country={r.country} size={20} />
                    <span className="truncate text-[color:var(--ink)]">
                      {r.venueName}
                    </span>
                    <Badge variant={r.raceType === "feature" ? "live" : "default"}>
                      {r.raceType === "feature" ? "Feature" : "Sprint"}
                    </Badge>
                  </Link>
                </td>
                <td className="py-2.5 text-center font-tabular text-[color:var(--muted)]">
                  {r.predictedPosition != null ? `P${r.predictedPosition}` : "—"}
                </td>
                <td className="py-2.5 text-center font-tabular font-bold text-[color:var(--ink)]">
                  {r.actualPosition != null ? (
                    `P${r.actualPosition}`
                  ) : r.dnf ? (
                    <span className="text-[color:var(--muted)]">DNF</span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="py-2.5 text-center font-tabular">
                  {delta != null ? (
                    <span style={{ color: deltaColor(delta) }}>
                      {delta > 0 ? `+${delta}` : delta}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="py-2.5 text-right font-tabular text-[color:var(--ink)]">
                  {r.points != null && r.points > 0 ? r.points : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
