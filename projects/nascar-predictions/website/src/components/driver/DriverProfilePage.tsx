"use client";

/**
 * DriverProfilePage — /driver/[code] client profile.
 *
 * Assembles one Cup driver's season story from the same static JSON the rest of
 * the site consumes:
 *   - identity ........ nascar.json driverStandings (team, make, colour, points)
 *   - season summary .. driverStandings (wins, podiums, top-10s, stage wins, …)
 *   - playoff outlook . championship[] (make-the-Chase + title odds + projection)
 *   - points chart .... driverStandings `pointsHistory`
 *   - next-race call .. nextPrediction.race (win / podium / DNF markets)
 *   - pred vs actual .. rounds/*.json `classification` (predicted vs actual)
 *   - reliability ..... rounds/*.json running statuses (observed DNF rate)
 *
 * Every section is null-tolerant: it renders only what the data supports and
 * hides gracefully when a field is absent (reserve drivers, pre-race weeks).
 */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";

import type { NascarData, RoundDetail } from "@/types/nascar";
import { useSeasonNascarData, fetchRoundDetail } from "@/lib/nascarclient";
import { useSeason } from "@/lib/SeasonProvider";
import {
  driverRoundResult,
  computeReliability,
  bestFinish,
  pointsProgression,
  pointsByRound,
  recentForm,
  findStanding,
  findChampionship,
  type DriverRoundResult,
} from "@/lib/driverData";

import DriverPortrait from "@/components/standings/DriverPortrait";
import TeamBadge from "@/components/standings/TeamBadge";
import { teamColor as teamColorFor } from "@/lib/teams";
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

function pct(p: number | null | undefined): string {
  return p == null ? "—" : `${Math.round(p * 100)}%`;
}

