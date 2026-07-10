import type { Metadata } from "next";
import Link from "next/link";

import { AnimatedGradientText } from "@/components/magicui/animated-gradient-text";
import { MagicCard } from "@/components/magicui/magic-card";
import HowItWorksDiagram from "@/components/marketing/HowItWorksDiagram";
import { getNascarData } from "@/lib/nascardata";

export const metadata: Metadata = {
  title: "About the Model — RaceIQ NASCAR",
  description:
    "How RaceIQ NASCAR forecasts the Cup Series — 36 races, stage racing, four track archetypes and the Chase playoffs.",
};

// NASCAR yellow identity (mirrors the F1 flagship's gradient treatment).
const NASCAR_FROM = "#FFD659";
const NASCAR_TO = "#E9BC2F";

const NAV = [
  { href: "/", title: "Home", copy: "The next Cup race up, the predicted podium, and a championship snapshot." },
  { href: "/calendar", title: "Calendar", copy: "Every round at a glance — race dates, track types, and the playoff stretch." },
  { href: "/standings", title: "Standings", copy: "Drivers, teams and manufacturers, plus the Chase playoff projection." },
];

export default function AboutPage() {
  const data = getNascarData();
  const seasonLabel = data.seasonLabel ?? String(data.season);

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-16">
      {/* ── Hero ── */}
      <div className="text-center mb-20">
        <p className="eyebrow mb-4">NASCAR Cup Series · Season {seasonLabel}</p>
        <h1 className="display-xl mb-6 [font-weight:700]">
          The {seasonLabel}{" "}
          <AnimatedGradientText speed={10} colorFrom={NASCAR_FROM} colorTo={NASCAR_TO}>
            Predictions Board
          </AnimatedGradientText>
        </h1>
        <p className="body-md max-w-2xl mx-auto text-[color:var(--ink-muted)]">
          RaceIQ&nbsp;NASCAR forecasts every round of the NASCAR Cup Series — all{" "}
          {data.totalRounds} races, from the Daytona&nbsp;500 to the championship finale —
          and projects the title fight through the Chase playoffs. It&rsquo;s built on the
          same MotorsportVerse core that powers RaceIQ&nbsp;F1, tuned for what makes
          stock-car racing different.
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

      {/* ── The NASCAR-specific story ── */}
      <Section title="Four kinds of racetrack, four kinds of race">
        A Cup season sweeps across superspeedways, intermediate ovals, short tracks and
        road courses — and they play by very different rules. Superspeedway pack racing
        makes almost anyone in the draft a live winner (and a live DNF); intermediates
        reward clean air and raw pace; short tracks come down to track position and
        restarts; road courses reward braking and racecraft. The forecast is tuned
        separately for each — a probability earned at Talladega means something different
        from one earned at Sonoma, and the model treats them that way.
      </Section>

      <Section title="Stage racing: points before the finish">
        Every race runs in three stages, and the top ten of each stage score championship
        points on the spot. Stage points reward all-day speed, not just the last lap —
        they shape the standings, the playoff seeding, and the model&rsquo;s read on who is
        genuinely fast. Completed rounds on this site show the stage-by-stage top tens
        alongside the final classification.
      </Section>

      <Section title="The Chase: a 36-race season with a playoff">
        Twenty-six regular-season races set a sixteen-driver playoff field; ten playoff
        races then decide the title. That structure changes what a forecast should say:
        points projections here run to the end of the regular season (the playoffs reset
        the field), while title odds simulate the full Chase. The standings page draws
        today&rsquo;s playoff cut line — who&rsquo;s in, who&rsquo;s out, and who&rsquo;s on the
        bubble — and the playoff panel only ships because the simulator proved itself on
        historical seasons first.
      </Section>

      <Section title="Retirements are part of the forecast">
        Stock-car racing wrecks. The model carries a per-driver retirement hazard for every
        race — higher in the pack at Daytona and Talladega, lower on the road courses — and
        folds it into every finishing-position range. That&rsquo;s why a favourite can lead the
        win market and still show a wide projected range: a DNF is always on the table.
      </Section>

      <Section title="What the numbers mean">
        For each race you get a win and podium probability per driver, an expected
        finishing range rather than a single guess, a DNF risk, and a confidence read.
        For the season, the championship view shows each driver&rsquo;s playoff and title
        odds — and who is still mathematically alive for the Cup.
      </Section>

      <Section title="Honest about accuracy">
        Every forecast is made using only what was known before the round — no peeking at
        the result — and scored against what actually happened on the{" "}
        <Link href="/accuracy" className="text-[var(--accent-f1-red-bright)] underline-offset-4 hover:underline">
          accuracy dashboard
        </Link>
        . Probabilities are calibrated on real Cup results, separately for each of the four
        track types — and the dashboard shows the model&rsquo;s health warnings as openly as
        its wins.
      </Section>

      {/* ── Navigation guide (MagicCard grid) ── */}
      <section className="hairline-divider-top pt-12 mt-16 mb-16">
        <p className="eyebrow mb-4">How to use this site</p>
        <h2 className="display-md mb-8">Navigation</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {NAV.map((n) => (
            <MagicCard
              key={n.href}
              gradientFrom={NASCAR_FROM}
              gradientTo={NASCAR_TO}
              gradientColor="#2c2410"
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
        RaceIQ&nbsp;NASCAR is one project in the{" "}
        <a
          href="https://github.com/roni-altshuler/motorsportverse"
          target="_blank"
          rel="noreferrer"
          className="text-[var(--accent)] underline-offset-4 hover:underline"
        >
          MotorsportVerse
        </a>{" "}
        ecosystem — a shared, open-source core for forecasting any racing series. The same
        machinery runs RaceIQ&nbsp;F1; NASCAR adds only what the championship genuinely
        needs — stage points, the DNF hazard, and the Chase.
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
            The project is not affiliated with, endorsed by, or connected to NASCAR or any team.
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
