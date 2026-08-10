"use client";

/**
 * DriverProfilePage — /driver/[code] client profile (Formula E).
 *
 * Assembles a single driver's season story from the same static JSON the rest
 * of the site consumes:
 *   - identity ......... fe.json driverStandings (name, team, colour, position)
 *   - season summary ... fe.json standings (points, position, wins, podiums)
 *   - points chart ..... reconstructed per-round from each completed race,
 *                        scaled to the standings total (driverData helper)
 *   - next outlook ..... the driver's classification row on the next/last round
 *                        (win / podium / top-6 / top-10 / mean finish / range)
 *   - pred vs actual ... rounds/*.json classification.position vs actualPosition
 *
 * Ported from the RaceIQ F1 flagship and adapted to FE's data: one race per
 * round, doubleheaders as sibling rounds, and NO per-driver finish status or
 * retirement-risk feed — so the DNF-rate / reliability surface the F1 profile
 * shows is deliberately omitted here rather than faked. Every section is
 * null-tolerant and hides gracefully when a field is absent.
 */
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import Link from "next/link";
import { motion } from "framer-motion";

import type { FEData, RoundDetail, ClassificationEntry } from "@/types/fe";
import { useSeason } from "@/lib/SeasonProvider";
import { fetchFEData, fetchRoundDetail } from "@/lib/feclient";
import { teamColor as teamColorFor } from "@/lib/teams";
import {
  buildDriverResults,
  driverPointsProgression,
  recentForm,
  bestFinish,
  racesScored,
  podiumFinishes,
  findStanding,
  type DriverRoundResult,
} from "@/lib/driverData";

import DriverPortrait from "@/components/standings/DriverPortrait";
import { Stat } from "@/components/ui/Stat";
import { Badge } from "@/components/ui/Badge";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import HUDPanel from "@/components/ui/HUDPanel";
import LoadingTire from "@/components/ui/LoadingTire";
import ShareButton from "@/components/ShareButton";
import DriverPointsChart from "@/components/driver/DriverPointsChart";
import PredictedVsActualTable from "@/components/driver/PredictedVsActualTable";

interface Props {
  code: string;
}

function pct(p: number): string {
  return `${Math.round(p * 100)}%`;
}

