import type { Metadata } from "next";
import Link from "next/link";

import { AnimatedGradientText } from "@/components/magicui/animated-gradient-text";
import { MagicCard } from "@/components/magicui/magic-card";
import HowItWorksDiagram from "@/components/marketing/HowItWorksDiagram";
import { getWrcData } from "@/lib/wrcData";

export const metadata: Metadata = {
  title: "About the Model — RaceIQ WRC",
  description:
    "How RaceIQ WRC forecasts the World Rally Championship — one classification per rally over mixed surfaces (gravel, tarmac, snow), and the drivers' and manufacturers' title fights.",
};

// WRC blue identity (mirrors the F1 flagship's gradient treatment).
const WRC_FROM = "#0F62FE";
const WRC_TO = "#6BA5FF";

const NAV = [
  { href: "/", title: "Home", copy: "The next rally up, the predicted podium, and a championship snapshot." },
  { href: "/calendar", title: "Calendar", copy: "Every round at a glance — its surface (gravel, tarmac or snow) and status per rally." },
  { href: "/standings", title: "Standings", copy: "Drivers and manufacturers, updated through the latest rally, with title projections." },
];

export default function AboutPage() {
  const data = getWrcData();

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-16">
      {/* ── Hero ── */}
      <div className="text-center mb-20">
        <p className="eyebrow mb-4">WRC · {data.season}</p>
        <h1 className="display-xl mb-6 [font-weight:700]">
          The {data.season}{" "}
          <AnimatedGradientText speed={10} colorFrom={WRC_FROM} colorTo={WRC_TO}>
            Predictions Board
          </AnimatedGradientText>
        </h1>
        <p className="body-md max-w-2xl mx-auto text-[color:var(--ink-muted)]">
          RaceIQ&nbsp;WRC forecasts every round of the World Rally Championship — the classified
          result of each rally, run over gravel, tarmac and snow — and projects the drivers&rsquo;
          and manufacturers&rsquo; title fights to the end of the season. It&rsquo;s built on the
          same MotorsportVerse core that powers RaceIQ&nbsp;F1, tuned for what makes rallying
          different.
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

      {/* ── The WRC-specific story ── */}
      <Section title="Surface is the defining variable">
        No two rounds are alike, because the ground keeps changing. The WRC runs on loose gravel,
        grippy tarmac and — in the depths of winter — snow and ice, and each surface rewards a
        different car balance, tyre choice and driving style. RaceIQ reads every forecast against
        the surface the rally is run on, so a crew that flies on gravel isn&rsquo;t assumed to carry
        that form onto a tarmac round.
      </Section>

      <Section title="Crew form and championship position">
        Rallying has no qualifying and no starting grid to condition on, so the model leans on what
        it can actually observe: a crew&rsquo;s own recent form, the surface ahead, and their place
        in the championship. It re-trains as the season unfolds and reads each Rally1 crew against
        the field, so the numbers follow who is genuinely fast right now rather than a name or a
        badge.
      </Section>

      <Section title="What the numbers mean">
        For each rally you get a win and podium probability per crew, an expected finishing range
        rather than a single guess, and a confidence read. For the season, the championship view
        shows each driver&rsquo;s title odds and projected points — and who is still mathematically
        alive for the crown — alongside the manufacturers&rsquo; standings.
      </Section>

      <Section title="Honest about accuracy">
        Every forecast is made using only what was known before the rally — no peeking at the
        result — and scored against what actually happened on the{" "}
        <Link href="/accuracy" className="text-[var(--accent)] underline-offset-4 hover:underline">
          accuracy dashboard
        </Link>
        , against the honest yardstick of championship form: does the forecast beat simply picking
        by the standings? Probability calibration stays switched off until enough real-feed rounds
        are banked, so the site never claims precision it hasn&rsquo;t earned.
      </Section>

      {/* ── Navigation guide (MagicCard grid) ── */}
      <section className="hairline-divider-top pt-12 mt-16 mb-16">
        <p className="eyebrow mb-4">How to use this site</p>
        <h2 className="display-md mb-8">Navigation</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {NAV.map((n) => (
            <MagicCard
              key={n.href}
              gradientFrom={WRC_FROM}
              gradientTo={WRC_TO}
              gradientColor="#0d1a2a"
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
        RaceIQ&nbsp;WRC is one project in the{" "}
        <a
          href="https://github.com/roni-altshuler/motorsportverse"
          target="_blank"
          rel="noreferrer"
          className="text-[var(--accent)] underline-offset-4 hover:underline"
        >
          MotorsportVerse
        </a>{" "}
        ecosystem — a shared, open-source core for forecasting any racing series. The same machinery
        runs RaceIQ&nbsp;F1; WRC adds only what rallying genuinely needs.
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
            The project is not affiliated with, endorsed by, or connected to the WRC, the FIA, the
            WRC Promoter, or any team.
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
