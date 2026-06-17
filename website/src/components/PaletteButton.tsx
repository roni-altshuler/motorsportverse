"use client";

/** Small client trigger that opens the global command palette. */
export function PaletteButton({ className }: { className?: string }) {
  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new Event("mv:open-palette"))}
      aria-label="Open command palette"
      className={
        className ??
        "group flex items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--line)] bg-[var(--surface-2)]/60 px-3 py-1.5 text-xs text-[var(--ink-dim)] transition-colors hover:border-[var(--line-strong)] hover:text-[var(--ink-muted)]"
      }
    >
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden>
        <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
        <path d="m20 20-3-3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <span className="hidden sm:inline">Search</span>
      <span className="kbd ml-1">⌘K</span>
    </button>
  );
}
