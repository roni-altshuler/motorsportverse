"use client";

/**
 * PredictedVsActualTable — per-round predicted finishing position vs the
 * classified result for one driver (Formula E).
 *
 * Predicted position comes from each round's `classification[*].position`; the
 * actual position + points come from the same row's `actualPosition` (with the
 * round's `actualResults` as a fallback) — all distilled upstream into
 * `DriverRoundResult`. Only rounds with an official result are shown. Each row
 * links to the full race page. Doubleheader rounds (two rounds sharing a venue)
 * carry a small race-index chip so the two are never conflated.
 *
 * Formula E publishes no per-driver finish status (Finished/Retired/DNS), so —
 * unlike the F1 profile — there is no Status column here. We show only what the
 * data supports.
 */
import Link from "next/link";
import CountryFlag from "@/components/CountryFlag";
import type { DriverRoundResult } from "@/lib/driverData";

interface Props {
  results: DriverRoundResult[];
}

/** Colour a predicted-vs-actual delta: green if the driver beat the call. */
function deltaColor(delta: number): string {
  if (delta < 0) return "var(--accent-positive)";
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
            {["Round", "E-Prix", "Pred.", "Actual", "Δ", "Pts"].map((h, i) => (
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
                key={r.round}
                className="border-b border-[color:var(--hairline)] last:border-0 hover:bg-[color:var(--surface-elevated)] transition-colors"
              >
                <td className="py-2.5 font-mono tabular-nums text-[color:var(--muted)]">
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
                    {r.dhIndex != null && (
                      <span
                        className="shrink-0 font-mono text-[10px] uppercase tracking-[0.12em] px-1.5 py-0.5 border border-[color:var(--hairline-strong)] text-[color:var(--muted)]"
                        title={`Doubleheader — race ${r.dhIndex} of ${r.dhCount}`}
                      >
                        R{r.dhIndex}
                      </span>
                    )}
                  </Link>
                </td>
                <td className="py-2.5 text-center font-mono tabular-nums text-[color:var(--muted)]">
                  {r.predictedPosition != null ? `P${r.predictedPosition}` : "—"}
                </td>
                <td className="py-2.5 text-center font-mono tabular-nums font-bold text-[color:var(--ink)]">
                  {r.actualPosition != null ? `P${r.actualPosition}` : "—"}
                </td>
                <td className="py-2.5 text-center font-mono tabular-nums">
                  {delta != null ? (
                    <span style={{ color: deltaColor(delta) }}>
                      {delta > 0 ? `+${delta}` : delta}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="py-2.5 text-right font-mono tabular-nums text-[color:var(--ink)]">
                  {r.points != null ? r.points : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
