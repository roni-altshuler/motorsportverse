import Image from "next/image";
import Link from "next/link";

const BASE = process.env.NEXT_PUBLIC_BASE_PATH || "";

const LINKS = [
  { href: "/", label: "Race Day" },
  { href: "/garage/", label: "The Garage" },
  { href: "/season/", label: "The Season" },
];

export default function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-[color:var(--hairline)] bg-[color:var(--canvas)]/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-3" aria-label="Chrome Valley Racing League home">
          <Image
            src={`${BASE}/brand/logo.svg`}
            alt="Chrome Valley Racing League"
            width={210}
            height={49}
            priority
          />
        </Link>
        <nav aria-label="Primary" className="flex items-center gap-1 sm:gap-2">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="nav-link-text px-2 py-2 text-[color:var(--muted)] transition-colors hover:text-[color:var(--ink)] sm:px-3"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
