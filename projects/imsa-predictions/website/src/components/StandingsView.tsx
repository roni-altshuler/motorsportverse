"use client";

import { useState } from "react";

import ClassSelector from "@/components/ClassSelector";
import EntryIdentity from "@/components/EntryIdentity";
import ProgressionChart, { type ProgressionSeries } from "@/components/charts/ProgressionChart";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { pct, tidyNum } from "@/lib/format";
import type {
  ChampionshipClass,
  ClassMeta,
  EntryStanding,
} from "@/types/imsa";
import type { PointsProgression } from "@/lib/imsaData";

export default function StandingsView({
  classes,
  standings,
  championship,
  progression,
}: {
  classes: ClassMeta[];
  standings: Record<string, EntryStanding[]>;
  championship: Record<string, ChampionshipClass>;
  progression: PointsProgression;
}) {
  const [activeClass, setActiveClass] = useState(classes[0]?.key ?? "");
  const active = classes.find((c) => c.key === activeClass) ?? classes[0];
  const rows = standings[activeClass] ?? [];
  const champ = championship[activeClass];

  // Progression series — the top 6 by current points, coloured by team.
  const series: ProgressionSeries[] = rows.slice(0, 6).map((r) => ({
    code: r.code,
    label: `#${r.number} ${r.team}`,
    color: r.teamColor,
    values: progression.byClass[activeClass]?.[r.code] ?? [],
  }));

  const canStillWin = champ?.entries.filter((e) => e.canStillWin).length ?? 0;
  const titleRace = (champ?.entries ?? []).slice(0, 8);
  const maxTitle = Math.max(0.0001, ...titleRace.map((e) => e.pTitle));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <header className="mb-8">
        <p className="eyebrow mb-2">Championship</p>
        <h1 className="display-lg">Standings</h1>
        <p className="body-md mt-3 max-w-2xl text-[color:var(--muted)]">
          Endurance racing runs several championships at once. Pick a class to see its points table,
          per-round progression, and the mathematical title race.
        </p>
      </header>

      <div className="mb-8">
        <ClassSelector classes={classes} value={activeClass} onChange={setActiveClass} />
      </div>

      <div
        role="tabpanel"
        id={`class-panel-${activeClass}`}
        aria-labelledby={`class-tab-${activeClass}`}
      >
        {/* Progression chart */}
        {progression.rounds.length > 0 && series.length > 0 && (
          <Card className="p-5 sm:p-6 mb-8">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="title-md">{active.label} · points progression</h2>
                <p className="body-sm text-[color:var(--muted)] mt-1">
                  Cumulative championship points across the {progression.rounds.length} completed round
                  {progression.rounds.length === 1 ? "" : "s"} — top {series.length} shown.
                </p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <div className="min-w-[560px]">
                <ProgressionChart rounds={progression.rounds} series={series} />
              </div>
            </div>
          </Card>
        )}

        {/* Standings table */}
        <Card className="overflow-hidden mb-8">
          <div className="px-5 py-4 border-b border-[color:var(--hairline)] flex items-center justify-between">
            <h2 className="title-md">{active.label} · table</h2>
            <Badge variant="muted">{rows.length} cars</Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse">
              <thead>
                <tr>
                  {["", "Pos", "Car", "Pts", "Wins", "Podiums"].map((h, i) => (
                    <th
                      key={i}
                      className="eyebrow text-left px-4 py-3 border-b border-[color:var(--hairline)] whitespace-nowrap"
                      style={{ textAlign: i >= 3 ? "right" : "left" }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.code} className="transition-colors hover:bg-[color:var(--surface-elevated)]/40">
                    <td className="px-2 py-3 border-b border-[color:var(--hairline)]">
                      <span
                        aria-hidden
                        className="block w-1 h-8 rounded-full"
                        style={{ background: r.teamColor }}
                      />
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] font-mono tabular-nums text-[color:var(--ink)]">
                      {r.position}
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)]">
                      <EntryIdentity
                        number={r.number}
                        team={r.team}
                        manufacturer={r.manufacturer}
                        vehicle={r.vehicle}
                        teamColor={r.teamColor}
                        drivers={r.drivers}
                        href={`/entry/${r.code}`}
                        compact
                      />
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-tabular text-[color:var(--ink)]">
                      {tidyNum(r.points)}
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-tabular text-[color:var(--muted)]">
                      {r.wins}
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-tabular text-[color:var(--muted)]">
                      {r.podiums}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Title race */}
        {champ && titleRace.length > 0 && (
          <Card className="p-5 sm:p-6">
            <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
              <div>
                <h2 className="title-md">{active.label} · title race</h2>
                <p className="body-sm text-[color:var(--muted)] mt-1">
                  Title odds and projected final points {champ.basis}.
                </p>
              </div>
              <Badge variant="muted">{canStillWin} can still win</Badge>
            </div>
            <div className="flex flex-col gap-3">
              {titleRace.map((e) => (
                <div key={e.code} className="flex items-center gap-3">
                  <div className="w-[40%] min-w-0">
                    <EntryIdentity
                      number={e.number}
                      team={e.team}
                      manufacturer={e.manufacturer}
                      teamColor={e.teamColor}
                      href={`/entry/${e.code}`}
                      compact
                    />
                  </div>
                  <div className="flex-1 relative h-5">
                    <div
                      className="absolute inset-y-0 left-0 rounded-sm"
                      style={{
                        width: `${Math.max(2, (e.pTitle / maxTitle) * 100)}%`,
                        background: active.color,
                        opacity: e.pTitle > 0 ? 1 : 0.25,
                      }}
                    />
                  </div>
                  <div className="w-16 text-right font-tabular text-[13px] text-[color:var(--ink)]">
                    {pct(e.pTitle, e.pTitle >= 0.1 ? 0 : 1)}
                  </div>
                  <div className="w-28 text-right text-[11px] text-[color:var(--muted)] hidden sm:block font-tabular">
                    {Math.round(e.projP10)}–{Math.round(e.projP90)} proj
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-5 text-[11px] text-[color:var(--muted-soft)]">
              Projected points show the P10–P90 range for the rest of the season. &ldquo;Can still
              win&rdquo; counts every car still mathematically able to reach the top of the class.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}
