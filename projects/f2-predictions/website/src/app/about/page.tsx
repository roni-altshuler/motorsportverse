import type { Metadata } from "next";
import Link from "next/link";

import { getF2Data } from "@/lib/f2data";

export const metadata: Metadata = {
  title: "About the Model — RaceIQ F2",
  description:
    "How RaceIQ F2 forecasts the FIA Formula 2 championship — a spec series where driver skill rules and the sprint runs a reversed grid.",
};

export default function AboutPage() {
  const data = getF2Data();

  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <p className="eyebrow mb-3">Formula 2 · {data.season}</p>
      <h1 className="font-display text-4xl font-bold tracking-tight text-[var(--ink)] sm:text-5xl">
        About the model
      </h1>
      <p className="mt-4 text-lg leading-relaxed text-[var(--ink-muted)]">
        RaceIQ F2 forecasts every round of the FIA Formula&nbsp;2 championship — both the Saturday
        sprint and the Sunday feature race — and projects the title fight to the end of the season.
        It&rsquo;s built on the same MotorsportVerse core that powers RaceIQ&nbsp;F1, tuned for what
        makes Formula&nbsp;2 different.
      </p>

      <Section title="A spec series rewards the driver">
        Every team runs the same chassis, engine, and tyres, so the car barely separates the field —
        what you&rsquo;re really watching is driver quality. The forecast weights a driver&rsquo;s own
        form and head-to-head record far more heavily than their team, the opposite of how a Formula&nbsp;1
        model has to think.
      </Section>

      <Section title="Two very different races a weekend">
        The feature race starts from a merit grid: fastest in qualifying lines up first. The sprint
        flips the top ten of that grid, so the quickest drivers have to fight forward from the back.
        RaceIQ models the two races separately — that reversed grid is exactly why the sprint is so much
        more unpredictable, and the forecast reflects it.
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

      <Section title="Part of MotorsportVerse">
        RaceIQ&nbsp;F2 is one project in the{" "}
        <a
          href="https://github.com/roni-altshuler/motorsportverse"
          target="_blank"
          rel="noreferrer"
          className="text-[var(--accent)] underline-offset-4 hover:underline"
        >
          MotorsportVerse
        </a>{" "}
        ecosystem — a shared, open-source core for forecasting any racing series. The same machinery
        runs RaceIQ&nbsp;F1; F2 adds only what the championship genuinely needs.
      </Section>

      <div className="mt-12 flex flex-wrap gap-3">
        <Link
          href="/standings"
          className="rounded-[var(--radius-pill)] bg-[var(--accent)] px-5 py-2.5 text-sm font-semibold text-[var(--accent-ink,#04222e)]"
        >
          See the standings →
        </Link>
        <Link
          href="/calendar"
          className="rounded-[var(--radius-pill)] border border-[var(--hairline-strong)] px-5 py-2.5 text-sm font-medium text-[var(--ink)]"
        >
          Season calendar
        </Link>
      </div>
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
