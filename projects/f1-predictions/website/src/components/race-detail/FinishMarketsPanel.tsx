"use client";

/**
 * FinishMarketsPanel — compact, above-the-fold "finish markets" module.
 *
 * Surfaces the four finish-position probabilities the model publishes for
 * every driver — podium, top 6, top 10, and retirement (DNF) — in one
 * scannable table, so the reader gets the full outcome picture without
 * digging into the detailed heatmap in the Visualisations drawer.
 *
 * Data comes straight from the round's probability run (`markets`): podium /
 * top6 / top10 and the DNF market are all published there. When a round has
 * no probability file yet (older rounds), the panel renders nothing rather
 * than inventing numbers.
 */
import { useMemo } from "react";
import HUDPanel from "@/components/ui/HUDPanel";
import { Badge } from "@/components/ui/Badge";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { resolveDriverHeadshot } from "@/lib/headshots";
import type { ClassificationEntry, ProbabilityMarketEntry, ProbabilityRoundData } from "@/types";

interface FinishMarketsPanelProps {
  classification: ClassificationEntry[];
  probabilities: ProbabilityRoundData | null;
  /** How many drivers (rows) to show. Default 10. */
  driverLimit?: number;
}

type MarketKey = "podium" | "top6" | "top10" | "dnf";

function marketLookup(
  probabilities: ProbabilityRoundData | null,
  key: MarketKey,
): Map<string, number> {
  // `dnf` ships in the JSON but isn't in the published TS market union — read
  // the markets bag permissively so we surface it without editing the type.
  const rows = (probabilities?.markets as Record<string, ProbabilityMarketEntry[]> | undefined)?.[
    key
  ];
  const map = new Map<string, number>();
  if (rows) for (const r of rows) map.set(r.driver, r.probability);
  return map;
}

function fmtPct(p: number | undefined): string {
  return p == null ? "—" : `${Math.round(p * 100)}%`;
}

function MarketCell({
  p,
  fill,
  emphasis,
}: {
  p: number | undefined;
  fill: string;
  emphasis?: boolean;
}) {
  const width = p == null ? 0 : Math.max(0, Math.min(1, p)) * 100;
  return (
    <div className="min-w-0">
      <div
        className="font-mono font-tabular text-sm leading-none mb-1.5"
        style={{ color: emphasis ? "var(--ink)" : "var(--text-secondary)", fontWeight: emphasis ? 700 : 400 }}
      >
        {fmtPct(p)}
      </div>
      <div className="h-1.5 w-full overflow-hidden" style={{ background: "var(--hairline)" }}>
        <div className="h-full" style={{ width: `${width}%`, background: fill }} />
      </div>
    </div>
  );
}

export default function FinishMarketsPanel({
  classification,
  probabilities,
  driverLimit = 10,
}: FinishMarketsPanelProps) {
  const podium = useMemo(() => marketLookup(probabilities, "podium"), [probabilities]);
  const top6 = useMemo(() => marketLookup(probabilities, "top6"), [probabilities]);
  const top10 = useMemo(() => marketLookup(probabilities, "top10"), [probabilities]);
  const dnf = useMemo(() => marketLookup(probabilities, "dnf"), [probabilities]);

  const rows = useMemo(
    () =>
      [...classification]
        .sort((a, b) => a.position - b.position)
        .slice(0, driverLimit)
        .map((c) => ({
          entry: c,
          podium: podium.get(c.driver),
          top6: top6.get(c.driver),
          top10: top10.get(c.driver),
          dnf: dnf.get(c.driver),
        })),
    [classification, driverLimit, podium, top6, top10, dnf],
  );

  // Nothing to render without the probability run — never fabricate markets.
  const hasData = podium.size > 0 || top6.size > 0 || top10.size > 0;
  if (!hasData || rows.length === 0) return null;

  const headers: Array<{ key: MarketKey; label: string }> = [
    { key: "podium", label: "Podium" },
    { key: "top6", label: "Top 6" },
    { key: "top10", label: "Top 10" },
    { key: "dnf", label: "DNF risk" },
  ];

  return (
    <div className="mb-8">
      <HUDPanel
        kicker="Probability Layer"
        title="Finish Markets"
        rightSlot={<Badge variant="live">Model odds</Badge>}
        bodyClassName="p-4 sm:p-5"
      >
        <p className="body-sm text-[color:var(--muted)] mb-4">
          Chance each driver lands in the podium, the top six, the points, or fails to see the
          flag — the model&apos;s full finish-position outlook at a glance.
        </p>
        <div className="overflow-x-auto">
          <div className="min-w-[560px]">
            {/* Column headers */}
            <div className="grid grid-cols-[minmax(120px,1.4fr)_repeat(4,minmax(72px,1fr))] gap-3 sm:gap-4 pb-2 mb-2 border-b border-[color:var(--hairline)]">
              <span className="eyebrow">Driver</span>
              {headers.map((h) => (
                <span key={h.key} className="eyebrow">
                  {h.label}
                </span>
              ))}
            </div>
            {/* Rows */}
            <div className="divide-y divide-[color:var(--hairline)]">
              {rows.map(({ entry, podium: pPod, top6: pT6, top10: pT10, dnf: pDnf }) => (
                <div
                  key={entry.driver}
                  className="grid grid-cols-[minmax(120px,1.4fr)_repeat(4,minmax(72px,1fr))] gap-3 sm:gap-4 items-center py-3"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <DriverPortrait
                      driver={entry.driver}
                      driverFullName={entry.driverFullName}
                      team={entry.team}
                      teamColor={entry.teamColor}
                      headshotUrl={resolveDriverHeadshot(entry.driver, entry.headshotUrl)}
                      size={28}
                    />
                    <div className="min-w-0">
                      <p className="font-mono font-tabular text-sm text-[color:var(--ink)] leading-none">
                        {entry.driver}
                      </p>
                      <p className="body-sm text-[color:var(--muted)] truncate text-xs mt-0.5">
                        {entry.team}
                      </p>
                    </div>
                  </div>
                  <MarketCell p={pPod} fill={entry.teamColor || "var(--muted)"} emphasis />
                  <MarketCell p={pT6} fill={entry.teamColor || "var(--muted)"} />
                  <MarketCell p={pT10} fill={entry.teamColor || "var(--muted)"} />
                  {/* DNF is attrition risk — kept a neutral muted tone so it never
                      reads as one of the team-coloured "good" markets. */}
                  <MarketCell p={pDnf} fill="var(--muted)" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </HUDPanel>
    </div>
  );
}