export default function DriverProfilePage({ code: rawCode }: Props) {
  const code = (rawCode || "").toUpperCase();
  const { basePath } = useSeason();
  const { data } = useSeasonNascarData();

  const [rounds, setRounds] = useState<RoundDetail[]>([]);
  const [loadingRounds, setLoadingRounds] = useState(true);

  const completedRounds = data?.completedRounds ?? 0;

  useEffect(() => {
    let active = true;
    if (!data) return;
    (async () => {
      setLoadingRounds(true);
      const roundNums = Array.from({ length: completedRounds }, (_, i) => i + 1);
      const fetched = await Promise.all(
        roundNums.map((r) => fetchRoundDetail(r, basePath)),
      );
      if (!active) return;
      setRounds(fetched.filter((r): r is RoundDetail => r !== null));
      setLoadingRounds(false);
    })();
    return () => {
      active = false;
    };
  }, [basePath, data, completedRounds]);

  // ------------------------------------------------------------------ derived
  const standing = useMemo(
    () => findStanding(data?.driverStandings, code),
    [data, code],
  );
  const champ = useMemo(
    () => findChampionship(data?.championship, code),
    [data, code],
  );

  const deltaByRound = useMemo(
    () => pointsByRound(standing?.pointsHistory),
    [standing],
  );

  const results: DriverRoundResult[] = useMemo(() => {
    return rounds
      .map((r) => driverRoundResult(r, code, deltaByRound[r.round] ?? null))
      .filter((r) => r.predictedPosition != null || r.completed)
      .sort((a, b) => a.round - b.round);
  }, [rounds, code, deltaByRound]);

  const reliability = useMemo(() => computeReliability(results), [results]);
  const best = useMemo(() => bestFinish(results), [results]);
  const progression = useMemo(
    () => pointsProgression(standing?.pointsHistory),
    [standing],
  );
  const form = useMemo(() => recentForm(standing?.pointsHistory), [standing]);

  // This driver's forecast for the next scheduled race, when one exists.
  const nextCall = useMemo(() => {
    const race = data?.nextPrediction?.race;
    return race?.find((r) => r.code === code) ?? null;
  }, [data, code]);

  // ------------------------------------------------------------------ identity
  const seasonYear = data?.season ?? new Date().getFullYear();
  const fullName = standing?.name ?? champ?.name ?? code;
  const team = standing?.team ?? champ?.team ?? null;
  const make = standing?.make ?? champ?.make ?? null;
  const teamColor =
    standing?.teamColor ?? (team ? teamColorFor(team) : "var(--accent)");

  // ------------------------------------------------------------------ states
  if (!data) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <LoadingTire label="Loading driver profile" />
      </div>
    );
  }

  const known = Boolean(standing || champ);
  if (!known) {
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

  const positionLabel = standing?.position != null ? `P${standing.position}` : null;
  const playoffFieldSize = data.playoffFieldSize ?? 16;
  const inChaseSpot =
    standing?.position != null && standing.position <= playoffFieldSize;
  const winLocked = (standing?.wins ?? 0) > 0;

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
              {make && <Badge variant="muted">{make}</Badge>}
            </div>
            <h1 className="display-md leading-none">{fullName}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-[color:var(--muted)]">
              {team && (
                <span className="inline-flex items-center gap-2">
                  <TeamBadge team={team} teamColor={teamColor} size={22} />
                  <span className="eyebrow text-[color:var(--body)]">{team}</span>
                </span>
              )}
              <span className="eyebrow">{seasonYear} Cup Series</span>
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
          <Stat label="Top 10s" value={standing.top10s ?? "—"} />
          <Stat label="Stage Wins" value={standing.stageWins ?? "—"} />
          <Stat label="Laps Led" value={standing.lapsLed ?? "—"} />
          <Stat label="Best Finish" value={best != null ? `P${best}` : "—"} />
          <Stat
            label="DNF Rate"
            value={
              reliability.dnfRate != null
                ? `${Math.round(reliability.dnfRate * 100)}%`
                : "—"
            }
            hint={
              reliability.starts > 0
                ? `${reliability.dnfs} DNF · ${reliability.finishes}/${reliability.starts} ran`
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

      {/* ------------------------------------------------------ playoff outlook */}
      {champ && (
        <div className="mt-8">
          <HUDPanel kicker="The Chase" title="Playoff outlook">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <p className="eyebrow mb-1">Makes the Chase field</p>
                <p className="font-tabular text-2xl text-[color:var(--ink)]">
                  {pct(champ.pMakePlayoffs)}
                </p>
              </div>
              <div>
                <p className="eyebrow mb-1">Title odds</p>
                <p className="font-tabular text-2xl text-[color:var(--ink)]">
                  {pct(champ.pTitle)}
                </p>
              </div>
              <div>
                <p className="eyebrow mb-1">Projected reg.-season pts</p>
                <p className="font-tabular text-2xl text-[color:var(--ink)]">
                  {champ.projMean != null ? Math.round(champ.projMean) : "—"}
                </p>
                {champ.projP10 != null && champ.projP90 != null && (
                  <p className="body-sm text-[color:var(--muted)] mt-0.5">
                    {Math.round(champ.projP10)}–{Math.round(champ.projP90)} range
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <p className="eyebrow mb-1">Status</p>
                <div className="flex flex-wrap gap-1.5">
                  {winLocked ? (
                    <Badge variant="positive">Race winner · playoff-eligible</Badge>
                  ) : inChaseSpot ? (
                    <Badge variant="live">In a Chase spot (provisional)</Badge>
                  ) : champ.canStillWin ? (
                    <Badge variant="muted">Chasing a spot</Badge>
                  ) : (
                    <Badge variant="muted">Out of contention</Badge>
                  )}
                </div>
              </div>
            </div>
            <p className="body-sm text-[color:var(--muted)] mt-4">
              The top {playoffFieldSize} on points after the 26-race regular season
              make the Chase; a win all but locks a berth. These odds are the
              model&apos;s, over the rounds still to run.
            </p>
          </HUDPanel>
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
          {nextCall && data.nextPrediction ? (
            <div className="border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-4">
              <p className="body-sm text-[color:var(--muted)] mb-3">
                {data.nextPrediction.raceName || data.nextPrediction.venueName} ·
                predicted P{nextCall.position}
              </p>
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  { label: "Win", value: pct(nextCall.pWin) },
                  { label: "Podium", value: pct(nextCall.pPodium) },
                  { label: "DNF risk", value: pct(nextCall.pDnf) },
                ].map((m) => (
                  <div
                    key={m.label}
                    className="border border-[color:var(--hairline)] p-3"
                  >
                    <div className="font-tabular text-lg text-[color:var(--ink)]">
                      {m.value}
                    </div>
                    <div className="eyebrow mt-1">{m.label}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="body-sm text-[color:var(--muted)] border border-[color:var(--hairline)] p-4">
              No upcoming-race forecast for this driver.
            </div>
          )}
          {reliability.dnfRate != null && (
            <div className="mt-3 flex items-baseline justify-between border border-[color:var(--hairline)] px-4 py-3">
              <span className="eyebrow">Observed DNF rate</span>
              <span className="font-tabular text-sm text-[color:var(--ink)]">
                {Math.round(reliability.dnfRate * 100)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ------------------------------------------------ predicted vs actual */}
      <div className="mt-8">
        <HUDPanel kicker="Round by round" title="Predicted vs actual finish">
          {loadingRounds && results.length === 0 ? (
            <div className="py-8 flex justify-center">
              <LoadingTire label="Loading results" />
            </div>
          ) : (
            <PredictedVsActualTable results={results} />
          )}
        </HUDPanel>
        <p className="body-sm text-[color:var(--muted)] mt-3">
          &ldquo;Pred.&rdquo; is the model&apos;s pre-race finishing call;
          &ldquo;Actual&rdquo; is the classified result. A negative &Delta; means
          the driver finished ahead of the prediction. The next-race DNF risk is a
          forecast, shown alongside the observed DNF rate for honesty.
        </p>
      </div>
    </div>
  );
}
