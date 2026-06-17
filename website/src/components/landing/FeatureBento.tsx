/**
 * FeatureBento — the shared-core capabilities as a Linear-style bento grid,
 * built on the existing BentoGrid/BentoCard primitives. Server component.
 */

import { BentoCard, BentoGrid } from "@/components/magicui/bento-grid";

function GridBg() {
  return <div className="bg-grid bg-grid-fade absolute inset-0 opacity-[0.5]" />;
}

function GlowBg({ from }: { from: string }) {
  return (
    <div
      className="absolute inset-0"
      style={{ background: `radial-gradient(80% 70% at 30% 0%, ${from}, transparent 70%)` }}
      aria-hidden
    />
  );
}

export function FeatureBento() {
  return (
    <BentoGrid className="auto-rows-[14rem] gap-4">
      <BentoCard
        className="col-span-3 lg:col-span-2"
        background={
          <>
            <GridBg />
            <GlowBg from="rgba(231,16,47,0.12)" />
          </>
        }
      >
        <div className="flex h-full flex-col justify-between p-7">
          <span className="mono-label">motorsport-core</span>
          <div>
            <h3 className="title-md text-[var(--ink)]">Calibrated probabilities, not point picks</h3>
            <p className="body-sm mt-2 max-w-md">
              Plackett-Luce calibration + per-lap Monte Carlo turn raw pace into win, podium, and
              finishing-range probabilities you can actually trust.
            </p>
          </div>
        </div>
      </BentoCard>

      <BentoCard
        className="col-span-3 lg:col-span-1"
        background={<GlowBg from="rgba(56,225,198,0.12)" />}
      >
        <div className="flex h-full flex-col justify-between p-7">
          <span className="mono-label">motorsport-data</span>
          <div>
            <h3 className="title-md text-[var(--ink)]">One canonical schema</h3>
            <p className="body-sm mt-2">
              Season · Round · Competitor · Result · Prediction — every project speaks the same
              language over a DuckDB history store.
            </p>
          </div>
        </div>
      </BentoCard>

      <BentoCard
        className="col-span-3 lg:col-span-1"
        background={<GlowBg from="rgba(106,166,255,0.12)" />}
      >
        <div className="flex h-full flex-col justify-between p-7">
          <span className="mono-label">Continuous learning</span>
          <div>
            <h3 className="title-md text-[var(--ink)]">Drift &amp; A/B promotion</h3>
            <p className="body-sm mt-2">
              A model registry, drift detection, and gated promotion keep every sport&apos;s model
              honest as new results land.
            </p>
          </div>
        </div>
      </BentoCard>

      <BentoCard
        className="col-span-3 lg:col-span-2"
        background={
          <>
            <GridBg />
            <GlowBg from="rgba(231,16,47,0.10)" />
          </>
        }
      >
        <div className="flex h-full flex-col justify-between p-7">
          <span className="mono-label">Leakage-safe by construction</span>
          <div>
            <h3 className="title-md text-[var(--ink)]">Forward-only evaluation</h3>
            <p className="body-sm mt-2 max-w-md">
              Strict temporal splits, conformal intervals, and shared leakage guards mean the
              accuracy you see offline is the accuracy you get on race day.
            </p>
          </div>
        </div>
      </BentoCard>
    </BentoGrid>
  );
}
