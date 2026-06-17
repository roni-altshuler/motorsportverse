import Image from "next/image";
import Link from "next/link";

import { asset } from "@/lib/asset";

export function Footer() {
  return (
    <footer className="relative mt-24 border-t border-[var(--line)] bg-[var(--canvas-deep)]">
      <div className="bg-grid bg-grid-fade pointer-events-none absolute inset-0 opacity-[0.35]" />
      <div className="shell relative grid gap-10 py-16 sm:grid-cols-[1.6fr_1fr_1fr]">
        <div>
          <Image
            src={asset("/brand/motorsportverse-logo.png")}
            alt="MotorsportVerse"
            width={1217}
            height={414}
            className="h-auto w-44"
          />
          <p className="mt-5 max-w-xs text-sm leading-relaxed text-[var(--ink-dim)]">
            An open-source motorsport AI ecosystem — shared ML &amp; data infrastructure powering a
            family of RaceIQ prediction projects.
          </p>
          <div className="mt-5 inline-flex items-center gap-2 text-xs text-[var(--ink-dim)]">
            <span className="live-dot" />
            <span className="font-mono tracking-wide">systems operational</span>
          </div>
        </div>
        <FooterCol
          title="Explore"
          links={[
            { href: "/projects", label: "Projects" },
            { href: "/docs", label: "Documentation" },
            { href: "/contribute", label: "Contribute" },
          ]}
        />
        <FooterCol
          title="Ecosystem"
          links={[
            { href: "/projects/f1-predictions", label: "RaceIQ F1" },
            { href: "/projects/f2-predictions", label: "RaceIQ F2" },
            { href: "https://github.com/motorsportverse", label: "GitHub", external: true },
          ]}
        />
      </div>
      <div className="relative border-t border-[var(--line)]">
        <div className="shell flex flex-col gap-2 py-6 text-xs text-[var(--ink-dim)] sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} MotorsportVerse · MIT licensed</p>
          <p>Forecasts are model estimates, not betting advice.</p>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({
  title,
  links,
}: {
  title: string;
  links: { href: string; label: string; external?: boolean }[];
}) {
  return (
    <div>
      <p className="mono-label mb-3">{title}</p>
      <ul className="space-y-2.5 text-sm text-[var(--ink-muted)]">
        {links.map((l) =>
          l.external ? (
            <li key={l.href}>
              <a
                href={l.href}
                target="_blank"
                rel="noreferrer"
                className="transition-colors hover:text-[var(--ink)]"
              >
                {l.label}
              </a>
            </li>
          ) : (
            <li key={l.href}>
              <Link href={l.href} className="transition-colors hover:text-[var(--ink)]">
                {l.label}
              </Link>
            </li>
          ),
        )}
      </ul>
    </div>
  );
}
