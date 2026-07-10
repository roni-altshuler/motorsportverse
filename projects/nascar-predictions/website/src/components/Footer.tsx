import Link from "next/link";

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

const NEWS_OUTLETS = [
  { name: "NASCAR.com", url: "https://www.nascar.com/" },
  { name: "Autosport · NASCAR", url: "https://www.autosport.com/nascar/" },
  { name: "Motorsport.com · NASCAR", url: "https://www.motorsport.com/nascar-cup/" },
  { name: "The Race", url: "https://www.the-race.com/nascar/" },
];

const ECOSYSTEM = [
  { name: "MotorsportVerse", url: "https://motorsportverse.org" },
  { name: "RaceIQ F1", url: "https://motorsportverse.org/projects/f1-predictions" },
  { name: "motorsport-core", url: "https://motorsportverse.org/projects/motorsport-core" },
];

export default function Footer() {
  return (
    <footer className="mt-24 border-t" style={{ borderColor: "var(--hairline)", background: "var(--canvas)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-12">
          <div>
            <img
              src={`${BASE_PATH}/brand/raceiq-nascar-lockup.svg`}
              alt="RaceIQ NASCAR"
              width={387}
              height={104}
              className="mb-4 h-10 w-auto"
            />
            <p className="body-sm" style={{ color: "var(--muted)" }}>
              Race and championship forecasts for the NASCAR Cup Series — every points race
              from Daytona to the Chase finale, stage racing and playoff odds included.
              A MotorsportVerse project on the shared motorsport-core.
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
            <h4 className="eyebrow mb-4">NASCAR News</h4>
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
              &copy; 2026 RaceIQ NASCAR — a MotorsportVerse project. Forecasts are model
              estimates, not betting advice. Not affiliated with NASCAR.
            </span>
            <a
              href="https://motorsportverse.org/projects/nascar-predictions"
              target="_blank"
              rel="noopener noreferrer"
              className="body-sm transition-colors hover:text-[color:var(--ink)]"
              style={{ color: "var(--muted)" }}
            >
              About this project →
            </a>
          </div>
          <img
            src={`${BASE_PATH}/brand/raceiq-nascar-lockup.svg`}
            alt="RaceIQ NASCAR"
            width={387}
            height={104}
            className="h-8 w-auto opacity-80"
          />
        </div>
      </div>
    </footer>
  );
}
