import Link from "next/link";

/**
 * EntryIdentity — the standard way to name a IMSA car everywhere on the site:
 * a team-coloured stripe, the car NUMBER as the primary token (the unit of an
 * endurance entry), then team + manufacturer. Optional driver lineup below.
 */
export default function EntryIdentity({
  number,
  team,
  manufacturer,
  vehicle,
  teamColor,
  drivers,
  href,
  compact = false,
}: {
  number: string;
  team: string;
  manufacturer?: string;
  vehicle?: string;
  teamColor: string;
  drivers?: string[];
  href?: string;
  compact?: boolean;
}) {
  const inner = (
    <div className="flex items-stretch gap-3 min-w-0">
      <span
        aria-hidden
        className="w-1 shrink-0 rounded-full"
        style={{ background: teamColor }}
      />
      <div className="min-w-0">
        <div className="flex items-baseline gap-2 min-w-0">
          <span
            className="font-mono font-medium tabular-nums text-[color:var(--ink)] shrink-0"
            style={{ fontSize: compact ? 13 : 15 }}
          >
            #{number}
          </span>
          <span className="truncate text-[color:var(--body-strong)]" style={{ fontSize: compact ? 13 : 14 }}>
            {team}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-[color:var(--muted)] truncate">
          {manufacturer && <span>{manufacturer}</span>}
          {manufacturer && vehicle && <span aria-hidden>·</span>}
          {vehicle && <span className="truncate">{vehicle}</span>}
        </div>
        {drivers && drivers.length > 0 && !compact && (
          <p className="mt-0.5 text-[11px] text-[color:var(--muted-soft)] truncate">
            {drivers.join(" · ")}
          </p>
        )}
      </div>
    </div>
  );

  return href ? (
    <Link href={href} className="block transition-opacity hover:opacity-80">
      {inner}
    </Link>
  ) : (
    inner
  );
}
