"use client";

/**
 * DriverProfilePage — /driver/[code] client profile.
 *
 * Assembles a single driver's season story from the same static JSON the rest
 * of the site consumes:
 *   - identity ....... season.json roster (number, team, colour) + standings
 *   - season summary . standings.json (points, position, wins, podiums, form)
 *   - points chart ... standings.json `pointsHistory`
 *   - pred vs actual . rounds/*.json `classification` vs race-result rows
 *   - reliability .... rounds/*.json finish statuses (observed DNF rate)
 *
 * Every section is null-tolerant: it renders only what the data supports and
 * hides gracefully when a field is absent (reserve drivers, pre-race weeks).
 */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";

import type {
  SeasonData,
  StandingsData,
  RoundData,
  ClassificationEntry,
} from "@/types";
import { useSeason } from "@/lib/SeasonProvider";
import { DEFAULT_SEASON_YEAR } from "@/lib/season";
import {
  fetchSeasonJson,
  fetchStandingsJson,
  fetchRoundJson,
  driverRoundResult,
  computeReliability,
  meanPredictedDnfRisk,
  bestFinish,
  pointsProgression,
  recentForm,
  findStanding,
  findDriverInfo,
  type DriverRoundResult,
} from "@/lib/driverData";

import DriverPortrait from "@/components/standings/DriverPortrait";
import DriverDetailSheet from "@/components/DriverDetailSheet";
import { resolveDriverHeadshot } from "@/lib/headshots";
import { Stat } from "@/components/ui/Stat";
import { Badge } from "@/components/ui/Badge";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import HUDPanel from "@/components/ui/HUDPanel";
import LoadingTire from "@/components/ui/LoadingTire";
import DriverPointsChart from "@/components/driver/DriverPointsChart";
import PredictedVsActualTable from "@/components/driver/PredictedVsActualTable";

interface Props {
  code: string;
}

