"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Flag, Menu, X } from "lucide-react";

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/racers", label: "Racers" },
  { href: "/tracks", label: "Tracks" },
  { href: "/cups", label: "Cups" },
];

export default function Navbar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <nav
      className="sticky top-0 z-50"
      aria-label="Primary"
      style={{
        background: "rgba(0, 0, 0, 0.85)",
        backdropFilter: "blur(10px)",
        borderBottom: "1px solid var(--hairline)",
      }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center h-14 gap-2 sm:gap-4">
          <button
            onClick={() => setMobileOpen((o) => !o)}
            className="md:hidden inline-flex items-center justify-center w-9 h-9 -ml-1.5"
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
          >
            {mobileOpen ? (
              <X className="w-5 h-5 text-[color:var(--ink)]" />
            ) : (
              <Menu className="w-5 h-5 text-[color:var(--ink)]" />
            )}
          </button>

          <Link href="/" className="flex items-center shrink-0" aria-label="Prism Cup home">
            <img
              src={`${BASE_PATH}/brand/logo.svg`}
              alt="Prism Cup Karting League"
              width={340}
              height={80}
              className="h-9 w-auto"
            />
          </Link>

          <div className="hidden md:flex items-center gap-0 ml-4">
            {LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                aria-current={isActive(link.href) ? "page" : undefined}
                className={`nav-link-text px-3 lg:px-4 py-2 inline-flex items-center gap-1.5 transition-colors ${
                  isActive(link.href)
                    ? "text-[color:var(--ink)]"
                    : "text-[color:var(--muted)] hover:text-[color:var(--ink)]"
                }`}
              >
                {link.label}
              </Link>
            ))}
          </div>

          <div className="flex-1" />

          <Link
            href="/#race-night"
            className="hidden sm:inline-flex items-center gap-2 button-label h-9 px-4 rounded-full text-[12px] transition-colors"
            style={{ background: "var(--accent-prism)", color: "var(--accent-ink)" }}
          >
            <Flag className="w-3.5 h-3.5" />
            Race Night
          </Link>
        </div>
      </div>

      {mobileOpen && (
        <div className="md:hidden border-t" style={{ borderColor: "var(--hairline)", background: "var(--canvas)" }}>
          <div className="px-4 py-2 flex flex-col">
            {LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                aria-current={isActive(link.href) ? "page" : undefined}
                className={`nav-link-text px-2 py-3.5 border-b transition-colors ${
                  isActive(link.href) ? "text-[color:var(--ink)]" : "text-[color:var(--muted)]"
                }`}
                style={{ borderColor: "var(--hairline)" }}
              >
                {link.label}
              </Link>
            ))}
            <Link
              href="/#race-night"
              onClick={() => setMobileOpen(false)}
              className="button-label inline-flex items-center justify-center gap-2 h-10 my-3 rounded-full text-[12px]"
              style={{ background: "var(--accent-prism)", color: "var(--accent-ink)" }}
            >
              <Flag className="w-3.5 h-3.5" />
              Race Night
            </Link>
          </div>
        </div>
      )}
    </nav>
  );
}
