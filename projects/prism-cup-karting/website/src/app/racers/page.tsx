import type { Metadata } from "next";

import { getRoster } from "@/lib/data";
import type { Racer } from "@/lib/types";

export const metadata: Metadata = {
  title: "The Racers — Prism Cup Karting",
  description:
    "The twelve original racers of the Prism Cup: stats, weight classes and bios. A fan-made simulated league.",
};

const STAT_ROWS: { key: "accel" | "topSpeed" | "knockResistance"; label: string }[] = [
  { key: "accel", label: "Acceleration" },
  { key: "topSpeed", label: "Top speed" },
  { key: "knockResistance", label: "Knock resistance" },
];

function RacerCard({ racer }: { racer: Racer }) {
  return (
    <div
      className="card p-6 racer-stripe flex flex-col"
      style={{ "--racer-color": racer.color } as React.CSSProperties}
    >
      <div className="flex items-start justify-between gap-3 mb-1">
        <h3 className="title-md" style={{ color: "var(--ink)" }}>
          {racer.name}
        </h3>
        <span className="status-pill status-pill-slate shrink-0">{racer.weightClass}</span>
      </div>
      <p className="caption-uppercase mb-4" style={{ color: racer.color }}>
        {racer.vibe}
      </p>
      <p className="body-sm mb-6" style={{ color: "var(--body)" }}>
        {racer.bio}
      </p>
      <div className="mt-auto flex flex-col gap-3">
        {STAT_ROWS.map((stat) => (
          <div key={stat.key}>
            <div className="flex items-center justify-between mb-1.5">
              <span className="mono-label">{stat.label}</span>
              <span className="font-mono text-[11px] font-tabular" style={{ color: "var(--body-strong)" }}>
                {racer.stats[stat.key]}/10
              </span>
            </div>
            <div className="stat-bar">
              <div
                className="stat-bar-fill"
                style={{ width: `${racer.stats[stat.key] * 10}%`, background: racer.color }}
              />
            </div>
          </div>
        ))}
        <div className="flex items-center justify-between pt-2 hairline-divider-top">
          <span className="mono-label">Item luck</span>
          <span className="font-mono text-[11px] font-tabular" style={{ color: "var(--body-strong)" }}>
            ×{racer.stats.itemLuck.toFixed(2)}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function RacersPage() {
  const roster = getRoster();
  const classes: ("light" | "medium" | "heavy")[] = ["light", "medium", "heavy"];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
      <p className="eyebrow mb-3" style={{ color: "var(--accent-prism-bright)" }}>
        The grid · 12 originals
      </p>
      <h1 className="display-lg mb-4">The Racers</h1>
      <p className="body-md max-w-2xl mb-14">
        Three weight classes, one deal: lights launch like fireworks and get
        flung like them too; heavies take half a season to reach top speed and
        then simply stay there. Every racer here is an original character —
        and every stat feeds the simulator.
      </p>

      {classes.map((wc) => (
        <section key={wc} className="mb-14">
          <div className="flex items-baseline gap-4 mb-6">
            <h2 className="display-sm">{roster.weightClasses[wc].label} class</h2>
            <p className="caption-uppercase">{roster.weightClasses[wc].trait}</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {roster.racers
              .filter((r) => r.weightClass === wc)
              .map((racer) => (
                <RacerCard key={racer.id} racer={racer} />
              ))}
          </div>
        </section>
      ))}
    </div>
  );
}
