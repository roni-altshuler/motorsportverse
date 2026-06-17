"use client";

/** A subtle hint that the command palette exists; clicking opens it. */
export function CommandPaletteHint() {
  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new Event("mv:open-palette"))}
      className="mt-8 inline-flex items-center gap-2 text-xs text-[var(--ink-dim)] transition-colors hover:text-[var(--ink-muted)]"
    >
      Jump anywhere with
      <span className="kbd">⌘K</span>
    </button>
  );
}
