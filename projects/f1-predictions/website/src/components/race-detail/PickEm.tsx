"use client";

/**
 * PickEm — "Beat the Model" fan game (client-only, localStorage).
 *
 * Before a round's prediction is published, a fan taps three drivers to call
 * the podium. Their pick is persisted per season+round in the browser. Once the
 * model's forecast is out the pick locks; once the race is graded we reveal the
 * fan's podium against BOTH the official result and the model's predicted
 * podium — e.g. "You: 2/3 · Model: 3/3".
 *
 * This is an additive, clearly-labelled fan game. It never overwrites or
 * competes with the honest model content; it degrades gracefully when storage
 * is unavailable and hides itself when there is no roster to pick from.
 */

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import HUDPanel from "@/components/ui/HUDPanel";
import { Badge } from "@/components/ui/Badge";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { resolveDriverHeadshot } from "@/lib/headshots";
import { loadPodiumPick, savePodiumPick, clearPodiumPick, gradePodium } from "@/lib/picks";

export interface PickEmRosterDriver {
  /** 3-letter code — the stored pick identity. */
  driver: string;
  driverFullName?: string;
  team?: string;
  teamColor?: string;
  headshotUrl?: string | null;
}

interface PickEmProps {
  season: number;
  round: number;
  /** Drivers available to pick from (typically the round's classification). */
  roster: PickEmRosterDriver[];
  /** Model's predicted top-3 codes — only once the forecast is published. */
  modelPodium?: string[] | null;
  /** Official top-3 codes — present only once the race is graded. */
  actualPodium?: string[] | null;
  /** The model forecast is out → the fan's pick locks. */
  predictionPublished: boolean;
  /** Official result present → reveal the head-to-head. */
  graded: boolean;
}

const SLOT_LABELS = ["p1", "p2", "p3"] as const;

