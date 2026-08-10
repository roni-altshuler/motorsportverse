"use client";

/**
 * Rally narrative card — WRC adaptation of the F1 flagship's RaceNarrativeCard.
 * Same idea: 2-4 auto-generated bullets describing what the model "sees" for a
 * rally, derived from a tiny rule engine with no per-round editorial work.
 *
 * The rules are built around the data WRC actually has (there is no weather
 * feed and no per-stage timing in the snapshot — those are deliberately absent
 * rather than faked):
 *
 *   1. Favourite shape — who leads the win market and by how much (open vs
 *      locked-in rally), from the round's classification.
 *   2. Surface angle — the defining variable of world rally: which surface this
 *      round is run on (gravel / tarmac / snow).
 *   3. Championship stakes — leader's title probability and how many crews are
 *      still mathematically alive (upcoming rounds only; the championship block
 *      reflects the season as it stands today, not as of a past round).
 *   4. Post-rally verdict — for completed rounds, how the forecast actually
 *      scored (winner call, podium overlap, typical miss).
 */
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { surfaceLabel } from "@/lib/surface";
import type { RoundDetail, TitleOdds } from "@/types/wrc";

interface NarrativeBullet {
  text: string;
  tone: "live" | "positive" | "negative" | "info" | "default";
  label: string;
}

const OPEN_RACE_P = 0.14; // no clear favourite below this win probability
const LOCKED_RACE_P = 0.3; // strong favourite above this
const TITLE_GRIP_P = 0.75; // "one hand on the title"

const SURFACE_NOTE: Record<string, string> = {
  gravel: "loose, ever-changing gravel rewards a clean read of the road and punishes an early road position.",
  tarmac: "sealed tarmac rewards precision and grip over the rough-road pace that wins on gravel.",
  snow: "studded tyres on snow and ice make this the most specialist round on the calendar.",
};

function buildBullets(round: RoundDetail, championship: TitleOdds[]): NarrativeBullet[] {
  const out: NarrativeBullet[] = [];
  const block = round.rally;
  const cls = block.classification ?? [];

  // 1. Favourite shape from the win market. Classification is ordered by
  //    predicted finish, which need not match the win market — rank by pWin.
  if (cls.length >= 2) {
    const [top, second] = [...cls].sort((a, b) => b.pWin - a.pWin);
    const a = (top.pWin * 100).toFixed(0);
    const b = (second.pWin * 100).toFixed(0);
    if (top.pWin >= LOCKED_RACE_P) {
      out.push({
        label: "MODEL",
        tone: "live",
        text: `${top.name} is the clear rally favourite at ${a}% — nobody else clears ${b}%.`,
      });
    } else if (top.pWin < OPEN_RACE_P) {
      out.push({
        label: "MODEL",
        tone: "info",
        text: `Wide-open rally: ${top.name} leads the win market at just ${a}%, with ${second.name} right behind on ${b}%.`,
      });
    } else {
      out.push({
        label: "MODEL",
        tone: "live",
        text: `Model favours ${top.name} (${a}%) over ${second.name} (${b}%) for the rally win.`,
      });
    }
  }

  // 2. Surface angle — the single biggest driver of who is fast in world rally.
  const surface = (round.surface ?? block.surface ?? "").toLowerCase();
  const note = SURFACE_NOTE[surface];
  if (surface) {
    out.push({
      label: "SURFACE",
      tone: "info",
      text: `Run on ${surfaceLabel(surface).toLowerCase()}${note ? ` — ${note}` : "."}`,
    });
  }

  // 3. Championship stakes — only for the upcoming round (the championship
  //    block is a live season projection, not a per-round archive).
  if (!round.completed && championship.length > 0) {
    const leader = championship[0];
    const alive = championship.filter((t) => t.canStillWin).length;
    if (leader.pTitle >= TITLE_GRIP_P) {
      out.push({
        label: "TITLE",
        tone: "positive",
        text: `${leader.name} has one hand on the title (${(leader.pTitle * 100).toFixed(0)}% on ${leader.currentPoints} pts); ${alive} crews remain mathematically alive.`,
      });
    } else if (championship.length >= 2) {
      const rival = championship[1];
      out.push({
        label: "TITLE",
        tone: "default",
        text: `Title fight: ${leader.name} (${(leader.pTitle * 100).toFixed(0)}%) vs ${rival.name} (${(rival.pTitle * 100).toFixed(0)}%), ${alive} crews still mathematically in it.`,
      });
    }
  }

  // 4. Post-rally verdict from the stored accuracy block.
  const acc = block.accuracy;
  if (round.completed && acc && (acc.n ?? 0) > 0) {
    const winner = acc.winner_hit ? "called the winner" : "missed the winner";
    const podium =
      typeof acc.podium_hits === "number" ? `${acc.podium_hits}/3 of the podium` : null;
    const miss =
      typeof acc.mean_position_error === "number"
        ? `typical miss ${acc.mean_position_error.toFixed(1)} places`
        : null;
    out.push({
      label: "VERDICT",
      tone: acc.winner_hit ? "positive" : "default",
      text: `The rally forecast ${winner}${podium ? `, had ${podium}` : ""}${miss ? ` — ${miss}` : ""}.`,
    });
  }

  return out.slice(0, 4);
}

export default function RaceNarrativeCard({
  round,
  championship = [],
}: {
  round: RoundDetail | null;
  championship?: TitleOdds[];
}) {
  if (!round) return null;
  const bullets = buildBullets(round, championship);
  if (bullets.length === 0) return null;
  return (
    <Card className="mb-6">
      <CardHeader className="gap-2">
        <Badge variant="live" className="self-start">
          What The Model Sees
        </Badge>
        <CardTitle className="text-xl">Auto-generated rally angles</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {bullets.map((b, i) => (
          <div
            key={i}
            className="flex items-start gap-3 rounded-[var(--radius-md)] border border-[var(--hairline)] bg-[var(--surface-2)] p-3"
          >
            <Badge variant={b.tone} className="mt-0.5 shrink-0 text-[10px]">
              {b.label}
            </Badge>
            <p className="text-sm leading-snug text-[var(--ink-muted)]">{b.text}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
