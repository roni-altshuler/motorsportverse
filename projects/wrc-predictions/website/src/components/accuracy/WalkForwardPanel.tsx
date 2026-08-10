import type { ForwardEvalSeason, WalkForwardBlock } from "@/types/wrc";

// Metrics we surface, with the direction that counts as "better".
const METRICS: { key: string; label: string; lowerBetter: boolean; digits: number }[] = [
  { key: "mean_position_error", label: "Mean position error", lowerBetter: true, digits: 2 },
  { key: "ndcg_at_5", label: "Top-5 ranking", lowerBetter: false, digits: 3 },
  { key: "spearman_correlation", label: "Order agreement", lowerBetter: false, digits: 3 },
  { key: "podium_hits", label: "Podium hits / round", lowerBetter: false, digits: 2 },
];

const RACE_LABELS: Record<string, string> = { rally: "Rally" };

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
  baseline,
}: {
  raceType: string;
  model: WalkForwardBlock;
  baseline: WalkForwardBlock | undefined;
}) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="text-lg font-semibold text-[var(--ink)]">
          {RACE_LABELS[raceType] ?? raceType}
        </h3>
        <span className="text-xs text-[var(--ink-dim)]">
          {model.n_rounds} rounds · model vs championship form
        </span>
      </div>
      <div className="overflow-hidden rounded-[var(--radius-md)] border border-[var(--hairline)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[var(--surface-2)] text-left text-xs uppercase tracking-wider text-[var(--ink-dim)]">
              <th className="px-4 py-2.5 font-medium">Metric</th>
              <th className="px-4 py-2.5 text-right font-medium">Model</th>
              <th className="px-4 py-2.5 text-right font-medium">Championship form</th>
            </tr>
          </thead>
          <tbody>
            {METRICS.map((metric) => {
              const mv = metricMean(model, metric.key);
              const bv = metricMean(baseline, metric.key);
              let modelWins: boolean | null = null;
              if (mv != null && bv != null && mv !== bv) {
                modelWins = metric.lowerBetter ? mv < bv : mv > bv;
              }
              return (
                <tr
                  key={metric.key}
                  className="border-t border-[var(--hairline)] bg-[var(--surface)]"
                >
                  <td className="px-4 py-2.5 text-[var(--ink-muted)]">{metric.label}</td>
                  <td
                    className="px-4 py-2.5 text-right tabular-nums"
                    style={{
                      color: modelWins === true ? "var(--accent)" : "var(--ink)",
                      fontWeight: modelWins === true ? 700 : 400,
                    }}
                  >
                    {fmt(mv, metric.digits)}
                  </td>
                  <td
                    className="px-4 py-2.5 text-right tabular-nums"
                    style={{
                      color: modelWins === false ? "var(--accent)" : "var(--ink-muted)",
                      fontWeight: modelWins === false ? 700 : 400,
                    }}
                  >
                    {fmt(bv, metric.digits)}
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
 * Walk-forward headline: is the WRC model actually beating championship-form
 * order — ranking crews by their standings — over the season? Renders the
 * `walkForward` block on forward_eval/season.json, model vs the standings-order
 * baseline, on the ranking metrics.
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
          Model vs the championship-form baseline
        </h2>
        <p className="mt-2 text-sm text-[var(--ink-muted)]">
          Every completed round is re-forecast using only earlier rounds, then scored against a
          baseline that simply ranks crews by their championship standings. Gold marks the better
          side. Beating championship form on the ranking metrics is the bar the model has to clear.
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        {raceTypes.map((rt) => (
          <RaceTypeCard
            key={rt}
            raceType={rt}
            model={wf[rt].model}
            baseline={wf[rt].baselines?.standingsOrder}
          />
        ))}
      </div>
    </section>
  );
}
