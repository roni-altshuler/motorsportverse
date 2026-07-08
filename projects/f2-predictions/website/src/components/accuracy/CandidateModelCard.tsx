import type { PromotionStatus } from "@/types/f2";

const VERDICT_COPY: Record<string, string> = {
  "production-better": "Production model still ahead",
  "candidate-better": "Candidate ahead",
  inconclusive: "Too close to call",
};

function fmt(v: number | null | undefined, digits = 2): string {
  return v == null ? "—" : v.toFixed(digits);
}

/**
 * Small status card for the position-head A/B candidate model. Renders the
 * additive `candidate` / `abVerdict` block on promotion_status.json — the
 * walk-forward head-to-head between the direct finishing-position head and the
 * production path. The candidate stays behind a flag until it wins on real data.
 */
export default function CandidateModelCard({
  status,
}: {
  status: PromotionStatus | null;
}) {
  if (!status || !status.candidate || !status.abVerdict) return null;
  const ab = status.abVerdict;
  const productionAhead = ab.recommendation === "production-better";

  return (
    <section className="mt-12">
      <div className="mb-4">
        <p className="eyebrow mb-1">Candidate model</p>
        <h2 className="text-xl font-semibold text-[var(--ink)]">
          A shadow model runs alongside the live one
        </h2>
      </div>

      <div className="rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm text-[var(--ink)]">
              <span className="font-semibold">{status.candidate}</span> candidate ·
              gated behind{" "}
              <code className="rounded bg-[var(--surface-2)] px-1.5 py-0.5 text-xs">
                {status.candidateFlag}
              </code>
            </p>
            <p className="mt-1 text-xs text-[var(--ink-muted)]">
              Comparison basis: {ab.basis}
            </p>
          </div>
          <span
            className="rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider"
            style={{
              background: productionAhead
                ? "var(--surface-2)"
                : "color-mix(in srgb, var(--accent) 16%, transparent)",
              color: productionAhead ? "var(--ink-muted)" : "var(--accent)",
              border: `1px solid ${
                productionAhead
                  ? "var(--hairline)"
                  : "color-mix(in srgb, var(--accent) 40%, transparent)"
              }`,
            }}
          >
            {VERDICT_COPY[ab.recommendation] ?? ab.recommendation}
          </span>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <div className="rounded-[var(--radius-md)] border border-[var(--hairline)] p-4">
            <p className="mono-label">Production error</p>
            <p className="font-display font-tabular mt-1 text-2xl font-bold text-[var(--ink)]">
              {fmt(ab.productionMeanError)}
            </p>
            <p className="mt-1 text-xs text-[var(--ink-dim)]">mean positions off</p>
          </div>
          <div className="rounded-[var(--radius-md)] border border-[var(--hairline)] p-4">
            <p className="mono-label">Candidate error</p>
            <p className="font-display font-tabular mt-1 text-2xl font-bold text-[var(--ink)]">
              {fmt(ab.positionHeadMeanError)}
            </p>
            <p className="mt-1 text-xs text-[var(--ink-dim)]">mean positions off</p>
          </div>
          <div className="rounded-[var(--radius-md)] border border-[var(--hairline)] p-4">
            <p className="mono-label">Gap</p>
            <p
              className="font-display font-tabular mt-1 text-2xl font-bold"
              style={{ color: productionAhead ? "var(--ink)" : "var(--accent)" }}
            >
              {ab.meanErrorDelta != null && ab.meanErrorDelta > 0 ? "+" : ""}
              {fmt(ab.meanErrorDelta)}
            </p>
            <p className="mt-1 text-xs text-[var(--ink-dim)]">
              candidate minus production
            </p>
          </div>
        </div>

        <p className="mt-4 text-xs text-[var(--ink-dim)]">
          {status.reason}. The candidate only gets promoted once it beats the live model
          on enough real rounds — until then the site keeps serving the production forecast.
        </p>
      </div>
    </section>
  );
}
