import Link from "next/link";
import { DEFAULT_SEASON_YEAR } from "@/lib/season";

const NEWS_OUTLETS = [
  { name: "Formula1.com", url: "https://www.formula1.com/en/latest" },
  { name: "Autosport", url: "https://www.autosport.com/f1/" },
  { name: "Motorsport.com", url: "https://www.motorsport.com/f1/" },
  { name: "The Race", url: "https://www.the-race.com/formula-1/" },
  { name: "RaceFans", url: "https://www.racefans.net/" },
];

const YOUTUBE_CHANNELS = [
  { name: "F1 Official", url: "https://www.youtube.com/@Formula1" },
  { name: "F1 TV", url: "https://www.youtube.com/@F1TV" },
  { name: "Sky Sports F1", url: "https://www.youtube.com/@SkySportsF1" },
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
            <p className="wordmark mb-4">F1 {DEFAULT_SEASON_YEAR} PREDICTIONS</p>
            <p className="body-sm" style={{ color: "var(--muted)" }}>
              Race-by-race classification forecasts, championship standings, pit strategy
              and weekend telemetry — published every Grand Prix weekend.
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
            <h4 className="eyebrow mb-4">F1 News</h4>
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
            <h4 className="eyebrow mb-4">YouTube</h4>
            <div className="flex flex-col gap-3">
              {YOUTUBE_CHANNELS.map((ch) => (
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
              &copy; {DEFAULT_SEASON_YEAR} F1 Predictions. Not affiliated with Formula 1.
            </span>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="body-sm transition-colors hover:text-[color:var(--ink)]"
              style={{ color: "var(--muted)" }}
            >
              GitHub
            </a>
          </div>
          <p className="wordmark" style={{ color: "var(--body)" }}>F1 PREDICTIONS</p>
        </div>
      </div>
    </footer>
  );
}
