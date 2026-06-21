"use client";

import { BorderBeam } from "@/components/magicui/border-beam";
import { Marquee } from "@/components/magicui/marquee";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { ShimmerButton } from "@/components/magicui/shimmer-button";
import { MagicCard } from "@/components/magicui/magic-card";
import { AnimatedGradientText } from "@/components/magicui/animated-gradient-text";
import { Spotlight } from "@/components/magicui/spotlight";
import { PulsatingButton } from "@/components/magicui/pulsating-button";
import { AvatarCircles } from "@/components/magicui/avatar-circles";
import { DotPattern } from "@/components/magicui/dot-pattern";
import { GridPattern } from "@/components/magicui/grid-pattern";
import { NeonGradientCard } from "@/components/magicui/neon-gradient-card";
import { OrbitingCircles } from "@/components/magicui/orbiting-circles";
import { BentoCard, BentoGrid } from "@/components/magicui/bento-grid";

const SECTION_LABEL =
  "text-[11px] font-mono uppercase tracking-[0.18em] text-[color:var(--muted)] mb-4";

const SAMPLE_AVATARS = [
  { initials: "VER", teamColor: "#3671C6" },
  { initials: "NOR", teamColor: "#FF8000" },
  { initials: "PIA", teamColor: "#FF8000" },
  { initials: "RUS", teamColor: "#27F4D2" },
  { initials: "LEC", teamColor: "#E8002D" },
];

