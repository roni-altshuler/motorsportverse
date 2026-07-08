// Sprint grid-flip explainer — F2's answer to the F1 flagship's
// StrategyExplorer. F1 explores tyre-stop strategies (it has a race
// simulator); F2 has no telemetry or strategy data, but it has something F1
// doesn't: a reverse-grid sprint. The top of the feature-qualifying order is
// reversed for the sprint start, so the quickest drivers begin buried in the
// pack and have to carve forward. That flip IS the strategic story of an F2
// weekend, and every input here is real: the feature grid, the sprint grid,
// the model's predicted sprint recovery, and (post-race) the actual result.
//
// The reversal is verified against the two grids before anything is claimed —
// if a scraped grid carries penalties that break the pure flip, the component
// degrades to the plain quali-vs-start table without the "reversed" framing.

import { DriverHeadshot } from "@/components/ui/DriverHeadshot";
import type { ClassificationEntry, GridEntry } from "@/types/f2";

interface FlipRow {
  code: string;
  name: string;
  team: string;
  teamColor: string;
  qualiPos: number;
  sprintStart: number;
  predictedFinish: number | null;
  rangeLow: number | null;
  rangeHigh: number | null;
  actual: number | null;
}

/** Largest N ≤ 14 for which the sprint grid is exactly the feature grid's
 *  top-N reversed (F2 2026 uses 10; detected, not assumed). */
function detectFlipSize(featureGrid: GridEntry[], sprintGrid: GridEntry[]): number {
  const f = featureGrid.map((g) => g.code);
  const s = sprintGrid.map((g) => g.code);
  for (let n = Math.min(14, f.length, s.length); n >= 2; n--) {
    let match = true;
    for (let i = 0; i < n; i++) {
      if (s[i] !== f[n - 1 - i]) {
        match = false;
        break;
      }
    }
    if (match) return n;
  }
  return 0;
}

function DeltaBadge({ from, to }: { from: number; to: number | null }) {
  if (to == null) return <span className="text-[var(--ink-dim)]">—</span>;
  const delta = from - to; // positive = places gained
  if (delta === 0) return <span className="tabular-nums text-[var(--ink-dim)]">·</span>;
  const up = delta > 0;
  return (
    <span
      className="tabular-nums"
      style={{ color: up ? "var(--success)" : "var(--ink-dim)" }}
    >
      {up ? "▲" : "▼"}
      {Math.abs(delta)}
    </span>
  );
}

export function SprintGridFlip({
  featureGrid,
  sprintGrid,
  sprintClassification,
  completed,
}: {
  featureGrid: GridEntry[];
  sprintGrid: GridEntry[];
  sprintClassification: ClassificationEntry[];
  completed: boolean;
}) {
  const flipSize = detectFlipSize(featureGrid, sprintGrid);
  const qualiPos = new Map(featureGrid.map((g) => [g.code, g.position]));
  const byCode = new Map(sprintClassification.map((e) => [e.code, e]));

  const shown = flipSize > 0 ? sprintGrid.slice(0, flipSize) : sprintGrid.slice(0, 10);
  const rows: FlipRow[] = shown.map((g) => {
    const cls = byCode.get(g.code);
    return {
      code: g.code,
      name: g.name,
      team: g.team,
      teamColor: cls?.teamColor ?? "var(--accent)",
      qualiPos: qualiPos.get(g.code) ?? g.position,
      sprintStart: g.position,
      predictedFinish: cls?.position ?? null,
      rangeLow: cls?.finishRangeLow ?? null,
      rangeHigh: cls?.finishRangeHigh ?? null,
      actual: cls?.actualPosition ?? null,
    };
  });
  if (rows.length === 0) return null;

  return (
    <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--hairline)]">
      <div className="border-b border-[var(--hairline)] bg-[var(--surface-2)] px-4 py-3">
        <p className="eyebrow">Sprint grid flip</p>
        <p className="mt-1 text-sm text-[var(--ink-muted)]">
          {flipSize > 0 ? (
            <>
              The sprint grid is the feature-qualifying top {flipSize} reversed — the quickest
              qualifiers start at the back of the flipped group and have to carve through.
              {completed
                ? " Predicted recovery vs where they actually finished:"
                : " Here is how far the model expects each of them to recover:"}
            </>
          ) : (
            <>Sprint starting order vs feature-qualifying position (grid penalties applied).</>
          )}
        </p>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wider text-[var(--ink-dim)]">
            <th className="px-3 py-2 font-medium">Start</th>
            <th className="px-3 py-2 font-medium">Driver</th>
            <th className="hidden px-3 py-2 font-medium sm:table-cell">Quali</th>
            <th className="px-3 py-2 font-medium">Model finish</th>
            {completed && <th className="px-3 py-2 text-right font-medium">Actual</th>}
            <th className="px-3 py-2 text-right font-medium" title="Places gained vs sprint start">
              {completed ? "Gained" : "Proj."}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.code} className="border-t border-[var(--hairline)] bg-[var(--surface)]">
              <td
                className="px-3 py-2 font-bold tabular-nums text-[var(--ink)]"
                style={{ borderLeft: `3px solid ${r.teamColor}` }}
              >
                P{r.sprintStart}
              </td>
              <td className="px-3 py-2">
                <div className="flex items-center gap-2.5">
                  <DriverHeadshot code={r.code} teamColor={r.teamColor} size={26} />
                  <div className="min-w-0">
                    <p className="truncate font-medium text-[var(--ink)]">{r.name}</p>
                    <p className="truncate text-xs text-[var(--ink-dim)]">{r.team}</p>
                  </div>
                </div>
              </td>
              <td className="hidden px-3 py-2 tabular-nums text-[var(--ink-muted)] sm:table-cell">
                Q{r.qualiPos}
              </td>
              <td className="px-3 py-2 tabular-nums text-[var(--ink-muted)]">
                {r.predictedFinish != null ? (
                  <>
                    P{r.predictedFinish}
                    {r.rangeLow != null && r.rangeHigh != null && (
                      <span className="text-xs text-[var(--ink-dim)]">
                        {" "}
                        (P{r.rangeLow}–P{r.rangeHigh})
                      </span>
                    )}
                  </>
                ) : (
                  "—"
                )}
              </td>
              {completed && (
                <td className="px-3 py-2 text-right font-semibold tabular-nums text-[var(--ink)]">
                  {r.actual != null ? `P${r.actual}` : "—"}
                </td>
              )}
              <td className="px-3 py-2 text-right">
                <DeltaBadge from={r.sprintStart} to={completed ? r.actual : r.predictedFinish} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
