"use client";

/**
 * DriverProfilePage — /driver/[code] client profile for RaceIQ F2.
 *
 * Assembles one driver's season story from the same static JSON the rest of the
 * site consumes:
 *   - identity ....... driverStandings row (team, colour, headshot)
 *   - season summary . driverStandings (points, position, wins, podiums) +
 *                      championship (title chance, projected finish)
 *   - points chart ... driverStandings `pointsHistory`
 *   - next outlook ... nextPrediction feature-race line (win / podium %)
 *   - pred vs actual . rounds/*.json sprint + feature `classification`
 *
 * Ported from the F1 flagship and adapted to F2's data reality: a single
 * f2.json (no season/standings split), two scored races per round, and no
 * per-driver finish-status / DNF field — so the F1 reliability + retirement-risk
 * sections are intentionally omitted rather than faked.
 */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";

import type { F2Data, RoundDetail } from "@/types/f2";
import { fetchF2Data, fetchRoundDetail } from "@/lib/f2client";
import { useSeason } from "@/lib/SeasonProvider";
import { DEFAULT_SEASON_YEAR } from "@/lib/season";
import { teamColor as teamColorFor } from "@/lib/teams";
import {
  driverRaceResults,
  bestFinish,
  meanAbsError,
  pointsProgression,
  recentForm,
  findDriverStanding,
  findTitleOdds,
  findNextRaceEntry,
  type DriverRaceResult,
} from "@/lib/driverData";

import DriverPortrait from "@/components/standings/DriverPortrait";
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

  const [data, setData] = useState<F2Data | null>(null);
  const [rounds, setRounds] = useState<RoundDetail[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    (async () => {
      setLoading(true);
      const seasonData = await fetchF2Data(basePath).catch(() => null);
      if (!active) return;
      setData(seasonData);

      const total = seasonData?.totalRounds ?? 14;
      const roundNums = Array.from({ length: total }, (_, i) => i + 1);
      const fetched = await Promise.all(
        roundNums.map((r) => fetchRoundDetail(r, basePath)),
      );
      if (!active) return;
      setRounds(fetched.filter((r): r is RoundDetail => r !== null));
      setLoading(false);
    })();

    return () => {
      active = false;
    };
  }, [basePath]);

  // ------------------------------------------------------------------ derived
  const standing = useMemo(
    () => findDriverStanding(data?.driverStandings, code),
    [data, code],
  );
  const titleOdds = useMemo(
    () => findTitleOdds(data?.championship, code),
    [data, code],
  );
  const nextEntry = useMemo(
    () => findNextRaceEntry(data?.nextPrediction?.race, code),
    [data, code],
  );

  const results: DriverRaceResult[] = useMemo(
    () => driverRaceResults(rounds, code),
    [rounds, code],
  );
  const bestFeature = useMemo(() => bestFinish(results, "feature"), [results]);
  const modelError = useMemo(() => meanAbsError(results), [results]);
  const progression = useMemo(
    () => pointsProgression(standing?.pointsHistory),
    [standing],
  );
  const form = useMemo(() => recentForm(standing?.pointsHistory), [standing]);

  // ------------------------------------------------------------------ identity
  const seasonYear = data?.season ?? DEFAULT_SEASON_YEAR;
  const fullName = standing?.name ?? code;
  const team = standing?.team ?? null;
  const teamColor =
    standing?.teamColor ?? (team ? teamColorFor(team) : "var(--accent)");

  // ------------------------------------------------------------------ states
  if (loading && !data) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <LoadingTire label="Loading driver profile" />
      </div>
    );
  }

  if (!loading && !standing) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-24 text-center">
        <p className="eyebrow mb-3">Driver profile</p>
        <h1 className="display-sm mb-4">Driver not found</h1>
        <p className="body-sm text-[color:var(--muted)] mb-8">
          We don&apos;t have a {seasonYear} profile for
          <span className="font-tabular"> &ldquo;{code}&rdquo;</span>.
        </p>
        <Link href="/standings" className="link-bugatti button-label text-[12px]">
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
        {/* Full-height team accent strip. */}
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
            headshotUrl={standing?.headshotUrl}
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
            <div className="mt-2 flex flex-wrap items-center gap-4 text-[color:var(--muted)]">
              <span className="font-tabular text-sm">
                <span className="text-[color:var(--muted)]">Code</span>{" "}
                <span className="text-[color:var(--ink)] font-bold">{code}</span>
              </span>
              <span className="eyebrow">{seasonYear} FIA Formula 2</span>
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
          <Stat label="Championship" value={positionLabel ?? "—"} />
          <Stat label="Points" value={standing.points ?? "—"} />
          <Stat label="Wins" value={standing.wins ?? 0} />
          <Stat label="Podiums" value={standing.podiums ?? 0} />
          <Stat
            label="Best Feature"
            value={bestFeature != null ? `P${bestFeature}` : "—"}
          />
          <Stat
            label="Title Chance"
            value={
              titleOdds?.pTitle != null
                ? `${Math.round(titleOdds.pTitle * 100)}%`
                : "—"
            }
            hint={
              titleOdds?.projMean != null
                ? `Proj. ${Math.round(titleOdds.projMean)} pts`
                : undefined
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
          <DriverPointsChart data={progression} teamColor={teamColor} />
        </HUDPanel>

        <div>
          <p className="eyebrow mb-3">Next-race outlook</p>
          {nextEntry && data?.nextPrediction ? (
            <div className="border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-5">
              <div className="flex items-baseline justify-between mb-4">
                <span className="title-md">{data.nextPrediction.venueName}</span>
                <Badge variant="info">R{data.nextPrediction.round}</Badge>
              </div>
              <p className="body-sm text-[color:var(--muted)] mb-4">
                The model&apos;s call for {fullName} in the next feature race.
              </p>
              <div className="grid grid-cols-3 gap-3">
                <Stat
                  size="sm"
                  label="Grid"
                  value={nextEntry.position != null ? `P${nextEntry.position}` : "—"}
                />
                <Stat
                  size="sm"
                  label="Win"
                  value={`${Math.round(nextEntry.pWin * 100)}%`}
                />
                <Stat
                  size="sm"
                  label="Podium"
                  value={`${Math.round(nextEntry.pPodium * 100)}%`}
                />
              </div>
            </div>
          ) : (
            <div className="border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-5 body-sm text-[color:var(--muted)]">
              No upcoming-round forecast for {fullName} yet.
            </div>
          )}
          {modelError != null && (
            <div className="mt-3 flex items-baseline justify-between border border-[color:var(--hairline)] px-4 py-3">
              <span className="eyebrow">Model&apos;s avg position error</span>
              <span className="font-tabular text-sm text-[color:var(--ink)]">
                {modelError.toFixed(1)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ------------------------------------------------ predicted vs actual */}
      <div className="mt-8">
        <HUDPanel kicker="Race by race" title="Predicted vs actual finish">
          <PredictedVsActualTable results={results} />
        </HUDPanel>
        <p className="body-sm text-[color:var(--muted)] mt-3">
          Every F2 round runs a reversed-grid Sprint and a merit Feature race,
          each modelled separately. &ldquo;Pred.&rdquo; is the model&apos;s
          pre-race finishing call; &ldquo;Actual&rdquo; is the classified result.
          A negative &Delta; means the driver finished ahead of the prediction.
          Points are the base points for the finishing position.
        </p>
      </div>
    </div>
  );
}
