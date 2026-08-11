"use client";

import { useState } from "react";

import ClassSelector from "@/components/ClassSelector";
import EntryIdentity from "@/components/EntryIdentity";
import ProbabilityBars, { type ProbabilityRow } from "@/components/charts/ProbabilityBars";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { pct } from "@/lib/format";
import type { ClassMeta, NextPrediction } from "@/types/wec";

export default function PredictionsView({
  next,
  classes,
}: {
  next: NextPrediction | null;
  classes: ClassMeta[];
}) {
  const [activeClass, setActiveClass] = useState(classes[0]?.key ?? "");

  if (!next) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-24 text-center">
        <p className="eyebrow mb-3">Next round</p>
        <h1 className="display-md">No forecast published yet</h1>
        <p className="body-md mt-4 text-[color:var(--muted)]">
          The next-round forecast appears here as soon as the season&rsquo;s next event is scheduled.
        </p>
      </div>
    );
  }

  const active = classes.find((c) => c.key === activeClass) ?? classes[0];
  const cls = next.classes.find((c) => c.key === activeClass) ?? next.classes[0];
  const race = cls?.race ?? [];
  const podium = [...race].sort((a, b) => a.position - b.position).slice(0, 3);

  const bars: ProbabilityRow[] = [...race]
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
        <p className="eyebrow mb-2">Forecast · Round {next.round}</p>
        <h1 className="display-lg">{next.event === `Round ${next.round}` ? "Next-round forecast" : next.event}</h1>
        <p className="body-md mt-3 max-w-2xl text-[color:var(--muted)]">
          Win and podium probability for every car, plus the predicted finishing order. Each class is
          its own race — switch between them below.
        </p>
      </header>

      <div className="mb-8 flex flex-wrap items-center gap-4">
        <ClassSelector classes={classes} value={activeClass} onChange={setActiveClass} />
        <Badge variant="muted">{race.length} cars</Badge>
      </div>

      <div role="tabpanel" id={`class-panel-${activeClass}`} aria-labelledby={`class-tab-${activeClass}`}>
        {/* Predicted podium */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
          {podium.map((e, i) => (
            <Card key={e.code} teamColor={e.teamColor} className={`p-5 ${i === 0 ? "md:-translate-y-2" : ""}`}>
              <div className="flex items-center justify-between mb-3">
                <span
                  className="inline-flex items-center justify-center w-9 h-9 rounded-full font-mono text-[14px]"
                  style={{
                    border: `1px solid ${
                      i === 0 ? "var(--accent-podium-1)" : i === 1 ? "var(--accent-podium-2)" : "var(--accent-podium-3)"
                    }`,
                    color:
                      i === 0 ? "var(--accent-podium-1)" : i === 1 ? "var(--accent-podium-2)" : "var(--accent-podium-3)",
                  }}
                >
                  P{i + 1}
                </span>
                <span
                  className="class-chip"
                  data-class={active.key}
                  style={{ ["--class-color" as string]: active.color }}
                >
                  {active.label}
                </span>
              </div>
              <EntryIdentity
                number={e.number}
                team={e.team}
                manufacturer={e.manufacturer}
                vehicle={e.vehicle}
                teamColor={e.teamColor}
                drivers={e.drivers}
                href={`/entry/${e.code}`}
              />
              <div className="mt-4 pt-3 border-t border-[color:var(--hairline)] grid grid-cols-2 gap-3">
                <div>
                  <p className="eyebrow">Win</p>
                  <p className="title-md font-tabular mt-1" style={{ color: active.color }}>
                    {pct(e.pWin, 1)}
                  </p>
                </div>
                <div>
                  <p className="eyebrow">Podium</p>
                  <p className="title-md font-tabular mt-1 text-[color:var(--ink)]">{pct(e.pPodium, 1)}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* Full grid probability bars */}
        <Card className="p-5 sm:p-6">
          <div className="mb-4">
            <h2 className="title-md">{active.label} · win &amp; podium probability</h2>
            <p className="body-sm text-[color:var(--muted)] mt-1">
              Ordered by win chance. The faint bar behind each is that car&rsquo;s podium chance.
            </p>
          </div>
          <ProbabilityBars rows={bars} valueLabel="Win" secondaryLabel="Podium" />
        </Card>

        <p className="mt-6 text-[11px] text-[color:var(--muted-soft)] max-w-2xl">
          Probabilities reflect the forecast at publication and are calibrated on the season&rsquo;s
          real results so far. Predicted finishing order is the model&rsquo;s single most likely
          result — the probabilities describe the spread around it.
        </p>
      </div>
    </div>
  );
}
