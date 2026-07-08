"use client";

import { useState } from "react";

import type { DriverStanding, TeamStanding } from "@/types/fe";

export function StandingsTabs({
  drivers,
  teams,
  teamColor,
}: {
  drivers: DriverStanding[];
  teams: TeamStanding[];
  teamColor: Record<string, string>;
}) {
  const [tab, setTab] = useState<"drivers" | "teams">("drivers");
  return (
    <div>
      <div className="mb-6 flex gap-2">
        {(["drivers", "teams"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className="rounded-full border px-4 py-1.5 text-sm font-medium capitalize"
            style={{
              color: tab === t ? "var(--accent-ink)" : "var(--ink-muted)",
              backgroundColor: tab === t ? "var(--accent)" : "transparent",
              borderColor: tab === t ? "var(--accent)" : "var(--hairline)",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "drivers" ? (
        <Table
          headers={["#", "Driver", "Team", "Pts", "Wins", "Podiums"]}
          rows={drivers.map((d) => ({
            color: teamColor[d.team] || "var(--accent)",
            cells: [d.position, d.name, d.team, d.points, d.wins, d.podiums],
          }))}
        />
      ) : (
        <Table
          headers={["#", "Team", "Pts", "Wins", "Podiums"]}
          rows={teams.map((t) => ({
            color: teamColor[t.team] || "var(--accent)",
            cells: [t.position, t.team, t.points, t.wins, t.podiums],
          }))}
        />
      )}
    </div>
  );
}

function Table({
  headers,
  rows,
}: {
  headers: string[];
  rows: { color: string; cells: (string | number)[] }[];
}) {
  return (
    <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--hairline)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-[var(--surface-2)] text-left text-xs uppercase tracking-wider text-[var(--ink-dim)]">
            {headers.map((h) => (
              <th key={h} className="px-4 py-3 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={i}
              className="border-t border-[var(--hairline)] bg-[var(--surface)] hover:bg-[var(--surface-2)]"
            >
              {r.cells.map((c, j) => (
                <td
                  key={j}
                  className="px-4 py-3 text-[var(--ink)]"
                  style={j === 0 ? { borderLeft: `3px solid ${r.color}` } : undefined}
                >
                  {j === 0 ? <span className="font-semibold">{c}</span> : c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
