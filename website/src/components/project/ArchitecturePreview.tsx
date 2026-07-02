/**
 * ArchitecturePreview — the "what exists today" panel for scaffolded
 * (in-development) projects. Server component, zero client JS.
 *
 * Tells the honest story: the project tree is real and lives in the monorepo,
 * everything numerically heavy is inherited from motorsport-core, and taking
 * the series live means implementing exactly two seams — a DataSource and a
 * Predictor. Driven by the registry `uses_core` field.
 */

import { accentText } from "@/lib/color";
import { CORE_CAPABILITIES, coreLabel } from "@/lib/labels";

interface ArchitecturePreviewProps {
  sport: string;
  accent: string;
  repo?: string;
  docs?: string;
  usesCore?: string[];
}

type NodeState = "todo" | "seam" | "inherited";

const PIPELINE: { label: string; hint: string; state: NodeState }[] = [
  { label: "Series data feed", hint: "official timing · results", state: "todo" },
  { label: "DataSource", hint: "seam 1 · to implement", state: "seam" },
  { label: "motorsport-core", hint: "inherited · zero rebuild", state: "inherited" },
  { label: "Predictor", hint: "seam 2 · to implement", state: "seam" },
  { label: "Forecast site", hint: "unlocks the live demo", state: "todo" },
];

export function ArchitecturePreview({
  sport,
  accent,
  repo,
  docs,
  usesCore = [],
}: ArchitecturePreviewProps) {
  const wired = new Set(usesCore);

  return (
    <div className="card-premium overflow-hidden" style={{ ["--team-color" as string]: accent }}>
      {/* header strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] px-6 py-4 sm:px-8">
        <p className="eyebrow eyebrow-tick" style={{ color: accentText(accent) }}>
          Architecture preview
        </p>
        <span className="mono-label flex items-center gap-1.5 text-[var(--maturity-in-development)]">
          <span
            className="inline-block h-1.5 w-1.5 rounded-full border border-current"
            aria-hidden
          />
          scaffold in the monorepo
        </span>
      </div>

      <div className="p-6 sm:p-8">
        <h2 className="font-display text-2xl font-semibold text-[var(--ink)] sm:text-3xl">
          Two seams to implement
        </h2>
        <p className="body-sm mt-3 max-w-2xl">
          The {sport} project tree exists today. Everything numerically heavy — calibration,
          simulation, evaluation — is inherited from the shared core. Bringing the series live
          means implementing exactly two interfaces.
        </p>

        {/* pipeline: data feed → DataSource → core → Predictor → site */}
        <div className="mt-7 flex flex-col items-stretch gap-1.5 lg:flex-row lg:items-center lg:gap-2">
          {PIPELINE.map((n, i) => (
            <PipelineStep key={n.label} node={n} accent={accent} last={i === PIPELINE.length - 1} />
          ))}
        </div>

        {/* inherited capabilities, driven by uses_core */}
        <div className="mt-10">
          <p className="mono-label">Inherited from motorsport-core</p>
          <div className="mt-4 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {CORE_CAPABILITIES.map((cap) => {
              const isWired = wired.has(cap.key);
              return (
                <div
                  key={cap.key}
                  className="flex items-start gap-2.5 rounded-[var(--radius-md)] border border-[var(--line)] bg-[var(--surface)] px-3.5 py-3"
                >
                  {isWired ? (
                    <svg
                      width="15"
                      height="15"
                      viewBox="0 0 24 24"
                      fill="none"
                      aria-hidden
                      className="mt-0.5 shrink-0 text-[var(--maturity-production)]"
                    >
                      <path
                        d="m5 13 4 4L19 7"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  ) : (
                    <span
                      className="mt-1 inline-block h-2.5 w-2.5 shrink-0 rounded-full border border-[var(--ink-dim)] opacity-70"
                      aria-hidden
                    />
                  )}
                  <div>
                    <p className="text-sm font-medium leading-snug text-[var(--ink)]">
                      {coreLabel(cap.key)}
                    </p>
                    <p className="mt-0.5 text-[11px] leading-snug text-[var(--ink-dim)]">
                      {isWired ? "wired into the scaffold" : cap.blurb}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* actions — source is real; the demo stays hidden until `website` lands */}
        <div className="mt-8 flex flex-wrap items-center gap-3">
          {repo && (
            <a
              href={repo}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] border px-5 py-2.5 text-sm font-semibold transition-colors"
              style={{
                color: accentText(accent),
                borderColor: `color-mix(in srgb, ${accent} 45%, transparent)`,
              }}
            >
              Browse the project tree
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path
                  d="M7 17 17 7M9 7h8v8"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </a>
          )}
          {docs && (
            <a
              href={docs}
              target="_blank"
              rel="noreferrer"
              className="rounded-[var(--radius-pill)] border border-[var(--line-strong)] px-5 py-2.5 text-sm font-medium text-[var(--ink)] transition-colors hover:border-[var(--ink-dim)]"
            >
              Adding-a-sport guide →
            </a>
          )}
          <span className="text-xs text-[var(--ink-dim)]">
            Live demo appears here once the first forecasts publish.
          </span>
        </div>
      </div>
    </div>
  );
}

function PipelineStep({
  node,
  accent,
  last,
}: {
  node: { label: string; hint: string; state: NodeState };
  accent: string;
  last: boolean;
}) {
  const styles: Record<NodeState, React.CSSProperties> = {
    todo: {
      borderColor: "var(--line)",
      borderStyle: "dashed",
      color: "var(--ink-muted)",
      background: "transparent",
    },
    seam: {
      borderColor: `color-mix(in srgb, ${accent} 45%, transparent)`,
      color: "var(--ink)",
      background: `color-mix(in srgb, ${accent} 8%, transparent)`,
    },
    inherited: {
      borderColor: "color-mix(in srgb, var(--maturity-production) 45%, transparent)",
      color: "var(--ink)",
      background: "color-mix(in srgb, var(--maturity-production) 7%, transparent)",
    },
  };

  return (
    <>
      <div
        className="flex-1 rounded-[var(--radius-md)] border px-3.5 py-3 text-center"
        style={styles[node.state]}
      >
        <p
          className={`text-[13px] font-semibold leading-tight ${
            node.state === "inherited" ? "font-mono tracking-tight" : ""
          }`}
        >
          {node.label}
        </p>
        <p className="mt-1 font-mono text-[9.5px] uppercase tracking-[0.14em] text-[var(--ink-dim)]">
          {node.hint}
        </p>
      </div>
      {!last && (
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden
          className="mx-auto shrink-0 rotate-90 text-[var(--ink-dim)] lg:mx-0 lg:rotate-0"
        >
          <path
            d="M5 12h14M13 6l6 6-6 6"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </>
  );
}
