"use client";

/**
 * Stage results — NASCAR-specific surface. Cup races run in three stages; the
 * top ten of each stage score stage points that feed both the season standings
 * and playoff seeding. Completed rounds ship `stageResults` (top ten + points
 * per stage), rendered here as side-by-side stage columns.
 */
import HUDPanel from "@/components/ui/HUDPanel";
import { DriverHeadshot } from "@/components/ui/DriverHeadshot";
import { teamColor } from "@/lib/teams";
import type { ClassificationEntry, StageResultEntry } from "@/types/nascar";

export default function StageResultsPanel({
  stageResults,
  classification,
  stageLaps = null,
}: {
  stageResults: Record<string, StageResultEntry[]>;
  classification: ClassificationEntry[];
  stageLaps?: number[] | null;
}) {
  const stages = Object.keys(stageResults)
    .sort((a, b) => Number(a) - Number(b))
    .map((k) => ({ stage: Number(k), rows: stageResults[k] ?? [] }))
    .filter((s) => s.rows.length > 0);
  if (stages.length === 0) return null;

  // Resolve names/teams from the classification (stage rows only carry codes).
  const byCode = new Map(classification.map((e) => [e.code, e]));

  return (
    <div className="mt-8">
      <HUDPanel
        kicker="Stage Racing"
        title="Stage Results"
        bodyClassName="p-4 sm:p-5"
      >
        <p className="body-sm mb-4 text-[color:var(--muted)]">
          The top ten of each stage score championship points — stage racing is
          where consistent speed shows up before the finish does.
        </p>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {stages.map(({ stage, rows }) => (
            <div
              key={stage}
              className="overflow-hidden rounded-[var(--radius-card)] border border-[var(--hairline)]"
            >
              <div className="flex items-baseline justify-between bg-[var(--surface-2)] px-3 py-2">
                <p className="eyebrow">Stage {stage}</p>
                {stageLaps && stageLaps[stage - 1] != null && (
                  <p className="font-mono text-[11px] text-[color:var(--muted)]">
                    {stageLaps[stage - 1]} laps
                  </p>
                )}
              </div>
              <table className="w-full text-sm">
                <tbody>
                  {rows.map((r) => {
                    const entry = byCode.get(r.code);
                    const color = entry?.teamColor ?? teamColor(entry?.team ?? "");
                    return (
                      <tr
                        key={r.code}
                        className="border-t border-[var(--hairline)] bg-[var(--surface)]"
                      >
                        <td
                          className="w-8 px-2 py-1.5 font-bold tabular-nums text-[var(--ink)]"
                          style={{ borderLeft: `3px solid ${color}` }}
                        >
                          {r.position}
                        </td>
                        <td className="px-2 py-1.5">
                          <div className="flex items-center gap-2">
                            <DriverHeadshot code={r.code} teamColor={color} size={22} />
                            <span className="truncate text-[var(--ink-muted)]">
                              {entry?.name ?? r.code}
                            </span>
                          </div>
                        </td>
                        <td className="px-2 py-1.5 text-right font-mono text-xs tabular-nums text-[var(--ink-dim)]">
                          +{Math.round(r.points)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      </HUDPanel>
    </div>
  );
}
