"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  BASE_PATH,
  basePathForYear,
  fetchSeasonsIndex,
  type SeasonsIndex,
} from "./seasons";

interface SeasonContextValue {
  /** Selected season year (defaults to the current season). */
  year: number;
  /** Data root for the selected season — pass to the f2client fetchers. */
  basePath: string;
  /** The full multi-season index (null until loaded). */
  index: SeasonsIndex | null;
  /** Whether more than one season exists (controls switcher visibility). */
  hasMultiple: boolean;
  setYear: (year: number) => void;
}

const SeasonContext = createContext<SeasonContextValue | null>(null);

function readYearFromUrl(): number | null {
  if (typeof window === "undefined") return null;
  const v = new URLSearchParams(window.location.search).get("season");
  const n = v ? parseInt(v, 10) : NaN;
  return Number.isFinite(n) ? n : null;
}

export function SeasonProvider({ children }: { children: ReactNode }) {
  const [index, setIndex] = useState<SeasonsIndex | null>(null);
  const [year, setYearState] = useState<number>(() => new Date().getFullYear());

  useEffect(() => {
    let active = true;
    fetchSeasonsIndex().then((idx) => {
      if (!active) return;
      setIndex(idx);
      const urlYear = readYearFromUrl();
      setYearState(
        urlYear && idx.available.includes(urlYear) ? urlYear : idx.current
      );
    });
    return () => {
      active = false;
    };
  }, []);

  const setYear = useCallback(
    (next: number) => {
      setYearState(next);
      if (typeof window !== "undefined") {
        const url = new URL(window.location.href);
        if (index && next === index.current) {
          url.searchParams.delete("season");
        } else {
          url.searchParams.set("season", String(next));
        }
        window.history.replaceState({}, "", url.toString());
      }
    },
    [index]
  );

  const value = useMemo<SeasonContextValue>(() => {
    const basePath = index ? basePathForYear(index, year) : BASE_PATH;
    return {
      year,
      basePath,
      index,
      hasMultiple: (index?.available.length ?? 1) > 1,
      setYear,
    };
  }, [index, year, setYear]);

  return <SeasonContext.Provider value={value}>{children}</SeasonContext.Provider>;
}

export function useSeason(): SeasonContextValue {
  const ctx = useContext(SeasonContext);
  if (!ctx) {
    // Safe fallback when used outside the provider (e.g. isolated tests).
    return {
      year: new Date().getFullYear(),
      basePath: BASE_PATH,
      index: null,
      hasMultiple: false,
      setYear: () => {},
    };
  }
  return ctx;
}
