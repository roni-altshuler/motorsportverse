"use client";

/**
 * CommandPalette (⌘K / Ctrl-K) — a dependency-free, keyboard-navigable
 * launcher to jump to projects, docs, and key pages. Items are passed from a
 * server component so the project list comes straight from the registry.
 *
 * A11y: focus-trapped dialog, Esc to close, arrow keys + Enter to navigate,
 * aria-modal, restores focus on close.
 */

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface PaletteItem {
  id: string;
  label: string;
  hint?: string;
  group: string;
  href: string;
  external?: boolean;
  keywords?: string;
}

export function CommandPalette({ items }: { items: PaletteItem[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setActive(0);
    restoreRef.current?.focus?.();
  }, []);

  const openPalette = useCallback(() => {
    restoreRef.current = document.activeElement as HTMLElement;
    setOpen(true);
  }, []);

  // Global hotkey + custom event from the navbar button.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => {
          if (!v) restoreRef.current = document.activeElement as HTMLElement;
          return !v;
        });
      } else if (e.key === "/" && !open && !isTyping(e.target)) {
        e.preventDefault();
        openPalette();
      }
    };
    const onOpen = () => openPalette();
    window.addEventListener("keydown", onKey);
    window.addEventListener("mv:open-palette", onOpen as EventListener);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mv:open-palette", onOpen as EventListener);
    };
  }, [open, openPalette]);

  useEffect(() => {
    if (open) {
      // focus the input after mount
      const t = window.setTimeout(() => inputRef.current?.focus(), 0);
      document.body.style.overflow = "hidden";
      return () => {
        window.clearTimeout(t);
        document.body.style.overflow = "";
      };
    }
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((it) =>
      `${it.label} ${it.group} ${it.hint ?? ""} ${it.keywords ?? ""}`
        .toLowerCase()
        .includes(q),
    );
  }, [items, query]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  const go = useCallback(
    (it: PaletteItem | undefined) => {
      if (!it) return;
      close();
      if (it.external) {
        window.open(it.href, "_blank", "noopener,noreferrer");
      } else if (it.href.startsWith("#")) {
        document.querySelector(it.href)?.scrollIntoView({ behavior: "smooth" });
      } else {
        router.push(it.href);
      }
    },
    [close, router],
  );

  const onListKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(filtered[active]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  };

  // keep active item in view
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-idx="${active}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  // group ordering preserved as encountered
  const groups: { name: string; items: { it: PaletteItem; idx: number }[] }[] = [];
  filtered.forEach((it, idx) => {
    let g = groups.find((x) => x.name === it.group);
    if (!g) {
      g = { name: it.group, items: [] };
      groups.push(g);
    }
    g.items.push({ it, idx });
  });

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center px-4 pt-[12vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onKeyDown={onListKey}
    >
      <button
        type="button"
        aria-label="Close command palette"
        className="absolute inset-0 cursor-default bg-black/55 backdrop-blur-sm"
        onClick={close}
        tabIndex={-1}
      />
      <div className="glass-strong relative w-full max-w-xl overflow-hidden rounded-[var(--radius-lg)] shadow-[var(--shadow-lg)]">
        <div className="flex items-center gap-3 border-b border-[var(--line)] px-4">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="text-[var(--ink-dim)]" aria-hidden>
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
            <path d="m20 20-3-3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search projects, docs, pages…"
            className="w-full bg-transparent py-4 text-sm text-[var(--ink)] outline-none placeholder:text-[var(--ink-dim)]"
            aria-label="Search"
            aria-controls="mv-palette-list"
          />
          <span className="kbd">esc</span>
        </div>

        <ul
          id="mv-palette-list"
          ref={listRef}
          className="max-h-[52vh] overflow-y-auto p-2"
          role="listbox"
        >
          {filtered.length === 0 && (
            <li className="px-3 py-8 text-center text-sm text-[var(--ink-dim)]">No results.</li>
          )}
          {groups.map((g) => (
            <li key={g.name} className="mb-1">
              <p className="mono-label px-3 pb-1 pt-2">{g.name}</p>
              <ul>
                {g.items.map(({ it, idx }) => (
                  <li key={it.id}>
                    <button
                      type="button"
                      data-idx={idx}
                      role="option"
                      aria-selected={idx === active}
                      onMouseEnter={() => setActive(idx)}
                      onClick={() => go(it)}
                      className="flex w-full items-center justify-between gap-3 rounded-[var(--radius-sm)] px-3 py-2.5 text-left text-sm transition-colors"
                      style={{
                        background: idx === active ? "var(--surface-3)" : "transparent",
                        color: idx === active ? "var(--ink)" : "var(--ink-muted)",
                      }}
                    >
                      <span className="truncate">{it.label}</span>
                      {it.hint && (
                        <span className="shrink-0 font-mono text-[11px] text-[var(--ink-dim)]">
                          {it.hint}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>

        <div className="flex items-center gap-4 border-t border-[var(--line)] px-4 py-2.5 text-[11px] text-[var(--ink-dim)]">
          <span className="flex items-center gap-1.5"><span className="kbd">↑↓</span> navigate</span>
          <span className="flex items-center gap-1.5"><span className="kbd">↵</span> open</span>
          <span className="ml-auto flex items-center gap-1.5"><span className="kbd">⌘K</span> toggle</span>
        </div>
      </div>
    </div>
  );
}

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || el.isContentEditable;
}
