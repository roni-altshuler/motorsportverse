"use client";

// Client-side loader for f2.json. The Navbar and other client components need
// the calendar + accuracy at runtime; the static export serves the JSON from
// /data/f2.json under the basePath. Mirrors the F1 flagship's fetchSeasonData.
import { useEffect, useState } from "react";

import type { F2Data } from "@/types/f2";

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

let cached: F2Data | null = null;
let inflight: Promise<F2Data | null> | null = null;

export function fetchF2Data(): Promise<F2Data | null> {
  if (cached) return Promise.resolve(cached);
  if (inflight) return inflight;
  inflight = fetch(`${BASE_PATH}/data/f2.json`)
    .then((r) => (r.ok ? (r.json() as Promise<F2Data>) : null))
    .then((d) => {
      cached = d;
      return d;
    })
    .catch(() => null);
  return inflight;
}

export function useF2Data(): F2Data | null {
  const [data, setData] = useState<F2Data | null>(cached);
  useEffect(() => {
    let active = true;
    fetchF2Data().then((d) => {
      if (active) setData(d);
    });
    return () => {
      active = false;
    };
  }, []);
  return data;
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
