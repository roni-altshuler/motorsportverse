import type { Metadata } from "next";
import Link from "next/link";

import { AnimatedGradientText } from "@/components/magicui/animated-gradient-text";
import { MagicCard } from "@/components/magicui/magic-card";
import HowItWorksDiagram from "@/components/marketing/HowItWorksDiagram";
import { getF3Data } from "@/lib/f3data";

export const metadata: Metadata = {
  title: "About the Model — RaceIQ F3",
  description:
    "How RaceIQ F3 forecasts the FIA Formula 3 championship — a spec series where driver skill rules and the sprint runs a reversed grid.",
};

// F3 championship gold identity (mirrors the F1 flagship's gradient treatment).
const F3_FROM = "#D9A441";
const F3_TO = "#9FE2FF";

const NAV = [
  { href: "/", title: "Home", copy: "The next round up, the predicted podium, and a championship snapshot." },
  { href: "/calendar", title: "Calendar", copy: "Every round at a glance — sprint and feature dates, status per round." },
  { href: "/standings", title: "Standings", copy: "Drivers and teams, updated through the latest round, with title projections." },
];

export default function AboutPage() {
  const data = getF3Data();

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-16">
      {/* ── Hero ── */}
      <div className="text-center mb-20">
        <p className="eyebrow mb-4">Formula 3 · {data.season}</p>
        <h1 className="display-xl mb-6 [font-weight:700]">
          The {data.season}{" "}
          <AnimatedGradientText speed={10} colorFrom={F3_FROM} colorTo={F3_TO}>
            Predictions Board
          </AnimatedGradientText>
        </h1>
        <p className="body-md max-w-2xl mx-auto text-[color:var(--ink-muted)]">
          RaceIQ&nbsp;F3 forecasts every round of the FIA Formula&nbsp;2 championship — both the
          Saturday sprint and the Sunday feature race — and projects the title fight to the end of
          the season. It&rsquo;s built on the same MotorsportVerse core that powers RaceIQ&nbsp;F1,
          tuned for what makes Formula&nbsp;2 different.
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

      {/* ── The F3-specific story ── */}
      <Section title="A spec series rewards the driver">
        Every team runs the same chassis, engine, and tyres, so the car barely separates the field —
        what you&rsquo;re really watching is driver quality. The forecast weights a driver&rsquo;s own
        form and head-to-head record far more heavily than their team, the opposite of how a
        Formula&nbsp;1 model has to think.
      </Section>

      <Section title="Two very different races a weekend">
        The feature race starts from a merit grid: fastest in qualifying lines up first. The sprint
        flips the top twelve of that grid, so the quickest drivers have to fight forward from the back.
        RaceIQ models the two races separately — that reversed grid is exactly why the sprint is so
        much more unpredictable, and the forecast reflects it.
      </Section>

      <Section title="What the numbers mean">
        For each race you get a win and podium probability per driver, an expected finishing range
        rather than a single guess, and a confidence read. For the season, the championship view shows
        each driver&rsquo;s title odds and projected points — and who is still mathematically alive for
        the crown.
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
              gradientFrom={F3_FROM}
              gradientTo={F3_TO}
              gradientColor="#10202c"
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
        RaceIQ&nbsp;F3 is one project in the{" "}
        <a
          href="https://github.com/roni-altshuler/motorsportverse"
          target="_blank"
          rel="noreferrer"
          className="text-[var(--accent)] underline-offset-4 hover:underline"
        >
          MotorsportVerse
        </a>{" "}
        ecosystem — a shared, open-source core for forecasting any racing series. The same machinery
        runs RaceIQ&nbsp;F1; F3 adds only what the championship genuinely needs.
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
            The project is not affiliated with, endorsed by, or connected to Formula&nbsp;2, the FIA,
            or any team.
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
