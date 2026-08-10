"use client";

/**
 * DriverProfilePage — /driver/[code] client profile (RaceIQ WRC).
 *
 * Assembles a single crew's season story from the same static JSON the rest
 * of the site consumes:
 *   - identity ........ wrc.json `driverStandings` (code, name, team, colour)
 *   - season summary .. wrc.json standings (points, position, wins, podiums)
 *   - points chart .... wrc.json standings `pointsHistory`
 *   - next-rally outlook wrc.json `nextPrediction` (predicted win / podium)
 *   - pred vs actual .. rounds/*.json `classification` vs the classified result —
 *                       one scored classification per round
 *   - reliability ..... rounds/*.json classified finishes (observed DNF/NC rate)
 *
 * Ported from the RaceIQ F1 flagship's DriverProfilePage and rewired to WRC's
 * single-file / one-rally-per-round data. Every section is null-tolerant: it
 * renders only what the data supports and hides gracefully when a field is absent.
 */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";

import type { WrcData, RoundDetail } from "@/types/wrc";
import { useSeason } from "@/lib/SeasonProvider";
import { fetchWrcData, fetchRoundDetail } from "@/lib/wrcClient";
import { DEFAULT_SEASON_YEAR } from "@/lib/season";
import { teamColor as teamColorFor } from "@/lib/teams";
import { surfaceColor, surfaceLabel } from "@/lib/surface";
import {
  driverSeasonResults,
  computeReliability,
  bestFinish,
  pointsFinishes,
  pointsProgression,
  recentForm,
  findDriverStanding,
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

function pct(p: number | null | undefined): string {
  return p == null ? "—" : `${Math.round(p * 100)}%`;
}

export default function DriverProfilePage({ code: rawCode }: Props) {
  const code = (rawCode || "").toUpperCase();
  const { basePath } = useSeason();

  const [data, setData] = useState<WrcData | null>(null);
  const [rounds, setRounds] = useState<RoundDetail[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    (async () => {
      setLoading(true);
      const seasonData = await fetchWrcData(basePath).catch(() => null);
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

  const results: DriverRaceResult[] = useMemo(
    () => driverSeasonResults(rounds, code),
    [rounds, code],
  );

  const reliability = useMemo(() => computeReliability(results), [results]);
  const best = useMemo(() => bestFinish(results), [results]);
  const scoring = useMemo(() => pointsFinishes(results), [results]);
  const progression = useMemo(
    () => pointsProgression(standing?.pointsHistory),
    [standing],
  );
  const form = useMemo(() => recentForm(standing?.pointsHistory), [standing]);

  // Next-rally outlook for this crew, from the season's nextPrediction block.
  // A rally is a single classification — the forecast is win / podium probability
  // for the crew's next event.
  const nextOutlook = useMemo(() => {
    const np = data?.nextPrediction;
    if (!np) return null;
    const entry = np.rally?.find((r) => r.code === code) ?? null;
    if (!entry) return null;
    return {
      round: np.round,
      venueName: np.venueName,
      surface: np.surface,
      surfaceColor: np.surfaceColor,
      predictedPosition: entry.position ?? null,
      pWin: entry.pWin ?? null,
      pPodium: entry.pPodium ?? null,
    };
  }, [data, code]);

  // ------------------------------------------------------------------ identity
  const seasonYear = data?.season ?? DEFAULT_SEASON_YEAR;
  const fullName = standing?.name ?? code;
  const team = standing?.team ?? null;
  const teamColor = standing?.teamColor || (team ? teamColorFor(team) : "var(--accent)");

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

  const positionLabel = standing?.position != null ? `P${standing.position}` : null;

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
              <span className="eyebrow">{seasonYear} WRC</span>
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
            label="Best Finish"
            value={best != null ? `P${best}` : "—"}
            hint={scoring > 0 ? `${scoring} points finish${scoring === 1 ? "" : "es"}` : undefined}
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
                ? `${reliability.dnfs} DNF · ${reliability.finishes}/${reliability.starts} classified`
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
          <p className="eyebrow mb-3">Next-rally outlook</p>
          {nextOutlook ? (
            <div className="border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-5">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="eyebrow mb-1">Round {nextOutlook.round} · Pre-rally forecast</p>
                  <p className="title-md text-[color:var(--ink)] truncate">
                    {nextOutlook.venueName}
                  </p>
                </div>
                <span
                  className="shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em]"
                  style={{
                    color: surfaceColor(nextOutlook.surface, nextOutlook.surfaceColor),
                    border: `1px solid color-mix(in srgb, ${surfaceColor(
                      nextOutlook.surface,
                      nextOutlook.surfaceColor,
                    )} 45%, transparent)`,
                    background: `color-mix(in srgb, ${surfaceColor(
                      nextOutlook.surface,
                      nextOutlook.surfaceColor,
                    )} 12%, transparent)`,
                  }}
                >
                  {surfaceLabel(nextOutlook.surface)}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="border border-[color:var(--hairline)] py-3">
                  <div className="font-mono font-tabular text-lg text-[color:var(--ink)]">
                    {nextOutlook.predictedPosition != null
                      ? `P${nextOutlook.predictedPosition}`
                      : "—"}
                  </div>
                  <div className="eyebrow mt-1">Predicted</div>
                </div>
                <div className="border border-[color:var(--hairline)] py-3">
                  <div className="font-mono font-tabular text-lg text-[color:var(--ink)]">
                    {pct(nextOutlook.pWin)}
                  </div>
                  <div className="eyebrow mt-1">Win</div>
                </div>
                <div className="border border-[color:var(--hairline)] py-3">
                  <div className="font-mono font-tabular text-lg text-[color:var(--ink)]">
                    {pct(nextOutlook.pPodium)}
                  </div>
                  <div className="eyebrow mt-1">Podium</div>
                </div>
              </div>
              <p className="body-sm text-[color:var(--muted)] mt-4">
                The model&apos;s pre-rally call. Win and podium chances are its forecast,
                not a certainty.
              </p>
            </div>
          ) : (
            <div className="border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-5 body-sm text-[color:var(--muted)]">
              No upcoming-round forecast available for {code}.
            </div>
          )}
          {reliability.starts > 0 && (
            <div className="mt-3 flex items-baseline justify-between border border-[color:var(--hairline)] px-4 py-3">
              <span className="eyebrow">Classified finish rate</span>
              <span className="font-tabular text-sm text-[color:var(--ink)]">
                {Math.round((reliability.finishes / reliability.starts) * 100)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ------------------------------------------------ predicted vs actual */}
      <div className="mt-8">
        <HUDPanel kicker="Rally by rally" title="Predicted vs actual finish">
          <PredictedVsActualTable results={results} />
        </HUDPanel>
        <p className="body-sm text-[color:var(--muted)] mt-3">
          Each round is a single rally on gravel, tarmac or snow. &ldquo;Pred.&rdquo; is
          the model&apos;s pre-rally finishing call; &ldquo;Actual&rdquo; is the official
          classification. A negative &Delta; means the crew finished ahead of the
          prediction; &ldquo;Pts&rdquo; is the base championship points for that finish.
        </p>
      </div>
    </div>
  );
}
