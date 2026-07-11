import type { StandingsRow } from "@/types/data";

export default function StandingsTable({
  standings,
  compact = false,
}: {
  standings: StandingsRow[];
  compact?: boolean;
}) {
  return (
    <div className="card overflow-x-auto">
      <table className="valley-table min-w-[520px]">
        <thead>
          <tr>
            <th>Pos</th>
            <th>Racer</th>
            <th className="text-right">Points</th>
            <th className="text-right">Wins</th>
            {!compact && <th className="text-right">Podiums</th>}
            {!compact && <th className="text-right">DNFs</th>}
          </tr>
        </thead>
        <tbody>
          {standings.map((row) => (
            <tr key={row.slug}>
              <td>
                <span className={`position-badge${row.position <= 3 ? ` p${row.position}` : ""}`}>
                  {row.position}
                </span>
              </td>
              <td>
                <div
                  className="racer-stripe pl-3"
                  style={{ "--racer-color": row.color } as React.CSSProperties}
                >
                  <span className="text-[color:var(--body-strong)]">{row.name}</span>
                  <span className="mono-label ml-2">#{row.number}</span>
                </div>
              </td>
              <td className="text-right font-tabular text-[color:var(--ink)]">{row.points}</td>
              <td className="text-right font-tabular">{row.wins}</td>
              {!compact && <td className="text-right font-tabular">{row.podiums}</td>}
              {!compact && <td className="text-right font-tabular">{row.dnfs}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
