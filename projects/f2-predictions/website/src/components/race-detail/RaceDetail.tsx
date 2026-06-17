"use client";

import { useState } from "react";

import { FinishProbabilityHeatmap } from "@/components/charts/FinishProbabilityHeatmap";
import { HeadToHeadMatrix } from "@/components/charts/HeadToHeadMatrix";
import { PodiumProbabilityChart } from "@/components/charts/PodiumProbabilityChart";
import { DriverHeadshot } from "@/components/ui/DriverHeadshot";
import type { ProbabilitiesRound, RaceBlock, RoundDetail } from "@/types/f2";

type RaceKey = "feature" | "sprint";

export function RaceDetail({
  round,
  probabilities,
}: {
  round: RoundDetail;
  probabilities: ProbabilitiesRound | null;
}) {
  const [tab, setTab] = useState<RaceKey>("feature");
  const block = round[tab];
  const probs = probabilities?.[tab] ?? null;

  return (
    <div>
      {/* Weekend session tabs — F2's two scored races. */}
      <div className="mb-6 flex gap-2">
        {(["feature", "sprint"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className="rounded-full border px-4 py-1.5 text-sm font-medium capitalize"
            style={{
              color: tab === t ? "var(--accent-ink)" : "var(--ink-muted)",
              backgroundColor: tab === t ? "var(--accent)" : "transparent",
              borderColor: tab === t ? "var(--accent)" : "var(--hairline)",
            }}
          >
            {t === "feature" ? "Feature race" : "Sprint race"}
          </button>
        ))}
      </div>

      {tab === "sprint" && (
        <p className="mb-5 rounded-[var(--radius-md)] border border-[var(--hairline)] bg-[var(--surface-2)] px-4 py-3 text-sm text-[var(--ink-muted)]">
          The sprint grid is the feature-qualifying top {Math.min(10, block.grid.length)} reversed,
          so the quickest drivers start at the back and have to carve through — that&rsquo;s why the
          sprint is the more open race.
        </p>
      )}

      <Classification block={block} completed={round.completed} />

      {/* Deep dive — model probabilities, opt-in like F1's <details> panels. */}
      <details className="group mt-8 rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)]">
        <summary className="cursor-pointer select-none px-5 py-4 text-sm font-semibold text-[var(--ink)]">
          Deep dive — model probabilities
        </summary>
        <div className="space-y-10 border-t border-[var(--hairline)] px-5 py-6">
          <PodiumProbabilityChart
            rows={block.classification.slice(0, 12).map((e) => ({
              code: e.code,
              name: e.name,
              team: e.team,
              teamColor: e.teamColor,
              pWin: e.pWin,
              pPodium: e.pPodium,
            }))}
          />
          <FinishProbabilityHeatmap
            rows={block.classification.map((e) => ({
              code: e.code,
              name: e.name,
              teamColor: e.teamColor,
              meanFinish: e.meanFinish,
              finishRangeLow: e.finishRangeLow,
              finishRangeHigh: e.finishRangeHigh,
              actualPosition: e.actualPosition,
            }))}
            maxPosition={block.classification.length}
            completed={round.completed}
          />
          {probs && (
            <div>
              <p className="eyebrow mb-3">Head-to-head — P(row beats column)</p>
              <HeadToHeadMatrix h2h={probs.h2h} />
            </div>
          )}
        </div>
      </details>
    </div>
  );
}

function Classification({ block, completed }: { block: RaceBlock; completed: boolean }) {
  const maxWin = Math.max(0.0001, ...block.classification.map((e) => e.pWin));
  return (
    <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--hairline)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-[var(--surface-2)] text-left text-xs uppercase tracking-wider text-[var(--ink-dim)]">
            <th className="px-3 py-3 font-medium">P</th>
            <th className="px-3 py-3 font-medium">Driver</th>
            <th className="hidden px-3 py-3 font-medium sm:table-cell">Win</th>
            <th className="hidden px-3 py-3 font-medium md:table-cell">Podium</th>
            <th className="hidden px-3 py-3 font-medium md:table-cell">Range</th>
            <th className="hidden px-3 py-3 font-medium lg:table-cell">Confidence</th>
            {completed && <th className="px-3 py-3 text-right font-medium">Actual</th>}
          </tr>
        </thead>
        <tbody>
          {block.classification.map((e) => (
            <tr
              key={e.code}
              className="border-t border-[var(--hairline)] bg-[var(--surface)] hover:bg-[var(--surface-2)]"
            >
              <td
                className="px-3 py-2.5 font-bold text-[var(--ink)]"
                style={{ borderLeft: `3px solid ${e.teamColor}` }}
              >
                {e.position}
              </td>
              <td className="px-3 py-2.5">
                <div className="flex items-center gap-2.5">
                  <DriverHeadshot code={e.code} teamColor={e.teamColor} size={30} />
                  <div className="min-w-0">
                    <p className="truncate font-medium text-[var(--ink)]">{e.name}</p>
                    <p className="truncate text-xs text-[var(--ink-dim)]">{e.team}</p>
                  </div>
                </div>
              </td>
              <td className="hidden px-3 py-2.5 sm:table-cell">
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-16 overflow-hidden rounded-full bg-[var(--surface-3)]">
                    <span
                      className="block h-1.5 rounded-full"
                      style={{ width: `${(e.pWin / maxWin) * 100}%`, backgroundColor: "var(--accent)" }}
                    />
                  </span>
                  <span className="tabular-nums text-[var(--ink-muted)]">
                    {(e.pWin * 100).toFixed(0)}%
                  </span>
                </div>
              </td>
              <td className="hidden px-3 py-2.5 tabular-nums text-[var(--ink-muted)] md:table-cell">
                {(e.pPodium * 100).toFixed(0)}%
              </td>
              <td className="hidden px-3 py-2.5 tabular-nums text-[var(--ink-muted)] md:table-cell">
                P{e.finishRangeLow}–P{e.finishRangeHigh}
              </td>
              <td className="hidden px-3 py-2.5 lg:table-cell">
                <span
                  className="rounded-full px-2 py-0.5 text-xs"
                  style={{
                    color: "var(--ink-muted)",
                    border: "1px solid var(--hairline-strong)",
                  }}
                >
                  {e.confidence}
                </span>
              </td>
              {completed && (
                <td className="px-3 py-2.5 text-right font-semibold text-[var(--ink)]">
                  {e.actualPosition ? `P${e.actualPosition}` : "—"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
