import type { ForwardEvalSeason } from "@/types/motogp";

/**
 * PhaseComparisonPanel — honest model-vs-baseline read for the Grand Prix.
 *
 * The headline forecast is made AFTER qualifying, so it knows the starting grid.
 * The season eval scores three things on the same rounds:
 *   • our forecast (grid-conditioned)         — "post"
 *   • a pre-qualifying, form-only forecast     — "pre"
 *   • the bare qualifying order as a forecast  — "grid"
 *
 * The honest story: our grid-conditioned forecast is SHARPER than the grid on
 * win and podium probabilities, while the form-only forecast is WEAKER than the
 * grid — so we never claim to predict qualifying from nothing. Lower probability
 * scores are better; winner accuracy is higher-is-better.
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
  const pc = season?.phaseComparison;
  if (!pc || !pc.feature) return null;

  const winBrier = pc.feature.winBrier;
  const podiumBrier = pc.feature.podiumBrier;
  const winnerHit = pc.feature.winnerHit;

  const winSharper =
    winBrier != null && winBrier.post != null && winBrier.grid != null
      ? winBrier.post < winBrier.grid
      : false;
  const podiumSharper =
    podiumBrier != null && podiumBrier.post != null && podiumBrier.grid != null
      ? podiumBrier.post < podiumBrier.grid
      : false;

  const rows: {
    label: string;
    hint: string;
    ours: string;
    grid: string;
    form: string;
    oursBeatsGrid: boolean | null;
  }[] = [
    winBrier && {
      label: "Win probability score",
      hint: "lower is sharper",
      ours: num(winBrier.post),
      grid: num(winBrier.grid),
      form: num(winBrier.pre),
      oursBeatsGrid: winBrier.post < winBrier.grid,
    },
    podiumBrier && {
      label: "Podium probability score",
      hint: "lower is sharper",
      ours: num(podiumBrier.post),
      grid: num(podiumBrier.grid),
      form: num(podiumBrier.pre),
      oursBeatsGrid: podiumBrier.post < podiumBrier.grid,
    },
    winnerHit && {
      label: "Winner called",
      hint: "higher is better",
      ours: pctScore(winnerHit.post),
      grid: pctScore(winnerHit.grid),
      form: pctScore(winnerHit.pre),
      oursBeatsGrid: winnerHit.post >= winnerHit.grid,
    },
  ].filter(Boolean) as {
    label: string;
    hint: string;
    ours: string;
    grid: string;
    form: string;
    oursBeatsGrid: boolean | null;
  }[];

  if (rows.length === 0) return null;

  return (
    <section className="mt-12">
      <div className="mb-4">
        <p className="eyebrow mb-1">Vs the baselines</p>
        <h2 className="text-xl font-semibold text-[var(--ink)]">
          Does the forecast beat the grid?
        </h2>
        <p className="mt-2 text-sm text-[var(--ink-muted)]">
          Our Grand Prix forecast is made after qualifying, so it starts from the real grid. Over{" "}
          {pc.roundsScored} completed round{pc.roundsScored === 1 ? "" : "s"}{" "}
          {winSharper && podiumSharper
            ? "it is sharper than the grid order alone on win and podium probabilities."
            : podiumSharper
              ? "it is sharper than the grid order alone on podium probabilities, while the raw grid currently holds a slim edge on the win score."
              : winSharper
                ? "it is sharper than the grid order alone on win probabilities, while the raw grid currently holds a slim edge on the podium score."
                : "the raw grid order currently holds the edge on the probability scores — shown here honestly rather than hidden."}{" "}
          A pre-qualifying, form-only forecast is weaker than the grid — so we don&rsquo;t claim to
          call the grid from nothing.
        </p>
      </div>

      <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-[var(--hairline)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[var(--surface-2)] text-left text-xs uppercase tracking-wider text-[var(--ink-dim)]">
              <th className="px-4 py-3 font-medium">Measure</th>
              <th className="px-4 py-3 font-medium">Our forecast</th>
              <th className="px-4 py-3 font-medium">Grid order</th>
              <th className="hidden px-4 py-3 font-medium sm:table-cell">Form only</th>
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
                  <span style={{ color: r.oursBeatsGrid ? "var(--accent-positive)" : "var(--ink)" }}>
                    {r.ours}
                  </span>
                </td>
                <td className="px-4 py-3 tabular-nums text-[var(--ink-muted)]">{r.grid}</td>
                <td className="hidden px-4 py-3 tabular-nums text-[var(--ink-dim)] sm:table-cell">
                  {r.form}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pc.beatsGridBaseline && (
        <p className="mt-2 text-xs text-[var(--ink-dim)]">
          Green marks where the grid-conditioned forecast beats the bare grid order.
        </p>
      )}
    </section>
  );
}
