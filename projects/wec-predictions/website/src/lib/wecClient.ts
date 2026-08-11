"use client";

// Client-side loaders for the WEC dataset. The Navbar and other client
// components need the calendar + accuracy at runtime; the static export serves
// the JSON from /data (current season) or /data/seasons/<year> (archives).
import { useEffect, useState } from "react";

import type { ProbabilitiesRound, RoundDetail, WecData } from "@/types/wec";

import { useSeason } from "./SeasonProvider";
import { BASE_PATH } from "./seasons";

const cache = new Map<string, WecData | null>();
const inflight = new Map<string, Promise<WecData | null>>();

export function fetchWecData(base: string = BASE_PATH): Promise<WecData | null> {
  if (cache.has(base)) return Promise.resolve(cache.get(base) ?? null);
  const pending = inflight.get(base);
  if (pending) return pending;
  const p = fetch(`${base}/wec.json`)
    .then((r) => (r.ok ? (r.json() as Promise<WecData>) : null))
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

/** wec.json for a data root (defaults to the CURRENT season's root). */
export function useWecData(base: string = BASE_PATH): WecData | null {
  const [data, setData] = useState<WecData | null>(cache.get(base) ?? null);
  useEffect(() => {
    let active = true;
    fetchWecData(base).then((d) => {
      if (active) setData(d);
    });
    return () => {
      active = false;
    };
  }, [base]);
  return data;
}

/**
 * wec.json for the season selected in the SeasonProvider. `isArchived` is true
 * only when a non-current season is selected.
 */
export function useSeasonWecData(): { data: WecData | null; isArchived: boolean } {
  const { basePath, year, index } = useSeason();
  const data = useWecData(basePath);
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

// ── Round lifecycle (completed / next / upcoming) ──
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
