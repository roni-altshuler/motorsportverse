"use client";

/**
 * PredictedVsActualTable — per-round predicted finishing position vs the
 * classified result for one driver.
 *
 * Predicted position comes from each round's `classification`; the actual
 * position + running status come from the same entry's `actualPosition` and the
 * round's `actualStatus` map — all distilled upstream into `DriverRoundResult`.
 * Only rounds with an official result are shown. Each row links through to the
 * full race page. (NASCAR ovals carry no country flag, so this drops F1's flag
 * column and leads with the race name.)
 */
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import type { DriverRoundResult } from "@/lib/driverData";

interface Props {
  results: DriverRoundResult[];
}

/** Colour a predicted-vs-actual delta: green if the driver beat the call. */
function deltaColor(delta: number): string {
  if (delta < 0) return "var(--accent-positive, var(--success))";
  if (delta > 0) return "var(--muted)";
  return "var(--ink)";
}

function statusVariant(
  r: DriverRoundResult,
): "positive" | "negative" | "muted" | "default" {
  if (r.dnf) return "negative";
  return "default";
}

function statusLabel(r: DriverRoundResult): string {
  if (r.status) return r.status;
  return r.completed ? "Classified" : "—";
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
            {["Round", "Race", "Pred.", "Actual", "Δ", "Status", "Pts"].map(
              (h, i) => (
                <th
                  key={h}
                  className={`eyebrow pb-2 border-b border-[color:var(--hairline)] ${
                    i >= 2 && i <= 4 ? "text-center" : ""
                  } ${i === 6 ? "text-right" : ""}`}
                >
                  {h}
                </th>
              ),
            )}
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
                    className="min-w-0 hover:opacity-80 transition-opacity"
                  >
                    <span className="truncate text-[color:var(--ink)]">
                      {r.name}
                    </span>
                  </Link>
                </td>
                <td className="py-2.5 text-center font-tabular text-[color:var(--muted)]">
                  {r.predictedPosition != null ? `P${r.predictedPosition}` : "—"}
                </td>
                <td className="py-2.5 text-center font-tabular font-bold text-[color:var(--ink)]">
                  {r.actualPosition != null ? `P${r.actualPosition}` : "—"}
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
                <td className="py-2.5">
                  <Badge variant={statusVariant(r)}>{statusLabel(r)}</Badge>
                </td>
                <td className="py-2.5 text-right font-tabular text-[color:var(--ink)]">
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
