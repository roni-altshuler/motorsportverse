import Link from "next/link";

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

const ECOSYSTEM = [
  { name: "MotorsportVerse", url: "https://motorsportverse.org" },
  { name: "RaceIQ F1", url: "https://motorsportverse.org/projects/f1-predictions" },
  { name: "RaceIQ Indy", url: "https://motorsportverse.org/projects/indycar-predictions" },
];

export default function Footer() {
  return (
    <footer
      className="mt-24 border-t"
      style={{ borderColor: "var(--hairline)", background: "var(--canvas)" }}
    >
      <div className="prism-hairline" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-12">
          <div>
            <img
              src={`${BASE_PATH}/brand/logo.svg`}
              alt="Prism Cup Karting League"
              width={340}
              height={80}
              className="mb-4 h-10 w-auto"
            />
            <p className="body-sm" style={{ color: "var(--muted)" }}>
              Twelve original racers, eight fantasy circuits, four cups — and a
              race simulator that runs right in your browser. A MotorsportVerse
              fun project with fully synthetic data.
            </p>
          </div>

          <div>
            <h4 className="eyebrow mb-4">Navigation</h4>
            <div className="flex flex-col gap-3">
              {[
                { href: "/", label: "Home" },
                { href: "/racers", label: "The Racers" },
                { href: "/tracks", label: "The Tracks" },
                { href: "/cups", label: "Cups & Standings" },
                { href: "/#race-night", label: "Race Night Simulator" },
              ].map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="body-sm transition-colors hover:text-[color:var(--ink)]"
                  style={{ color: "var(--muted)" }}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>

          <div>
            <h4 className="eyebrow mb-4">Ecosystem</h4>
            <div className="flex flex-col gap-3">
              {ECOSYSTEM.map((ch) => (
                <a
                  key={ch.name}
                  href={ch.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="body-sm transition-colors hover:text-[color:var(--ink)]"
                  style={{ color: "var(--muted)" }}
                >
                  {ch.name}
                </a>
              ))}
            </div>
          </div>
        </div>

        <div
          className="mt-16 pt-6 flex flex-col items-center gap-4 hairline-divider-top text-center"
          style={{ color: "var(--muted-soft)" }}
        >
          <p className="body-sm" style={{ color: "var(--muted)" }}>
            A fan-made fictional league. All characters, items, tracks and
            results are simulated and original. Not affiliated with any video
            game company.
          </p>
          <span className="body-sm">
            &copy; 2026 Prism Cup Karting — a MotorsportVerse fun project.
          </span>
        </div>
      </div>
    </footer>
  );
}
