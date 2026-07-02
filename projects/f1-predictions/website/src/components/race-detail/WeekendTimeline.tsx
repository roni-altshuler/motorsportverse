"use client";

/**
 * WeekendTimeline — horizontal state timeline for a Grand Prix round:
 *
 *   Preview → Qualifying → Race → Graded
 *
 * Stage state derives from the same fields the status badges use today:
 * `predictionPhase` (preview / post-quali / post-race), presence of
 * `actualResults`, and the calendar lifecycle (`awaiting-results`).
 *
 * Completed stages render a filled ink marker with a check; the current
 * stage carries the live red marker (glow suppressed under
 * prefers-reduced-motion via the .timeline-node-live CSS fallback);
 * future stages stay dim. Single row on mobile — four short mono labels.
 */
import type { RoundLifecycle } from "@/types";

interface WeekendTimelineProps {
  predictionPhase?: "preview" | "post-quali" | "post-race";
  hasActualResults: boolean;
  lifecycle?: RoundLifecycle | null;
}

interface StageMeta {
  key: string;
  label: string;
  detail: string;
}

const STAGES: StageMeta[] = [
  { key: "preview", label: "Preview", detail: "Round scheduled" },
  { key: "qualifying", label: "Qualifying", detail: "Final forecast" },
  { key: "race", label: "Race", detail: "Lights out" },
  { key: "graded", label: "Graded", detail: "Forecast scored" },
];

/** Index of the current stage (0..3); 4 = everything complete. */
function currentStageIndex(
  phase: WeekendTimelineProps["predictionPhase"],
  hasActual: boolean,
  lifecycle: RoundLifecycle | null | undefined,
): number {
  if (hasActual) return 4;
  if (phase === "post-race" || lifecycle === "awaiting-results") return 2;
  if (phase === "post-quali") return 2;
  return 0;
}

function stageDetail(
  stage: StageMeta,
  state: "done" | "current" | "future",
  raceRun: boolean,
): string {
  if (state === "current") {
    if (stage.key === "preview") return "Forecast pending quali";
    if (stage.key === "race") return raceRun ? "Results syncing" : "Lights out";
  }
  return stage.detail;
}

export default function WeekendTimeline({
  predictionPhase,
  hasActualResults,
  lifecycle,
}: WeekendTimelineProps) {
  const current = currentStageIndex(predictionPhase, hasActualResults, lifecycle);
  const raceRun = predictionPhase === "post-race" || lifecycle === "awaiting-results";

  return (
    <nav aria-label="Race weekend progress" className="mb-8">
      <ol className="flex items-start">
        {STAGES.map((stage, i) => {
          const state: "done" | "current" | "future" =
            i < current ? "done" : i === current ? "current" : "future";
          const isLast = i === STAGES.length - 1;
          return (
            <li
              key={stage.key}
              className={`flex items-start min-w-0 ${isLast ? "flex-none" : "flex-1"}`}
              aria-current={state === "current" ? "step" : undefined}
            >
              <div className="flex flex-col items-start min-w-0">
                <span
                  aria-hidden
                  className={`timeline-node ${
                    state === "done"
                      ? "timeline-node-done"
                      : state === "current"
                        ? "timeline-node-live"
                        : "timeline-node-future"
                  }`}
                >
                  {state === "done" && (
                    <svg
                      viewBox="0 0 10 10"
                      className="w-2 h-2"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M1.5 5.5 4 8l4.5-6" />
                    </svg>
                  )}
                </span>
                <span
                  className="mt-2 font-mono uppercase tracking-[0.16em] text-[10px] sm:text-[11px] whitespace-nowrap"
                  style={{
                    color:
                      state === "current"
                        ? "var(--accent-f1-red-bright)"
                        : state === "done"
                          ? "var(--ink)"
                          : "var(--muted-soft)",
                  }}
                >
                  {stage.label}
                </span>
                <span
                  className="hidden sm:block mt-0.5 font-mono text-[9px] tracking-[0.08em] uppercase truncate max-w-full"
                  style={{ color: state === "future" ? "var(--muted-soft)" : "var(--muted)" }}
                >
                  {stageDetail(stage, state, raceRun)}
                </span>
              </div>
              {!isLast && (
                <span
                  aria-hidden
                  className="flex-1 h-px mt-[8px] mx-2 sm:mx-3"
                  style={{
                    background: i < current ? "var(--ink)" : "var(--hairline)",
                  }}
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
