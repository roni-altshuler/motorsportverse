"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import ChartContainer from "@/components/charts/ChartContainer";
import { FinishProbabilityHeatmap } from "@/components/charts/FinishProbabilityHeatmap";
import { HeadToHeadMatrix } from "@/components/charts/HeadToHeadMatrix";
import { PodiumProbabilityChart } from "@/components/charts/PodiumProbabilityChart";
import { PredictedVsActualSlope } from "@/components/charts/PredictedVsActualSlope";
import WinProbabilityChart, {
  type WinProbabilityTrend,
} from "@/components/charts/WinProbabilityChart";
import AddToCalendar from "@/components/AddToCalendar";
import DriverDetailSheet from "@/components/DriverDetailSheet";
import ShareButton from "@/components/ShareButton";
import HUDHeader from "@/components/race-detail/HUDHeader";
import PodiumPredictionTrio from "@/components/race-detail/PodiumPredictionTrio";
import RaceVolatilityBadge from "@/components/race-detail/RaceVolatilityBadge";
import RiderForecastTable from "@/components/race-detail/RiderForecastTable";
import RaceNarrativeCard from "@/components/race-weekend/RaceNarrativeCard";
import HUDPanel from "@/components/ui/HUDPanel";
import { fetchMotogpData, fetchRoundDetail, fetchRoundProbabilities } from "@/lib/motogpClient";
import { useSeason } from "@/lib/SeasonProvider";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type {
  CalendarRound,
  ClassificationEntry,
  DriverStanding,
  ProbabilitiesRound,
  RoundDetail,
  TitleOdds,
} from "@/types/motogp";

type RaceKey = "feature" | "sprint";

export function RaceDetail({
  round: bakedRound,
  probabilities: bakedProbabilities,
  driverStandings: bakedStandings = [],
  championship: bakedChampionship = [],
  winTrend = null,
  calendarRound = null,
}: {
  round: RoundDetail;
  probabilities: ProbabilitiesRound | null;
  driverStandings?: DriverStanding[];
  championship?: TitleOdds[];
  /** Win-market-by-round trend baked from the CURRENT season's probability
   *  files (built server-side in the page); hidden on archived-season overlay. */
  winTrend?: WinProbabilityTrend | null;
  /** The season-calendar entry for this round (dates/city) — powers the .ics
   *  "Add to calendar" button. Baked from the current season. */
  calendarRound?: CalendarRound | null;
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
    basePath: string;
    round: RoundDetail;
    probabilities: ProbabilitiesRound | null;
    driverStandings: DriverStanding[];
    championship: TitleOdds[];
  } | null>(null);

  useEffect(() => {
    if (!isArchived) return;
    let active = true;
    Promise.all([
      fetchRoundDetail(bakedRound.round, basePath),
      fetchRoundProbabilities(bakedRound.round, basePath),
      fetchMotogpData(basePath),
    ]).then(([r, p, d]) => {
      if (!active) return;
      setOverlay(
        r
          ? {
              basePath,
              round: r,
              probabilities: p,
              driverStandings: d?.driverStandings ?? [],
              championship: d?.championship ?? [],
            }
          : null
      );
    });
    return () => {
      active = false;
    };
  }, [isArchived, basePath, bakedRound.round]);

  // Select only the archive that belongs to this route; current-season props
  // need no state reset or extra effect render.
  const activeOverlay = isArchived && overlay?.basePath === basePath
    && overlay.round.round === bakedRound.round ? overlay : null;
  const round = activeOverlay?.round ?? bakedRound;
  const probabilities = activeOverlay ? activeOverlay.probabilities : bakedProbabilities;
  const driverStandings = activeOverlay ? activeOverlay.driverStandings : bakedStandings;
  const championship = activeOverlay ? activeOverlay.championship : bakedChampionship;
  // The trend is baked from the current season's files only — never show it
  // against an archived season's rounds.
  const trend = isArchived ? null : winTrend;

  const block = round[tab];
  const probs = probabilities?.[tab] ?? null;
  const raceLabel = tab === "feature" ? "Grand Prix" : "Sprint";
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

      {/* Share + add-to-calendar actions. */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <ShareButton
          title={`${round.venueName} — MotoGP round ${round.round}`}
          text={`Sprint + Grand Prix forecasts for the MotoGP ${round.venueName} round — win probabilities, predicted podium and the model's classification.`}
        />
        {calendarRound && !isArchived && (
          <AddToCalendar race={calendarRound} season={round.season} size="sm" />
        )}
      </div>

      {/* Primary race tabs — MotoGP's two scored races (Grand Prix + Sprint). */}
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
            className="rounded-full border px-4 py-1.5 text-sm font-medium"
            style={{
              color: tab === t ? "var(--accent-ink)" : "var(--ink-muted)",
              backgroundColor: tab === t ? "var(--accent)" : "transparent",
              borderColor: tab === t ? "var(--accent)" : "var(--hairline)",
            }}
          >
            {t === "feature" ? "Grand Prix" : "Sprint"}
          </button>
        ))}
      </div>

      {/* Auto-generated "what the model sees" bullets for the active race. */}
      <RaceNarrativeCard round={round} race={tab} championship={championship} />

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
              pTop6: e.pTop6,
              pTop10: e.pTop10,
              meanFinish: e.meanFinish,
            }))}
          />
        </HUDPanel>
      </div>

      {/* Classification table — every row opens the driver detail sheet. */}
      <RiderForecastTable
        key={`${round.season}:${round.round}`}
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
                        <p className="eyebrow mb-1">Riders Forecast</p>
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
                Select a rider in the forecasts above to open their per-race
                forecast and season form.
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
                  pTop6: e.pTop6,
                  pTop10: e.pTop10,
                  meanFinish: e.meanFinish,
                }))}
              />
              {trend && trend.series.length > 0 && (
                <div>
                  <p className="eyebrow mb-3">Win market by round — Grand Prix</p>
                  <ChartContainer height={440}>
                    <WinProbabilityChart trend={trend} />
                  </ChartContainer>
                </div>
              )}
              {round.completed && (
                <PredictedVsActualSlope
                  title={`Predicted vs actual — ${raceLabel.toLowerCase()}`}
                  rows={block.classification.map((e) => ({
                    code: e.code,
                    name: e.name,
                    teamColor: e.teamColor,
                    predicted: e.position,
                    actual: e.actualPosition,
                  }))}
                />
              )}
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
