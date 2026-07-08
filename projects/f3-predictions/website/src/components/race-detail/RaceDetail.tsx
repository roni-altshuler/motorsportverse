"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { FinishProbabilityHeatmap } from "@/components/charts/FinishProbabilityHeatmap";
import { HeadToHeadMatrix } from "@/components/charts/HeadToHeadMatrix";
import { PodiumProbabilityChart } from "@/components/charts/PodiumProbabilityChart";
import DriverDetailSheet from "@/components/DriverDetailSheet";
import HUDHeader from "@/components/race-detail/HUDHeader";
import PodiumPredictionTrio from "@/components/race-detail/PodiumPredictionTrio";
import RaceVolatilityBadge from "@/components/race-detail/RaceVolatilityBadge";
import TrackMapWithOverlay from "@/components/race-detail/TrackMapWithOverlay";
import { DriverHeadshot } from "@/components/ui/DriverHeadshot";
import HUDPanel from "@/components/ui/HUDPanel";
import { fetchF3Data, fetchRoundDetail, fetchRoundProbabilities } from "@/lib/f3client";
import { useSeason } from "@/lib/SeasonProvider";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { CircuitGeometry } from "@/types/circuit";
import type {
  ClassificationEntry,
  DriverStanding,
  ProbabilitiesRound,
  RaceBlock,
  RoundDetail,
} from "@/types/f3";

type RaceKey = "feature" | "sprint";

