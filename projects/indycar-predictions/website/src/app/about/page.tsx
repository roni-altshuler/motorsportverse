import type { Metadata } from "next";
import Link from "next/link";

import { AnimatedGradientText } from "@/components/magicui/animated-gradient-text";
import { MagicCard } from "@/components/magicui/magic-card";
import HowItWorksDiagram from "@/components/marketing/HowItWorksDiagram";
import { getIndycarData } from "@/lib/indycardata";

export const metadata: Metadata = {
  title: "About the Model — RaceIQ Indy",
  description:
    "How RaceIQ Indy forecasts the NTT IndyCar Series — ovals, road courses and street circuits, the Indianapolis 500, and a championship that runs to the finale.",
};

// IndyCar red identity (mirrors the F1 flagship's gradient treatment).
const INDY_FROM = "#D31217";
const INDY_TO = "#FF6B6E";

const NAV = [
  { href: "/", title: "Home", copy: "The next race up, the predicted podium, and a championship snapshot." },
  { href: "/calendar", title: "Calendar", copy: "Every round at a glance — race dates, ovals vs road and street courses, and the 500." },
  { href: "/standings", title: "Standings", copy: "Drivers, teams and engine manufacturers, plus the title-race forecast." },
];

export default function AboutPage() {
  const data = getIndycarData();
  const seasonLabel = data.seasonLabel ?? String(data.season);

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-16">
      {/* ── Hero ── */}
      <div className="text-center mb-20">
        <p className="eyebrow mb-4">NTT IndyCar Series · Season {seasonLabel}</p>
        <h1 className="display-xl mb-6 [font-weight:700]">
          The {seasonLabel}{" "}
          <AnimatedGradientText speed={10} colorFrom={INDY_FROM} colorTo={INDY_TO}>
            Predictions Board
          </AnimatedGradientText>
        </h1>
        <p className="body-md max-w-2xl mx-auto text-[color:var(--ink-muted)]">
          RaceIQ&nbsp;Indy forecasts every round of the NTT IndyCar Series — all{" "}
          {data.totalRounds} races, from the streets of St.&nbsp;Petersburg to the
          season finale, with the Indianapolis&nbsp;500 in the middle — and projects
          the title fight to the last lap of the year. It&rsquo;s built on the same
          MotorsportVerse core that powers RaceIQ&nbsp;F1, tuned for what makes
          American open-wheel racing different.
        </p>
      </div>

      {/* ── How it works — shared AnimatedBeam diagram ── */}
      <section className="mb-20" aria-labelledby="about-how-heading">
        <div className="text-center mb-10">
          <p className="eyebrow mb-2">How it works</p>
          <h2 id="about-how-heading" className="display-md">
            Curated data → Model → Forecast
          </h2>
        </div>
        <HowItWorksDiagram variant="beam" />
      </section>

      {/* ── The IndyCar-specific story ── */}
      <Section title="Ovals and road courses are different sports">
        An IndyCar season splits almost evenly between ovals, permanent road courses
        and temporary street circuits — and the same driver is rarely equally good at
        all of them. The model&rsquo;s signature is a dual rating: every driver carries
        one score for oval racing and another for road and street racing, because
        walk-forward testing showed the split genuinely beats a single blended number.
        A forecast at Milwaukee and a forecast at Barber start from different reads of
        the same field.
      </Section>

      <Section title="The Indianapolis 500 is its own event">
        The 500 runs the traditional 33-car field — bigger than a normal weekend, with
        one-off entries who show up only for May. The forecast covers the full field,
        and the race page flags the crown jewel explicitly. There is no double-points
        twist in {seasonLabel}: the 500 pays like any other round, and the model
        scores it that way.
      </Section>

      <Section title="A championship without playoffs">
        IndyCar still crowns its champion the classic way: most points after the last
        race wins. That makes the title forecast a clean simulation — every remaining
        round is raced thousands of times, and the standings page shows each
        driver&rsquo;s title odds, projected points range, and whether they are still
        mathematically alive. No resets, no eliminations — just the season-long math.
      </Section>

      <Section title="Retirements are part of the forecast">
        Open-wheel cars touch wheels and find walls. The model carries a per-driver
        retirement hazard for every race — higher in oval traffic, lower on the
        permanent road courses — and folds it into every finishing-position range.
        That&rsquo;s why a favourite can lead the win market and still show a wide
        projected range: a DNF is always on the table.
      </Section>

      <Section title="Built on hand-verified history">
        There is no public IndyCar data feed, so this project inverts the usual
        pipeline: fifteen seasons of race results were hand-curated and checked
        against official standings, and that committed archive is the ground truth
        the model learns from. Live updates land only after strict validation — a bad
        scrape can&rsquo;t silently poison a forecast.
      </Section>

      <Section title="What the numbers mean">
        For each race you get a win and podium probability per driver, an expected
        finishing range rather than a single guess, a DNF risk, and a confidence read.
        For the season, the championship view shows each driver&rsquo;s title odds —
        and who is still mathematically alive for the championship.
      </Section>

      <Section title="Honest about accuracy">
        Every forecast is made using only what was known before the round — no peeking at
        the result — and scored against what actually happened on the{" "}
        <Link href="/accuracy" className="text-[var(--accent-f1-red-bright)] underline-offset-4 hover:underline">
          accuracy dashboard
        </Link>
        . Probabilities are calibrated on real IndyCar results, separately for ovals,
        road courses and street circuits — and the dashboard shows the model&rsquo;s
        health warnings as openly as its wins.
      </Section>

      {/* ── Navigation guide (MagicCard grid) ── */}
      <section className="hairline-divider-top pt-12 mt-16 mb-16">
        <p className="eyebrow mb-4">How to use this site</p>
        <h2 className="display-md mb-8">Navigation</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {NAV.map((n) => (
            <MagicCard
              key={n.href}
              gradientFrom={INDY_FROM}
              gradientTo={INDY_TO}
              gradientColor="#2a0e0f"
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
        RaceIQ&nbsp;Indy is one project in the{" "}
        <a
          href="https://github.com/roni-altshuler/motorsportverse"
          target="_blank"
          rel="noreferrer"
          className="text-[var(--accent)] underline-offset-4 hover:underline"
        >
          MotorsportVerse
        </a>{" "}
        ecosystem — a shared, open-source core for forecasting any racing series. The same
        machinery runs RaceIQ&nbsp;F1; IndyCar adds only what the championship genuinely
        needs — the oval/road split, the DNF hazard, and the 500&rsquo;s 33-car field.
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
            The project is not affiliated with, endorsed by, or connected to INDYCAR or any team.
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
