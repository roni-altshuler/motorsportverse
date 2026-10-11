"use client";

import { useEffect, useMemo, useState } from "react";
import type { RoundData, SeasonData } from "@/types";
import { fetchRoundData } from "./data";

export type RoundArtifactState =
  | { status: "loading" | "unavailable"; data: null }
  | { status: "ready"; data: RoundData };

/** Only expose a response for the currently requested season/event identity. */
export function useRoundArtifact(
  round: number | null,
  basePath: string,
  season: SeasonData | null,
): RoundArtifactState {
  const expected = season?.calendar.find((entry) => entry.round === round);
  const key =
    expected && season
      ? JSON.stringify([
          basePath,
          season.season,
          round,
          expected.gpKey,
          expected.name,
          expected.circuit,
          expected.date,
        ])
      : null;
  const request = useMemo(() => ({ key, round, basePath, season }), [key, round, basePath, season]);
  const [snapshot, setSnapshot] = useState<{
    request: typeof request;
    state: RoundArtifactState;
  } | null>(null);

  useEffect(() => {
    if (!request.key || request.round === null || !request.season) return;
    let active = true;
    fetchRoundData(request.round, request.basePath, request.season)
      .then((data) => {
        if (active) setSnapshot({ request, state: { status: "ready", data } });
      })
      .catch(() => {
        if (active) setSnapshot({ request, state: { status: "unavailable", data: null } });
      });
    return () => {
      active = false;
    };
  }, [request]);

  if (!season) return { status: "loading", data: null };
  if (!expected) return { status: "unavailable", data: null };
  return snapshot?.request === request ? snapshot.state : { status: "loading", data: null };
}
