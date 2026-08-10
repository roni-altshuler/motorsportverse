"use client";

/**
 * DriverProfilePage — /driver/[code] client profile.
 *
 * Assembles a single driver's season story from the same static JSON the rest
 * of the site consumes:
 *   - identity ....... indycar.json standings row (team, engine, colour)
 *   - season summary . standings row (points, position, wins, podiums, form)
 *   - points chart ... the row's cumulative `pointsHistory`
 *   - pred vs actual . rounds/*.json `classification` (predicted vs actual)
 *   - reliability .... rounds/*.json `actualStatus` finish/DNF vocabulary
 *   - next-race look . the next round's `classification` markets, when present
 *
 * Every section is null-tolerant: it renders only what the data supports and
 * hides gracefully when a field is absent. IndyCar ships no per-driver car
 * number or nationality, so those chips are simply omitted (never faked).
 *
 * Ported from the RaceIQ F1 flagship, adapted to IndyCar's single-JSON,
 * `code`-keyed data shape.
 */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";

import type {
  ClassificationEntry,
  IndycarData,
  RoundDetail,
} from "@/types/indycar";
import { useSeason } from "@/lib/SeasonProvider";
import { DEFAULT_SEASON_YEAR } from "@/lib/season";
import { fetchIndycarData, fetchRoundDetail } from "@/lib/indycarclient";
import { teamColor as teamColorFor, engineColor } from "@/lib/teams";
import {
  buildDriverResults,
  computeReliability,
  meanPredictedDnfRisk,
  bestFinish,
  pointsProgression,
  recentForm,
  findStanding,
  type DriverRoundResult,
} from "@/lib/driverData";

