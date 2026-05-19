"use client";

import { useEffect, useMemo, useState } from "react";
import {
  RaceCalendarEntry,
  SeasonData,
  ValueOpportunity,
  ValueRoundData,
} from "@/types";
import {
  fetchSeasonData,
  fetchSeasonTrackerData,
  formatDate,
  formatDateTime,
} from "@/lib/data";
import {
  formatCurrency,
  formatOdds,
  formatPct,
  formatSignedPct,
  getValueRoundData,
  listAvailableValueRounds,
} from "@/lib/value";

type SortKey =
  | "rank"
  | "driver"
  | "market"
  | "modelProbability"
  | "marketProbability"
  | "edgePct"
  | "kellyFraction"
  | "expectedValue";

type SortDir = "asc" | "desc";

const DEFAULT_DISCLAIMER =
  "For educational use only. Not financial advice. Past model performance does not guarantee future results. Gamble responsibly; if betting is causing harm, seek help.";

interface ValueFinderProps {
  initialRound?: number;
}

function edgeTone(edge: number): "green" | "yellow" | "red" | "slate" {
  if (edge >= 0.03) return "green";
  if (edge >= 0) return "yellow";
  if (edge < 0) return "red";
  return "slate";
}

function rowTintStyle(edge: number): React.CSSProperties {
  const tone = edgeTone(edge);
  switch (tone) {
    case "green":
      return { background: "rgba(0, 210, 190, 0.06)" };
    case "yellow":
      return { background: "rgba(255, 215, 0, 0.05)" };
    case "red":
      return { background: "rgba(225, 6, 0, 0.05)", opacity: 0.85 };
    default:
      return {};
  }
}

function edgeTextColor(edge: number): string {
  const tone = edgeTone(edge);
  switch (tone) {
    case "green":
      return "#00D2BE";
    case "yellow":
      return "#FFD700";
    case "red":
      return "#E10600";
    default:
      return "var(--text)";
  }
}

function marketLabel(market: string): string {
  const m = market.toLowerCase();
  if (m === "win") return "Win";
  if (m === "podium") return "Podium";
  if (m === "top6" || m === "top 6") return "Top 6";
  if (m === "top10" || m === "top 10") return "Top 10";
  return market;
}

function compareOpportunities(
  a: ValueOpportunity,
  b: ValueOpportunity,
  key: SortKey,
  dir: SortDir,
): number {
  const mul = dir === "asc" ? 1 : -1;
  let av: number | string;
  let bv: number | string;
  switch (key) {
    case "driver":
      av = a.driver;
      bv = b.driver;
      break;
    case "market":
      av = a.market;
      bv = b.market;
      break;
    case "modelProbability":
      av = a.modelProbability;
      bv = b.modelProbability;
      break;
    case "marketProbability":
      av = a.marketProbability;
      bv = b.marketProbability;
      break;
    case "edgePct":
      av = a.edgePct;
      bv = b.edgePct;
      break;
    case "kellyFraction":
      av = a.kellyFraction;
      bv = b.kellyFraction;
      break;
    case "expectedValue":
      av = a.expectedValue;
      bv = b.expectedValue;
      break;
    case "rank":
    default:
      return 0;
  }
  if (typeof av === "number" && typeof bv === "number") {
    return (av - bv) * mul;
  }
  return String(av).localeCompare(String(bv)) * mul;
}

function ariaSortFor(active: boolean, dir: SortDir): "ascending" | "descending" | "none" {
  if (!active) return "none";
  return dir === "asc" ? "ascending" : "descending";
}

