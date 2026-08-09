"use client";

/**
 * favorites.ts — a tiny, SSR-safe store for a fan's favourite drivers.
 *
 * The list of starred driver codes lives in `localStorage` so it survives
 * reloads and syncs across tabs, but it is a purely client-side preference —
 * nothing is fetched or persisted server-side. The whole module is safe to
 * import from a static export: every `window`/`localStorage` touch is guarded,
 * and the React bindings use `useSyncExternalStore` with a stable server
 * snapshot so the prerendered HTML (no favourites) matches first hydration
 * without a flash or a mismatch warning.
 *
 * Public surface:
 *   getFavorites()            → string[]      (SSR-safe; [] on the server)
 *   isFavorite(code)          → boolean
 *   toggleFavorite(code)      → void          (writes localStorage + notifies)
 *   subscribe(listener)       → unsubscribe   (also listens for cross-tab writes)
 *   useFavorites()            → string[]      (reactive hook)
 *   useIsFavorite(code)       → boolean       (reactive hook)
 */

import { useSyncExternalStore } from "react";

const STORAGE_KEY = "raceiq:favorite-drivers";

/** Stable empty reference — required so snapshots don't change identity when
 *  there are no favourites (a fresh `[]` each call would loop the store). */
const EMPTY: readonly string[] = Object.freeze([]);

/** Cached parsed snapshot. `null` = "not yet read / invalidated". Kept stable
 *  between reads so `useSyncExternalStore` sees a consistent reference. */
let cache: string[] | null = null;

const listeners = new Set<() => void>();

function readFromStorage(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is string => typeof x === "string");
  } catch {
    return [];
  }
}

function emit(): void {
  for (const listener of listeners) listener();
}

function handleStorageEvent(event: StorageEvent): void {
  // `key === null` fires on a full storage clear; otherwise only react to ours.
  if (event.key !== null && event.key !== STORAGE_KEY) return;
  cache = null; // invalidate — next read re-parses and yields a new reference
  emit();
}

/** Current favourites. SSR-safe: returns a stable empty array on the server. */
export function getFavorites(): string[] {
  if (typeof window === "undefined") return EMPTY as string[];
  if (cache === null) cache = readFromStorage();
  return cache;
}

export function isFavorite(code: string): boolean {
  return getFavorites().includes(code);
}

/** Add the code if absent, remove it if present, then persist + notify. */
export function toggleFavorite(code: string): void {
  if (typeof window === "undefined" || !code) return;
  const current = getFavorites();
  const next = current.includes(code)
    ? current.filter((c) => c !== code)
    : [...current, code];
  cache = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* storage full / disabled — keep the in-memory value so the UI still works */
  }
  emit();
}

/** Subscribe to favourite changes (in-tab toggles + cross-tab storage events). */
export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  if (listeners.size === 1 && typeof window !== "undefined") {
    window.addEventListener("storage", handleStorageEvent);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && typeof window !== "undefined") {
      window.removeEventListener("storage", handleStorageEvent);
    }
  };
}

// Server snapshot is a stable empty list (no favourites during prerender).
function getServerSnapshot(): string[] {
  return EMPTY as string[];
}

/** Reactive list of favourite driver codes. */
export function useFavorites(): string[] {
  return useSyncExternalStore(subscribe, getFavorites, getServerSnapshot);
}

/** Reactive boolean for a single driver — booleans compare by value, so this
 *  is safe even though `getFavorites().includes(...)` re-evaluates each call. */
export function useIsFavorite(code: string): boolean {
  return useSyncExternalStore(
    subscribe,
    () => getFavorites().includes(code),
    () => false,
  );
}
