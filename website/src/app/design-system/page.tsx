/**
 * /design-system — visual showcase of the design tokens + UI primitives.
 *
 * Living style guide. Open this page to verify a token change cascades to
 * every primitive, and to confirm light/dark swap is clean.  Not linked
 * from the main navigation — internal QA surface only.
 */
import type { Metadata } from "next";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Stat } from "@/components/ui/Stat";

export const metadata: Metadata = {
  title: "Design System · F1 Predictions",
  description:
    "Internal showcase of design tokens, palette, typography, and UI primitives.",
};

const SECTION_CLS =
  "rounded-[12px] border border-[color:var(--border)] bg-[color:var(--surface)] p-6 space-y-4";

const SECTION_LABEL_CLS =
  "text-[11px] font-bold uppercase tracking-[0.16em] text-[color:var(--text-muted)]";

function TokenSwatch({
  label,
  cssVar,
  value,
}: {
  label: string;
  cssVar: string;
  value?: string;
}) {
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
          F1 Predictions · Design System
        </h1>
        <p className="text-[color:var(--text-secondary)] max-w-2xl">
          Racing-inspired tokens, typography, and primitives. Theme-swap via the
          navbar toggle — every surface, accent, and chart hue should follow.
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
          <TokenSwatch label="Accent · live" cssVar="--accent-live" value="telemetry orange" />
          <TokenSwatch label="Accent · positive" cssVar="--accent-positive" value="hot-lap green" />
          <TokenSwatch label="Accent · negative" cssVar="--accent-negative" value="penalty red" />
          <TokenSwatch label="Accent · info" cssVar="--accent-info" value="timing cyan" />
          <TokenSwatch label="Podium · gold" cssVar="--accent-podium-1" />
          <TokenSwatch label="Podium · silver" cssVar="--accent-podium-2" />
        </div>
      </section>

      {/* Typography */}
      <section className={SECTION_CLS}>
        <div className={SECTION_LABEL_CLS}>2 · Typography</div>
        <div className="space-y-3">
          <div className="font-sans text-4xl font-extrabold tracking-tight">
            Pole position lap · Saturday
          </div>
          <div className="font-sans text-xl font-semibold text-[color:var(--text-secondary)]">
            Lando Norris · 1m 19.482s · MCL fastest sector 2
          </div>
          <div className="font-sans text-sm text-[color:var(--text-muted)]">
            Geist Sans, loaded via next/font.  Body copy at 16px / 1.6 line-height.
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
          <Badge variant="info">Sprint</Badge>
          <Badge variant="muted">Soft tyres</Badge>
          <Badge variant="outline">DNF</Badge>
        </div>
      </section>

      {/* Buttons */}
      <section className={SECTION_CLS}>
        <div className={SECTION_LABEL_CLS}>4 · Buttons</div>
        <div className="flex flex-wrap gap-3">
          <Button>Predict winner</Button>
          <Button variant="secondary">Show probabilities</Button>
          <Button variant="outline">Compare to market</Button>
          <Button variant="ghost">Reset filters</Button>
          <Button variant="destructive">Stop simulation</Button>
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
          <Stat label="P(win)" value="34%" hint="Verstappen · Red Bull" tone="live" />
          <Stat label="Pace gap" value="-0.182s" hint="vs pole" tone="positive" />
          <Stat label="Pit loss" value="22.4s" hint="median over 5 stops" />
          <Stat label="Tyre deg" value="0.08s/lap" tone="negative" hint="medium compound" />
        </div>
      </section>

      {/* Cards */}
      <section className={SECTION_CLS}>
        <div className={SECTION_LABEL_CLS}>6 · Cards</div>
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <Badge variant="live" className="self-start">
                Round 6 · Monaco
              </Badge>
              <CardTitle>Monaco Grand Prix · 2026</CardTitle>
              <CardDescription>
                Quali in 2d 14h · forecast updated 2 min ago
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="font-mono font-tabular text-3xl font-extrabold">
                VER &nbsp;<span className="text-[color:var(--text-muted)]">·</span>&nbsp;
                <span className="text-[color:var(--accent-live)]">34%</span>
              </div>
              <p className="text-sm text-[color:var(--text-secondary)]">
                Model favours Verstappen narrowly; Norris (27%) and Leclerc (18%)
                lead the upside. SC probability elevated at this circuit.
              </p>
            </CardContent>
            <CardFooter className="gap-2">
              <Button size="sm">View race</Button>
              <Button size="sm" variant="ghost">
                Probabilities →
              </Button>
            </CardFooter>
          </Card>

          <Card className="surface-carbon">
            <CardHeader>
              <CardTitle>Calibration · /accuracy</CardTitle>
              <CardDescription>
                Probability calibrator status across the season
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
                <Stat label="Brier" value="0.18" hint="lower is better" />
                <Stat label="Log-loss" value="0.42" />
                <Stat label="Calibration" value="applied" tone="positive" hint="≥3 rounds in history" />
                <Stat label="Drift" value="0.08" hint="PSI rolling 12-round" />
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
