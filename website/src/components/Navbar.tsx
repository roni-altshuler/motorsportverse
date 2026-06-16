import Image from "next/image";
import Link from "next/link";

const LINKS = [
  { href: "/projects", label: "Projects" },
  { href: "/docs", label: "Docs" },
  { href: "/contribute", label: "Contribute" },
];

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-[var(--hairline)] bg-[color-mix(in_srgb,var(--canvas)_85%,transparent)] backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2.5">
          <Image
            src="/brand/motorsportverse-mark.png"
            alt="MotorsportVerse"
            width={28}
            height={28}
            className="h-7 w-7"
            priority
          />
          <span className="text-sm font-semibold tracking-tight text-[var(--ink)]">
            Motorsport<span style={{ color: "var(--accent)" }}>Verse</span>
          </span>
        </Link>
        <div className="flex items-center gap-6 text-sm text-[var(--ink-muted)]">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="hover:text-[var(--ink)]">
              {l.label}
            </Link>
          ))}
          <a
            href="https://github.com/motorsportverse"
            className="rounded-full border border-[var(--hairline-strong)] px-3 py-1.5 text-xs text-[var(--ink)] hover:border-[var(--accent)]"
          >
            GitHub
          </a>
        </div>
      </nav>
    </header>
  );
}
