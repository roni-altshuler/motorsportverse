"use client";

/**
 * DriverComparison — pick any two drivers from the round's predicted
 * classification and compare them side-by-side: predicted finish + range,
 * win/podium/top-10 probabilities, head-to-head edge, retirement risk,
 * key factors, and recent form. Everything renders from data that is
 * already loaded client-side (round classification, standings) plus the
 * round's probability file when it exists — no extra per-interaction fetch.
 */
import { useMemo, useState, type ReactNode } from "react";
import HUDPanel from "@/components/ui/HUDPanel";
import DriverPortrait from "@/components/standings/DriverPortrait";
import TeamColorBar from "@/components/ui/TeamColorBar";
import KeyFactorBars from "@/components/race-detail/KeyFactorBars";
import { FinishRangeChip } from "@/components/race-detail/PredictedClassificationTable";
import { resolveDriverHeadshot } from "@/lib/headshots";
import type { ClassificationEntry, DriverStanding, ProbabilityRoundData } from "@/types";

interface DriverComparisonProps {
  classification: ClassificationEntry[];
  standings: DriverStanding[] | null;
  probabilities: ProbabilityRoundData | null;
}

type Better = "a" | "b" | "tie" | null;

function marketProbability(
  probabilities: ProbabilityRoundData | null,
  market: "win" | "podium" | "top10",
  driver: string,
): number | null {
  const rows = probabilities?.markets?.[market];
  if (!rows) return null;
  const hit = rows.find((r) => r.driver === driver);
  return hit ? hit.probability : null;
}

