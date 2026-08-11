"use client";

export interface ProbabilityRow {
  key: string;
  /** Primary label (e.g. "#51 Ferrari"). */
  label: string;
  /** Optional secondary label (e.g. manufacturer / drivers). */
  sub?: string;
  /** Bar colour (team colour). */
  color: string;
  /** 0–1 value for the primary bar. */
  value: number;
  /** Optional 0–1 secondary value drawn as a faint track marker (e.g. podium). */
  secondary?: number;
  /** Optional href to make the row a link. */
  href?: string;
}

/**
 * ProbabilityBars — labelled horizontal probability bars. The primary bar is the
 * team-coloured fill; an optional faint secondary bar (e.g. podium chance behind
 * win chance) sits underneath. Bars scale to the largest value in the set so the
 * leader always reads full-width.
 */
export default function ProbabilityBars({
  rows,
  valueLabel = "Win",
  secondaryLabel,
  className = "",
}: {
  rows: ProbabilityRow[];
  valueLabel?: string;
  secondaryLabel?: string;
  className?: string;
}) {
  // Scale BOTH bars to a shared max over win AND podium so the faint podium bar
  // (usually the larger value) never overflows the track. The solid win bar
  // draws in front of the longer, faint podium bar behind it.
  const max = Math.max(
    0.0001,
    ...rows.flatMap((r) => [r.value, r.secondary ?? 0]),
  );

  return (
    <div className={`flex flex-col ${className}`}>
      <div className="flex items-center justify-between px-1 pb-2">
        <span className="eyebrow">Car</span>
        <span className="eyebrow">
          {valueLabel}
          {secondaryLabel ? ` · ${secondaryLabel}` : ""}
        </span>
      </div>
      {rows.map((r) => {
        const w = Math.min(100, Math.max(2, (r.value / max) * 100));
        const sw = r.secondary != null ? Math.min(100, Math.max(1, (r.secondary / max) * 100)) : 0;
        const content = (
          <div className="flex items-center gap-3 py-2 border-b border-[color:var(--hairline)]">
            <div className="w-[38%] min-w-0">
              <p className="truncate text-[13px] text-[color:var(--ink)] font-mono tracking-[0.02em]">{r.label}</p>
              {r.sub && <p className="truncate text-[11px] text-[color:var(--muted)]">{r.sub}</p>}
            </div>
            <div className="flex-1 relative h-4">
              {r.secondary != null && (
                <div
                  className="absolute inset-y-0 left-0 rounded-sm"
                  style={{
                    width: `${sw}%`,
                    background: `color-mix(in oklab, ${r.color} 22%, transparent)`,
                  }}
                />
              )}
              <div
                className="absolute inset-y-0 left-0 rounded-sm"
                style={{ width: `${w}%`, background: r.color }}
              />
            </div>
            <div className="w-14 text-right font-tabular text-[13px] text-[color:var(--ink)]">
              {(r.value * 100).toFixed(1)}%
            </div>
          </div>
        );
        return r.href ? (
          <a key={r.key} href={r.href} className="transition-colors hover:bg-[color:var(--surface-elevated)]/40">
            {content}
          </a>
        ) : (
          <div key={r.key}>{content}</div>
        );
      })}
    </div>
  );
}
