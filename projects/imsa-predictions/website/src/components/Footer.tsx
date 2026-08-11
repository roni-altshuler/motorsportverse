import Link from "next/link";

import Wordmark from "@/components/Wordmark";

const NEWS_OUTLETS = [
  { name: "IMSA.com", url: "https://www.imsa.com/" },
  { name: "Sportscar365", url: "https://sportscar365.com/" },
  { name: "Autosport · IMSA", url: "https://www.autosport.com/imsa/" },
  { name: "Motorsport.com · IMSA", url: "https://www.motorsport.com/imsa/" },
  { name: "RACER · Sports Cars", url: "https://racer.com/imsa/" },
];

const ECOSYSTEM = [
  { name: "MotorsportVerse", url: "https://motorsportverse.org" },
  { name: "RaceIQ F1", url: "https://motorsportverse.org/projects/f1-predictions" },
  { name: "motorsport-core", url: "https://motorsportverse.org/projects/motorsport-core" },
];

export default function Footer() {
  return (
    <footer
      className="mt-24 border-t"
      style={{ borderColor: "var(--hairline)", background: "var(--canvas)" }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-12">
          <div>
            <Wordmark className="mb-4 h-10 w-auto" />
            <p className="body-sm" style={{ color: "var(--muted)" }}>
              Race-by-race and championship forecasts for the IMSA WeatherTech SportsCar Championship — a
              win and podium probability for every car in GTP, LMP2, GTD PRO and GTD, plus each
              class&rsquo;s title fight. A MotorsportVerse project on the shared motorsport-core.
            </p>
          </div>

          <div>
            <h4 className="eyebrow mb-4">Navigation</h4>
            <div className="flex flex-col gap-3">
              {[
                { href: "/", label: "Home" },
                { href: "/calendar", label: "Season Calendar" },
                { href: "/standings", label: "Championships" },
                { href: "/predictions", label: "Next-Round Forecast" },
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
            <h4 className="eyebrow mb-4">IMSA News</h4>
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

        <div
          className="mt-16 pt-6 flex flex-col items-center gap-6 hairline-divider-top"
          style={{ color: "var(--muted-soft)" }}
        >
          <div className="flex flex-col sm:flex-row items-center justify-between w-full gap-3">
            <span className="body-sm">
              &copy; 2026 RaceIQ IMSA — a MotorsportVerse project. Forecasts are model estimates, not
              betting advice. Not affiliated with IMSA, IMSA WeatherTech, or any team.
            </span>
            <a
              href="https://motorsportverse.org/projects/imsa-predictions"
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