function pct(value: number | null | undefined, decimals = 1): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(decimals)}%`;
}

function lastThreePoints(standings: DriverStanding[] | null, driver: string): number | null {
  const record = standings?.find((d) => d.driver === driver);
  const history = record?.pointsHistory;
  if (!history || history.length === 0) return null;
  const deltas = history.map((cum, i) => (i === 0 ? cum : cum - history[i - 1]));
  return deltas.slice(-3).reduce((a, b) => a + b, 0);
}

function CompareValue({
  value,
  better,
  align,
}: {
  value: ReactNode;
  better: boolean;
  align: "left" | "right";
}) {
  return (
    <div
      className={`font-mono font-tabular text-sm sm:text-base ${align === "right" ? "text-right" : "text-left"}`}
      style={{
        color: better ? "var(--ink)" : "var(--muted)",
        fontWeight: better ? 700 : 400,
      }}
    >
      {value}
    </div>
  );
}

export default function DriverComparison({
  classification,
  standings,
  probabilities,
}: DriverComparisonProps) {
  const [codeA, setCodeA] = useState<string>(classification[0]?.driver ?? "");
  const [codeB, setCodeB] = useState<string>(classification[1]?.driver ?? "");

  const entryA = useMemo(
    () => classification.find((e) => e.driver === codeA) ?? null,
    [classification, codeA],
  );
  const entryB = useMemo(
    () => classification.find((e) => e.driver === codeB) ?? null,
    [classification, codeB],
  );

  if (classification.length < 2) return null;

  const h2hRaw =
    entryA && entryB ? probabilities?.h2h?.[entryA.driver]?.[entryB.driver] : undefined;
  const h2hInverse =
    entryA && entryB ? probabilities?.h2h?.[entryB.driver]?.[entryA.driver] : undefined;
  const pAheadA = h2hRaw ?? (h2hInverse != null ? 1 - h2hInverse : null);

  // Win % mirrors the classification table / win-probability chart (same
  // number, same label elsewhere on this page); the market file is only a
  // fallback for older rounds that predate per-entry winProbability.
  const winA = entryA
    ? entryA.winProbability != null
      ? entryA.winProbability / 100
      : marketProbability(probabilities, "win", entryA.driver)
    : null;
  const winB = entryB
    ? entryB.winProbability != null
      ? entryB.winProbability / 100
      : marketProbability(probabilities, "win", entryB.driver)
    : null;
  const podiumA = entryA ? marketProbability(probabilities, "podium", entryA.driver) : null;
  const podiumB = entryB ? marketProbability(probabilities, "podium", entryB.driver) : null;
  const top10A = entryA ? marketProbability(probabilities, "top10", entryA.driver) : null;
  const top10B = entryB ? marketProbability(probabilities, "top10", entryB.driver) : null;
  const formA = entryA ? lastThreePoints(standings, entryA.driver) : null;
  const formB = entryB ? lastThreePoints(standings, entryB.driver) : null;

  const higherWins = (a: number | null, b: number | null): Better => {
    if (a == null || b == null) return null;
    if (a === b) return "tie";
    return a > b ? "a" : "b";
  };
  const lowerWins = (a: number | null | undefined, b: number | null | undefined): Better => {
    if (a == null || b == null) return null;
    if (a === b) return "tie";
    return a < b ? "a" : "b";
  };

  const rows: Array<{
    label: string;
    a: ReactNode;
    b: ReactNode;
    better: Better;
  }> = [
    {
      label: "Predicted finish",
      a: entryA ? `P${entryA.position}` : "—",
      b: entryB ? `P${entryB.position}` : "—",
      better: lowerWins(entryA?.position, entryB?.position),
    },
    {
      label: "Finish range",
      a:
        entryA?.finishRangeLow != null && entryA?.finishRangeHigh != null ? (
          <FinishRangeChip low={entryA.finishRangeLow} high={entryA.finishRangeHigh} />
        ) : (
          "—"
        ),
      b:
        entryB?.finishRangeLow != null && entryB?.finishRangeHigh != null ? (
          <FinishRangeChip low={entryB.finishRangeLow} high={entryB.finishRangeHigh} />
        ) : (
          "—"
        ),
      better: null,
    },
    { label: "Win probability", a: pct(winA), b: pct(winB), better: higherWins(winA, winB) },
    {
      label: "Podium probability",
      a: pct(podiumA),
      b: pct(podiumB),
      better: higherWins(podiumA, podiumB),
    },
    {
      label: "Top-10 probability",
      a: pct(top10A),
      b: pct(top10B),
      better: higherWins(top10A, top10B),
    },
    {
      label: "DNF risk",
      a: pct(entryA?.dnfProbability, 0),
      b: pct(entryB?.dnfProbability, 0),
      better: lowerWins(entryA?.dnfProbability, entryB?.dnfProbability),
    },
    {
      label: "Points, last 3 rounds",
      a: formA != null ? `${formA}` : "—",
      b: formB != null ? `${formB}` : "—",
      better: higherWins(formA, formB),
    },
  ];

  const selectClass =
    "w-full bg-[color:var(--surface-card)] border border-[color:var(--hairline-strong)] " +
    "text-[color:var(--ink)] font-mono uppercase tracking-[0.08em] text-xs px-3 py-2 " +
    "focus:outline-none focus:border-[color:var(--ink)] cursor-pointer";

  const renderPicker = (
    which: "a" | "b",
    code: string,
    setCode: (c: string) => void,
    entry: ClassificationEntry | null,
    align: "left" | "right",
  ) => (
    <div className={`min-w-0 ${align === "right" ? "sm:text-right" : ""}`}>
      <label className="eyebrow block mb-2" htmlFor={`compare-driver-${which}`}>
        Driver {which.toUpperCase()}
      </label>
      <select
        id={`compare-driver-${which}`}
        className={selectClass}
        value={code}
        onChange={(e) => setCode(e.target.value)}
      >
        {classification.map((c) => (
          <option key={`${which}-${c.driver}`} value={c.driver}>
            P{c.position} · {c.driverFullName ?? c.driver}
          </option>
        ))}
      </select>
      {entry && (
        <div
          className={`mt-4 flex items-center gap-3 ${align === "right" ? "sm:flex-row-reverse" : ""}`}
        >
          <DriverPortrait
            driver={entry.driver}
            driverFullName={entry.driverFullName}
            team={entry.team}
            teamColor={entry.teamColor}
            headshotUrl={resolveDriverHeadshot(entry.driver, entry.headshotUrl)}
            size={48}
          />
          <div className={`min-w-0 ${align === "right" ? "sm:text-right" : ""}`}>
            <p className="title-sm truncate">{entry.driverFullName ?? entry.driver}</p>
            <p className="body-sm text-[color:var(--muted)] truncate">{entry.team}</p>
            <div className={`mt-1 ${align === "right" ? "sm:flex sm:justify-end" : ""}`}>
              <TeamColorBar
                teamColor={entry.teamColor}
                team={entry.team}
                variant="solid"
                size="sm"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <HUDPanel kicker="Head to Head" title="Driver Comparison" bodyClassName="p-5 sm:p-6">
      <div className="grid grid-cols-2 gap-4 sm:gap-10 mb-6">
        {renderPicker("a", codeA, setCodeA, entryA, "left")}
        {renderPicker("b", codeB, setCodeB, entryB, "right")}
      </div>

      {entryA && entryB && entryA.driver === entryB.driver ? (
        <p className="body-sm text-[color:var(--muted)] text-center py-4">
          Pick two different drivers to compare.
        </p>
      ) : (
        <>
          {/* Head-to-head split bar */}
          <div className="mb-8">
            <div className="flex items-baseline justify-between mb-2">
              <span className="font-mono font-tabular text-sm" style={{ color: "var(--ink)" }}>
                {pAheadA != null ? pct(pAheadA, 0) : "—"}
              </span>
              <span className="eyebrow">Finishes ahead</span>
              <span className="font-mono font-tabular text-sm" style={{ color: "var(--ink)" }}>
                {pAheadA != null ? pct(1 - pAheadA, 0) : "—"}
              </span>
            </div>
            {pAheadA != null ? (
              <div
                className="flex h-2 w-full"
                role="img"
                aria-label={`${entryA?.driverFullName ?? codeA} finishes ahead of ${
                  entryB?.driverFullName ?? codeB
                } in ${Math.round(pAheadA * 100)}% of race simulations`}
              >
                <div
                  className="h-full"
                  style={{
                    width: `${pAheadA * 100}%`,
                    background: entryA?.teamColor ?? "var(--ink)",
                  }}
                />
                <div className="h-full w-px" style={{ background: "var(--canvas)" }} />
                <div
                  className="h-full flex-1"
                  style={{ background: entryB?.teamColor ?? "var(--muted)" }}
                />
              </div>
            ) : (
              <p className="body-sm text-[color:var(--muted)]">
                Head-to-head simulation odds publish with the round&apos;s probability run.
              </p>
            )}
          </div>

          {/* Stat rows */}
          <div className="divide-y divide-[color:var(--hairline)] border-y border-[color:var(--hairline)]">
            {rows.map((row) => (
              <div
                key={row.label}
                className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 py-3"
              >
                <CompareValue value={row.a} better={row.better === "a"} align="left" />
                <div className="eyebrow text-center px-2">{row.label}</div>
                <CompareValue value={row.b} better={row.better === "b"} align="right" />
              </div>
            ))}
          </div>

          {/* Key factors side by side */}
          {((entryA?.keyFactors?.length ?? 0) > 0 || (entryB?.keyFactors?.length ?? 0) > 0) && (
            <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-6 sm:gap-10">
              {[entryA, entryB].map((entry, i) =>
                entry ? (
                  <div key={`cmp-factors-${entry.driver}-${i}`}>
                    <p className="eyebrow mb-3">{entry.driver} — key factors</p>
                    {entry.keyFactors && entry.keyFactors.length > 0 ? (
                      <KeyFactorBars factors={entry.keyFactors} compact />
                    ) : (
                      <p className="body-sm text-[color:var(--muted)]">
                        Factor breakdown publishes with the next model run.
                      </p>
                    )}
                  </div>
                ) : null,
              )}
            </div>
          )}
        </>
      )}
    </HUDPanel>
  );
}
