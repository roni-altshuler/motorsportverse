"use client";

/**
 * Race-weekend narrative card — Formula E adaptation of the F1 flagship's
 * RaceNarrativeCard. Same idea: 2-4 auto-generated bullets describing what the
 * model "sees" this weekend, derived from a tiny rule engine with no per-round
 * editorial work.
 *
 * The rules are rebuilt around the data Formula E actually has (there is no
 * weather feed, no safety-car model, no energy telemetry in the snapshot —
 * those F1 rules are deliberately absent rather than faked):
 *
 *   1. Favourite shape — who leads the win market and by how much (open vs
 *      locked-in race), from the round's classification.
 *   2. Venue framing — street E-Prix vs permanent circuit, and doubleheader
 *      context ("second race of the Jeddah weekend") when the venue hosts two
 *      rounds back-to-back.
 *   3. Championship stakes — leader's title probability and how many drivers
 *      are still mathematically alive (upcoming rounds only; the championship
 *      block reflects the season as it stands today, not as of a past round).
 *   4. Post-race verdict — for completed rounds, how the forecast actually
 *      scored (winner call, podium overlap, typical miss).
 */
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import type { RoundDetail, TitleOdds } from "@/types/fe";

interface NarrativeBullet {
  text: string;
  tone: "live" | "positive" | "negative" | "info" | "default";
  label: string;
}

const OPEN_RACE_P = 0.14; // no clear favourite below this win probability
const LOCKED_RACE_P = 0.3; // strong favourite above this
const TITLE_GRIP_P = 0.75; // "one hand on the title"

function buildBullets(
  round: RoundDetail,
  championship: TitleOdds[],
  doubleheader: { race: number; of: number } | null,
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
  }

  // 2. Venue framing — doubleheader context first (it's the sharper angle),
  //    otherwise the street-vs-circuit read.
  const baseVenue = round.venueName.replace(/\s+II$/, "");
  if (doubleheader) {
    const which = doubleheader.race === 1 ? "first" : "second";
    const carry =
      doubleheader.race === 1
        ? "form shown here carries straight into the second race"
        : "drivers arrive with a race's worth of reads on these exact corners";
    out.push({
      label: "DOUBLEHEADER",
      tone: "info",
      text: `The ${which} race of the ${baseVenue} doubleheader weekend — ${carry}, on a ${
        round.venueKind === "street" ? "walled street layout" : "permanent circuit"
      }.`,
    });
  } else if (round.venueKind === "street") {
    out.push({
      label: "STREET",
      tone: "info",
      text: `${round.venueName} is a walled street E-Prix — grid position and clean racecraft count for more here, and the forecast ranges widen accordingly.`,
    });
  } else {
    out.push({
      label: "CIRCUIT",
      tone: "info",
      text: `${round.venueName} runs on a permanent circuit — more overtaking room than the street venues, so race pace can recover a poor grid slot.`,
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
        text: `${leader.name} has one hand on the title (${(leader.pTitle * 100).toFixed(0)}% on ${leader.currentPoints} pts); ${alive} drivers remain mathematically alive.`,
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

  // 4. Post-race verdict from the stored accuracy block.
  const acc = round.race.accuracy;
  if (round.completed && acc && (acc.n ?? 0) > 0) {
    const winner = acc.winner_hit
      ? "called the winner"
      : "missed the winner";
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
  doubleheader = null,
}: {
  round: RoundDetail | null;
  championship?: TitleOdds[];
  doubleheader?: { race: number; of: number } | null;
}) {
  if (!round) return null;
  const bullets = buildBullets(round, championship, doubleheader);
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
