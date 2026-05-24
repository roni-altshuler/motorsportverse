"use client";

import Link from "next/link";
import { useRef } from "react";
import { Database, Cpu, Trophy } from "lucide-react";

import { DEFAULT_SEASON_YEAR } from "@/lib/season";
import { AnimatedGradientText } from "@/components/magicui/animated-gradient-text";
import { AnimatedBeam } from "@/components/magicui/animated-beam";
import { MagicCard } from "@/components/magicui/magic-card";

const ACTIVE_SEASON_YEAR = String(DEFAULT_SEASON_YEAR);

export default function AboutPage() {
  const diagramRef = useRef<HTMLDivElement>(null);
  const dataRef = useRef<HTMLDivElement>(null);
  const modelRef = useRef<HTMLDivElement>(null);
  const forecastRef = useRef<HTMLDivElement>(null);

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 section-bugatti">
      <div className="text-center mb-20">
        <p className="eyebrow mb-4">About</p>
        <h1 className="display-xl mb-6 [font-weight:700]">
          The {ACTIVE_SEASON_YEAR}{" "}
          <AnimatedGradientText
            speed={10}
            colorFrom="#E10600"
            colorTo="#FFD166"
          >
            Predictions Board
          </AnimatedGradientText>
        </h1>
        <p className="body-md max-w-2xl mx-auto">
          A self-updating dashboard for the {ACTIVE_SEASON_YEAR} Formula 1
          season: per-Grand-Prix forecasts, championship standings, head-to-head
          matchups, and post-race accuracy — all in one place.
        </p>
      </div>

      {/* ── How it works — AnimatedBeam diagram ── */}
      <section className="mb-20">
        <div className="text-center mb-10">
          <p className="eyebrow mb-2">How it works</p>
          <h2 className="display-md">Live data → Model → Forecast</h2>
        </div>

        <div
          ref={diagramRef}
          className="relative grid grid-cols-3 gap-4 sm:gap-8 py-10 px-2 sm:px-8"
        >
          <DiagramNode
            innerRef={dataRef}
            Icon={Database}
            title="Live F1 Data"
            description="Race results, telemetry, weather and standings ingested every Grand Prix weekend."
          />
          <DiagramNode
            innerRef={modelRef}
            Icon={Cpu}
            title="AI Model"
            description="A learning system that re-trains as the season progresses, then weighs every car in the field."
          />
          <DiagramNode
            innerRef={forecastRef}
            Icon={Trophy}
            title="Race Forecast"
            description="Probabilities for win, podium, top 6 and full classification — refreshed before lights out."
          />

          <AnimatedBeam
            containerRef={diagramRef}
            fromRef={dataRef}
            toRef={modelRef}
            duration={4}
            gradientStartColor="#E10600"
            gradientStopColor="#3671C6"
          />
          <AnimatedBeam
            containerRef={diagramRef}
            fromRef={modelRef}
            toRef={forecastRef}
            duration={4}
            delay={1}
            gradientStartColor="#3671C6"
            gradientStopColor="#FFD166"
          />
        </div>
      </section>

      {/* ── Methodology anchor section ── */}
      <section id="methodology" className="hairline-divider-top pt-12 mb-16 scroll-mt-32">
        <p className="eyebrow mb-4">Methodology</p>
        <h2 className="display-md mb-8">How we measure accuracy</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
          <div>
            <p className="title-md mb-2">Per-position grading</p>
            <p className="body-sm text-[color:var(--muted)]">
              Each predicted finish position is graded against the official
              classification once a race is over. A prediction is considered a
              hit when it lands within three positions of the actual result.
            </p>
          </div>
          <div>
            <p className="title-md mb-2">Live vs published</p>
            <p className="body-sm text-[color:var(--muted)]">
              &quot;Live&quot; means the race weekend is currently in progress —
              practice, qualifying or the race itself is happening as you read
              this. Forecasts are time-stamped so you always know how fresh
              they are.
            </p>
          </div>
          <div>
            <p className="title-md mb-2">Why we re-train weekly</p>
            <p className="body-sm text-[color:var(--muted)]">
              The model takes the latest data into account every weekend so
              that recent form, car upgrades, and weather patterns inform the
              next forecast without manual intervention.
            </p>
          </div>
        </div>
      </section>

      {/* ── Navigation guide ── */}
      <section className="hairline-divider-top pt-12 mb-16">
        <p className="eyebrow mb-4">How to use this site</p>
        <h2 className="display-md mb-8">Navigation</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            {
              href: "/",
              title: "Home",
              copy: "The next race up, the predicted podium, and championship snapshot.",
            },
            {
              href: "/calendar",
              title: "Calendar",
              copy: `All ${ACTIVE_SEASON_YEAR} Grands Prix at a glance with status per round.`,
            },
            {
              href: "/standings",
              title: "Standings",
              copy: "Drivers and constructors championships, updated through the latest round.",
            },
          ].map((n) => (
            <MagicCard
              key={n.href}
              gradientFrom="#E10600"
              gradientTo="#3671C6"
              gradientColor="#262626"
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

      <section className="hairline-divider-top pt-12">
        <div className="border border-[color:var(--hairline)] rounded-[var(--radius-card)] p-6 sm:p-7" style={{ borderColor: "rgba(212,160,23,0.4)" }}>
          <p className="eyebrow mb-3" style={{ color: "var(--warning)" }}>
            Disclaimer
          </p>
          <p className="body-md text-[color:var(--body)]">
            This site is a personal project published for educational and
            entertainment purposes. Forecasts are model outputs and should not
            be used for betting or any form of gambling. The project is not
            affiliated with, endorsed by, or connected to Formula 1, the FIA,
            or any constructor.
          </p>
        </div>
      </section>
    </div>
  );
}

function DiagramNode({
  innerRef,
  Icon,
  title,
  description,
}: {
  innerRef: React.RefObject<HTMLDivElement | null>;
  Icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
}) {
  return (
    <div ref={innerRef} className="relative z-10 flex flex-col items-center text-center">
      <span
        className="inline-flex items-center justify-center w-14 h-14 rounded-full border mb-4"
        style={{
          borderColor: "var(--hairline-strong)",
          background: "var(--surface-card)",
        }}
      >
        <Icon className="w-6 h-6 text-[color:var(--ink)]" />
      </span>
      <p className="title-sm text-[color:var(--ink)] mb-2">{title}</p>
      <p className="body-sm text-[color:var(--muted)] max-w-[200px]">{description}</p>
    </div>
  );
}
