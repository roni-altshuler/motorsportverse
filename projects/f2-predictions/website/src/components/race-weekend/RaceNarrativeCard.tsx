"use client";

/**
 * Race-weekend narrative card — F2 adaptation of the F1 flagship's
 * RaceNarrativeCard (B-P1.3). Same idea: 2-4 auto-generated bullets describing
 * what the model "sees" this weekend, derived from a tiny rule engine with no
 * per-round editorial work.
 *
 * The rules are rebuilt around the data F2 actually has (there is no weather
 * feed, no safety-car model, no tyre data in the snapshot — those F1 rules are
 * deliberately absent rather than faked):
 *
 *   1. Favourite shape — who leads the win market and by how much (open vs
 *      locked-in race), from the round's classification.
 *   2. Reverse-grid sprint context — where the top qualifiers start the sprint
 *      and how far the model expects the fastest of them to recover.
 *   3. Championship stakes — leader's title probability and how many drivers
 *      are still mathematically alive (upcoming rounds only; the championship
 *      block reflects the season as it stands today, not as of a past round).
 *   4. Post-race verdict — for completed rounds, how the forecast actually
 *      scored (winner call, podium overlap, typical miss).
 */
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import type { RoundDetail, TitleOdds } from "@/types/f2";

type RaceKey = "feature" | "sprint";

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
  race: RaceKey,
  championship: TitleOdds[],
): NarrativeBullet[] {
  const out: NarrativeBullet[] = [];
  const block = round[race];
  const cls = block.classification ?? [];
  const raceLabel = race === "feature" ? "feature race" : "sprint";

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
        text: `${top.name} is the clear ${raceLabel} favourite at ${a}% — nobody else clears ${b}%.`,
      });
    } else if (top.pWin < OPEN_RACE_P) {
      out.push({
        label: "MODEL",
        tone: "info",
        text: `Wide-open ${raceLabel}: ${top.name} leads the win market at just ${a}%, with ${second.name} right behind on ${b}%.`,
      });
    } else {
      out.push({
        label: "MODEL",
        tone: "live",
        text: `Model favours ${top.name} (${a}%) over ${second.name} (${b}%) in the ${raceLabel}.`,
      });
    }
  }

  // 2. Reverse-grid sprint context: the top feature qualifier starts deep in
  //    the flipped pack — how far does the model see them recovering?
  if (race === "sprint" && round.feature.grid.length > 0) {
    const poleCode = round.feature.grid[0].code;
    const sprintStart = block.grid.find((g) => g.code === poleCode);
    const forecast = cls.find((e) => e.code === poleCode);
    if (sprintStart && sprintStart.position > 1 && forecast) {
      out.push({
        label: "GRID FLIP",
        tone: "info",
        text: `Reverse grid buries top qualifier ${forecast.name} at P${sprintStart.position}; the model sees a recovery to around P${Math.round(forecast.meanFinish)} (range P${forecast.finishRangeLow}–P${forecast.finishRangeHigh}).`,
      });
    }
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
  const acc = block.accuracy;
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
      text: `The ${raceLabel} forecast ${winner}${podium ? `, had ${podium}` : ""}${miss ? ` — ${miss}` : ""}.`,
    });
  }

  return out.slice(0, 4);
}

export default function RaceNarrativeCard({
  round,
  race,
  championship = [],
}: {
  round: RoundDetail | null;
  race: RaceKey;
  championship?: TitleOdds[];
}) {
  if (!round) return null;
  const bullets = buildBullets(round, race, championship);
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
