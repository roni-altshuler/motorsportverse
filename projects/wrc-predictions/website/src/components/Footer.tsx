import Link from "next/link";

const NEWS_OUTLETS = [
  { name: "WRC.com", url: "https://www.wrc.com/" },
  { name: "Autosport · WRC", url: "https://www.autosport.com/wrc/" },
  { name: "Motorsport.com · WRC", url: "https://www.motorsport.com/wrc/" },
  { name: "DirtFish", url: "https://dirtfish.com/" },
  { name: "The Race · Rally", url: "https://www.the-race.com/rallying/" },
];

const ECOSYSTEM = [
  { name: "MotorsportVerse", url: "https://motorsportverse.org" },
  { name: "RaceIQ F1", url: "https://motorsportverse.org/projects/f1-predictions" },
  { name: "motorsport-core", url: "https://motorsportverse.org/projects/motorsport-core" },
];

/** Inline "RaceIQ WRC" wordmark — SVG so the accent tracks the live token. */
function Wordmark({ className, opacity }: { className?: string; opacity?: number }) {
  return (
    <svg
      viewBox="0 0 300 80"
      className={className}
      role="img"
      aria-label="RaceIQ WRC"
      style={opacity != null ? { opacity } : undefined}
    >
      <g transform="translate(4,22)" fill="var(--accent-f1-red)">
        <path d="M0 0 L15.12 0 L25.92 18 L15.12 36 L0 36 L10.8 18 Z" />
        <path d="M14.4 0 L29.52 0 L40.32 18 L29.52 36 L14.4 36 L25.2 18 Z" opacity="0.55" />
      </g>
      <g fontFamily="'Saira Condensed','Arial Narrow',system-ui,sans-serif" fontWeight={700}>
        <text x="58" y="46" fontSize="34" letterSpacing="1.5" fill="#f4f5f7">
          Race
          <tspan fill="var(--accent-f1-red-bright)">IQ</tspan>
        </text>
        <text x="60" y="66" fontSize="15" letterSpacing="6" fill="var(--accent-f1-red-bright)">
          WRC
        </text>
      </g>
    </svg>
  );
}

export default function Footer() {
  return (
    <footer className="mt-24 border-t" style={{ borderColor: "var(--hairline)", background: "var(--canvas)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-12">
          <div>
            <Wordmark className="mb-4 h-10 w-auto" />
            <p className="body-sm" style={{ color: "var(--muted)" }}>
              Rally and championship forecasts for the World Rally Championship — a win and podium
              probability for every crew across gravel, tarmac and snow, plus the drivers&rsquo; and
              manufacturers&rsquo; title fights. A MotorsportVerse project on the shared
              motorsport-core.
            </p>
          </div>

          <div>
            <h4 className="eyebrow mb-4">Navigation</h4>
            <div className="flex flex-col gap-3">
              {[
                { href: "/", label: "Home" },
                { href: "/calendar", label: "Season Calendar" },
                { href: "/standings", label: "Championships" },
                { href: "/accuracy", label: "Accuracy Dashboard" },
                { href: "/about", label: "About the Model" },
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
            <h4 className="eyebrow mb-4">WRC News</h4>
            <div className="flex flex-col gap-3">
              {NEWS_OUTLETS.map((outlet) => (
                <a
                  key={outlet.name}
                  href={outlet.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="body-sm transition-colors hover:text-[color:var(--ink)]"
                  style={{ color: "var(--muted)" }}
                >
                  {outlet.name}
                </a>
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

        <div className="mt-16 pt-6 flex flex-col items-center gap-6 hairline-divider-top" style={{ color: "var(--muted-soft)" }}>
          <div className="flex flex-col sm:flex-row items-center justify-between w-full gap-3">
            <span className="body-sm">
              &copy; 2026 RaceIQ WRC — a MotorsportVerse project. Forecasts are model estimates, not
              betting advice. Not affiliated with the WRC, FIA, WRC Promoter, or any team.
            </span>
            <a
              href="https://motorsportverse.org/projects/wrc-predictions"
              target="_blank"
              rel="noopener noreferrer"
              className="body-sm transition-colors hover:text-[color:var(--ink)]"
              style={{ color: "var(--muted)" }}
            >
              About this project →
            </a>
          </div>
          <Wordmark className="h-8 w-auto" opacity={0.8} />
        </div>
      </div>
    </footer>
  );
}
