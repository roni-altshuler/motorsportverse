import Image from "next/image";
import Link from "next/link";

import { NavProjectsMenu } from "@/components/NavProjectsMenu";
import { PaletteButton } from "@/components/PaletteButton";
import { asset } from "@/lib/asset";
import { getProjects } from "@/lib/registry";

const LINKS = [
  { href: "/docs", label: "Docs" },
  { href: "/contribute", label: "Contribute" },
];

// Surface the real (shipping) ecosystem projects in the header dropdown so
// nothing nav-worthy lives only in the footer.
function navProjects() {
  const all = getProjects();
  const shipping = all.filter((p) => p.maturity === "production" || p.maturity === "experimental");
  return (shipping.length ? shipping : all.slice(0, 4)).map((p) => ({
    slug: p.slug,
    name: p.name,
    sport: p.sport,
    maturity: p.maturity,
    accent: p.accent,
  }));
}

export function Navbar() {
  const projects = navProjects();
  return (
    <header className="sticky top-0 z-50 border-b border-[var(--line)] bg-[var(--glass)] backdrop-blur-2xl backdrop-saturate-[170%] shadow-[inset_0_1px_0_var(--glass-spec-highlight)]">
      <nav className="shell flex items-center justify-between py-3">
        <Link href="/" className="group flex items-center gap-2.5">
          <Image
            src={asset("/brand/motorsportverse-mark.png")}
            alt="MotorsportVerse"
            width={28}
            height={28}
            className="h-7 w-7"
            priority
          />
          <span className="font-display text-base font-semibold tracking-tight text-[var(--ink)]">
            Motorsport<span className="text-[var(--accent-text)]">Verse</span>
          </span>
        </Link>

        <div className="flex items-center gap-1 sm:gap-1.5">
          <div className="mr-1 hidden items-center sm:flex">
            <NavProjectsMenu projects={projects} />
            {LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className="rounded-full px-3 py-2 text-sm text-[var(--ink-muted)] transition-colors hover:text-[var(--ink)]"
              >
                {l.label}
              </Link>
            ))}
          </div>
          <PaletteButton />
          <a
            href="https://github.com/roni-altshuler/motorsportverse"
            target="_blank"
            rel="noreferrer"
            aria-label="GitHub organization"
            className="ml-0.5 hidden rounded-[var(--radius-pill)] border border-[var(--line)] p-2 text-[var(--ink-muted)] transition-colors hover:border-[var(--line-strong)] hover:text-[var(--ink)] sm:inline-flex"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
              <path d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.49 0-.24-.01-.88-.01-1.73-2.78.62-3.37-1.37-3.37-1.37-.46-1.18-1.11-1.49-1.11-1.49-.91-.64.07-.62.07-.62 1 .07 1.53 1.06 1.53 1.06.89 1.57 2.34 1.12 2.91.85.09-.66.35-1.12.63-1.38-2.22-.26-4.56-1.14-4.56-5.06 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.3.1-2.71 0 0 .84-.27 2.75 1.05a9.3 9.3 0 0 1 5 0c1.91-1.32 2.75-1.05 2.75-1.05.55 1.41.2 2.45.1 2.71.64.72 1.03 1.63 1.03 2.75 0 3.93-2.35 4.8-4.58 5.05.36.32.68.94.68 1.9 0 1.37-.01 2.47-.01 2.81 0 .27.18.6.69.49A10.26 10.26 0 0 0 22 12.25C22 6.58 17.52 2 12 2Z" />
            </svg>
          </a>
        </div>
      </nav>
    </header>
  );
}
