import Image from "next/image";
import Link from "next/link";

import { asset } from "@/lib/asset";

const LINKS = [
  { href: "/projects", label: "Projects" },
  { href: "/docs", label: "Docs" },
  { href: "/contribute", label: "Contribute" },
];

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-[var(--hairline)]/70 bg-[var(--canvas)]/70 backdrop-blur-xl">
      <nav className="shell flex items-center justify-between py-3.5">
        <Link href="/" className="group flex items-center gap-2.5">
          <Image
            src={asset("/brand/motorsportverse-mark.png")}
            alt="MotorsportVerse"
            width={30}
            height={30}
            className="h-[30px] w-[30px]"
            priority
          />
          <span className="font-display text-base font-semibold tracking-tight text-[var(--ink)]">
            Motorsport<span className="text-[var(--accent-bright)]">Verse</span>
          </span>
        </Link>

        <div className="flex items-center gap-1 sm:gap-2">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="rounded-full px-3 py-2 text-sm text-[var(--ink-muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--ink)]"
            >
              {l.label}
            </Link>
          ))}
          <a
            href="https://github.com/motorsportverse"
            className="btn-ghost ml-1 hidden px-4 py-2 text-xs font-medium sm:inline-block"
          >
            GitHub
          </a>
        </div>
      </nav>
    </header>
  );
}