export default function ValueFinder({ initialRound }: ValueFinderProps) {
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [availableRounds, setAvailableRounds] = useState<number[]>([]);
  const [selectedRound, setSelectedRound] = useState<number | null>(
    initialRound ?? null,
  );
  const [valueData, setValueData] = useState<ValueRoundData | null>(null);
  const [loadingSeason, setLoadingSeason] = useState(true);
  const [loadingValue, setLoadingValue] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("edgePct");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [actualRoundsSet, setActualRoundsSet] = useState<Set<number>>(
    new Set(),
  );

  // Load season + tracker
  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchSeasonData(), fetchSeasonTrackerData()])
      .then(([s, tracker]) => {
        if (cancelled) return;
        setSeason(s);
        setActualRoundsSet(
          new Set(
            (tracker?.rounds || [])
              .filter((r) => r.hasActual)
              .map((r) => r.round),
          ),
        );
      })
      .catch(() => {
        /* graceful */
      })
      .finally(() => {
        if (!cancelled) setLoadingSeason(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Once we have season, determine candidate rounds (completed + currently-predicted),
  // then probe which have value data.
  useEffect(() => {
    if (!season) return;
    const predictionSet = new Set(season.completedRounds);
    // Candidate rounds are those with either a prediction published OR official
    // results synced — i.e. the model has "seen" enough to publish probabilities.
    const candidates = new Set<number>();
    for (const r of predictionSet) candidates.add(r);
    for (const r of actualRoundsSet) candidates.add(r);
    const candidateList = Array.from(candidates).sort((a, b) => a - b);
    let cancelled = false;
    listAvailableValueRounds(candidateList).then((rounds) => {
      if (cancelled) return;
      setAvailableRounds(rounds);
      // Pick default round: initialRound (if listed), else latest available.
      setSelectedRound((cur) => {
        if (cur && rounds.includes(cur)) return cur;
        if (rounds.length > 0) return rounds[rounds.length - 1];
        // Fallback: still show the latest candidate even if no value file
        // exists yet — page will render empty state.
        if (candidateList.length > 0) return candidateList[candidateList.length - 1];
        return null;
      });
    });
    return () => {
      cancelled = true;
    };
  }, [season, actualRoundsSet]);

  // Load value data for the selected round
  useEffect(() => {
    if (selectedRound == null) {
      return;
    }
    let cancelled = false;
    setLoadingValue(true);
    getValueRoundData(selectedRound)
      .then((data) => {
        if (cancelled) return;
        setValueData(data);
      })
      .finally(() => {
        if (!cancelled) setLoadingValue(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRound]);

  const selectedRace: RaceCalendarEntry | null = useMemo(() => {
    if (!season || selectedRound == null) return null;
    return season.calendar.find((r) => r.round === selectedRound) ?? null;
  }, [season, selectedRound]);

  // Build a candidate list for the picker (predicted ∪ official ∪ rounds with value data).
  const roundPickerOptions: number[] = useMemo(() => {
    if (!season) return [];
    const set = new Set<number>();
    for (const r of season.completedRounds) set.add(r);
    for (const r of actualRoundsSet) set.add(r);
    for (const r of availableRounds) set.add(r);
    return Array.from(set).sort((a, b) => a - b);
  }, [season, actualRoundsSet, availableRounds]);

  const handleSort = (key: SortKey) => {
    setSortKey((prev) => {
      if (prev === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        return prev;
      }
      // Default direction: numeric desc, string asc
      const isNumeric =
        key === "modelProbability" ||
        key === "marketProbability" ||
        key === "edgePct" ||
        key === "kellyFraction" ||
        key === "expectedValue";
      setSortDir(isNumeric ? "desc" : "asc");
      return key;
    });
  };

  const sortedOpps: ValueOpportunity[] = useMemo(() => {
    if (!valueData?.opportunities) return [];
    return [...valueData.opportunities].sort((a, b) =>
      compareOpportunities(a, b, sortKey, sortDir),
    );
  }, [valueData, sortKey, sortDir]);

  const disclaimer = valueData?.disclaimer || DEFAULT_DISCLAIMER;

  // ----------------------------- Render -----------------------------

  if (loadingSeason) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-3 border-f1-red border-t-transparent rounded-full animate-spin" />
          <div
            className="text-lg"
            style={{ color: "var(--text-muted)" }}
          >
            Loading value data...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-10 pb-16">
      {/* Page header */}
      <div className="mb-8 text-center">
        <p
          className="text-xs font-bold tracking-[0.3em] uppercase mb-2"
          style={{ color: "#E10600" }}
        >
          Betting Tool · Pre-Race
        </p>
        <h1
          className="text-3xl sm:text-4xl font-black tracking-tight mb-2"
          style={{ color: "var(--text)" }}
        >
          Value Finder
        </h1>
        <p
          className="text-sm max-w-2xl mx-auto"
          style={{ color: "var(--text-muted)" }}
        >
          Model probabilities vs sportsbook odds, with fractional Kelly sizing.
          Sorted by largest edge first.
        </p>
      </div>

      {/* Round picker */}
      {roundPickerOptions.length > 0 && (
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-center gap-3 mb-8">
          <label
            htmlFor="value-round-picker"
            className="text-xs font-bold uppercase tracking-[0.18em] self-center"
            style={{ color: "var(--text-muted)" }}
          >
            Round
          </label>
          <select
            id="value-round-picker"
            value={selectedRound ?? ""}
            onChange={(e) => setSelectedRound(Number(e.target.value))}
            className="px-4 py-2 rounded-lg text-sm font-semibold border focus:outline-none focus:border-f1-red transition-colors"
            style={{
              background: "var(--bg-surface)",
              borderColor: "var(--border)",
              color: "var(--text)",
              minWidth: "260px",
            }}
          >
            {roundPickerOptions.map((r) => {
              const race = season?.calendar.find((c) => c.round === r);
              const hasValue = availableRounds.includes(r);
              return (
                <option key={r} value={r}>
                  R{r} · {race?.name ?? `Round ${r}`}
                  {hasValue ? "" : " · No odds yet"}
                </option>
              );
            })}
          </select>
        </div>
      )}

      {/* Header strip */}
      <HeaderStrip
        race={selectedRace}
        valueData={valueData}
        loading={loadingValue}
      />

      {/* Top disclaimer */}
      <DisclaimerBanner text={disclaimer} className="mb-6" />

      {/* Empty / loading / content states */}
      {loadingValue ? (
        <div className="card p-12 text-center">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-3 border-f1-red border-t-transparent rounded-full animate-spin" />
            <p style={{ color: "var(--text-muted)" }}>Loading opportunities...</p>
          </div>
        </div>
      ) : !valueData || valueData.opportunities.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          {/* Stats row */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
            <StatCard
              label="Total opportunities"
              value={String(valueData.summary.totalOpportunities)}
              hint="Markets scanned vs available bookmaker odds"
            />
            <StatCard
              label="Positive-edge picks"
              value={String(valueData.summary.positiveEdgeCount)}
              hint="Model probability exceeds market-implied probability"
              accent="#00D2BE"
            />
            <StatCard
              label="Total Kelly exposure"
              value={formatPct(valueData.summary.totalKellyExposure, 2)}
              hint="Sum of fractional Kelly stakes across all picks"
            />
          </div>

          {/* Table (desktop) */}
          <DesktopTable
            opps={sortedOpps}
            sortKey={sortKey}
            sortDir={sortDir}
            onSort={handleSort}
          />

          {/* Mobile cards */}
          <MobileCards opps={sortedOpps} />
        </>
      )}

      {/* Bottom disclaimer */}
      <DisclaimerBanner text={disclaimer} className="mt-8" emphasis />
    </div>
  );
}

// ------------------------------- Subcomponents -------------------------------

function HeaderStrip({
  race,
  valueData,
  loading,
}: {
  race: RaceCalendarEntry | null;
  valueData: ValueRoundData | null;
  loading: boolean;
}) {
  return (
    <div
      className="rounded-xl border p-5 mb-6"
      style={{
        background:
          "linear-gradient(135deg, rgba(225, 6, 0, 0.07), transparent 42%), var(--bg-card)",
        borderColor: "rgba(225, 6, 0, 0.16)",
        backdropFilter: "blur(20px)",
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <p
            className="text-[10px] font-bold uppercase tracking-[0.24em] mb-1"
            style={{ color: "#E10600" }}
          >
            {race ? `Round ${race.round}` : "Round —"}
          </p>
          <h2
            className="text-xl sm:text-2xl font-black truncate"
            style={{ color: "var(--text)" }}
          >
            {race?.name ?? "No round selected"}
          </h2>
          {race?.date && (
            <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
              {race.circuit} · {formatDate(race.date)}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {valueData?.bookmaker && (
            <span
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider"
              style={{
                background: "rgba(225, 6, 0, 0.10)",
                color: "#E10600",
                border: "1px solid rgba(225, 6, 0, 0.22)",
              }}
            >
              {valueData.bookmaker}
            </span>
          )}
          {valueData?.oddsTimestamp && (
            <span
              className="inline-flex items-center px-3 py-1.5 rounded-full text-[11px] font-semibold"
              style={{
                background: "rgba(255, 255, 255, 0.04)",
                color: "var(--text-secondary)",
                border: "1px solid var(--glass-border)",
              }}
            >
              Odds as of {formatDateTime(valueData.oddsTimestamp)}
            </span>
          )}
          {valueData?.bankrollRef != null && (
            <span
              className="inline-flex items-center px-3 py-1.5 rounded-full text-[11px] font-semibold"
              style={{
                background: "rgba(0, 210, 190, 0.08)",
                color: "#00D2BE",
                border: "1px solid rgba(0, 210, 190, 0.20)",
              }}
            >
              Bankroll ref {formatCurrency(valueData.bankrollRef)}
            </span>
          )}
          {!valueData && !loading && (
            <span
              className="inline-flex items-center px-3 py-1.5 rounded-full text-[11px] font-semibold"
              style={{
                background: "rgba(255, 128, 0, 0.10)",
                color: "#FF8000",
                border: "1px solid rgba(255, 128, 0, 0.25)",
              }}
            >
              No odds published yet
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function DisclaimerBanner({
  text,
  className = "",
  emphasis = false,
}: {
  text: string;
  className?: string;
  emphasis?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border px-4 py-3 text-xs leading-relaxed ${className}`}
      style={{
        background: emphasis
          ? "rgba(255, 215, 0, 0.06)"
          : "rgba(255, 255, 255, 0.025)",
        borderColor: emphasis
          ? "rgba(255, 215, 0, 0.22)"
          : "var(--glass-border)",
        color: "var(--text-muted)",
      }}
      role="note"
      aria-label="Disclaimer"
    >
      <span
        className="font-bold uppercase tracking-wider text-[10px] mr-2"
        style={{ color: emphasis ? "#FFD700" : "#FF8000" }}
      >
        Disclaimer
      </span>
      {text}
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: string;
}) {
  return (
    <div className="metric-card">
      <p
        className="text-[11px] font-bold uppercase tracking-[0.14em]"
        style={{ color: "var(--text-muted)" }}
      >
        {label}
      </p>
      <p
        className="stat-number text-3xl font-black mt-2"
        style={{ color: accent || "var(--text)" }}
      >
        {value}
      </p>
      {hint && (
        <p
          className="text-[11px] mt-2 leading-snug"
          style={{ color: "var(--text-muted)" }}
        >
          {hint}
        </p>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div
      className="card p-10 text-center"
      role="status"
      aria-live="polite"
    >
      <div className="max-w-lg mx-auto">
        <div
          className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-4"
          style={{
            background: "rgba(225, 6, 0, 0.10)",
            border: "1px solid rgba(225, 6, 0, 0.25)",
          }}
        >
          <span
            className="text-lg font-black"
            style={{ color: "#E10600" }}
          >
            —
          </span>
        </div>
        <h3
          className="text-lg font-black mb-2"
          style={{ color: "var(--text)" }}
        >
          No value opportunities yet
        </h3>
        <p
          className="text-sm"
          style={{ color: "var(--text-muted)" }}
        >
          Pre-race odds typically publish after Friday qualifying. Check back
          then to see how the model&apos;s probabilities stack up against the
          sportsbook.
        </p>
      </div>
    </div>
  );
}

function SortHeader({
  label,
  align = "left",
  active,
  dir,
  onClick,
  srHint,
}: {
  label: string;
  align?: "left" | "right" | "center";
  active: boolean;
  dir: SortDir;
  onClick: () => void;
  srHint?: string;
}) {
  const arrow = active ? (dir === "asc" ? "▲" : "▼") : "";
  const justify =
    align === "right"
      ? "justify-end"
      : align === "center"
      ? "justify-center"
      : "justify-start";
  return (
    <th
      scope="col"
      aria-sort={ariaSortFor(active, dir)}
      className={`px-4 py-3 text-${align} text-[11px] font-bold uppercase tracking-wider`}
      style={{ color: "var(--text-muted)" }}
    >
      <button
        type="button"
        onClick={onClick}
        className={`inline-flex items-center gap-1.5 ${justify} w-full transition-colors hover:text-[var(--text)] focus:outline-none focus-visible:text-[var(--text)]`}
      >
        <span>{label}</span>
        <span
          aria-hidden="true"
          className={`text-[10px] ${active ? "" : "opacity-30"}`}
        >
          {arrow || "↕"}
        </span>
        {srHint && <span className="sr-only">{srHint}</span>}
      </button>
    </th>
  );
}

function DesktopTable({
  opps,
  sortKey,
  sortDir,
  onSort,
}: {
  opps: ValueOpportunity[];
  sortKey: SortKey;
  sortDir: SortDir;
  onSort: (k: SortKey) => void;
}) {
  return (
    <div className="card overflow-hidden hidden sm:block">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">
            Pre-race betting value opportunities. Each row shows a driver and
            market with the model&apos;s probability, the sportsbook&apos;s
            implied probability, the edge percentage, the fractional Kelly
            stake, and the expected value. Columns are sortable.
          </caption>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th
                scope="col"
                className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider w-12"
                style={{ color: "var(--text-muted)" }}
              >
                #
              </th>
              <SortHeader
                label="Driver"
                active={sortKey === "driver"}
                dir={sortDir}
                onClick={() => onSort("driver")}
              />
              <SortHeader
                label="Market"
                active={sortKey === "market"}
                dir={sortDir}
                onClick={() => onSort("market")}
              />
              <SortHeader
                label="Model %"
                align="right"
                active={sortKey === "modelProbability"}
                dir={sortDir}
                onClick={() => onSort("modelProbability")}
              />
              <SortHeader
                label="Market %"
                align="right"
                active={sortKey === "marketProbability"}
                dir={sortDir}
                onClick={() => onSort("marketProbability")}
              />
              <SortHeader
                label="Edge %"
                align="right"
                active={sortKey === "edgePct"}
                dir={sortDir}
                onClick={() => onSort("edgePct")}
              />
              <SortHeader
                label="Kelly %"
                align="right"
                active={sortKey === "kellyFraction"}
                dir={sortDir}
                onClick={() => onSort("kellyFraction")}
              />
              <SortHeader
                label="EV"
                align="right"
                active={sortKey === "expectedValue"}
                dir={sortDir}
                onClick={() => onSort("expectedValue")}
              />
            </tr>
          </thead>
          <tbody>
            {opps.map((o, i) => {
              const edgeColor = edgeTextColor(o.edgePct);
              const tone = edgeTone(o.edgePct);
              return (
                <tr
                  key={`${o.driver}-${o.market}-${i}`}
                  style={{
                    borderBottom: "1px solid var(--border)",
                    ...rowTintStyle(o.edgePct),
                  }}
                >
                  <td
                    className="px-4 py-3 text-[12px]"
                    style={{ color: "var(--text-muted)" }}
                  >
                    {i + 1}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-1 h-9 rounded shrink-0"
                        style={{ backgroundColor: o.teamColor }}
                        aria-hidden="true"
                      />
                      <div className="min-w-0">
                        <div
                          className="font-bold truncate"
                          style={{ color: "var(--text)" }}
                        >
                          {o.driverFullName || o.driver}
                        </div>
                        <div
                          className="text-[11px] truncate"
                          style={{ color: "var(--text-muted)" }}
                        >
                          {o.team}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="inline-flex px-2 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider"
                      style={{
                        background: "rgba(255, 255, 255, 0.04)",
                        color: "var(--text-secondary)",
                        border: "1px solid var(--glass-border)",
                      }}
                    >
                      {marketLabel(o.market)}
                    </span>
                  </td>
                  <td
                    className="px-4 py-3 text-right stat-number font-semibold"
                    style={{ color: "var(--text)" }}
                  >
                    {formatPct(o.modelProbability)}
                  </td>
                  <td
                    className="px-4 py-3 text-right stat-number"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {formatPct(o.marketProbability)}
                    <span
                      className="text-[10px] ml-1"
                      style={{ color: "var(--text-muted)" }}
                    >
                      ({formatOdds(o.marketOdds)})
                    </span>
                  </td>
                  <td
                    className="px-4 py-3 text-right stat-number font-black text-base"
                    style={{ color: edgeColor }}
                  >
                    <span className="sr-only">
                      {tone === "green"
                        ? "Strong positive edge: "
                        : tone === "yellow"
                        ? "Small positive edge: "
                        : "Negative edge: "}
                    </span>
                    {formatSignedPct(o.edgePct)}
                  </td>
                  <td
                    className="px-4 py-3 text-right stat-number font-semibold"
                    style={{ color: "var(--text)" }}
                  >
                    {formatPct(o.kellyFraction, 2)}
                  </td>
                  <td
                    className="px-4 py-3 text-right stat-number font-semibold"
                    style={{
                      color:
                        o.expectedValue > 0
                          ? "#00D2BE"
                          : o.expectedValue < 0
                          ? "#E10600"
                          : "var(--text-secondary)",
                    }}
                  >
                    {formatCurrency(o.expectedValue)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MobileCards({ opps }: { opps: ValueOpportunity[] }) {
  return (
    <div className="sm:hidden space-y-3">
      {opps.map((o, i) => {
        const edgeColor = edgeTextColor(o.edgePct);
        return (
          <div
            key={`${o.driver}-${o.market}-${i}`}
            className="card p-4 relative overflow-hidden"
            style={{
              ...rowTintStyle(o.edgePct),
            }}
          >
            <div
              className="absolute top-0 left-0 w-full h-0.5"
              style={{ background: o.teamColor }}
              aria-hidden="true"
            />
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="min-w-0">
                <p
                  className="text-[10px] font-bold uppercase tracking-wider mb-0.5"
                  style={{ color: "var(--text-muted)" }}
                >
                  #{i + 1} · {marketLabel(o.market)}
                </p>
                <h3
                  className="text-base font-black leading-tight"
                  style={{ color: "var(--text)" }}
                >
                  {o.driverFullName || o.driver}
                </h3>
                <p
                  className="text-[11px]"
                  style={{ color: "var(--text-muted)" }}
                >
                  {o.team}
                </p>
              </div>
              <div className="text-right shrink-0">
                <p
                  className="text-[10px] font-bold uppercase tracking-wider"
                  style={{ color: "var(--text-muted)" }}
                >
                  Edge
                </p>
                <p
                  className="stat-number text-2xl font-black leading-none"
                  style={{ color: edgeColor }}
                >
                  {formatSignedPct(o.edgePct)}
                </p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div
                className="rounded-md px-3 py-2"
                style={{
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid var(--glass-border)",
                }}
              >
                <p
                  className="text-[10px] uppercase tracking-wider font-bold"
                  style={{ color: "var(--text-muted)" }}
                >
                  Kelly
                </p>
                <p
                  className="stat-number text-base font-bold"
                  style={{ color: "var(--text)" }}
                >
                  {formatPct(o.kellyFraction, 2)}
                </p>
              </div>
              <div
                className="rounded-md px-3 py-2"
                style={{
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid var(--glass-border)",
                }}
              >
                <p
                  className="text-[10px] uppercase tracking-wider font-bold"
                  style={{ color: "var(--text-muted)" }}
                >
                  EV
                </p>
                <p
                  className="stat-number text-base font-bold"
                  style={{
                    color:
                      o.expectedValue > 0
                        ? "#00D2BE"
                        : o.expectedValue < 0
                        ? "#E10600"
                        : "var(--text)",
                  }}
                >
                  {formatCurrency(o.expectedValue)}
                </p>
              </div>
            </div>
            <div
              className="flex items-center justify-between mt-3 pt-3 text-[11px] gap-3"
              style={{ borderTop: "1px solid var(--glass-border)" }}
            >
              <span style={{ color: "var(--text-muted)" }}>
                Model{" "}
                <span
                  className="stat-number font-semibold"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {formatPct(o.modelProbability)}
                </span>
              </span>
              <span style={{ color: "var(--text-muted)" }}>
                Market{" "}
                <span
                  className="stat-number font-semibold"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {formatPct(o.marketProbability)}
                </span>
              </span>
              <span style={{ color: "var(--text-muted)" }}>
                @{" "}
                <span
                  className="stat-number font-semibold"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {formatOdds(o.marketOdds)}
                </span>
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
