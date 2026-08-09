"use client";

/**
 * PodiumRationale — the one-line "why the model ranks them" headline that
 * rides directly under the predicted podium trio.
 *
 * Instead of leaving the reasoning to a quiet separate panel, this distils
 * the model's read into a single plain-language sentence: who leads, the
 * factor they lead on, their win projection, and how clear the margin is.
 * Everything is derived from the round's own classification (`winProbability`
 * + `keyFactors`) — no editorial copy, no fabricated numbers. Renders nothing
 * when the round carries no win projection to talk about.
 */
import { useMemo } from "react";
import type { ClassificationEntry, KeyFactor } from "@/types";

function topAdvantage(factors: KeyFactor[] | undefined): KeyFactor | null {
  if (!factors || factors.length === 0) return null;
  const advantages = factors.filter((f) => f.direction === "advantage");
  const pool = advantages.length > 0 ? advantages : factors;
  return pool.reduce((best, f) => (f.weight > best.weight ? f : best), pool[0]);
}

export default function PodiumRationale({
  classification,
}: {
  classification: ClassificationEntry[];
}) {
  const sentence = useMemo(() => {
    const leader = classification[0];
    const p2 = classification[1];
    if (!leader || leader.winProbability == null) return null;

    const leaderName = leader.driverFullName ?? leader.driver;
    const p2Name = p2 ? (p2.driverFullName ?? p2.driver) : null;
    const win = leader.winProbability;
    const factor = topAdvantage(leader.keyFactors);

    const margin = p2?.winProbability != null ? win - p2.winProbability : null;
    const marginPhrase =
      margin == null
        ? null
        : margin >= 4
          ? "clear of"
          : margin >= 1.5
            ? "narrowly ahead of"
            : "in a near dead-heat with";

    const lead = factor
      ? `${leaderName} heads the board — strongest on ${factor.factor.toLowerCase()}`
      : `${leaderName} heads the board`;
    const winClause = `with a ${win.toFixed(0)}% win projection`;
    const tail =
      p2Name && marginPhrase ? `, ${marginPhrase} ${p2Name}.` : ".";

    return `${lead}, ${winClause}${tail}`;
  }, [classification]);

  if (!sentence) return null;
  const leaderColor = classification[0]?.teamColor || "var(--accent-live)";

  return (
    <div className="mb-8 flex items-stretch gap-4 border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-5 sm:p-6">
      <span aria-hidden className="w-[3px] flex-shrink-0" style={{ background: leaderColor }} />
      <div className="min-w-0">
        <p className="eyebrow mb-2">Why the model ranks them</p>
        <p className="title-sm sm:text-lg leading-snug text-[color:var(--ink)]">{sentence}</p>
      </div>
    </div>
  );
}