export default function DriverProfilePage({ code: rawCode }: Props) {
  const code = (rawCode || "").toUpperCase();
  const { basePath } = useSeason();

  const [data, setData] = useState<FEData | null>(null);
  const [rounds, setRounds] = useState<RoundDetail[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    (async () => {
      setLoading(true);
      const feData = await fetchFEData(basePath).catch(() => null);
      if (!active) return;
      setData(feData);

      const total = feData?.totalRounds ?? 17;
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

  const results: DriverRoundResult[] = useMemo(() => {
    if (!data) return [];
    return buildDriverResults(data, rounds, code);
  }, [data, rounds, code]);

  const progression = useMemo(
    () => driverPointsProgression(results, standing?.points),
    [results, standing],
  );
  const form = useMemo(() => Math.round(recentForm(progression)), [progression]);
  const best = useMemo(() => bestFinish(results), [results]);
  const scored = useMemo(() => racesScored(results), [results]);
  const podiums = useMemo(() => podiumFinishes(results), [results]);

  // Next-race outlook: the driver's forecast row on the next round they have
  // not yet run, else their most recent forecast row.
  const outlook = useMemo((): {
    entry: ClassificationEntry;
    venueName: string;
    upcoming: boolean;
  } | null => {
    if (!data || rounds.length === 0) return null;
    const nextRoundNum = data.calendar.find((c) => !c.completed)?.round ?? null;
    const findEntry = (rn: number | null) =>
      rn != null
        ? rounds.find((r) => r.round === rn)?.race.classification.find((c) => c.code === code)
        : undefined;
    const nextEntry = findEntry(nextRoundNum);
    if (nextEntry && nextRoundNum != null) {
      const venueName =
        rounds.find((r) => r.round === nextRoundNum)?.venueName ?? `Round ${nextRoundNum}`;
      return { entry: nextEntry, venueName, upcoming: true };
    }
    // Fall back to the latest round that carries a forecast for this driver.
    const latest = [...rounds]
      .sort((a, b) => b.round - a.round)
      .map((r) => ({ r, e: r.race.classification.find((c) => c.code === code) }))
      .find((x) => x.e);
    if (latest?.e) {
      return { entry: latest.e, venueName: latest.r.venueName, upcoming: false };
    }
    return null;
  }, [data, rounds, code]);

  // ------------------------------------------------------------------ identity
  const seasonYear = data?.season ?? new Date().getFullYear();
  const seasonLabel = `${seasonYear - 1}-${String(seasonYear).slice(2)}`;
  const fullName = standing?.name ?? code;
  const team = standing?.team ?? null;
  const teamColor =
    standing?.teamColor ?? (team ? teamColorFor(team) : "var(--accent)");
  const headshot = standing?.headshotUrl ?? null;

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
          We don&apos;t have a {seasonLabel} Formula E profile for
          <span className="font-mono"> &ldquo;{code}&rdquo;</span>.
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
      {/* Breadcrumb + share */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-[color:var(--muted)]">
          <Link
            href="/standings"
            className="eyebrow hover:text-[color:var(--ink)] transition-colors"
          >
            Standings
          </Link>
          <span aria-hidden>/</span>
          <span className="eyebrow text-[color:var(--ink)]">{fullName}</span>
        </div>
        <ShareButton
          title={`${fullName} — Formula E ${seasonLabel}`}
          text={`${fullName}${team ? `, ${team}` : ""} — Formula E ${seasonLabel} season form, points progression & predicted-vs-actual results.`}
        />
      </div>

      {/* ---------------------------------------------------------- identity */}
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-5 sm:p-8"
        data-team={team ?? undefined}
        style={{ "--team-color": teamColor } as CSSProperties}
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
            <div className="mt-2 flex flex-wrap items-center gap-4 text-[color:var(--muted)]">
              <span className="eyebrow">{seasonLabel} Season</span>
            </div>
          </div>

          {standing?.points != null && (
            <div className="sm:text-right shrink-0">
              <div className="eyebrow mb-1">Points</div>
              <AnimatedNumber
                value={standing.points}
                variant="huge"
                className="font-mono tabular-nums"
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
            label="Races Scored"
            value={scored}
            hint={
              scored > 0
                ? `${podiums} podium${podiums === 1 ? "" : "s"} this season`
                : "No results yet"
            }
          />
        </div>
      )}

      {/* --------------------------------------------------- charts + outlook */}
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
          <p className="eyebrow mb-3">
            {outlook?.upcoming ? "Next-race outlook" : "Latest race forecast"}
          </p>
          {outlook ? (
            <div className="border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-4">
              <div className="flex items-baseline justify-between mb-3">
                <span className="title-md text-[color:var(--ink)]">
                  {outlook.venueName}
                </span>
                <span className="eyebrow">Pred. P{outlook.entry.position}</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {[
                  { label: "Win", value: pct(outlook.entry.pWin) },
                  { label: "Podium", value: pct(outlook.entry.pPodium) },
                  { label: "Top 6", value: pct(outlook.entry.pTop6) },
                  { label: "Top 10", value: pct(outlook.entry.pTop10) },
                ].map((m) => (
                  <div
                    key={m.label}
                    className="border border-[color:var(--hairline)] p-3 text-center"
                  >
                    <div className="font-mono tabular-nums text-lg text-[color:var(--ink)]">
                      {m.value}
                    </div>
                    <div className="eyebrow mt-1">{m.label}</div>
                  </div>
                ))}
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <div className="border border-[color:var(--hairline)] p-3">
                  <div className="eyebrow mb-1">Mean finish</div>
                  <div className="font-mono tabular-nums text-[color:var(--ink)]">
                    P{outlook.entry.meanFinish.toFixed(1)}
                  </div>
                </div>
                <div className="border border-[color:var(--hairline)] p-3">
                  <div className="eyebrow mb-1">Finish range</div>
                  <div className="font-mono tabular-nums text-[color:var(--ink)]">
                    P{outlook.entry.finishRangeLow}–P{outlook.entry.finishRangeHigh}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="body-sm text-[color:var(--muted)]">
              No current forecast for {code}.
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
          the driver finished ahead of the prediction. Points are the
          finishing-position score; pole and fastest-lap bonuses are absorbed into
          the season total shown above.
        </p>
      </div>
    </div>
  );
}
