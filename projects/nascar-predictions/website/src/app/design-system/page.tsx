/**
 * /design-system — visual showcase of the design tokens + UI primitives.
 *
 * Living style guide (ported from the RaceIQ F1 flagship, themed Formula E
 * championship gold). Open this page to verify a token change cascades to every
 * primitive. Not linked from the main navigation — internal QA surface only.
 */
import type { Metadata } from "next";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { Stat } from "@/components/ui/Stat";
import MagicUIGallery from "@/components/design-system/MagicUIGallery";

export const metadata: Metadata = {
  title: "Design System · RaceIQ Formula E",
  description: "Internal showcase of design tokens, palette, typography, and UI primitives.",
};

const SECTION_CLS =
  "rounded-[12px] border border-[color:var(--border)] bg-[color:var(--surface)] p-6 space-y-4";
const SECTION_LABEL_CLS =
  "text-[11px] font-bold uppercase tracking-[0.16em] text-[color:var(--text-muted)]";

function TokenSwatch({ label, cssVar, value }: { label: string; cssVar: string; value?: string }) {
  return (
    <div className="flex items-center gap-3 rounded-[8px] border border-[color:var(--border)] bg-[color:var(--surface-elevated)] p-2">
      <div
        className="h-10 w-14 shrink-0 rounded-[6px] border border-[color:var(--border)]"
        style={{ background: `var(${cssVar})` }}
        aria-hidden
      />
      <div className="min-w-0">
        <div className="text-xs font-semibold text-[color:var(--text-primary)]">{label}</div>
        <div className="font-mono text-[10px] uppercase tracking-wider text-[color:var(--text-muted)]">
          {cssVar}
          {value ? ` · ${value}` : ""}
        </div>
      </div>
    </div>
  );
}

export default function DesignSystemPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 space-y-8">
      {/* Hero */}
      <header className="space-y-3">
        <Badge variant="live">Internal · QA</Badge>
        <h1 className="text-3xl font-extrabold leading-tight tracking-tight">
          RaceIQ Formula E · Design System
        </h1>
        <p className="text-[color:var(--text-secondary)] max-w-2xl">
          The RaceIQ design system, themed in Formula E electric blue. Every surface, accent,
          and chart hue should follow from these tokens.
        </p>
      </header>

      {/* Palette */}
      <section className={SECTION_CLS}>
        <div className={SECTION_LABEL_CLS}>1 · Palette</div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          <TokenSwatch label="Background" cssVar="--bg" />
          <TokenSwatch label="Surface" cssVar="--surface" />
          <TokenSwatch label="Surface elevated" cssVar="--surface-elevated" />
          <TokenSwatch label="Border" cssVar="--border" />
          <TokenSwatch label="Text primary" cssVar="--text-primary" />
          <TokenSwatch label="Text muted" cssVar="--text-muted" />
          <TokenSwatch label="Accent" cssVar="--accent" value="electric blue" />
          <TokenSwatch label="Accent · live" cssVar="--accent-live" />
          <TokenSwatch label="Accent · positive" cssVar="--accent-positive" />
          <TokenSwatch label="Accent · negative" cssVar="--accent-negative" />
          <TokenSwatch label="Podium · gold" cssVar="--accent-podium-1" />
          <TokenSwatch label="Podium · silver" cssVar="--accent-podium-2" />
        </div>
      </section>

      {/* Typography */}
      <section className={SECTION_CLS}>
        <div className={SECTION_LABEL_CLS}>2 · Typography</div>
        <div className="space-y-3">
          <div className="font-sans text-4xl font-extrabold tracking-tight">
            E-Prix · Saturday
          </div>
          <div className="font-sans text-xl font-semibold text-[color:var(--text-secondary)]">
            Street circuit · racing between the walls
          </div>
          <div className="font-sans text-sm text-[color:var(--text-muted)]">
            Saira Condensed (display) + EB Garamond (body), loaded via next/font. Body copy at
            16px / 1.6 line-height.
          </div>
          <div className="font-mono font-tabular text-2xl font-bold">
            +0.182 · -0.341 · 00:01:19.482
          </div>
          <div className="font-mono font-tabular text-xs uppercase tracking-[0.12em] text-[color:var(--text-muted)]">
            JetBrains Mono — tabular figures for timing displays
          </div>
        </div>
      </section>

      {/* Badges */}
      <section className={SECTION_CLS}>
        <div className={SECTION_LABEL_CLS}>3 · Badges</div>
        <div className="flex flex-wrap gap-2">
          <Badge>Predicted</Badge>
          <Badge variant="live">Live</Badge>
          <Badge variant="positive">+0.18s</Badge>
          <Badge variant="negative">-0.41s</Badge>
          <Badge variant="info">Street</Badge>
          <Badge variant="muted">Circuit</Badge>
          <Badge variant="outline">DNF</Badge>
        </div>
      </section>

      {/* Buttons */}
      <section className={SECTION_CLS}>
        <div className={SECTION_LABEL_CLS}>4 · Buttons</div>
        <div className="flex flex-wrap gap-3">
          <Button>Predict winner</Button>
          <Button variant="secondary">Show probabilities</Button>
          <Button variant="outline">Compare rounds</Button>
          <Button variant="ghost">Reset filters</Button>
          <Button variant="destructive">Stop</Button>
          <Button variant="link">View raw data →</Button>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button size="sm">Small</Button>
          <Button size="md">Medium</Button>
          <Button size="lg">Large</Button>
        </div>
      </section>

      {/* Stats */}
      <section className={SECTION_CLS}>
        <div className={SECTION_LABEL_CLS}>5 · Telemetry stats</div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="P(win)" value="34%" hint="win-market leader" tone="live" />
          <Stat label="P(podium)" value="61%" hint="top-3 finish" tone="positive" />
          <Stat label="Mean finish" value="P4.2" hint="across simulations" />
          <Stat label="Finish range" value="P2–P7" tone="negative" hint="80% interval" />
        </div>
      </section>

      {/* Cards */}
      <section className={SECTION_CLS}>
        <div className={SECTION_LABEL_CLS}>6 · Cards</div>
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <Badge variant="live" className="self-start">
                Round 6 · E-Prix
              </Badge>
              <CardTitle>Formula E · Round 6</CardTitle>
              <CardDescription>Street circuit · forecast updated recently</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="font-mono font-tabular text-3xl font-extrabold">
                P1 &nbsp;<span className="text-[color:var(--text-muted)]">·</span>&nbsp;
                <span className="text-[color:var(--accent)]">34%</span>
              </div>
              <p className="text-sm text-[color:var(--text-secondary)]">
                The model narrowly favours the championship leader, with two challengers carrying
                meaningful upside into the race.
              </p>
            </CardContent>
            <CardFooter className="gap-2">
              <Button size="sm">View round</Button>
              <Button size="sm" variant="ghost">
                Probabilities →
              </Button>
            </CardFooter>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Calibration · /accuracy</CardTitle>
              <CardDescription>Forecast calibration status across the season</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
                <Stat label="Calibration Error" value="0.18" hint="lower is better" />
                <Stat label="Forecast Sharpness" value="0.42" />
                <Stat label="Calibration" value="gated" hint="awaiting real rounds" />
                <Stat label="Rounds scored" value="6" hint="this season" />
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <MagicUIGallery />
    </div>
  );
}
