import Link from "next/link";
import { DEFAULT_SEASON_YEAR } from "@/lib/season";

const ACTIVE_SEASON_YEAR = String(DEFAULT_SEASON_YEAR);

export default function AboutPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
      <div className="text-center mb-12">
        <p className="hud-kicker mb-2">About</p>
        <h1 className="text-4xl sm:text-5xl font-black tracking-tighter mb-3">
          The {ACTIVE_SEASON_YEAR} Predictions Board
        </h1>
        <p className="text-base text-[color:var(--text-muted)] max-w-2xl mx-auto">
          A self-updating dashboard for the {ACTIVE_SEASON_YEAR} Formula 1 season:
          per-Grand-Prix forecasts, championship standings, head-to-head matchups,
          and post-race accuracy — all in one place.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 mb-10">
        <div className="hud-frame p-5">
          <p className="hud-kicker mb-2">What you get</p>
          <ul className="space-y-2 text-sm text-[color:var(--text-secondary)]">
            <li>· Race-by-race winner and podium forecasts</li>
            <li>· Per-driver win and podium probabilities</li>
            <li>· Live championship standings</li>
            <li>· Pre-race deep dives with telemetry context</li>
            <li>· Post-race accuracy comparison once results land</li>
          </ul>
        </div>
        <div className="hud-frame p-5">
          <p className="hud-kicker mb-2">Cadence</p>
          <ul className="space-y-2 text-sm text-[color:var(--text-secondary)]">
            <li>· Forecasts refresh as each weekend approaches</li>
            <li>· Standings sync from official feeds after each round</li>
            <li>· Visualisations regenerate post-qualifying</li>
            <li>· Accuracy is reported as soon as classified results are available</li>
          </ul>
        </div>
      </div>

      <section className="hud-frame p-6 sm:p-8 mb-6">
        <p className="hud-kicker mb-2">How to use this site</p>
        <h2 className="text-xl font-black tracking-tight mb-3">Navigation</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          <div>
            <p className="font-bold mb-1">
              <Link href="/" className="hover:text-[color:var(--accent-live)]">Home</Link>
            </p>
            <p className="text-[color:var(--text-muted)]">
              The next race up, the predicted podium, and championship snapshot.
            </p>
          </div>
          <div>
            <p className="font-bold mb-1">
              <Link href="/calendar" className="hover:text-[color:var(--accent-live)]">Calendar</Link>
            </p>
            <p className="text-[color:var(--text-muted)]">
              All {ACTIVE_SEASON_YEAR} Grands Prix at a glance with status per round.
            </p>
          </div>
          <div>
            <p className="font-bold mb-1">
              <Link href="/standings" className="hover:text-[color:var(--accent-live)]">Standings</Link>
            </p>
            <p className="text-[color:var(--text-muted)]">
              Drivers and constructors championships, updated through the latest round.
            </p>
          </div>
        </div>
      </section>

      <section
        className="hud-frame p-6 sm:p-8"
        style={{ borderColor: "color-mix(in srgb, var(--hud-yellow) 30%, var(--border))" }}
      >
        <p className="hud-kicker mb-2" style={{ color: "var(--hud-yellow)" }}>Disclaimer</p>
        <p className="text-sm leading-relaxed text-[color:var(--text-secondary)]">
          This site is a personal project published for educational and entertainment
          purposes. Forecasts are model outputs and should not be used for betting or
          any form of gambling. The project is not affiliated with, endorsed by, or
          connected to Formula 1, the FIA, or any constructor.
        </p>
      </section>
    </div>
  );
}
