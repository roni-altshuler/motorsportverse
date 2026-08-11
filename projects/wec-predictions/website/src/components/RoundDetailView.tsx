"use client";

import { useState } from "react";

import ClassSelector from "@/components/ClassSelector";
import ConfidenceBadge from "@/components/ConfidenceBadge";
import CountryFlag from "@/components/CountryFlag";
import EntryIdentity from "@/components/EntryIdentity";
import ProbabilityBars, { type ProbabilityRow } from "@/components/charts/ProbabilityBars";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Stat } from "@/components/ui/Stat";
import { pct } from "@/lib/format";
import type { CalendarRound, ClassMeta, RoundClass, RoundDetail } from "@/types/wec";

function DeltaPill({ predicted, actual }: { predicted: number; actual: number | null }) {
  if (actual == null) {
    return <span className="text-[11px] font-mono text-[color:var(--muted-soft)]">DNF/NC</span>;
  }
  const d = actual - predicted;
  if (d === 0) {
    return <span className="text-[11px] font-mono" style={{ color: "var(--success)" }}>exact</span>;
  }
  const up = d < 0; // finished better (lower number) than predicted
  return (
    <span
      className="text-[11px] font-mono tabular-nums"
      style={{ color: up ? "var(--success)" : "var(--accent-negative)" }}
    >
      {up ? "▲" : "▼"} {Math.abs(d)}
    </span>
  );
}

export default function RoundDetailView({
  detail,
  calendarRound,
}: {
  detail: RoundDetail;
  calendarRound: CalendarRound | null;
}) {
  const selectorClasses: ClassMeta[] = detail.classes.map((c) => ({
    key: c.key,
    label: c.label,
    color: c.color,
  }));
  const [activeClass, setActiveClass] = useState(selectorClasses[0]?.key ?? "");
  const cls: RoundClass | undefined =
    detail.classes.find((c) => c.key === activeClass) ?? detail.classes[0];

  const name = calendarRound?.name ?? detail.place;
  const country = calendarRound?.country ?? detail.country;
  const isLeMans = calendarRound?.isLeMans ?? false;
  const completed = detail.completed;

  const acc = cls?.accuracy;
  const classification = cls?.classification ?? [];

  const bars: ProbabilityRow[] = [...classification]
    .sort((a, b) => b.pWin - a.pWin)
    .map((e) => ({
      key: e.code,
      label: `#${e.number} ${e.team}`,
      sub: e.manufacturer,
      color: e.teamColor,
      value: e.pWin,
      secondary: e.pPodium,
      href: `/entry/${e.code}`,
    }));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <header className="mb-8">
        <div className="flex items-center gap-2 mb-3">
          <span className="eyebrow">Round {detail.round}</span>
          {completed ? (
            <Badge variant="positive">Completed</Badge>
          ) : (
            <Badge variant="live">Upcoming</Badge>
          )}
          {isLeMans && (
            <Badge variant="live" className="!text-[color:var(--accent-podium-1)] !border-[color:var(--accent-podium-1)]">
              24 Hours
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3">
          <CountryFlag country={country} size={34} />
          <h1 className="display-lg">{name}</h1>
        </div>
        <p className="body-md mt-3 max-w-2xl text-[color:var(--muted)]">
          {completed
            ? "Predicted classification against the real result, by class — with win and podium probabilities."
            : "Predicted classification and win / podium probabilities, by class — this round has not run yet."}
        </p>
      </header>

      <div className="mb-8">
        <ClassSelector classes={selectorClasses} value={activeClass} onChange={setActiveClass} />
      </div>

      <div role="tabpanel" id={`class-panel-${activeClass}`} aria-labelledby={`class-tab-${activeClass}`}>
        {/* Accuracy summary (completed rounds only) */}
        {completed && acc && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
            <Stat
              label="Mean position error"
              value={acc.mean_position_error != null ? acc.mean_position_error.toFixed(2) : "—"}
              hint="places off, on average"
            />
            <Stat label="Podium hits" value={`${acc.podium_hits ?? 0}/3`} hint="predicted podium correct" />
            <Stat label="Exact finishes" value={`${acc.exact_matches ?? 0}/${acc.n}`} hint="predicted spot on" />
            <Stat
              label="Within 3 places"
              value={`${acc.within_3 ?? 0}/${acc.n}`}
              hint="cars within 3 of prediction"
            />
          </div>
        )}

        {/* Predicted (vs actual) classification */}
        <Card className="overflow-hidden mb-8">
          <div className="px-5 py-4 border-b border-[color:var(--hairline)]">
            <h2 className="title-md">{cls?.label} · predicted classification</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse">
              <thead>
                <tr>
                  {["Pred", "Car", "Proj. finish", "Win", "Podium", "Confidence", ...(completed ? ["Actual", "Δ"] : [])].map(
                    (h, i) => (
                      <th
                        key={i}
                        className="eyebrow px-4 py-3 border-b border-[color:var(--hairline)] whitespace-nowrap"
                        style={{ textAlign: i === 1 ? "left" : i === 0 ? "left" : "right" }}
                      >
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {classification.map((e) => (
                  <tr key={e.code} className="transition-colors hover:bg-[color:var(--surface-elevated)]/40">
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] font-mono tabular-nums text-[color:var(--ink)]">
                      {e.position}
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)]">
                      <EntryIdentity
                        number={e.number}
                        team={e.team}
                        manufacturer={e.manufacturer}
                        vehicle={e.vehicle}
                        teamColor={e.teamColor}
                        href={`/entry/${e.code}`}
                        compact
                      />
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-tabular text-[color:var(--muted)]">
                      {e.meanFinish.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-tabular text-[color:var(--ink)]">
                      {pct(e.pWin, 1)}
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-tabular text-[color:var(--muted)]">
                      {pct(e.pPodium, 1)}
                    </td>
                    <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right">
                      <ConfidenceBadge confidence={e.confidence} />
                    </td>
                    {completed && (
                      <>
                        <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-mono tabular-nums text-[color:var(--ink)]">
                          {e.actualPosition ?? "—"}
                        </td>
                        <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right">
                          <DeltaPill predicted={e.position} actual={e.actualPosition} />
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Probability bars */}
        <Card className="p-5 sm:p-6">
          <div className="mb-4">
            <h2 className="title-md">{cls?.label} · win &amp; podium probability</h2>
            <p className="body-sm text-[color:var(--muted)] mt-1">
              Ordered by win chance; the faint bar behind each is that car&rsquo;s podium chance.
            </p>
          </div>
          <ProbabilityBars rows={bars} valueLabel="Win" secondaryLabel="Podium" />
        </Card>
      </div>
    </div>
  );
}