export default function MagicUIGallery() {
  return (
    <section className="space-y-12">
      <header>
        <h2 className="display-md mb-2">Magic-UI Components</h2>
        <p className="body-sm text-[color:var(--muted)] max-w-2xl">
          Animated primitives wired up for the {new Date().getFullYear()}{" "}
          overhaul. Every component below also has a static fallback under
          <code className="ml-1 text-[color:var(--ink)]">
            prefers-reduced-motion: reduce
          </code>.
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* BorderBeam */}
        <div className="relative rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-6 overflow-hidden">
          <BorderBeam size={1} duration={8} colorFrom="#E10600" colorTo="#3671C6" />
          <p className={SECTION_LABEL}>BorderBeam</p>
          <p className="title-md text-[color:var(--ink)]">F1-red → broadcast-blue</p>
          <p className="body-sm text-[color:var(--muted)] mt-2">
            1px animated gradient stroke that traces the card perimeter.
          </p>
        </div>

        {/* MagicCard */}
        <MagicCard className="border border-[color:var(--hairline)]">
          <div className="p-6">
            <p className={SECTION_LABEL}>MagicCard</p>
            <p className="title-md text-[color:var(--ink)]">Cursor-tracking gradient</p>
            <p className="body-sm text-[color:var(--muted)] mt-2">
              Hover anywhere over this card.
            </p>
          </div>
        </MagicCard>

        {/* Shimmer + Pulsating buttons */}
        <div className="rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-6">
          <p className={SECTION_LABEL}>ShimmerButton + PulsatingButton</p>
          <div className="flex flex-wrap items-center gap-3">
            <ShimmerButton
              background="var(--accent-f1-red)"
              shimmerColor="rgba(255,255,255,0.9)"
              className="button-label h-10 !py-0 !px-5 text-[12px]"
            >
              Next Race →
            </ShimmerButton>
            <PulsatingButton pulseColor="#E10600">Live</PulsatingButton>
          </div>
        </div>

        {/* NumberTicker */}
        <div className="rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-6">
          <p className={SECTION_LABEL}>NumberTicker</p>
          <div className="flex items-baseline gap-6">
            <p className="font-mono font-tabular text-5xl text-[color:var(--ink)] [font-weight:700]">
              <NumberTicker value={310} />
            </p>
            <p className="font-mono font-tabular text-5xl text-[color:var(--accent-podium-1)]">
              <NumberTicker value={87.4} decimalPlaces={1} />
              <span className="text-2xl">%</span>
            </p>
          </div>
        </div>

        {/* AnimatedGradientText */}
        <div className="rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-6">
          <p className={SECTION_LABEL}>AnimatedGradientText</p>
          <p className="display-md [font-weight:700]">
            <AnimatedGradientText speed={8} colorFrom="#E10600" colorTo="#FFD166">
              Predictions Board
            </AnimatedGradientText>
          </p>
        </div>

        {/* AvatarCircles */}
        <div className="rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-6">
          <p className={SECTION_LABEL}>AvatarCircles</p>
          <AvatarCircles avatars={SAMPLE_AVATARS} numPeople={11} size={44} />
        </div>

        {/* Spotlight */}
        <div className="group rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)] overflow-hidden">
          <Spotlight color="rgba(225,6,0,0.10)" size={300}>
            <div className="p-6">
              <p className={SECTION_LABEL}>Spotlight</p>
              <p className="title-md text-[color:var(--ink)]">Cursor-following highlight</p>
              <p className="body-sm text-[color:var(--muted)] mt-2">
                Hover to reveal the spotlight gradient.
              </p>
            </div>
          </Spotlight>
        </div>

        {/* DotPattern + GridPattern */}
        <div className="relative rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-6 overflow-hidden h-40">
          <DotPattern className="opacity-30" width={16} height={16} cr={1} />
          <div className="relative z-10">
            <p className={SECTION_LABEL}>DotPattern</p>
            <p className="title-md text-[color:var(--ink)]">Background substrate</p>
          </div>
        </div>
        <div className="relative rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-6 overflow-hidden h-40">
          <GridPattern className="opacity-30" width={32} height={32} />
          <div className="relative z-10">
            <p className={SECTION_LABEL}>GridPattern</p>
            <p className="title-md text-[color:var(--ink)]">Telemetry grid</p>
          </div>
        </div>
      </div>

      {/* Marquee */}
      <div className="rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-6">
        <p className={SECTION_LABEL}>Marquee</p>
        <Marquee className="[--duration:30s]" pauseOnHover>
          {["P1 PIA +0.0s", "P2 NOR +1.4s", "P3 RUS +3.8s", "P4 VER +5.2s", "P5 LEC +7.5s"].map((line) => (
            <span
              key={line}
              className="caption-uppercase px-4 py-2 border border-[color:var(--hairline)] text-[color:var(--ink)] whitespace-nowrap"
            >
              {line}
            </span>
          ))}
        </Marquee>
      </div>

      {/* OrbitingCircles */}
      <div className="relative rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)] h-[340px] overflow-hidden">
        <p className={`${SECTION_LABEL} absolute top-5 left-5 z-10`}>OrbitingCircles</p>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="display-md text-[color:var(--ink)]">2026</span>
        </div>
        <OrbitingCircles radius={110} duration={20}>
          <span className="w-10 h-10 rounded-full bg-[color:var(--accent-f1-red)] text-white text-xs flex items-center justify-center font-mono">
            FER
          </span>
        </OrbitingCircles>
        <OrbitingCircles radius={110} duration={20} delay={10}>
          <span className="w-10 h-10 rounded-full bg-[#FF8000] text-white text-xs flex items-center justify-center font-mono">
            MCL
          </span>
        </OrbitingCircles>
        <OrbitingCircles radius={170} duration={28} reverse>
          <span className="w-10 h-10 rounded-full bg-[#27F4D2] text-black text-xs flex items-center justify-center font-mono">
            MER
          </span>
        </OrbitingCircles>
      </div>

      {/* BentoGrid + NeonGradientCard */}
      <div>
        <p className={SECTION_LABEL}>BentoGrid + NeonGradientCard</p>
        <BentoGrid className="grid-cols-3 auto-rows-[10rem]">
          <BentoCard className="col-span-2 row-span-1">
            <div className="p-5">
              <p className="title-sm text-[color:var(--ink)]">Wide cell</p>
              <p className="body-sm text-[color:var(--muted)]">2 columns</p>
            </div>
          </BentoCard>
          <BentoCard className="col-span-1 row-span-1">
            <div className="p-5">
              <p className="title-sm text-[color:var(--ink)]">Tall</p>
            </div>
          </BentoCard>
          <BentoCard className="col-span-1 row-span-1">
            <NeonGradientCard>
              <div className="p-5">
                <p className="title-sm text-[color:var(--ink)]">Neon</p>
                <p className="body-sm text-[color:var(--muted)]">Live race only</p>
              </div>
            </NeonGradientCard>
          </BentoCard>
          <BentoCard className="col-span-2 row-span-1">
            <div className="p-5">
              <p className="title-sm text-[color:var(--ink)]">Wide cell</p>
            </div>
          </BentoCard>
        </BentoGrid>
      </div>
    </section>
  );
}
