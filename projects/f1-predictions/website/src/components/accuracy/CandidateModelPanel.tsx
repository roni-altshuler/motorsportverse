"use client";

import type { PromotionHeadlineStats, PromotionStatusData } from "@/types";

/**
 * CandidateModelPanel — status card for the shadow (candidate) model stream.
 *
 * Renders the `headline` block from `promotion_status.json`: a challenger
 * model is scored on exactly the same graded rounds as the live one, and only
 * gets promoted when it clearly wins on real results. Hidden entirely when
 * the file or its headline block is absent (archived seasons).
 */

const VERDICT_META: Record<string, { label: string; tone: "model" | "candidate" | "neutral" }> = {
  "candidate-better": { label: "Challenger Ahead", tone: "candidate" },
  "production-better": { label: "Live Model Ahead", tone: "model" },
  parity: { label: "Dead Heat", tone: "neutral" },
};

function StatColumn({
  title,
  stats,
  highlight,
}: {
  title: string;
  stats: PromotionHeadlineStats;
  highlight: boolean;
}) {
  return (
    <div
      className="metric-card"
      style={
        highlight
          ? { border: "1px solid var(--accent-f1-red-soft, rgba(225,6,0,0.35))" }
          : undefined
      }
    >
      <p className="eyebrow mb-3">{title}</p>
      <div className="space-y-2 text-sm">
        <div className="flex items-baseline justify-between gap-2">
          <span style={{ color: "var(--text-muted)" }}>Winner called</span>
          <span className="font-mono font-bold" style={{ color: "var(--text)" }}>
            {stats.winnerHits}/{stats.rounds}
            <span className="text-xs font-normal ml-1" style={{ color: "var(--text-muted)" }}>
              ({stats.winnerHitPct.toFixed(1)}%)
            </span>
          </span>
        </div>
        {stats.blendPct != null && (
          <div className="flex items-baseline justify-between gap-2">
            <span style={{ color: "var(--text-muted)" }}>Podium &amp; points blend</span>
            <span className="font-mono font-bold" style={{ color: "var(--text)" }}>
              {stats.blendPct.toFixed(1)}%
            </span>
          </div>
        )}
        {stats.meanError != null && (
          <div className="flex items-baseline justify-between gap-2">
            <span style={{ color: "var(--text-muted)" }}>Mean position error</span>
            <span className="font-mono font-bold" style={{ color: "var(--text)" }}>
              {stats.meanError.toFixed(2)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function CandidateModelPanel({
  status,
}: {
  status: PromotionStatusData | null;
}) {
  const headline = status?.headline;
  if (!status || !headline?.production || !headline?.candidate) return null;

  const meta = VERDICT_META[headline.verdict] ?? {
    label: headline.verdict,
    tone: "neutral" as const,
  };
  const pillColor =
    meta.tone === "candidate"
      ? { background: "rgba(0,210,190,0.12)", color: "#00D2BE" }
      : meta.tone === "model"
        ? { background: "rgba(225,6,0,0.12)", color: "#E10600" }
        : { background: "rgba(136,136,136,0.12)", color: "var(--text-muted)" };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
        <h2 className="section-heading mb-0">Challenger Watch</h2>
        <span
          className="text-xs font-bold uppercase tracking-wider px-2 py-1 rounded-full"
          style={pillColor}
        >
          {meta.label}
        </span>
      </div>
      <p className="text-sm mb-5" style={{ color: "var(--text-muted)" }}>
        A challenger model shadows the live one on every graded round — scored head-to-head on{" "}
        {headline.roundsCompared} round{headline.roundsCompared !== 1 ? "s" : ""} of real results.
        It only takes over if it clearly wins.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <StatColumn
          title="Live Model"
          stats={headline.production}
          highlight={meta.tone !== "candidate"}
        />
        <StatColumn
          title="Challenger"
          stats={headline.candidate}
          highlight={meta.tone === "candidate"}
        />
      </div>
      {status.reason && (
        <p className="text-xs mt-4 leading-relaxed" style={{ color: "var(--text-muted)" }}>
          Current call: <strong style={{ color: "var(--text)" }}>{status.decision}</strong> —{" "}
          {status.reason}. The site keeps publishing the live model&apos;s forecast until the
          challenger earns the seat.
        </p>
      )}
    </div>
  );
}
