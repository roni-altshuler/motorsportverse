"use client";

/**
 * Race-weekend narrative card (B-P1.3).
 *
 * Auto-generates 2-4 bullet points describing what the model "sees" this
 * weekend.  No manual editorial work per round — bullets are derived from
 * the per-round JSON's circuitInfo, weatherData, classification, and
 * modelConfig fields using a tiny rule engine.
 *
 * Examples of generated bullets:
 *   - "Quali gaps are tight: P1→P10 within 1.2s of pole."
 *   - "Elevated safety-car risk (75%) — pace gaps may not survive R1."
 *   - "Wet conditions expected (rain probability 65%) — INTER strategy."
 *   - "Race simulator favours VER (34%) over NOR (27%) and LEC (18%)."
 */
import type { RoundData } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

interface NarrativeBullet {
  text: string;
  tone: "live" | "positive" | "negative" | "info" | "default";
  label: string;
}

const WET_RAIN_THRESHOLD = 0.45;
const HIGH_SC_THRESHOLD = 0.6;
const TIGHT_QUALI_S = 1.4;
const WIDE_QUALI_S = 3.5;

function buildBullets(round: RoundData): NarrativeBullet[] {
  const out: NarrativeBullet[] = [];

  // 1. Race simulator headline (highest priority when present).
  const simulator = (round as unknown as { modelConfig?: { raceSimulator?: { applied?: boolean } } })
    .modelConfig?.raceSimulator;
  const cls = round.classification ?? [];
  if (simulator?.applied && cls.length >= 3) {
    const topRow = cls[0] as unknown as { driver: string; simulatorWinProbability?: number };
    const p2 = cls[1] as unknown as { driver: string; simulatorWinProbability?: number };
    if (typeof topRow.simulatorWinProbability === "number") {
      const a = (topRow.simulatorWinProbability * 100).toFixed(0);
      const b =
        typeof p2.simulatorWinProbability === "number"
          ? (p2.simulatorWinProbability * 100).toFixed(0)
          : null;
      out.push({
        label: "MODEL",
        tone: "live",
        text: `Race simulator favours ${topRow.driver} (${a}%)${
          b ? ` over ${p2.driver} (${b}%)` : ""
        }.`,
      });
    }
  }

  // 2. Weather signal.
  const w = round.weatherData;
  if (w) {
    const rain = w.rainProbability ?? 0;
    if (rain >= WET_RAIN_THRESHOLD) {
      out.push({
        label: "WEATHER",
        tone: "info",
        text: `Wet conditions expected (rain probability ${Math.round(
          rain * 100,
        )}%). Inters/full-wets likely in play.`,
      });
    } else if (rain > 0.15) {
      out.push({
        label: "WEATHER",
        tone: "default",
        text: `Mixed forecast: ${Math.round(
          rain * 100,
        )}% rain probability with ${w.temperatureC ?? "—"}°C at the track.`,
      });
    }
  }

  // 3. Safety-car risk.
  const scLikelihood = round.circuitInfo?.safetyCarLikelihood;
  if (typeof scLikelihood === "number" && scLikelihood >= HIGH_SC_THRESHOLD) {
    out.push({
      label: "SC RISK",
      tone: "negative",
      text: `Elevated safety-car risk (${Math.round(
        scLikelihood * 100,
      )}%) — pace gaps may not survive race 1.`,
    });
  }

  // 4. Quali-gap shape.
  if (cls.length >= 10) {
    const topTime = (cls[0] as unknown as { predictedTime: number }).predictedTime;
    const p10Time = (cls[9] as unknown as { predictedTime: number }).predictedTime;
    if (typeof topTime === "number" && typeof p10Time === "number") {
      const spread = p10Time - topTime;
      if (spread <= TIGHT_QUALI_S) {
        out.push({
          label: "PACE",
          tone: "live",
          text: `Tight quali gaps: P1→P10 within ${spread.toFixed(2)}s of pole.`,
        });
      } else if (spread >= WIDE_QUALI_S) {
        out.push({
          label: "PACE",
          tone: "info",
          text: `Wide pace dispersion: ${spread.toFixed(1)}s from P1 to P10. Strategy matters more than usual.`,
        });
      }
    }
  }

  // 5. Tyre degradation / strategy hint.
  const tyreDeg = round.circuitInfo?.tyreDeg;
  const expectedStops = round.circuitInfo?.expectedStops;
  if (typeof tyreDeg === "number" && tyreDeg >= 0.65) {
    out.push({
      label: "TYRES",
      tone: "info",
      text: `High thermal degradation expected (${tyreDeg.toFixed(2)} index)${
        expectedStops ? ` — model targets ${expectedStops} stops` : ""
      }.`,
    });
  }

  return out.slice(0, 4);
}

export default function RaceNarrativeCard({ round }: { round: RoundData | null }) {
  if (!round) return null;
  const bullets = buildBullets(round);
  if (bullets.length === 0) return null;
  return (
    <Card className="mb-6">
      <CardHeader className="gap-2">
        <Badge variant="live" className="self-start">What The Model Sees</Badge>
        <CardTitle className="text-xl">Auto-generated weekend angles</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {bullets.map((b, i) => (
          <div key={i} className="flex items-start gap-3 rounded-[8px] border border-[color:var(--border)] bg-[color:var(--surface-elevated)] p-3">
            <Badge variant={b.tone} className="shrink-0 mt-0.5 text-[10px]">
              {b.label}
            </Badge>
            <p className="text-sm text-[color:var(--text-secondary)] leading-snug">
              {b.text}
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
