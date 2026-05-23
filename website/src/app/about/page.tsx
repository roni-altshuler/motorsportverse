import Link from "next/link";
import { DEFAULT_SEASON_YEAR } from "@/lib/season";

const ACTIVE_SEASON_YEAR = String(DEFAULT_SEASON_YEAR);

export default function AboutPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 section-bugatti">
      <div className="text-center mb-20">
        <p className="eyebrow mb-4">About</p>
        <h1 className="display-xl mb-6">The {ACTIVE_SEASON_YEAR} Predictions Board</h1>
        <p className="body-md max-w-2xl mx-auto">
          A self-updating dashboard for the {ACTIVE_SEASON_YEAR} Formula 1 season:
          per-Grand-Prix forecasts, championship standings, head-to-head matchups,
          and post-race accuracy — all in one place.
        </p>
      </div>

      <div className="grid gap-0 sm:grid-cols-2 mb-16">
        <div className="row-spec sm:border-b-0 sm:pr-8 sm:border-r border-[color:var(--hairline)]">
          <p className="eyebrow mb-3">What you get</p>
          <ul className="body-md space-y-3 list-none pl-0">
            <li>Race-by-race winner and podium forecasts</li>
            <li>Per-driver win and podium probabilities</li>
            <li>Live championship standings</li>
            <li>Pre-race deep dives with telemetry context</li>
            <li>Post-race accuracy comparison once results land</li>
          </ul>
        </div>
        <div className="row-spec sm:border-b-0 sm:pl-8">
          <p className="eyebrow mb-3">Cadence</p>
          <ul className="body-md space-y-3 list-none pl-0">
            <li>Forecasts refresh as each weekend approaches</li>
            <li>Standings sync from official feeds after each round</li>
            <li>Visualisations regenerate post-qualifying</li>
            <li>Accuracy is reported as soon as classified results are available</li>
          </ul>
        </div>
      </div>

      <section className="hairline-divider-top pt-12 mb-16">
        <p className="eyebrow mb-4">How to use this site</p>
        <h2 className="display-md mb-8">Navigation</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
          <div>
            <p className="title-md mb-2">
              <Link href="/" className="link-bugatti">Home</Link>
            </p>
            <p className="body-sm text-[color:var(--muted)]">
              The next race up, the predicted podium, and championship snapshot.
            </p>
          </div>
          <div>
            <p className="title-md mb-2">
              <Link href="/calendar" className="link-bugatti">Calendar</Link>
            </p>
            <p className="body-sm text-[color:var(--muted)]">
              All {ACTIVE_SEASON_YEAR} Grands Prix at a glance with status per round.
            </p>
          </div>
          <div>
            <p className="title-md mb-2">
              <Link href="/standings" className="link-bugatti">Standings</Link>
            </p>
            <p className="body-sm text-[color:var(--muted)]">
              Drivers and constructors championships, updated through the latest round.
            </p>
          </div>
        </div>
      </section>

      <section className="hairline-divider-top pt-12">
        <p className="eyebrow mb-4" style={{ color: "var(--warning)" }}>Disclaimer</p>
        <p className="body-md text-[color:var(--body)]">
          This site is a personal project published for educational and entertainment
          purposes. Forecasts are model outputs and should not be used for betting or
          any form of gambling. The project is not affiliated with, endorsed by, or
          connected to Formula 1, the FIA, or any constructor.
        </p>
      </section>
    </div>
  );
}
