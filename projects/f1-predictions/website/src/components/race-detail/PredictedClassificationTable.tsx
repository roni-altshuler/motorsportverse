"use client";

/**
 * PredictedClassificationTable — the "Model Predicted Classification" table,
 * extracted from the RaceDetailPage monolith (decompose-as-you-touch).
 *
 * Adds the previously-hidden uncertainty layer:
 *  - RANGE      — finishRangeLow/High as a "P4–P9" chip (falls back to gap)
 *  - PACE ±     — bootstrap 90% prediction interval rendered as a half-width
 *                 "±0.31s" readout (column appears only when data exists)
 *  - DNF RISK   — per-driver retirement probability; red-tinted only when
 *                 genuinely elevated so red keeps its risk semantics
 *
 * Row click expands the driver-detail sheet (season form + key factors).
 */
import React, { useState } from "react";
import DriverDetailSheet from "@/components/DriverDetailSheet";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { resolveDriverHeadshot } from "@/lib/headshots";
import { formatGap } from "@/lib/data";
import type { ClassificationEntry, DriverStanding } from "@/types";

interface PredictedClassificationTableProps {
  classification: ClassificationEntry[];
  standings: DriverStanding[] | null;
}

/** Elevated-risk cutoff for the red tint. The pack baseline sits around
 * 7–13%, with reliability-flagged drivers at 35%+ — red only fires for the
 * genuinely elevated tail so it keeps meaning. */
const DNF_ELEVATED = 0.15;

export function FinishRangeChip({ low, high }: { low?: number | null; high?: number | null }) {
  if (low == null || high == null) return null;
  return (
    <span
      className="inline-block font-mono font-tabular text-xs px-2 py-0.5 whitespace-nowrap"
      style={{
        border: "1px solid var(--hairline-strong)",
        color: "var(--body-strong)",
      }}
      title={`Expected finishing window: P${low} to P${high}`}
    >
      P{low}–P{high}
    </span>
  );
}

export function DnfRiskCell({ probability }: { probability?: number | null }) {
  if (probability == null) {
    return <span style={{ color: "var(--muted-soft)" }}>—</span>;
  }
  const pct = probability * 100;
  const elevated = probability > DNF_ELEVATED;
  return (
    <span
      className="font-mono font-tabular text-xs whitespace-nowrap"
      style={{ color: elevated ? "var(--accent-f1-red-bright)" : "var(--muted)" }}
      title={
        elevated
          ? "Elevated retirement risk versus the field baseline"
          : "Modelled probability of not being classified"
      }
    >
      {pct.toFixed(0)}%
    </span>
  );
}

function PaceWindowCell({ entry }: { entry: ClassificationEntry }) {
  const { predictionIntervalLow: low, predictionIntervalHigh: high } = entry;
  if (low == null || high == null || high < low) {
    return <span style={{ color: "var(--muted-soft)" }}>—</span>;
  }
  const halfWidth = (high - low) / 2;
  return (
    <span
      className="font-mono font-tabular text-xs whitespace-nowrap"
      style={{ color: "var(--muted)" }}
      title={`90% pace window: ${low.toFixed(3)}s – ${high.toFixed(3)}s`}
    >
      ±{halfWidth.toFixed(2)}s
    </span>
  );
}

