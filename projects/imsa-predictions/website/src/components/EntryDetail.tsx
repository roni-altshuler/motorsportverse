"use client";

import Link from "next/link";

import CountryFlag from "@/components/CountryFlag";
import ProgressionChart from "@/components/charts/ProgressionChart";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Stat } from "@/components/ui/Stat";
import { pct, tidyNum } from "@/lib/format";
import type { ChampionshipEntry } from "@/types/imsa";

export interface EntrySummary {
  code: string;
  classKey: string;
  classLabel: string;
  classColor: string;
  standing: {
    position: number;
    points: number;
    wins: number;
    podiums: number;
    number: string;
    team: string;
    manufacturer: string;
    vehicle: string;
    drivers: string[];
    teamColor: string;
    pointsHistory: number[];
  };
  championship: ChampionshipEntry | null;
  progression: { rounds: number[]; values: (number | null)[] };
  results: {
    round: number;
    name: string;
    country: string | null;
    completed: boolean;
    predicted: number;
    actual: number | null;
    pWin: number;
    pPodium: number;
    confidence: string;
  }[];
}

export default function EntryDetail({ summary }: { summary: EntrySummary }) {
  const s = summary.standing;
  const champ = summary.championship;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-3">
          <Link href="/standings" className="link-bugatti text-[11px] uppercase tracking-[0.18em]">
            ← Standings
          </Link>
          <span
            className="class-chip"
            data-class={summary.classKey}
            style={{ ["--class-color" as string]: summary.classColor }}
          >
            {summary.classLabel}
          </span>
        </div>
        <div className="flex items-stretch gap-4">
          <span aria-hidden className="w-1.5 rounded-full shrink-0" style={{ background: s.teamColor }} />
          <div>
            <h1 className="display-lg flex items-baseline gap-3">
              <span className="font-mono tabular-nums" style={{ color: s.teamColor }}>
                #{s.number}
              </span>
              <span>{s.team}</span>
            </h1>
            <p className="body-md mt-2 text-[color:var(--muted)]">
              {s.manufacturer} · {s.vehicle}
            </p>
            {s.drivers.length > 0 && (
              <p className="body-sm mt-1 text-[color:var(--body)]">{s.drivers.join(" · ")}</p>
            )}
          </div>
        </div>
      </div>

      {/* Season stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-10">
        <Stat label={`${summary.classLabel} position`} value={`P${s.position}`} hint="in class standings" />
        <Stat label="Points" value={tidyNum(s.points)} hint="this season" />
        <Stat label="Wins" value={s.wins} hint="class wins" />
        <Stat label="Podiums" value={s.podiums} hint="class podiums" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Points progression */}
        <div className="lg:col-span-2">
          <Card className="p-5 sm:p-6 h-full">
            <h2 className="title-md mb-1">Points progression</h2>
            <p className="body-sm text-[color:var(--muted)] mb-4">
              Cumulative championship points across the completed rounds.
            </p>
            {summary.progression.rounds.length > 0 ? (
              <div className="overflow-x-auto">
                <div className="min-w-[480px]">
                  <ProgressionChart
                    rounds={summary.progression.rounds}
                    series={[
                      {
                        code: summary.code,
                        label: `#${s.number} ${s.team}`,
                        color: s.teamColor,
                        values: summary.progression.values,
                      },
                    ]}
                    height={260}
                  />
                </div>
              </div>
            ) : (
              <p className="body-sm text-[color:var(--muted-soft)]">No completed rounds yet.</p>
            )}
          </Card>
        </div>

        {/* Title projection */}
        <div>
          <Card className="p-5 sm:p-6 h-full">
            <h2 className="title-md mb-4">Title projection</h2>
            {champ ? (
              <div className="flex flex-col gap-4">
                <div>
                  <p className="eyebrow">Title odds</p>
                  <p className="display-md font-tabular mt-1" style={{ color: summary.classColor }}>
                    {pct(champ.pTitle, champ.pTitle >= 0.1 ? 0 : 1)}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="eyebrow">Proj. final</p>
                    <p className="title-md font-tabular mt-1 text-[color:var(--ink)]">
                      {Math.round(champ.projMean)}
                    </p>
                  </div>
                  <div>
                    <p className="eyebrow">Range</p>
                    <p className="title-md font-tabular mt-1 text-[color:var(--ink)]">
                      {Math.round(champ.projP10)}–{Math.round(champ.projP90)}
                    </p>
                  </div>
                </div>
                <div className="pt-3 border-t border-[color:var(--hairline)]">
                  <Badge variant={champ.canStillWin ? "positive" : "muted"}>
                    {champ.canStillWin ? "Can still win the title" : "Out of title contention"}
                  </Badge>
                </div>
              </div>
            ) : (
              <p className="body-sm text-[color:var(--muted-soft)]">No projection available.</p>
            )}
          </Card>
        </div>
      </div>

      {/* Per-round results */}
      <Card className="overflow-hidden mt-6">
        <div className="px-5 py-4 border-b border-[color:var(--hairline)]">
          <h2 className="title-md">Round-by-round</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse">
            <thead>
              <tr>
                {["Round", "Predicted", "Actual", "Win", "Podium", ""].map((h, i) => (
                  <th
                    key={i}
                    className="eyebrow px-4 py-3 border-b border-[color:var(--hairline)] whitespace-nowrap"
                    style={{ textAlign: i === 0 ? "left" : "right" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {summary.results.map((r) => {
                const delta = r.actual != null ? r.actual - r.predicted : null;
                return (
                  <tr key={r.round} className="transition-colors hover:bg-[color:var(--surface-elevated)]/40">
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)]">
                      <Link href={`/round/${r.round}`} className="flex items-center gap-2 hover:opacity-80">
                        <CountryFlag country={r.country} size={20} />
                        <span className="text-[13px] text-[color:var(--ink)]">{r.name}</span>
                        <span className="eyebrow">R{r.round}</span>
                      </Link>
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-mono tabular-nums text-[color:var(--muted)]">
                      P{r.predicted}
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-mono tabular-nums text-[color:var(--ink)]">
                      {r.completed ? (r.actual != null ? `P${r.actual}` : "DNF/NC") : "—"}
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-tabular text-[color:var(--muted)]">
                      {pct(r.pWin, 1)}
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-tabular text-[color:var(--muted)]">
                      {pct(r.pPodium, 1)}
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right">
                      {r.completed && delta != null ? (
                        <span
                          className="text-[11px] font-mono tabular-nums"
                          style={{ color: delta <= 0 ? "var(--success)" : "var(--accent-negative)" }}
                        >
                          {delta === 0 ? "exact" : delta < 0 ? `▲ ${Math.abs(delta)}` : `▼ ${delta}`}
                        </span>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
