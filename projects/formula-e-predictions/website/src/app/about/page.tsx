import type { Metadata } from "next";
import Link from "next/link";

import { AnimatedGradientText } from "@/components/magicui/animated-gradient-text";
import { MagicCard } from "@/components/magicui/magic-card";
import HowItWorksDiagram from "@/components/marketing/HowItWorksDiagram";
import { getFEData } from "@/lib/fedata";

export const metadata: Metadata = {
  title: "About the Model — RaceIQ Formula E",
  description:
    "How RaceIQ Formula E forecasts the ABB FIA Formula E World Championship — street E-Prix, permanent circuits and doubleheader weekends.",
};

// FE electric-blue identity (mirrors the F1 flagship's gradient treatment).
const FE_FROM = "#4B48FF";
const FE_TO = "#7BD2F6";

const NAV = [
  { href: "/", title: "Home", copy: "The next E-Prix up, the predicted podium, and a championship snapshot." },
  { href: "/calendar", title: "Calendar", copy: "Every round at a glance — race dates, doubleheaders, street vs circuit." },
  { href: "/standings", title: "Standings", copy: "Drivers and teams, updated through the latest round, with title projections." },
];

export default function AboutPage() {
  const data = getFEData();

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-16">
      {/* ── Hero ── */}
      <div className="text-center mb-20">
        <p className="eyebrow mb-4">
          Formula E · Season {data.season - 1}-{String(data.season).slice(2)}
        </p>
        <h1 className="display-xl mb-6 [font-weight:700]">
          The {data.season - 1}-{String(data.season).slice(2)}{" "}
          <AnimatedGradientText speed={10} colorFrom={FE_FROM} colorTo={FE_TO}>
            Predictions Board
          </AnimatedGradientText>
        </h1>
        <p className="body-md max-w-2xl mx-auto text-[color:var(--ink-muted)]">
          RaceIQ&nbsp;Formula&nbsp;E forecasts every round of the ABB FIA Formula&nbsp;E World
          Championship — every E-Prix, doubleheaders included — and projects the title fight to
          the end of the season. It&rsquo;s built on the same MotorsportVerse core that powers
          RaceIQ&nbsp;F1, tuned for what makes Formula&nbsp;E different.
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

      {/* ── The Formula-E-specific story ── */}
      <Section title="Street circuits play by different rules">
        Most E-Prix run between walls on temporary street layouts, where grid position and
        clean racecraft matter far more than raw pace; a handful run on permanent circuits
        with real overtaking room. The forecast is tuned separately for the two — a
        probability earned on a street track means something different from one earned at a
        permanent venue, and the model treats them that way.
      </Section>

      <Section title="Doubleheaders: two rounds, one venue">
        Several weekends run two full championship rounds back-to-back at the same venue —
        Jeddah, Berlin, Monaco, Shanghai, Tokyo, London. Each race is forecast and graded as
        its own round, and by the second race the field has a full race of reads on the same
        corners; the calendar pairs those rounds so the weekend reads as one story.
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
        <Link href="/accuracy" className="text-[var(--accent-f1-red-bright)] underline-offset-4 hover:underline">
          accuracy dashboard
        </Link>
        . Probabilities are calibrated on the season&rsquo;s real results, separately for street
        and permanent circuits — and the dashboard shows the model&rsquo;s health warnings as
        openly as its wins.
      </Section>

      {/* ── Navigation guide (MagicCard grid) ── */}
      <section className="hairline-divider-top pt-12 mt-16 mb-16">
        <p className="eyebrow mb-4">How to use this site</p>
        <h2 className="display-md mb-8">Navigation</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {NAV.map((n) => (
            <MagicCard
              key={n.href}
              gradientFrom={FE_FROM}
              gradientTo={FE_TO}
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
        RaceIQ&nbsp;Formula&nbsp;E is one project in the{" "}
        <a
          href="https://github.com/roni-altshuler/motorsportverse"
          target="_blank"
          rel="noreferrer"
          className="text-[var(--accent)] underline-offset-4 hover:underline"
        >
          MotorsportVerse
        </a>{" "}
        ecosystem — a shared, open-source core for forecasting any racing series. The same machinery
        runs RaceIQ&nbsp;F1; Formula&nbsp;E adds only what the championship genuinely needs.
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
            The project is not affiliated with, endorsed by, or connected to Formula&nbsp;E, the FIA,
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
