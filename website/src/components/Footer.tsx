import Image from "next/image";
import Link from "next/link";

import { asset } from "@/lib/asset";

export function Footer() {
  return (
    <footer className="hairline-top mt-10 bg-[var(--canvas-deep)]">
      <div className="shell grid gap-8 py-14 sm:grid-cols-[1.5fr_1fr_1fr]">
        <div>
          <Image
            src={asset("/brand/motorsportverse-logo.png")}
            alt="MotorsportVerse"
            width={1217}
            height={414}
            className="h-auto w-44"
          />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-[var(--ink-dim)]">
            An open-source motorsport AI ecosystem — shared ML &amp; data infrastructure powering a
            family of RaceIQ prediction projects.
          </p>
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
            { href: "https://github.com/motorsportverse", label: "GitHub" },
          ]}
        />
      </div>
      <div className="hairline-top">
        <div className="shell flex flex-col gap-2 py-6 text-xs text-[var(--ink-dim)] sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} MotorsportVerse · MIT licensed</p>
          <p>Forecasts are model estimates, not betting advice.</p>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: { href: string; label: string }[] }) {
  return (
    <div>
      <p className="eyebrow mb-3 text-[var(--ink-dim)]">{title}</p>
      <ul className="space-y-2 text-sm text-[var(--ink-muted)]">
        {links.map((l) => (
          <li key={l.href}>
            <Link href={l.href} className="transition-colors hover:text-[var(--ink)]">
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