export default function PredictedClassificationTable({
  classification,
  standings,
}: PredictedClassificationTableProps) {
  const [expandedDriver, setExpandedDriver] = useState<string | null>(null);

  const hasDnf = classification.some((e) => e.dnfProbability != null);
  const hasPaceWindow = classification.some(
    (e) => e.predictionIntervalLow != null && e.predictionIntervalHigh != null,
  );

  const confidenceTone = (value?: string) =>
    value === "High"
      ? "var(--accent-positive)"
      : value === "Low"
        ? "var(--accent-live)"
        : "var(--accent-info)";

  const headers = [
    "POS",
    "DRIVER",
    "",
    "TEAM",
    "TIME",
    ...(hasPaceWindow ? ["PACE ±"] : []),
    "RANGE",
    "WIN",
    ...(hasDnf ? ["DNF RISK"] : []),
    "CONF",
    "PTS",
  ];
  const columnCount = headers.length;

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4" style={{ borderBottom: "1px solid var(--border)" }}>
        <h3 className="section-heading mb-0">Model Predicted Classification</h3>
        <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
          Click a row for season form and the factors behind the prediction.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {headers.map((h, i) => (
                <th
                  key={`${h}-${i}`}
                  className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider"
                  style={{ color: "var(--text-muted)" }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {classification.map((entry) => {
              const isExpanded = expandedDriver === entry.driver;
              return (
                <React.Fragment key={entry.driver}>
                  <tr
                    className="transition-colors hover:bg-[var(--bg-card-hover)] cursor-pointer"
                    style={{ borderBottom: "1px solid var(--border)" }}
                    onClick={() => setExpandedDriver(isExpanded ? null : entry.driver)}
                    aria-expanded={isExpanded}
                    title={`${isExpanded ? "Hide" : "Show"} detail for ${entry.driver}`}
                  >
                    <td className="px-4 py-3">
                      <span
                        className={`position-badge ${
                          entry.position === 1
                            ? "p1"
                            : entry.position === 2
                              ? "p2"
                              : entry.position === 3
                                ? "p3"
                                : entry.position <= 10
                                  ? "points"
                                  : "no-points"
                        }`}
                      >
                        {entry.position}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-3">
                        <DriverPortrait
                          driver={entry.driver}
                          driverFullName={entry.driverFullName}
                          team={entry.team}
                          teamColor={entry.teamColor}
                          headshotUrl={resolveDriverHeadshot(entry.driver, entry.headshotUrl)}
                          size={28}
                        />
                        <span className="font-bold" style={{ color: "var(--text)" }}>
                          {entry.driverFullName ?? entry.driver}
                        </span>
                        <span
                          className="text-xs font-mono select-none"
                          style={{ color: "var(--text-muted)" }}
                          aria-hidden
                        >
                          {isExpanded ? "−" : "+"}
                        </span>
                      </span>
                    </td>
                    <td className="px-1 py-3">
                      <div
                        className="w-1 h-6 rounded"
                        style={{ backgroundColor: entry.teamColor }}
                      />
                    </td>
                    <td className="px-4 py-3" style={{ color: "var(--text-muted)" }}>
                      {entry.team}
                    </td>
                    <td className="px-4 py-3 font-mono text-sm" style={{ color: "var(--text)" }}>
                      {entry.predictedTime}s
                    </td>
                    {hasPaceWindow && (
                      <td className="px-4 py-3">
                        <PaceWindowCell entry={entry} />
                      </td>
                    )}
                    <td className="px-4 py-3">
                      {entry.finishRangeLow != null && entry.finishRangeHigh != null ? (
                        <FinishRangeChip low={entry.finishRangeLow} high={entry.finishRangeHigh} />
                      ) : (
                        <span className="font-mono text-sm" style={{ color: "var(--text-muted)" }}>
                          {formatGap(entry.gap)}
                        </span>
                      )}
                    </td>
                    <td
                      className="px-4 py-3 font-mono text-sm"
                      style={{ color: "var(--text-muted)" }}
                    >
                      {entry.winProbability != null ? `${entry.winProbability.toFixed(1)}%` : "—"}
                    </td>
                    {hasDnf && (
                      <td className="px-4 py-3">
                        <DnfRiskCell probability={entry.dnfProbability} />
                      </td>
                    )}
                    <td className="px-4 py-3">
                      <span
                        className="text-xs font-bold uppercase tracking-wider"
                        style={{ color: confidenceTone(entry.confidence) }}
                      >
                        {entry.confidence || "Medium"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {entry.points > 0 ? (
                        <span className="font-bold text-f1-red">{entry.points}</span>
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      <td colSpan={columnCount} className="px-4 py-1">
                        <DriverDetailSheet
                          driver={entry.driver}
                          standings={standings ?? []}
                          fullName={entry.driverFullName}
                          entry={entry}
                        />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
