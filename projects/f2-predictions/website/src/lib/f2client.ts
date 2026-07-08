"use client";

// Client-side loaders for the F2 dataset. The Navbar and other client
// components need the calendar + accuracy at runtime; the static export serves
// the JSON from /data (current season) or /data/seasons/<year> (archives).
// Mirrors the F1 flagship's fetchSeasonData + season-aware base paths.
import { useEffect, useState } from "react";

import type { F2Data, ProbabilitiesRound, RoundDetail } from "@/types/f2";

import { useSeason } from "./SeasonProvider";
import { BASE_PATH } from "./seasons";

const cache = new Map<string, F2Data | null>();
const inflight = new Map<string, Promise<F2Data | null>>();

export function fetchF2Data(base: string = BASE_PATH): Promise<F2Data | null> {
  if (cache.has(base)) return Promise.resolve(cache.get(base) ?? null);
  const pending = inflight.get(base);
  if (pending) return pending;
  const p = fetch(`${base}/f2.json`)
    .then((r) => (r.ok ? (r.json() as Promise<F2Data>) : null))
    .then((d) => {
      cache.set(base, d);
      inflight.delete(base);
      return d;
    })
    .catch(() => {
      inflight.delete(base);
      return null;
    });
  inflight.set(base, p);
  return p;
}

/** f2.json for a data root (defaults to the CURRENT season's root). */
export function useF2Data(base: string = BASE_PATH): F2Data | null {
  const [data, setData] = useState<F2Data | null>(cache.get(base) ?? null);
  useEffect(() => {
    let active = true;
    fetchF2Data(base).then((d) => {
      if (active) setData(d);
    });
    return () => {
      active = false;
    };
  }, [base]);
  return data;
}

/**
 * f2.json for the season selected in the SeasonProvider. `isArchived` is true
 * only when a non-current season is selected — pages baked with the current
 * season's data at build time overlay `data` in that case.
 */
export function useSeasonF2Data(): { data: F2Data | null; isArchived: boolean } {
  const { basePath, year, index } = useSeason();
  const data = useF2Data(basePath);
  const isArchived = !!index && year !== index.current;
  return { data, isArchived };
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** Per-round detail for a data root; null instead of throwing (graceful degrade). */
export async function fetchRoundDetail(
  round: number,
  base: string = BASE_PATH,
): Promise<RoundDetail | null> {
  try {
    const res = await fetch(`${base}/rounds/round_${pad2(round)}.json`);
    return res.ok ? ((await res.json()) as RoundDetail) : null;
  } catch {
    return null;
  }
}

/** Per-round probabilities for a data root; null instead of throwing. */
export async function fetchRoundProbabilities(
  round: number,
  base: string = BASE_PATH,
): Promise<ProbabilitiesRound | null> {
  try {
    const res = await fetch(`${base}/probabilities/round_${pad2(round)}.json`);
    return res.ok ? ((await res.json()) as ProbabilitiesRound) : null;
  } catch {
    return null;
  }
}

// ── Round lifecycle (mirrors F1's getRoundLifecycle / getRoundStatusMeta) ──
export type RoundLifecycle = "completed" | "next" | "upcoming";

export function getRoundLifecycle(
  completed: boolean,
  isNext: boolean,
): RoundLifecycle {
  if (completed) return "completed";
  if (isNext) return "next";
  return "upcoming";
}

export function getRoundStatusMeta(
  lifecycle: RoundLifecycle,
): { shortLabel: string; tone: "green" | "amber" | "slate" } {
  switch (lifecycle) {
    case "completed":
      return { shortLabel: "Done", tone: "green" };
    case "next":
      return { shortLabel: "Next", tone: "amber" };
    default:
      return { shortLabel: "Soon", tone: "slate" };
  }
}
