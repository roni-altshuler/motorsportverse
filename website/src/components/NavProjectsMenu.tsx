"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { MaturityBadge } from "@/components/MaturityBadge";
import type { Maturity } from "@/types/registry";

export interface NavProject {
  slug: string;
  name: string;
  sport: string;
  maturity: Maturity;
  accent?: string;
}

/**
 * Header "Projects" dropdown — opens on hover (with a grace timeout so the
 * cursor can travel to the menu) and on click for touch/keyboard. Surfaces the
 * ecosystem projects directly in the nav bar so nothing nav-worthy lives only
 * in the footer.
 */
export function NavProjectsMenu({ projects }: { projects: NavProject[] }) {
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrap = useRef<HTMLDivElement>(null);

  const cancelClose = () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
  };
  const scheduleClose = () => {
    cancelClose();
    closeTimer.current = setTimeout(() => setOpen(false), 140);
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onClick = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  return (
    <div
      ref={wrap}
      className="relative"
      onMouseEnter={() => {
        cancelClose();
        setOpen(true);
      }}
      onMouseLeave={scheduleClose}
    >
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 rounded-full px-3 py-2 text-sm text-[var(--ink-muted)] transition-colors hover:text-[var(--ink)]"
      >
        Projects
        <svg
          width="11"
          height="11"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden
          className={`transition-transform ${open ? "rotate-180" : ""}`}
        >
          <path d="m6 9 6 6 6-6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute left-1/2 top-full z-50 mt-2 w-72 -translate-x-1/2 overflow-hidden rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--glass)] p-1.5 shadow-[var(--shadow-lg,0_20px_60px_rgba(0,0,0,0.5))] backdrop-blur-xl"
        >
          {projects.map((p) => (
            <Link
              key={p.slug}
              href={`/projects/${p.slug}`}
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] px-3 py-2.5 transition-colors hover:bg-[var(--surface-2)]"
            >
              <span className="flex items-center gap-2.5">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: p.accent || "var(--accent)" }}
                  aria-hidden
                />
                <span className="flex flex-col">
                  <span className="text-sm font-medium text-[var(--ink)]">{p.name}</span>
                  <span className="text-xs text-[var(--ink-dim)]">{p.sport}</span>
                </span>
              </span>
              <MaturityBadge maturity={p.maturity} />
            </Link>
          ))}
          <Link
            href="/projects"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="mt-1 block rounded-[var(--radius-md)] border-t border-[var(--line)] px-3 py-2.5 text-sm font-medium text-[var(--accent-text)] transition-colors hover:bg-[var(--surface-2)]"
          >
            All projects →
          </Link>
        </div>
      )}
    </div>
  );
}