import DriverPortrait from "@/components/standings/DriverPortrait";
import { Stat } from "@/components/ui/Stat";
import { Badge } from "@/components/ui/Badge";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { HUDPanel } from "@/components/ui/HUDPanel";
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

  const [data, setData] = useState<IndycarData | null>(null);
  const [rounds, setRounds] = useState<RoundDetail[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    (async () => {
      setLoading(true);
      const seasonData = await fetchIndycarData(basePath).catch(() => null);
      if (!active) return;
      setData(seasonData);

      const total = seasonData?.totalRounds ?? 18;
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
    () => findStanding(data?.driverStandings, code),
    [data, code],
  );

  const results: DriverRoundResult[] = useMemo(
    () => buildDriverResults(rounds, code, standing?.pointsHistory),
    [rounds, code, standing],
  );

  // This driver's classification entries across the season (predicted risk +
  // the "next-race outlook" panel).
  const entries: ClassificationEntry[] = useMemo(() => {
    return rounds
      .map((r) => r.race?.classification?.find((c) => c.code === code))
      .filter((e): e is ClassificationEntry => Boolean(e));
  }, [rounds, code]);

  const reliability = useMemo(() => computeReliability(results), [results]);
  const predictedRisk = useMemo(() => meanPredictedDnfRisk(entries), [entries]);
  const best = useMemo(() => bestFinish(results), [results]);
  const progression = useMemo(
    () => pointsProgression(standing?.pointsHistory),
    [standing],
  );
  const form = useMemo(() => recentForm(standing?.pointsHistory), [standing]);

  // The most relevant classification entry to explain: the next round the
  // driver hasn't run yet, else the latest round we have an entry for.
  const nextEntry: { round: RoundDetail; entry: ClassificationEntry } | null =
    useMemo(() => {
      if (rounds.length === 0) return null;
      const sorted = [...rounds].sort((a, b) => a.round - b.round);
      const upcoming = sorted.find(
        (r) => !r.completed && r.race?.classification?.some((c) => c.code === code),
      );
      const target =
        upcoming ??
        [...sorted].reverse().find((r) =>
          r.race?.classification?.some((c) => c.code === code),
        );
      if (!target) return null;
      const entry = target.race?.classification?.find((c) => c.code === code);
      return entry ? { round: target, entry } : null;
    }, [rounds, code]);

  // ------------------------------------------------------------------ identity
  const seasonYear = data?.season ?? DEFAULT_SEASON_YEAR;
  const fullName = standing?.name ?? code;
  const team = standing?.team ?? null;
  const teamColor =
    standing?.teamColor ?? (team ? teamColorFor(team) : "var(--accent)");
  const engine = standing?.engine ?? null;

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
              {engine && (
                <span
                  className="inline-flex items-center gap-1.5 border border-[color:var(--hairline)] px-2 py-0.5"
                  style={{ borderColor: `${engineColor(engine)}66` }}
                >
                  <span
                    aria-hidden
                    className="inline-block w-2 h-2 rounded-full"
                    style={{ background: engineColor(engine) }}
                  />
                  <span className="eyebrow text-[color:var(--body)]">{engine}</span>
                </span>
              )}
            </div>
            <h1 className="display-md leading-none">{fullName}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-[color:var(--muted)]">
              <span className="font-tabular text-sm">
                <span className="text-[color:var(--muted)]">Code</span>{" "}
                <span className="text-[color:var(--ink)] font-bold">{code}</span>
              </span>
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
          <Stat label="Championship" value={positionLabel ?? "—"} />
          <Stat label="Points" value={standing.points ?? "—"} />
          <Stat label="Wins" value={standing.wins ?? 0} />
          <Stat label="Podiums" value={standing.podiums ?? 0} />
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
          <DriverPointsChart data={progression} teamColor={teamColor} />
        </HUDPanel>

        <div>
          <p className="eyebrow mb-3">Next-race outlook</p>
          {nextEntry ? (
            <div className="border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-4">
              <div className="mb-3 flex items-baseline justify-between gap-2">
                <span className="title-sm text-[color:var(--ink)]">
                  {nextEntry.round.raceName || nextEntry.round.venueName}
                </span>
                <Badge variant={nextEntry.round.completed ? "muted" : "live"}>
                  R{nextEntry.round.round}
                  {nextEntry.round.completed ? " · Result" : " · Predicted"}
                </Badge>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {[
                  { label: "Win", value: pct(nextEntry.entry.pWin) },
                  { label: "Podium", value: pct(nextEntry.entry.pPodium) },
                  { label: "Top 6", value: pct(nextEntry.entry.pTop6) },
                  { label: "Top 10", value: pct(nextEntry.entry.pTop10) },
                ].map((m) => (
                  <div
                    key={m.label}
                    className="border border-[color:var(--hairline)] p-2.5 text-center"
                  >
                    <div className="font-mono font-tabular text-lg text-[color:var(--ink)]">
                      {m.value}
                    </div>
                    <div className="eyebrow mt-1">{m.label}</div>
                  </div>
                ))}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="border border-[color:var(--hairline)] p-2.5">
                  <div className="eyebrow mb-1">Mean finish</div>
                  <div className="font-mono font-tabular text-[color:var(--ink)]">
                    P{nextEntry.entry.meanFinish.toFixed(1)}
                  </div>
                </div>
                <div className="border border-[color:var(--hairline)] p-2.5">
                  <div className="eyebrow mb-1">Finish range</div>
                  <div className="font-mono font-tabular text-[color:var(--ink)]">
                    P{nextEntry.entry.finishRangeLow}–P
                    {nextEntry.entry.finishRangeHigh}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="body-sm text-[color:var(--muted)]">
              No upcoming forecast for this driver.
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
        <HUDPanel kicker="Round by round" title="Predicted vs actual finish">
          <PredictedVsActualTable results={results} />
        </HUDPanel>
        <p className="body-sm text-[color:var(--muted)] mt-3">
          &ldquo;Pred.&rdquo; is the model&apos;s pre-race finishing call;
          &ldquo;Actual&rdquo; is the classified result. A negative &Delta; means
          the driver finished ahead of the prediction. The model&apos;s average
          retirement risk is a forecast, shown alongside the observed DNF rate for
          honesty.
        </p>
      </div>
    </div>
  );
}
