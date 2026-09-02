import type { ForwardEvalSeason } from "@/types/wrc";

/**
 * PhaseComparisonPanel — honest model-vs-baseline read for the rally.
 *
 * A rally has no qualifying and no grid to condition on, so the fair question is
 * whether the forecast beats simply ordering crews by their CHAMPIONSHIP FORM.
 * The season eval scores three things on the same rounds:
 *   • our forecast (the ensemble)                 — "model"
 *   • ordering by championship standings          — "standings"
 *   • replaying the last rally's result           — "lastRally"
 *
 * The honest story: the ensemble is sharper than championship-form order on both
 * the win and podium probability scores. A last-rally momentum baseline is a
 * touch sharper than the model on the win score in this dominated season — we
 * show that rather than hide it. Lower probability scores are better; winner
 * accuracy is higher-is-better.
 */
function pctScore(v: number | null | undefined): string {
  return v == null ? "—" : `${(v * 100).toFixed(0)}%`;
}
function num(v: number | null | undefined, digits = 3): string {
  return v == null ? "—" : v.toFixed(digits);
}

export default function PhaseComparisonPanel({
  season,
}: {
  season: ForwardEvalSeason | null;
}) {
  const bc = season?.baselineComparison;
  if (!bc) return null;

  const { winBrier, podiumBrier, winnerHit } = bc;

  const winSharper =
    winBrier != null && winBrier.model != null && winBrier.standings != null
      ? winBrier.model <= winBrier.standings
      : false;
  const podiumSharper =
    podiumBrier != null && podiumBrier.model != null && podiumBrier.standings != null
      ? podiumBrier.model <= podiumBrier.standings
      : false;
  const lastRallySharper =
    winBrier != null && winBrier.model != null && winBrier.lastRally != null
      ? winBrier.lastRally < winBrier.model
      : false;

  const rows: {
    label: string;
    hint: string;
    model: string;
    standings: string;
    lastRally: string;
    modelBeatsStandings: boolean | null;
  }[] = [
    winBrier && {
      label: "Win probability score",
      hint: "lower is sharper",
      model: num(winBrier.model),
      standings: num(winBrier.standings),
      lastRally: num(winBrier.lastRally),
      modelBeatsStandings: winBrier.model < winBrier.standings,
    },
    podiumBrier && {
      label: "Podium probability score",
      hint: "lower is sharper",
      model: num(podiumBrier.model),
      standings: num(podiumBrier.standings),
      lastRally: num(podiumBrier.lastRally),
      modelBeatsStandings: podiumBrier.model < podiumBrier.standings,
    },
    winnerHit && {
      label: "Winner called",
      hint: "higher is better",
      model: pctScore(winnerHit.model),
      standings: pctScore(winnerHit.standings),
      lastRally: pctScore(winnerHit.lastRally),
      modelBeatsStandings: winnerHit.model >= winnerHit.standings,
    },
  ].filter(Boolean) as {
    label: string;
    hint: string;
    model: string;
    standings: string;
    lastRally: string;
    modelBeatsStandings: boolean | null;
  }[];

  if (rows.length === 0) return null;

  return (
    <section className="mt-12">
      <div className="mb-4">
        <p className="eyebrow mb-1">Vs the baselines</p>
        <h2 className="text-xl font-semibold text-[var(--ink)]">
          Does the forecast beat championship form?
        </h2>
        <p className="mt-2 text-sm text-[var(--ink-muted)]">
          A rally has no qualifying to lean on, so the fair test is whether the forecast is sharper
          than simply ordering crews by their championship standings. Over {bc.roundsScored} completed
          round{bc.roundsScored === 1 ? "" : "s"}{" "}
          {winSharper && podiumSharper
            ? "the model is sharper than championship form on both the win and podium probability scores."
            : podiumSharper
              ? "the model is sharper than championship form on the podium probability score, while championship form currently holds a slim edge on the win score."
              : winSharper
                ? "the model is sharper than championship form on the win probability score, while championship form currently holds a slim edge on the podium score."
                : "championship form currently holds the edge on both probability scores."}{" "}
          {lastRallySharper
            ? "A last-rally momentum baseline is a touch sharper on the win score this season — shown here honestly rather than hidden."
            : "Everything here is shown honestly rather than hidden."}
        </p>
      </div>

      <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-[var(--hairline)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[var(--surface-2)] text-left text-xs uppercase tracking-wider text-[var(--ink-dim)]">
              <th className="px-4 py-3 font-medium">Measure</th>
              <th className="px-4 py-3 font-medium">Our forecast</th>
              <th className="px-4 py-3 font-medium">Championship form</th>
              <th className="hidden px-4 py-3 font-medium sm:table-cell">Last rally</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.label}
                className="border-t border-[var(--hairline)] bg-[var(--surface)]"
              >
                <td className="px-4 py-3 text-[var(--ink)]">
                  {r.label}
                  <span className="ml-2 text-xs text-[var(--ink-dim)]">({r.hint})</span>
                </td>
                <td className="px-4 py-3 tabular-nums font-semibold">
                  <span style={{ color: r.modelBeatsStandings ? "var(--accent-positive)" : "var(--ink)" }}>
                    {r.model}
                  </span>
                </td>
                <td className="px-4 py-3 tabular-nums text-[var(--ink-muted)]">{r.standings}</td>
                <td className="hidden px-4 py-3 tabular-nums text-[var(--ink-dim)] sm:table-cell">
                  {r.lastRally}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {bc.skillOnly && (
        <p className="mt-3 text-xs text-[var(--ink-dim)]">
          The skill model alone scores {num(bc.skillOnly.winBrier)} on the win score and{" "}
          {num(bc.skillOnly.podiumBrier)} on podium — weaker than championship form on its own.
          {bc.beatsStandingsBaseline
            ? " Blending it with championship form is what edges the combined forecast ahead."
            : " Blending it with championship form keeps the combined forecast competitive with championship form."}
        </p>
      )}
      {bc.beatsStandingsBaseline && (
        <p className="mt-2 text-xs text-[var(--ink-dim)]">
          Green marks where the forecast beats championship-form order.
        </p>
      )}
    </section>
  );
}
