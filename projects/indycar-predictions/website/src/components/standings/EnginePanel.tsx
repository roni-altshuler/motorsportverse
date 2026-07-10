"use client";

/**
 * Engine-supplier standings — IndyCar-specific strip. Two suppliers
 * (Chevrolet / Honda) race for the manufacturers' championship; the export
 * ships points + wins + a brand accent per supplier in `engineStandings`.
 */
import { NumberTicker } from "@/components/magicui/number-ticker";
import type { EngineStanding } from "@/types/indycar";

export default function EnginePanel({ engines }: { engines: EngineStanding[] }) {
  if (!engines || engines.length === 0) return null;
  const maxPts = engines[0]?.points || 1;
  return (
    <div className="space-y-3">
      <h3 className="section-heading">Engine Manufacturers&rsquo; Championship</h3>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {engines.map((m) => (
          <div key={m.engine} className="card relative overflow-hidden p-5">
            <div
              className="absolute left-0 top-0 h-1 w-full"
              style={{ background: m.color }}
              aria-hidden
            />
            <div className="mb-3 flex items-center justify-between">
              <span
                className={`position-badge ${
                  m.position === 1 ? "p1" : m.position === 2 ? "p2" : "p3"
                }`}
              >
                P{m.position}
              </span>
              <span className="font-mono text-2xl font-black tabular-nums text-[color:var(--ink)]">
                <NumberTicker value={Math.round(m.points)} />{" "}
                <span className="text-sm font-normal text-[color:var(--muted)]">pts</span>
              </span>
            </div>
            <h4 className="title-md mb-1 text-[color:var(--ink)]">{m.engine}</h4>
            <p className="text-sm text-[color:var(--text-muted)]">
              {m.wins} win{m.wins === 1 ? "" : "s"} this season
            </p>
            <div className="progress-bar mt-3 h-2">
              <div
                className="progress-bar-fill"
                style={{ width: `${(m.points / maxPts) * 100}%`, background: m.color }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
