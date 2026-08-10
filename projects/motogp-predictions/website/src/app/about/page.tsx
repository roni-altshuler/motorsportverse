import type { Metadata } from "next";
import Link from "next/link";

import { AnimatedGradientText } from "@/components/magicui/animated-gradient-text";
import { MagicCard } from "@/components/magicui/magic-card";
import HowItWorksDiagram from "@/components/marketing/HowItWorksDiagram";
import { getMotogpData } from "@/lib/motogpData";

export const metadata: Metadata = {
  title: "About the Model — RaceIQ MotoGP",
  description:
    "How RaceIQ MotoGP forecasts the premier class of motorcycle Grand Prix racing — a Saturday sprint and a Sunday Grand Prix each round, and the rider and manufacturer title fights.",
};

// MotoGP red identity (mirrors the F1 flagship's gradient treatment).
const MOTOGP_FROM = "#CC0000";
const MOTOGP_TO = "#FF6B6B";

const NAV = [
  { href: "/", title: "Home", copy: "The next round up, the predicted podium, and a championship snapshot." },
  { href: "/calendar", title: "Calendar", copy: "Every round at a glance — sprint and Grand Prix dates, status per round." },
  { href: "/standings", title: "Standings", copy: "Riders and manufacturers, updated through the latest round, with title projections." },
];

export default function AboutPage() {
  const data = getMotogpData();

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-16">
      {/* ── Hero ── */}
      <div className="text-center mb-20">
        <p className="eyebrow mb-4">MotoGP · {data.season}</p>
        <h1 className="display-xl mb-6 [font-weight:700]">
          The {data.season}{" "}
          <AnimatedGradientText speed={10} colorFrom={MOTOGP_FROM} colorTo={MOTOGP_TO}>
            Predictions Board
          </AnimatedGradientText>
        </h1>
        <p className="body-md max-w-2xl mx-auto text-[color:var(--ink-muted)]">
          RaceIQ&nbsp;MotoGP forecasts every round of the premier class of motorcycle Grand Prix
          racing — both the Saturday sprint and the Sunday Grand Prix — and projects the rider and
          manufacturer title fights to the end of the season. It&rsquo;s built on the same
          MotorsportVerse core that powers RaceIQ&nbsp;F1, tuned for what makes MotoGP different.
        </p>
      </div>

      {/* ── How it works — shared AnimatedBeam diagram ── */}
      <section className="mb-20" aria-labelledby="about-how-heading">
        <div className="text-center mb-10">
          <p className="eyebrow mb-2">How it works</p>
          <h2 id="about-how-heading" className="display-md">
            Live data → Model → Forecast
          </h2>
        </div>
        <HowItWorksDiagram variant="beam" />
      </section>

      {/* ── The MotoGP-specific story ── */}
      <Section title="Rider form is the strongest signal">
        MotoGP fields a deep grid of world-class riders on machinery from five manufacturers — Ducati,
        Aprilia, KTM, Yamaha and Honda. The forecast leans hardest on a rider&rsquo;s own recent form,
        qualifying position and head-to-head record, then reads it against the field, so the numbers
        follow who is actually fast right now rather than a name or a badge.
      </Section>

      <Section title="Two races a weekend, one grid">
        Each round runs a shorter Saturday sprint and the full Sunday Grand Prix, and both line up off
        the same qualifying grid — there is no reverse grid in MotoGP. RaceIQ models the two races
        separately, because half distance and full distance reward different things, and the sprint&rsquo;s
        smaller points haul shifts the risk each rider is willing to take.
      </Section>

      <Section title="What the numbers mean">
        For each race you get a win and podium probability per rider, an expected finishing range
        rather than a single guess, and a confidence read. For the season, the championship view shows
        each rider&rsquo;s title odds and projected points — and who is still mathematically alive for
        the crown — alongside the manufacturer standings.
      </Section>

      <Section title="Honest about accuracy">
        Every forecast is made using only what was known before the round — no peeking at the result —
        and scored against what actually happened on the{" "}
        <Link href="/accuracy" className="text-[var(--accent)] underline-offset-4 hover:underline">
          accuracy dashboard
        </Link>
        . Probability calibration stays switched off until enough real-feed rounds are banked, so the
        site never claims precision it hasn&rsquo;t earned.
      </Section>

      {/* ── Navigation guide (MagicCard grid) ── */}
      <section className="hairline-divider-top pt-12 mt-16 mb-16">
        <p className="eyebrow mb-4">How to use this site</p>
        <h2 className="display-md mb-8">Navigation</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {NAV.map((n) => (
            <MagicCard
              key={n.href}
              gradientFrom={MOTOGP_FROM}
              gradientTo={MOTOGP_TO}
              gradientColor="#2a0d0d"
              className="border border-[color:var(--hairline)]"
            >
              <Link href={n.href} className="block p-5 h-full">
                <p className="title-md mb-2 text-[color:var(--ink)]">{n.title}</p>
                <p className="body-sm text-[color:var(--muted)]">{n.copy}</p>
              </Link>
            </MagicCard>
          ))}
        </div>
      </section>

      {/* ── Part of MotorsportVerse ── */}
      <Section title="Part of MotorsportVerse">
        RaceIQ&nbsp;MotoGP is one project in the{" "}
        <a
          href="https://github.com/roni-altshuler/motorsportverse"
          target="_blank"
          rel="noreferrer"
          className="text-[var(--accent)] underline-offset-4 hover:underline"
        >
          MotorsportVerse
        </a>{" "}
        ecosystem — a shared, open-source core for forecasting any racing series. The same machinery
        runs RaceIQ&nbsp;F1; MotoGP adds only what the championship genuinely needs.
      </Section>

      {/* ── Disclaimer ── */}
      <section className="hairline-divider-top pt-12 mt-12">
        <div
          className="border rounded-[var(--radius-card)] p-6 sm:p-7"
          style={{ borderColor: "rgba(212,160,23,0.4)" }}
        >
          <p className="eyebrow mb-3" style={{ color: "var(--warning)" }}>
            Disclaimer
          </p>
          <p className="body-md text-[color:var(--body)]">
            This site is a personal project published for educational and entertainment purposes.
            Forecasts are model outputs and should not be used for betting or any form of gambling.
            The project is not affiliated with, endorsed by, or connected to MotoGP, Dorna, the
            FIM, or any team.
          </p>
        </div>
      </section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="font-display text-2xl font-semibold text-[var(--ink)]">{title}</h2>
      <p className="mt-3 leading-relaxed text-[var(--ink-muted)]">{children}</p>
    </section>
  );
}
