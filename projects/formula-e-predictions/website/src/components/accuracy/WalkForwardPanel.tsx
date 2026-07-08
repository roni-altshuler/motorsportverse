import type { ForwardEvalSeason, WalkForwardBlock } from "@/types/fe";

// Metrics we surface, with the direction that counts as "better".
const METRICS: { key: string; label: string; lowerBetter: boolean; digits: number }[] = [
  { key: "mean_position_error", label: "Mean position error", lowerBetter: true, digits: 2 },
  { key: "ndcg_at_5", label: "Top-5 ranking", lowerBetter: false, digits: 3 },
  { key: "spearman_correlation", label: "Order agreement", lowerBetter: false, digits: 3 },
  { key: "podium_hits", label: "Podium hits / round", lowerBetter: false, digits: 2 },
];

const RACE_LABELS: Record<string, string> = { race: "E-Prix" };

function metricMean(block: WalkForwardBlock | undefined, key: string): number | null {
  const m = block?.metrics?.[key];
  return m ? m.mean : null;
}

function fmt(v: number | null, digits: number): string {
  return v == null ? "—" : v.toFixed(digits);
}

function RaceTypeCard({
  raceType,
  model,
  lastRace,
  gridOrder,
}: {
  raceType: string;
  model: WalkForwardBlock;
  lastRace: WalkForwardBlock | undefined;
  gridOrder: WalkForwardBlock | undefined;
}) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="text-lg font-semibold text-[var(--ink)]">
          {RACE_LABELS[raceType] ?? raceType}
        </h3>
        <span className="text-xs text-[var(--ink-dim)]">
          {model.n_rounds} rounds · model vs naive baselines
        </span>
      </div>
      <div className="overflow-hidden rounded-[var(--radius-md)] border border-[var(--hairline)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[var(--surface-2)] text-left text-xs uppercase tracking-wider text-[var(--ink-dim)]">
              <th className="px-4 py-2.5 font-medium">Metric</th>
              <th className="px-4 py-2.5 text-right font-medium">Model</th>
              <th className="px-4 py-2.5 text-right font-medium">Last-race</th>
              <th className="hidden px-4 py-2.5 text-right font-medium sm:table-cell">
                Grid order
              </th>
            </tr>
          </thead>
          <tbody>
            {METRICS.map((metric) => {
              const mv = metricMean(model, metric.key);
              const bv = metricMean(lastRace, metric.key);
              const gv = metricMean(gridOrder, metric.key);
              const best = [mv, bv, gv].filter((v): v is number => v != null);
              const winner =
                best.length > 1
                  ? metric.lowerBetter
                    ? Math.min(...best)
                    : Math.max(...best)
                  : null;
              const cell = (v: number | null, muted: boolean) => ({
                color:
                  winner != null && v === winner
                    ? "var(--accent-f1-red-bright)"
                    : muted
                    ? "var(--ink-muted)"
                    : "var(--ink)",
                fontWeight: winner != null && v === winner ? 700 : 400,
              });
              return (
                <tr
                  key={metric.key}
                  className="border-t border-[var(--hairline)] bg-[var(--surface)]"
                >
                  <td className="px-4 py-2.5 text-[var(--ink-muted)]">{metric.label}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums" style={cell(mv, false)}>
                    {fmt(mv, metric.digits)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums" style={cell(bv, true)}>
                    {fmt(bv, metric.digits)}
                  </td>
                  <td
                    className="hidden px-4 py-2.5 text-right tabular-nums sm:table-cell"
                    style={cell(gv, true)}
                  >
                    {fmt(gv, metric.digits)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * Walk-forward headline: is the Formula E model actually beating the trivial
 * "last race repeats" and "grid order finishes as-is" predictors over the
 * season? Renders the `walkForward` block on forward_eval/season.json — the F1
 * parity validation surface.
 */
export default function WalkForwardPanel({
  season,
}: {
  season: ForwardEvalSeason | null;
}) {
  const wf = season?.walkForward;
  if (!wf) return null;
  const raceTypes = Object.keys(wf);
  if (raceTypes.length === 0) return null;

  return (
    <section className="mt-12">
      <div className="mb-4">
        <p className="eyebrow mb-1">Walk-forward validation</p>
        <h2 className="text-xl font-semibold text-[var(--ink)]">
          Model vs the naive baselines
        </h2>
        <p className="mt-2 text-sm text-[var(--ink-muted)]">
          Every completed round is re-forecast using only earlier rounds, then scored
          against two trivial predictors — one that replays the previous result, one
          that assumes the grid finishes in order. Blue marks the best column. Beating
          these baselines is the bar the model has to clear.
        </p>
      </div>
      <div className="grid gap-6">
        {raceTypes.map((rt) => (
          <RaceTypeCard
            key={rt}
            raceType={rt}
            model={wf[rt].model}
            lastRace={wf[rt].baselines?.lastRace}
            gridOrder={wf[rt].baselines?.gridOrder}
          />
        ))}
      </div>
    </section>
  );
}
