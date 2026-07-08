"use client";

/**
 * Race-weekend narrative card — NASCAR adaptation of the F1 flagship's
 * RaceNarrativeCard. Same idea: 2-4 auto-generated bullets describing what the
 * model "sees" this weekend, derived from a tiny rule engine with no per-round
 * editorial work.
 *
 * The rules are rebuilt around the data the Cup export actually has (there is
 * no weather feed and no caution model in the snapshot — those F1 rules are
 * deliberately absent rather than faked):
 *
 *   1. Favourite shape — who leads the win market and by how much (open vs
 *      locked-in race), from the round's classification.
 *   2. Track framing — the four Cup archetypes read very differently
 *      (superspeedway pack racing vs intermediate aero racing vs short-track
 *      contact vs road courses).
 *   3. DNF risk — the model carries a first-class per-driver DNF hazard; when
 *      the favourite's hazard is elevated (superspeedway wrecks, mostly), say so.
 *   4. Stakes — playoff framing on Chase rounds; otherwise championship /
 *      playoff-cut stakes for upcoming regular-season rounds.
 *   5. Post-race verdict — for completed rounds, how the forecast scored.
 */
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { TRACK_TYPE_BLURB, trackTypeLabel } from "@/lib/track";
import type { RoundDetail, TitleOdds } from "@/types/nascar";

interface NarrativeBullet {
  text: string;
  tone: "live" | "positive" | "negative" | "info" | "default";
  label: string;
}

const OPEN_RACE_P = 0.1; // no clear favourite below this win probability (40-car fields)
const LOCKED_RACE_P = 0.25; // strong favourite above this
const TITLE_GRIP_P = 0.6; // "one hand on the title"
const HIGH_DNF_P = 0.15; // elevated retirement hazard worth flagging

function buildBullets(
  round: RoundDetail,
  championship: TitleOdds[],
  isPlayoff: boolean,
): NarrativeBullet[] {
  const out: NarrativeBullet[] = [];
  const cls = round.race.classification ?? [];

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
        text: `${top.name} is the clear favourite at ${a}% — nobody else clears ${b}%.`,
      });
    } else if (top.pWin < OPEN_RACE_P) {
      out.push({
        label: "MODEL",
        tone: "info",
        text: `Wide-open race: ${top.name} leads the win market at just ${a}%, with ${second.name} right behind on ${b}%.`,
      });
    } else {
      out.push({
        label: "MODEL",
        tone: "live",
        text: `Model favours ${top.name} (${a}%) over ${second.name} (${b}%).`,
      });
    }

    // 3. DNF-risk read on the favourite — the hazard is a first-class model
    //    component, and on the drafting tracks it reshapes the whole forecast.
    if (typeof top.pDnf === "number" && top.pDnf >= HIGH_DNF_P && !round.completed) {
      out.push({
        label: "DNF RISK",
        tone: "negative",
        text: `${top.name} carries a ${(top.pDnf * 100).toFixed(0)}% retirement hazard here — ${
          round.trackType === "superspeedway"
            ? "superspeedway wrecks don't care who was fastest"
            : "a finish is not a given even for the favourite"
        } — which is why the projected range stays wide.`,
      });
    }
  }

  // 2. Track framing — the four Cup archetypes.
  const blurb = TRACK_TYPE_BLURB[round.trackType];
  if (blurb) {
    out.push({
      label: trackTypeLabel(round.trackType).toUpperCase(),
      tone: "info",
      text: `${round.venueName} is ${
        round.trackType === "intermediate" ? "an" : "a"
      } ${trackTypeLabel(round.trackType).toLowerCase()} — ${blurb}.`,
    });
  }

  // 4. Stakes — playoff framing on Chase rounds beats the season-long read.
  if (isPlayoff && !round.completed) {
    out.push({
      label: "PLAYOFFS",
      tone: "live",
      text: `A Chase playoff round — the championship picture, not just the race win, moves on every stage point scored here.`,
    });
  } else if (!round.completed && championship.length > 0) {
    const leader = championship[0];
    const alive = championship.filter((t) => t.canStillWin).length;
    if (leader.pTitle >= TITLE_GRIP_P) {
      out.push({
        label: "TITLE",
        tone: "positive",
        text: `${leader.name} has one hand on the title (${(leader.pTitle * 100).toFixed(0)}% on ${leader.currentPoints} pts); ${alive} drivers remain mathematically alive in the regular season.`,
      });
    } else if (championship.length >= 2) {
      const rival = championship[1];
      out.push({
        label: "TITLE",
        tone: "default",
        text: `Title fight: ${leader.name} (${(leader.pTitle * 100).toFixed(0)}%) vs ${rival.name} (${(rival.pTitle * 100).toFixed(0)}%), ${alive} drivers still mathematically in it.`,
      });
    }
  }

  // 5. Post-race verdict from the stored accuracy block.
  const acc = round.race.accuracy;
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
      text: `The forecast ${winner}${podium ? `, had ${podium}` : ""}${miss ? ` — ${miss}` : ""}.`,
    });
  }

  return out.slice(0, 4);
}

export default function RaceNarrativeCard({
  round,
  championship = [],
  isPlayoff = false,
}: {
  round: RoundDetail | null;
  championship?: TitleOdds[];
  isPlayoff?: boolean;
}) {
  if (!round) return null;
  const bullets = buildBullets(round, championship, isPlayoff);
  if (bullets.length === 0) return null;
  return (
    <Card className="mb-6">
      <CardHeader className="gap-2">
        <Badge variant="live" className="self-start">
          What The Model Sees
        </Badge>
        <CardTitle className="text-xl">Auto-generated weekend angles</CardTitle>
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