export default function DriverProfilePage({ code: rawCode }: Props) {
  const code = (rawCode || "").toUpperCase();
  const { basePath } = useSeason();

  const [season, setSeason] = useState<SeasonData | null>(null);
  const [standings, setStandings] = useState<StandingsData | null>(null);
  const [rounds, setRounds] = useState<RoundData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);

    (async () => {
      // Season + standings in parallel; rounds depend on the season's length.
      const [seasonData, standingsData] = await Promise.all([
        fetchSeasonJson(basePath).catch(() => null),
        fetchStandingsJson(basePath).catch(() => null),
      ]);
      if (!active) return;
      setSeason(seasonData);
      setStandings(standingsData);

      const total = seasonData?.totalRounds ?? 22;
      const roundNums = Array.from({ length: total }, (_, i) => i + 1);
      const fetched = await Promise.all(
        roundNums.map((r) => fetchRoundJson(r, basePath)),
      );
      if (!active) return;
      setRounds(fetched.filter((r): r is RoundData => r !== null));
      setLoading(false);
    })();

    return () => {
      active = false;
    };
  }, [basePath]);

  // ------------------------------------------------------------------ derived
  const driverInfo = useMemo(
    () => findDriverInfo(season?.drivers, code),
    [season, code],
  );
  const standing = useMemo(
    () => findStanding(standings?.drivers, code),
    [standings, code],
  );

  // This driver's per-round predicted-vs-actual results (rounds where the
  // driver actually appears in the classification or the result set).
  const results: DriverRoundResult[] = useMemo(() => {
    return rounds
      .map((r) => driverRoundResult(r, code))
      .filter((r) => r.predictedPosition != null || r.completed)
      .sort((a, b) => a.round - b.round);
  }, [rounds, code]);

  // This driver's classification entries across the season (for predicted risk
  // + the "why this prediction" detail on the latest relevant round).
  const entries: ClassificationEntry[] = useMemo(() => {
    return rounds
      .map((r) => r.classification?.find((c) => c.driver === code))
      .filter((e): e is ClassificationEntry => Boolean(e));
  }, [rounds, code]);

  const reliability = useMemo(() => computeReliability(results), [results]);
  const predictedRisk = useMemo(() => meanPredictedDnfRisk(entries), [entries]);
  const best = useMemo(() => bestFinish(results), [results]);
  const progression = useMemo(
    () => pointsProgression(standing?.pointsHistory),
    [standing],
  );
  const form = useMemo(
    () => recentForm(standing?.pointsHistory),
    [standing],
  );

  // Pick the most relevant classification entry to explain: the next race the
  // driver hasn't run yet, else the latest round we have an entry for.
  const latestEntry: ClassificationEntry | null = useMemo(() => {
    if (!season || rounds.length === 0) return null;
    const completed = new Set(season.completedRounds ?? []);
    const nextRoundNum = rounds
      .map((r) => r.round)
      .sort((a, b) => a - b)
      .find((n) => !completed.has(n));
    const targetRound =
      rounds.find((r) => r.round === nextRoundNum) ??
      [...rounds].sort((a, b) => b.round - a.round)[0];
    return targetRound?.classification?.find((c) => c.driver === code) ?? null;
  }, [season, rounds, code]);

  // ------------------------------------------------------------------ identity
  const seasonYear = season?.season ?? DEFAULT_SEASON_YEAR;
  const fullName =
    driverInfo?.fullName ?? standing?.driverFullName ?? code;
  const team = driverInfo?.team ?? standing?.team ?? null;
  const teamColor =
    driverInfo?.teamColor ?? standing?.teamColor ?? "var(--accent)";
  const number = driverInfo?.number ?? null;
  const headshot = resolveDriverHeadshot(code, driverInfo?.headshotUrl);

  // ------------------------------------------------------------------ states
  if (loading && !season && !standings) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <LoadingTire label="Loading driver profile" />
      </div>
    );
  }

  const known = Boolean(driverInfo || standing);
  if (!loading && !known) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-24 text-center">
        <p className="eyebrow mb-3">Driver profile</p>
        <h1 className="display-sm mb-4">Driver not found</h1>
        <p className="body-sm text-[color:var(--muted)] mb-8">
          We don&apos;t have a {seasonYear} profile for
          <span className="font-tabular"> &ldquo;{code}&rdquo;</span>.
        </p>
        <Link
          href="/standings"
          className="link-bugatti button-label text-[12px]"
        >
          View the championship standings →
        </Link>
      </div>
    );
  }

  const positionLabel =
    standing?.position != null ? `P${standing.position}` : null;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-24">
      {/* Breadcrumb */}
      <div className="mb-6 flex items-center gap-2 text-[color:var(--muted)]">
        <Link
          href="/standings"
          className="eyebrow hover:text-[color:var(--ink)] transition-colors"
        >
          Standings
        </Link>
        <span aria-hidden>/</span>
        <span className="eyebrow text-[color:var(--ink)]">{fullName}</span>
      </div>

      {/* ---------------------------------------------------------- identity */}
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-5 sm:p-8"
        data-team={team ?? undefined}
        style={{ "--team-color": teamColor } as React.CSSProperties}
      >
        {/* Full-height team accent strip (inline-styled for predictable size). */}
        <span
          aria-hidden
          className="absolute left-0 top-0 bottom-0 w-1"
          style={{
            background: `linear-gradient(180deg, ${teamColor} 0%, ${teamColor}33 100%)`,
          }}
        />
        <div className="flex flex-col sm:flex-row sm:items-center gap-6 pl-3">
          <DriverPortrait
            driver={code}
            driverFullName={fullName}
            team={team ?? ""}
            teamColor={teamColor}
            headshotUrl={headshot}
            size={112}
          />

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              {positionLabel && (
                <Badge variant="live">Championship {positionLabel}</Badge>
              )}
              {team && <Badge variant="default">{team}</Badge>}
            </div>
            <h1 className="display-md leading-none">{fullName}</h1>
            <div className="mt-2 flex items-center gap-4 text-[color:var(--muted)]">
              {number != null && (
                <span className="font-tabular text-sm">
                  <span className="text-[color:var(--muted)]">No.</span>{" "}
                  <span className="text-[color:var(--ink)] font-bold">
                    {number}
                  </span>
                </span>
              )}
              <span className="eyebrow">{seasonYear} Season</span>
            </div>
          </div>

          {/* Points headline */}
          {standing?.points != null && (
            <div className="sm:text-right shrink-0">
              <div className="eyebrow mb-1">Points</div>
              <AnimatedNumber
                value={standing.points}
                variant="huge"
                className="font-tabular"
              />
            </div>
          )}
        </div>
      </motion.section>

      {/* ----------------------------------------------------- season summary */}
      {standing && (
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <Stat
            label="Championship"
            value={positionLabel ?? "—"}
          />
          <Stat label="Points" value={standing.points ?? "—"} />
          <Stat label="Wins" value={standing.wins ?? 0} />
          <Stat label="Podiums" value={standing.podiums ?? 0} />
          <Stat
            label="Best Finish"
            value={best != null ? `P${best}` : "—"}
          />
          <Stat
            label="DNF Rate"
            value={
              reliability.dnfRate != null
                ? `${Math.round(reliability.dnfRate * 100)}%`
                : "—"
            }
            hint={
              reliability.starts > 0
                ? `${reliability.dnfs} DNF · ${reliability.finishes}/${reliability.starts} finished`
                : "No race starts yet"
            }
            tone={
              reliability.dnfRate != null && reliability.dnfRate > 0.2
                ? "negative"
                : "default"
            }
          />
        </div>
      )}

      {/* --------------------------------------------------- charts + form row */}
      <div className="mt-8 grid gap-6 lg:grid-cols-[1.4fr_1fr] items-start">
        <HUDPanel
          kicker="Season progression"
          title="Championship points"
          rightSlot={
            form !== 0 ? (
              <Badge variant={form > 0 ? "positive" : "muted"}>
                Last 3: {form > 0 ? `+${form}` : form}
              </Badge>
            ) : undefined
          }
        >
          <DriverPointsChart
            data={progression}
            teamColor={teamColor}
          />
        </HUDPanel>

        <div>
          <p className="eyebrow mb-3">Recent form &amp; next-race outlook</p>
          {standings?.drivers ? (
            <DriverDetailSheet
              driver={code}
              standings={standings.drivers}
              fullName={fullName}
              entry={latestEntry}
            />
          ) : (
            <div className="body-sm text-[color:var(--muted)]">
              Form data unavailable.
            </div>
          )}
          {predictedRisk != null && (
            <div className="mt-3 flex items-baseline justify-between border border-[color:var(--hairline)] px-4 py-3">
              <span className="eyebrow">Model&apos;s avg retirement risk</span>
              <span className="font-tabular text-sm text-[color:var(--ink)]">
                {Math.round(predictedRisk * 100)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ------------------------------------------------ predicted vs actual */}
      <div className="mt-8">
        <HUDPanel
          kicker="Round by round"
          title="Predicted vs actual finish"
        >
          <PredictedVsActualTable results={results} />
        </HUDPanel>
        <p className="body-sm text-[color:var(--muted)] mt-3">
          &ldquo;Pred.&rdquo; is the model&apos;s pre-race finishing call;
          &ldquo;Actual&rdquo; is the classified result. A negative &Delta;
          means the driver finished ahead of the prediction. The model&apos;s
          average retirement risk is a forecast, shown alongside the observed
          DNF rate for honesty.
        </p>
      </div>
    </div>
  );
}
