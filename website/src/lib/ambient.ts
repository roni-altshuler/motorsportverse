/**
 * The reader-controlled ambient dial (DESIGN.md §6).
 *
 * Three states — 'soft' (default), 'vivid', 'off' — persisted in localStorage
 * under `motorsportverse-ambient` and mirrored as `data-ambient` on <html>.
 * The inline boot script in app/layout.tsx applies the stored value before
 * first paint; everything here runs after hydration. Client-only: the store
 * is the DOM attribute, the change signal is a window `ambientchange` event.
 */
import { useSyncExternalStore } from "react";

export type Ambient = "soft" | "vivid" | "off";

export const AMBIENT_KEY = "motorsportverse-ambient";
export const AMBIENT_EVENT = "ambientchange";
export const AMBIENT_DEFAULT: Ambient = "soft";
export const AMBIENT_VALUES: readonly Ambient[] = ["soft", "vivid", "off"];

export function isAmbient(value: unknown): value is Ambient {
  return typeof value === "string" && (AMBIENT_VALUES as readonly string[]).includes(value);
}

/** Current value from the <html> attribute; 'soft' when absent or invalid. */
export function readAmbient(): Ambient {
  if (typeof document === "undefined") return AMBIENT_DEFAULT;
  const v = document.documentElement.dataset.ambient;
  return isAmbient(v) ? v : AMBIENT_DEFAULT;
}

export function setAmbient(value: Ambient): void {
  document.documentElement.dataset.ambient = value;
  try {
    localStorage.setItem(AMBIENT_KEY, value);
  } catch {
    // Private mode / blocked storage: the attribute still applies for this visit.
  }
  window.dispatchEvent(new CustomEvent<Ambient>(AMBIENT_EVENT, { detail: value }));
}

function subscribe(onChange: () => void) {
  window.addEventListener(AMBIENT_EVENT, onChange);
  return () => window.removeEventListener(AMBIENT_EVENT, onChange);
}

/** Hook for client components that must react to the dial (hero bloom, canvas). */
export function useAmbient(): Ambient {
  return useSyncExternalStore(subscribe, readAmbient, () => AMBIENT_DEFAULT);
}
