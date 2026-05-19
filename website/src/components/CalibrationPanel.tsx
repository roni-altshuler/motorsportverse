"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import {
  CalibrationSummary,
  MarketCalibrationStats,
  ReliabilityBin,
} from "@/types";

interface CalibrationPanelProps {
  summary: CalibrationSummary | null;
}

const MARKET_ORDER = ["win", "podium", "top6", "top10"] as const;
type MarketKey = (typeof MARKET_ORDER)[number];

const MARKET_LABELS: Record<string, string> = {
  win: "Win",
  podium: "Podium",
  top6: "Top 6",
  top10: "Top 10",
};

function marketLabel(key: string): string {
  return MARKET_LABELS[key] ?? key;
}

function formatNumber(value: number | null | undefined, digits = 4): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

function formatSigned(value: number | null | undefined, digits = 4): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}`;
}

const REFERENCE_LINE: { meanPred: number; reference: number }[] = Array.from(
  { length: 11 },
  (_, i) => ({ meanPred: i / 10, reference: i / 10 }),
);

interface TooltipPayloadItem {
  name?: string | number;
  value?: string | number;
  payload?: ReliabilityBin & { reference?: number };
}

interface TooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}

function ReliabilityTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const binPayload = payload.find(
    (p) => p.payload && typeof p.payload.empirical === "number" && typeof p.payload.count === "number",
  );
  const bin = binPayload?.payload as ReliabilityBin | undefined;
  if (!bin) return null;
  return (
    <div
      style={{
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: "8px",
        padding: "8px 10px",
        fontSize: "12px",
        color: "var(--text)",
        minWidth: "160px",
      }}
    >
      <div style={{ color: "var(--text-muted)", marginBottom: 4 }}>
        Reliability bin
      </div>
      <div>Predicted: {(bin.meanPred * 100).toFixed(1)}%</div>
      <div>Empirical: {(bin.empirical * 100).toFixed(1)}%</div>
      <div>n = {bin.count}</div>
    </div>
  );
}

function buildEmptyMarketStats(): MarketCalibrationStats {
  return { brierScore: null, logLoss: null, reliability: [] };
}

function isAllNull(summary: CalibrationSummary | null): boolean {
  if (!summary) return true;
  const markets = Object.values(summary.perMarket ?? {});
  if (markets.length === 0) return true;
  return markets.every(
    (m) =>
      m.brierScore == null &&
      m.logLoss == null &&
      (!m.reliability || m.reliability.length === 0),
  );
}

const EMPTY_STATE_COMMAND =
  "python backfill_history.py --seasons 2023,2024,2025 --force";

const EMPTY_STATE_BODY =
  "Calibration not yet applied. Run the command below to populate the training set. Until then, the probabilities on /value are uncalibrated Plackett-Luce outputs.";

export default function CalibrationPanel({ summary }: CalibrationPanelProps) {
  const markets = useMemo(() => {
    if (!summary) return [] as MarketKey[];
    const known = MARKET_ORDER.filter((m) => m in summary.perMarket);
    if (known.length > 0) return known;
    // Fall back to whatever keys the summary supplies.
    return Object.keys(summary.perMarket) as MarketKey[];
  }, [summary]);

  const initialMarket: MarketKey =
    (markets[0] as MarketKey | undefined) ?? "win";

  const [activeMarket, setActiveMarket] = useState<MarketKey>(initialMarket);

  // If the user changed the data shape (rare) and the active market is gone,
  // gently re-snap to the first available market. We do this without
  // useEffect to avoid hydration churn — markets is derived from props.
  const effectiveMarket: MarketKey =
    markets.includes(activeMarket) ? activeMarket : initialMarket;

  const stats: MarketCalibrationStats =
    summary?.perMarket?.[effectiveMarket] ?? buildEmptyMarketStats();

  const empty = isAllNull(summary);

  const logLossDelta =
    stats.logLoss != null && stats.uniformBaselineLogLoss != null
      ? stats.logLoss - stats.uniformBaselineLogLoss
      : null;

  const reliabilityChartData = (stats.reliability ?? []).map((bin) => ({
    meanPred: bin.meanPred,
    empirical: bin.empirical,
    count: bin.count,
  }));

  // Combine the reference (y = x) line with the scatter data into a single
  // dataset so ComposedChart can render both with shared axes.
  const mergedChartData: Array<{
    meanPred: number;
    reference?: number;
    empirical?: number;
    count?: number;
  }> = [
    ...REFERENCE_LINE,
    ...reliabilityChartData.map((b) => ({
      meanPred: b.meanPred,
      empirical: b.empirical,
      count: b.count,
    })),
  ];

  const chartAriaLabel = `Reliability diagram, ${
    stats.reliability?.length ?? 0
  } bins, ${marketLabel(effectiveMarket)} market`;

  return (
    <motion.div
      className="card p-6 sm:p-8"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.35 }}
    >
      <div className="flex flex-col gap-1 mb-2">
        <p
          className="text-xs font-bold tracking-[0.3em] uppercase"
          style={{ color: "#E10600" }}
        >
          Probability Calibration
        </p>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          A well-calibrated model assigns probabilities that match observed
          frequencies. Bins close to the dashed reference line indicate good
          calibration.
        </p>
      </div>

      {empty ? (
        <div
          className="mt-4 p-5 rounded-xl"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
          }}
        >
          <p
            className="text-sm font-semibold mb-2"
            style={{ color: "var(--text)" }}
          >
            Awaiting historical backfill
          </p>
          <p className="text-sm mb-3" style={{ color: "var(--text-muted)" }}>
            {summary?.dataLimitation || EMPTY_STATE_BODY}
          </p>
          <div
            className="inline-block px-3 py-2 rounded-lg text-xs font-mono"
            style={{
              background: "var(--bg-card-solid)",
              border: "1px solid var(--border)",
              color: "var(--text)",
            }}
          >
            {EMPTY_STATE_COMMAND}
          </div>
        </div>
      ) : (
        <>
          {/* Market tab strip */}
          <div
            role="tablist"
            aria-label="Calibration market selector"
            className="flex flex-wrap gap-2 mb-5 mt-3"
          >
            {markets.map((m) => {
              const selected = m === effectiveMarket;
              return (
                <button
                  key={m}
                  role="tab"
                  type="button"
                  aria-selected={selected}
                  aria-controls={`calibration-panel-${m}`}
                  id={`calibration-tab-${m}`}
                  onClick={() => setActiveMarket(m)}
                  className="px-3 py-1.5 text-xs sm:text-sm font-bold uppercase tracking-wider rounded-full transition-colors"
                  style={{
                    background: selected
                      ? "rgba(225, 6, 0, 0.15)"
                      : "var(--bg-surface)",
                    color: selected ? "#E10600" : "var(--text-muted)",
                    border: selected
                      ? "1px solid rgba(225, 6, 0, 0.4)"
                      : "1px solid var(--border)",
                  }}
                >
                  {marketLabel(m)}
                </button>
              );
            })}
          </div>

          <div
            id={`calibration-panel-${effectiveMarket}`}
            role="tabpanel"
            aria-labelledby={`calibration-tab-${effectiveMarket}`}
          >
            {/* Reliability diagram */}
            <div
              className="w-full h-72 sm:h-80"
              role="img"
              aria-label={chartAriaLabel}
            >
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={mergedChartData}
                  margin={{ top: 12, right: 20, bottom: 28, left: 4 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--border)"
                  />
                  <XAxis
                    type="number"
                    dataKey="meanPred"
                    domain={[0, 1]}
                    ticks={[0, 0.25, 0.5, 0.75, 1]}
                    tickFormatter={(v) => `${Math.round(Number(v) * 100)}%`}
                    stroke="var(--text-muted)"
                    fontSize={11}
                    tickLine={false}
                    label={{
                      value: "Predicted probability",
                      position: "insideBottom",
                      offset: -10,
                      fill: "var(--text-muted)",
                      fontSize: 11,
                    }}
                  />
                  <YAxis
                    type="number"
                    domain={[0, 1]}
                    ticks={[0, 0.25, 0.5, 0.75, 1]}
                    tickFormatter={(v) => `${Math.round(Number(v) * 100)}%`}
                    stroke="var(--text-muted)"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    label={{
                      value: "Empirical frequency",
                      angle: -90,
                      position: "insideLeft",
                      offset: 14,
                      style: { textAnchor: "middle" },
                      fill: "var(--text-muted)",
                      fontSize: 11,
                    }}
                  />
                  <ZAxis
                    type="number"
                    dataKey="count"
                    range={[60, 360]}
                    name="count"
                  />
                  <Tooltip content={<ReliabilityTooltip />} cursor={false} />
                  <Line
                    type="linear"
                    dataKey="reference"
                    stroke="var(--text-muted)"
                    strokeDasharray="6 6"
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                    legendType="none"
                  />
                  <Scatter
                    name="Observed bins"
                    dataKey="empirical"
                    fill="#E10600"
                    fillOpacity={0.78}
                    stroke="#FF1801"
                    strokeWidth={1.2}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Legend (stacks below at narrow widths via flex-wrap) */}
            <div
              className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 mt-2 text-xs"
              style={{ color: "var(--text-muted)" }}
            >
              <span className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  style={{
                    display: "inline-block",
                    width: 16,
                    height: 0,
                    borderTop: "2px dashed var(--text-muted)",
                  }}
                />
                Perfect calibration (y = x)
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  style={{
                    display: "inline-block",
                    width: 10,
                    height: 10,
                    background: "#E10600",
                    border: "1.2px solid #FF1801",
                    borderRadius: "50%",
                  }}
                />
                Observed bins (size = sample count)
              </span>
            </div>

            {/* KPI strip */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-6">
              <div className="metric-card text-center">
                <p
                  className="text-xs font-medium mb-1"
                  style={{ color: "var(--text-muted)" }}
                >
                  Brier Score
                </p>
                <p
                  className="text-2xl font-black font-mono"
                  style={{ color: "var(--text)" }}
                >
                  {formatNumber(stats.brierScore, 4)}
                </p>
                <p
                  className="text-[10px] mt-1"
                  style={{ color: "var(--text-muted)" }}
                >
                  Lower is better
                </p>
              </div>
              <div className="metric-card text-center">
                <p
                  className="text-xs font-medium mb-1"
                  style={{ color: "var(--text-muted)" }}
                >
                  Log Loss
                </p>
                <p
                  className="text-2xl font-black font-mono"
                  style={{ color: "var(--text)" }}
                >
                  {formatNumber(stats.logLoss, 4)}
                </p>
                <p
                  className="text-[10px] mt-1"
                  style={{ color: "var(--text-muted)" }}
                >
                  Lower is better
                </p>
              </div>
              <div className="metric-card text-center">
                <p
                  className="text-xs font-medium mb-1"
                  style={{ color: "var(--text-muted)" }}
                >
                  vs Uniform Baseline
                </p>
                <p
                  className="text-2xl font-black font-mono"
                  style={{
                    color:
                      logLossDelta == null
                        ? "var(--text-muted)"
                        : logLossDelta < 0
                          ? "#00D2BE"
                          : "#E10600",
                  }}
                >
                  {formatSigned(logLossDelta, 4)}
                </p>
                <p
                  className="text-[10px] mt-1"
                  style={{ color: "var(--text-muted)" }}
                >
                  {logLossDelta == null
                    ? "Baseline not provided"
                    : logLossDelta < 0
                      ? "Model beats uniform"
                      : "Model worse than uniform"}
                </p>
              </div>
            </div>

            {(stats.sampleCount != null || stats.nSamples != null) && (
              <p
                className="text-xs mt-3 text-center"
                style={{ color: "var(--text-muted)" }}
              >
                Sample size: {stats.sampleCount ?? stats.nSamples} observations
              </p>
            )}

            {summary?.dataLimitation && (
              <p
                className="text-xs mt-3"
                style={{ color: "var(--text-muted)" }}
              >
                Note: {summary.dataLimitation}
              </p>
            )}

            {summary?.trainingSeasons &&
              summary.trainingSeasons.length > 0 && (
                <p
                  className="text-xs mt-1"
                  style={{ color: "var(--text-muted)" }}
                >
                  Training seasons: {summary.trainingSeasons.join(", ")}
                </p>
              )}

            {summary?.generatedAt && (
              <p
                className="text-xs mt-1"
                style={{ color: "var(--text-muted)" }}
              >
                Generated: {new Date(summary.generatedAt).toLocaleString()}
              </p>
            )}
          </div>
        </>
      )}
    </motion.div>
  );
}
