"use client";

/**
 * PredictedVsActualTable — per-rally predicted finishing position vs the
 * classified result for one crew.
 *
 * WRC runs a single scored classification per round, so each completed rally
 * contributes exactly one row. Predicted position comes from that rally's
 * `classification`; the actual position + base points are distilled upstream
 * into `DriverRaceResult`. Only rallies with an official result are shown, each
 * row carries its surface (gravel / tarmac / snow) and links through to the full
 * rally page. Ported from the RaceIQ F1 flagship and adapted to WRC's one-rally
 * weekend.
 */
import Link from "next/link";
import CountryFlag from "@/components/CountryFlag";
import type { DriverRaceResult } from "@/lib/driverData";
import { surfaceColor, surfaceLabel } from "@/lib/surface";

interface Props {
  results: DriverRaceResult[];
}

/** Colour a predicted-vs-actual delta: green if the crew beat the call. */
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
        No rally results to compare yet this season.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left">
            {["Round", "Rally", "Pred.", "Actual", "Δ", "Pts"].map((h, i) => (
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
            const chip = surfaceColor(r.surface);
            return (
              <tr
                key={r.round}
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
                    <span
                      className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em]"
                      style={{
                        color: chip,
                        border: `1px solid color-mix(in srgb, ${chip} 45%, transparent)`,
                        background: `color-mix(in srgb, ${chip} 12%, transparent)`,
                      }}
                    >
                      {surfaceLabel(r.surface)}
                    </span>
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