export function RaceDetail({
  round: bakedRound,
  probabilities: bakedProbabilities,
  geometry = null,
  driverStandings: bakedStandings = [],
}: {
  round: RoundDetail;
  probabilities: ProbabilitiesRound | null;
  geometry?: CircuitGeometry | null;
  driverStandings?: DriverStanding[];
}) {
  const reduced = useReducedMotion();
  const [tab, setTab] = useState<RaceKey>("feature");
  // Which classification row's detail sheet is open (driver code).
  const [openDriver, setOpenDriver] = useState<string | null>(null);

  // Multi-season: the page is baked with the CURRENT season's round data
  // (static export). When the SeasonSwitcher selects an archived season, that
  // season's round + probabilities + standings overlay the baked props
  // client-side (mirrors F1's RaceDetailPage useSeason wiring). Geometry stays
  // baked — circuits.json is season-independent.
  const { basePath, year, index } = useSeason();
  const isArchived = !!index && year !== index.current;
  const [overlay, setOverlay] = useState<{
    round: RoundDetail;
    probabilities: ProbabilitiesRound | null;
    driverStandings: DriverStanding[];
  } | null>(null);

  useEffect(() => {
    if (!isArchived) {
      setOverlay(null);
      return;
    }
    let active = true;
    Promise.all([
      fetchRoundDetail(bakedRound.round, basePath),
      fetchRoundProbabilities(bakedRound.round, basePath),
      fetchF3Data(basePath),
    ]).then(([r, p, d]) => {
      if (!active) return;
      setOverlay(
        r ? { round: r, probabilities: p, driverStandings: d?.driverStandings ?? [] } : null
      );
    });
    return () => {
      active = false;
    };
  }, [isArchived, basePath, bakedRound.round]);

  const round = (isArchived && overlay?.round) || bakedRound;
  const probabilities = isArchived && overlay ? overlay.probabilities : bakedProbabilities;
  const driverStandings =
    isArchived && overlay ? overlay.driverStandings : bakedStandings;

  const block = round[tab];
  const probs = probabilities?.[tab] ?? null;
  const raceLabel = tab === "feature" ? "Feature race" : "Sprint race";
  const openEntry: ClassificationEntry | null =
    openDriver != null ? block.classification.find((e) => e.code === openDriver) ?? null : null;

  return (
    <div>
      {/* Telemetry-framed header (round / venue / country / status + dual-race). */}
      <HUDHeader
        round={round.round}
        name={round.venueName}
        country={round.country}
        completed={round.completed}
        activeRace={tab}
        dataSource={round.dataSource}
      />

      {/* Primary race tabs — F3's two scored races (Feature + Sprint). */}
      <div className="mb-6 flex gap-2">
        {(["feature", "sprint"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => {
              setTab(t);
              setOpenDriver(null);
            }}
            aria-pressed={tab === t}
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

      {/* Predicted (or official) podium trio for the active race. */}
      <PodiumPredictionTrio classification={block.classification} completed={round.completed} />

      {/* Win-probability board (win vs podium) — leads the data, like the F1 page. */}
      <div className="mb-8">
        <HUDPanel
          kicker="Probability Layer"
          title="Win vs Podium"
          rightSlot={<RaceVolatilityBadge classification={block.classification} />}
          bodyClassName="p-4 sm:p-5"
        >
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
        </HUDPanel>
      </div>

      {/* Classification table — every row opens the driver detail sheet. */}
      <Classification
        block={block}
        completed={round.completed}
        onSelect={(code) => setOpenDriver(code)}
      />

      {/* ───── Deep Dive accordions (native <details>, styled .deep-dive-section). ───── */}
      <div className="mt-8">
        {/* Model Forecast */}
        <details className="deep-dive-section">
          <summary className="deep-dive-summary">Model Forecast</summary>
          <div className="deep-dive-section-body">
            <motion.div
              className="space-y-6"
              initial={reduced ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
                {(() => {
                  const top = block.classification[0];
                  const highConf = block.classification.filter(
                    (e) => e.confidence.toLowerCase() === "high",
                  ).length;
                  return (
                    <>
                      <div className="metric-card">
                        <p className="eyebrow mb-1">Likeliest Winner</p>
                        <p className="title-md">{top ? top.name : "—"}</p>
                        {top && (
                          <p className="body-sm mt-1 text-[color:var(--muted)]">
                            {(top.pWin * 100).toFixed(1)}% projected win
                          </p>
                        )}
                      </div>
                      <div className="metric-card">
                        <p className="eyebrow mb-1">High-Confidence Calls</p>
                        <p className="title-md text-[color:var(--accent-positive)]">{highConf}</p>
                      </div>
                      <div className="metric-card">
                        <p className="eyebrow mb-1">Drivers Forecast</p>
                        <p className="title-md">{block.classification.length}</p>
                      </div>
                      <div className="metric-card">
                        <p className="eyebrow mb-1">Race</p>
                        <p className="title-md">{raceLabel}</p>
                      </div>
                    </>
                  );
                })()}
              </div>
              <p className="body-sm text-[color:var(--muted)]">
                Tap any row in the classification above to open a driver&rsquo;s per-race
                forecast and season form.
              </p>
            </motion.div>
          </div>
        </details>

        {/* Circuit & Telemetry — framed track map (F3 has no live telemetry). */}
        <details className="deep-dive-section">
          <summary className="deep-dive-summary">Circuit &amp; Telemetry</summary>
          <div className="deep-dive-section-body">
            <motion.div
              initial={reduced ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <TrackMapWithOverlay
                geometry={geometry}
                kicker="Circuit"
                title={round.venueName}
                className=""
              />
              <p className="body-sm mt-4 text-[color:var(--muted)]">
                F3 races the same circuits as the lead category; layout geometry is shared.
                Per-lap telemetry (speed traps, sector times, tyre stints) isn&rsquo;t published
                for F3, so this round focuses on the forecast itself.
              </p>
            </motion.div>
          </div>
        </details>

        {/* Charts */}
        <details className="deep-dive-section">
          <summary className="deep-dive-summary">Charts</summary>
          <div className="deep-dive-section-body">
            <motion.div
              className="space-y-10"
              initial={reduced ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
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
            </motion.div>
          </div>
        </details>
      </div>

      {/* Driver detail pop-out. */}
      <DriverDetailSheet
        entry={openEntry}
        driverStandings={driverStandings}
        raceLabel={raceLabel}
        onClose={() => setOpenDriver(null)}
      />
    </div>
  );
}

function Classification({
  block,
  completed,
  onSelect,
}: {
  block: RaceBlock;
  completed: boolean;
  onSelect: (code: string) => void;
}) {
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
              role="button"
              tabIndex={0}
              aria-label={`Open ${e.name} forecast detail`}
              onClick={() => onSelect(e.code)}
              onKeyDown={(ev) => {
                if (ev.key === "Enter" || ev.key === " ") {
                  ev.preventDefault();
                  onSelect(e.code);
                }
              }}
              className="cursor-pointer border-t border-[var(--hairline)] bg-[var(--surface)] hover:bg-[var(--surface-2)] focus:bg-[var(--surface-2)] focus:outline-none"
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