export default function PickEm({
  season,
  round,
  roster,
  modelPodium,
  actualPodium,
  predictionPublished,
  graded,
}: PickEmProps) {
  const [podium, setPodium] = useState<string[]>([]);
  const [hydrated, setHydrated] = useState(false);

  // Load any saved pick after mount (localStorage is client-only, so the
  // server render and first client render both start from an empty podium —
  // no hydration mismatch). The read is deferred to a microtask so the state
  // update lands in an async callback rather than synchronously in the effect
  // body, matching the codebase's fetch-then-setState effect convention.
  useEffect(() => {
    let active = true;
    Promise.resolve().then(() => {
      if (!active) return;
      const saved = loadPodiumPick(season, round);
      setPodium(saved?.podium ?? []);
      setHydrated(true);
    });
    return () => {
      active = false;
    };
  }, [season, round]);

  const byCode = useMemo(
    () => new Map(roster.map((d) => [d.driver, d] as const)),
    [roster],
  );

  // Alphabetical roster for the picker so the model's predicted order never
  // leaks into the choice grid (the classification arrives pre-sorted by rank).
  const pickable = useMemo(
    () =>
      roster
        .filter((d) => d.driver)
        .slice()
        .sort((a, b) =>
          (a.driverFullName || a.driver).localeCompare(b.driverFullName || b.driver),
        ),
    [roster],
  );

  if (roster.length === 0) return null;

  const locked = graded || predictionPublished;
  const editable = hydrated && !locked;
  const showGraded = graded && Array.isArray(actualPodium) && actualPodium.length >= 3;

  const toggle = (code: string) => {
    if (!editable) return;
    setPodium((prev) => {
      let next: string[];
      if (prev.includes(code)) {
        next = prev.filter((c) => c !== code);
      } else if (prev.length >= 3) {
        return prev; // podium full — deselect one first
      } else {
        next = [...prev, code];
      }
      savePodiumPick(season, round, next);
      return next;
    });
  };

  const startOver = () => {
    if (!editable) return;
    clearPodiumPick(season, round);
    setPodium([]);
  };

  const actualSet =
    showGraded && actualPodium ? new Set(actualPodium.slice(0, 3)) : null;
  const userGrade =
    showGraded && actualPodium && podium.length > 0
      ? gradePodium(podium, actualPodium)
      : null;
  const modelGrade =
    showGraded && actualPodium && modelPodium && modelPodium.length > 0
      ? gradePodium(modelPodium, actualPodium)
      : null;

  let verdict = "";
  if (showGraded) {
    if (userGrade && modelGrade) {
      if (userGrade.hits > modelGrade.hits)
        verdict = "You beat the model this weekend — brilliant call.";
      else if (userGrade.hits === modelGrade.hits)
        verdict = "Dead heat with the model. Not bad at all.";
      else verdict = "The model edged you this time. Run it back next round.";
    } else if (userGrade) {
      verdict = `You called ${userGrade.hits} of 3. Try to out-predict the model next round.`;
    } else {
      verdict = "No pick recorded for this round — jump in on the next one.";
    }
  }

  return (
    <motion.section
      className="mb-8"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <HUDPanel
        kicker="Fan game"
        title="Beat the Model"
        rightSlot={
          showGraded ? (
            <Badge variant="positive">Result in</Badge>
          ) : locked ? (
            <Badge variant="muted">Locked in</Badge>
          ) : (
            <Badge variant="live">Play</Badge>
          )
        }
        bodyClassName="p-5 sm:p-6"
      >
        {/* ── Graded: fan vs official vs model ─────────────────────────── */}
        {showGraded ? (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              {userGrade && (
                <Badge
                  variant={
                    modelGrade && userGrade.hits >= modelGrade.hits ? "positive" : "outline"
                  }
                >
                  You {userGrade.hits}/3
                </Badge>
              )}
              {modelGrade && <Badge variant="live">Model {modelGrade.hits}/3</Badge>}
            </div>
            <p className="body-sm" style={{ color: "var(--text-muted)" }}>
              {verdict}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <PodiumColumn
                label="Your podium"
                codes={podium}
                targetSet={actualSet}
                byCode={byCode}
                emptyNote="You didn't lock a pick."
              />
              <PodiumColumn
                label="Model podium"
                codes={modelPodium ?? []}
                targetSet={actualSet}
                byCode={byCode}
                emptyNote="No model podium published."
              />
              <PodiumColumn
                label="Official podium"
                codes={actualPodium ?? []}
                targetSet={null}
                byCode={byCode}
                emptyNote="Result pending."
              />
            </div>
          </div>
        ) : locked ? (
          /* ── Locked: forecast out, race not run yet ──────────────────── */
          <div className="space-y-5">
            {podium.length > 0 ? (
              <>
                <p className="body-sm" style={{ color: "var(--text-muted)" }}>
                  Your podium is locked for this round. Come back after the race to see if you
                  beat the model.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <PodiumColumn
                    label="Your podium"
                    codes={podium}
                    targetSet={null}
                    byCode={byCode}
                    emptyNote=""
                  />
                  {modelPodium && modelPodium.length > 0 && (
                    <PodiumColumn
                      label="Model podium"
                      codes={modelPodium}
                      targetSet={null}
                      byCode={byCode}
                      emptyNote=""
                    />
                  )}
                </div>
              </>
            ) : (
              <p className="body-sm" style={{ color: "var(--text-muted)" }}>
                Picks close once the model publishes its forecast for a round. Catch the next
                Grand Prix to call the podium and take on the model.
              </p>
            )}
          </div>
        ) : (
          /* ── Open: pick your podium ──────────────────────────────────── */
          <div className="space-y-5">
            <p className="body-sm" style={{ color: "var(--text-muted)" }}>
              Call the podium before the model does. Tap three drivers for P1, P2 and P3 — your
              pick is saved on this device and graded against the result once the race runs.
            </p>

            {/* Chosen slots */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {SLOT_LABELS.map((slotClass, i) => {
                const code = podium[i];
                const d = code ? byCode.get(code) : undefined;
                return (
                  <div
                    key={slotClass}
                    className="flex items-center gap-3 rounded-none border border-[color:var(--hairline)] bg-[color:var(--surface-card)] px-3 py-2.5"
                  >
                    <span className={`position-badge ${slotClass}`}>P{i + 1}</span>
                    {code ? (
                      <>
                        <DriverPortrait
                          driver={code}
                          driverFullName={d?.driverFullName}
                          team={d?.team ?? ""}
                          teamColor={d?.teamColor}
                          headshotUrl={resolveDriverHeadshot(code, d?.headshotUrl)}
                          size={28}
                        />
                        <span className="font-bold text-sm truncate" style={{ color: "var(--text)" }}>
                          {d?.driverFullName ?? code}
                        </span>
                        <button
                          type="button"
                          onClick={() => toggle(code)}
                          className="ml-auto text-xs font-mono uppercase tracking-wider transition-colors hover:text-[color:var(--accent-f1-red)]"
                          style={{ color: "var(--text-muted)" }}
                          aria-label={`Remove ${d?.driverFullName ?? code} from your podium`}
                        >
                          Remove
                        </button>
                      </>
                    ) : (
                      <span className="text-sm" style={{ color: "var(--text-muted)" }}>
                        Tap a driver
                      </span>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Roster grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {pickable.map((d) => {
                const idx = podium.indexOf(d.driver);
                const picked = idx >= 0;
                const full = podium.length >= 3;
                return (
                  <button
                    key={d.driver}
                    type="button"
                    onClick={() => toggle(d.driver)}
                    disabled={!editable || (!picked && full)}
                    aria-pressed={picked}
                    className="flex items-center gap-2 rounded-none border px-2.5 py-2 text-left transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                    style={{
                      borderColor: picked ? "var(--accent-f1-red)" : "var(--hairline)",
                      background: picked
                        ? "color-mix(in srgb, var(--accent-f1-red) 12%, transparent)"
                        : "var(--surface-card)",
                    }}
                  >
                    <DriverPortrait
                      driver={d.driver}
                      driverFullName={d.driverFullName}
                      team={d.team ?? ""}
                      teamColor={d.teamColor}
                      headshotUrl={resolveDriverHeadshot(d.driver, d.headshotUrl)}
                      size={26}
                    />
                    <span className="min-w-0">
                      <span className="block font-bold text-sm truncate" style={{ color: "var(--text)" }}>
                        {d.driver}
                      </span>
                      {d.driverFullName && (
                        <span
                          className="block text-[11px] truncate"
                          style={{ color: "var(--text-muted)" }}
                        >
                          {d.driverFullName}
                        </span>
                      )}
                    </span>
                    {picked && (
                      <span
                        className="ml-auto font-mono text-xs font-bold"
                        style={{ color: "var(--accent-f1-red)" }}
                      >
                        P{idx + 1}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {podium.length > 0 && (
              <div className="flex items-center gap-4">
                <span className="text-xs font-mono uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                  {podium.length}/3 picked
                </span>
                <button
                  type="button"
                  onClick={startOver}
                  className="text-xs font-mono uppercase tracking-wider transition-colors hover:text-[color:var(--accent-f1-red)]"
                  style={{ color: "var(--text-muted)" }}
                >
                  Start over
                </button>
              </div>
            )}
          </div>
        )}
      </HUDPanel>
    </motion.section>
  );
}

/** A labelled podium column with optional hit-marking against a target set. */
function PodiumColumn({
  label,
  codes,
  targetSet,
  byCode,
  emptyNote,
}: {
  label: string;
  codes: string[];
  targetSet: Set<string> | null;
  byCode: Map<string, PickEmRosterDriver>;
  emptyNote: string;
}) {
  const trimmed = codes.slice(0, 3);
  return (
    <div>
      <p
        className="text-xs font-bold uppercase tracking-wider mb-2"
        style={{ color: "var(--text-muted)" }}
      >
        {label}
      </p>
      {trimmed.length === 0 ? (
        <p className="body-sm" style={{ color: "var(--text-muted)" }}>
          {emptyNote}
        </p>
      ) : (
        <div className="space-y-2">
          {trimmed.map((code, i) => {
            const d = byCode.get(code);
            const hit = targetSet ? targetSet.has(code) : null;
            return (
              <div key={`${label}-${code}`} className="flex items-center gap-2">
                <span
                  className="font-mono text-xs"
                  style={{ color: "var(--text-muted)", minWidth: 22 }}
                >
                  P{i + 1}
                </span>
                <DriverPortrait
                  driver={code}
                  driverFullName={d?.driverFullName}
                  team={d?.team ?? ""}
                  teamColor={d?.teamColor}
                  headshotUrl={resolveDriverHeadshot(code, d?.headshotUrl)}
                  size={24}
                />
                <span className="font-bold text-sm" style={{ color: "var(--text)" }}>
                  {code}
                </span>
                {hit !== null && (
                  <span
                    className="ml-auto font-mono text-xs font-bold"
                    style={{
                      color: hit ? "var(--accent-positive)" : "var(--text-muted)",
                    }}
                    aria-label={hit ? "On the podium" : "Missed the podium"}
                  >
                    {hit ? "✓" : "—"}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
