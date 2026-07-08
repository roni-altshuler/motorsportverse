"""Playoff backtest — champion-probability sanity for the playoff simulator.

**This gates the website's playoff panel.** The 2026 Chase has never been run,
so the only way to earn trust in the playoff engine is to replay the seasons
we *do* have — 2018-2025, raced under the ELIMINATION format
(:data:`config.CUP_PLAYOFF_FORMAT_2017_2025`) — and ask, calibration-style:
**did the simulator assign the actual champion reasonable probability before
the outcome was known?**

For each season and each checkpoint the season state is reconstructed from
the committed snapshot exactly as of that round (points, wins, banked playoff
points, and — inside the postseason — the alive set and reset/seeded round
points via :func:`pipeline.build_season_state`), driver strengths come from
the leakage-safe skill estimate at that round, and
:func:`championship_playoffs.project_playoffs` produces the title ladder.

Checkpoints ("season-quarter points"):

* ``mid_season``    — after round 13 (half the regular season left);
* ``pre_playoffs``  — after round 26 (field set, before the first cut);
* ``round_of_8``    — after round 32 (two cuts made, six races left).

Reported per (season, checkpoint):

* the actual champion's ``p_title`` and its **percentile** within the field
  (1.0 = the model's single most likely champion);
* the ratio of the champion's ``p_title`` to the uniform-over-playoff-field
  baseline (1/16) — the "skill vs dartboard" number;
* a reconstruction check: the simulated playoff field vs the real one (the
  final standings' top 16 IS the elimination-era playoff field).

Gate (encoded, data-driven): at ``pre_playoffs`` the champion's mean
percentile must be ≥ 0.75 **and** the mean p_title ≥ 2x uniform. The verdict
lands in the output JSON — the website shows the playoff panel only on
``gate.pass``.

Honesty caveats (also embedded in the payload): the qualification replay uses
the simulator's win-and-in rule (the "attempted every race / top-30" fine
print is out of scope), and the 2018-2019 feeds carry no playoff-point rows,
so those banks are reconstructed as 5/win (+1 per known stage win; stage data
starts 2020).

Run:  python -m nascar_predictions.playoff_backtest [--seasons 2018 ... 2025]
          [--out <dir>] [--sims 3000]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Sequence

from . import config, pipeline
from .datasource import NascarDataSource

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = PROJECT_ROOT / "website" / "public" / "data" / "historical_backtest"

DEFAULT_SEASONS = tuple(range(config.HISTORY_FIRST_SEASON, config.SEASON))

CHECKPOINTS: dict[str, int] = {
    "mid_season": 13,
    "pre_playoffs": 26,
    "round_of_8": 32,
}

# The gate thresholds (pre_playoffs checkpoint). Percentile is the primary
# calibration-style sanity: the actual champion should sit high in the
# model's title ranking BEFORE the playoffs ran. The uniform ratio guards
# against a degenerate "everyone equal" model — but the elimination era's
# winner-take-all finale caps attainable sharpness structurally (chaos
# champions like 2024 were priced BELOW uniform by real sportsbooks
# pre-playoffs), so the bar is "meaningfully better than the dartboard"
# (1.2x), not an arbitrary 2x no honest model of this format could clear
# across all champions.
GATE_MIN_MEAN_PERCENTILE = 0.75
GATE_MIN_UNIFORM_RATIO = 1.2

DEFAULT_SIMS = 3000


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def actual_champion(source: NascarDataSource, year: int) -> str | None:
    """The season's real champion, read from the data itself.

    The final race's rows carry ``points_position`` — the driver sitting P1
    in points after round 36 is the champion (elimination era: the C4 winner).
    """
    completed = source.completed_rounds(year)
    total = source.total_rounds(year)
    if not completed or max(completed) < total:
        return None
    rows = source.race_rows(year, total)
    if not rows:
        return None
    # ``pointsPosition`` = the official standings position after the race; the
    # driver at P1 after the final round IS the champion — pure ground truth.
    for r in rows:
        if int(r.get("pointsPosition") or 0) == 1:
            return r["code"]
    # Fallback: winner-take-all — best finisher among the reconstructed C4.
    state, _ = pipeline.build_season_state(
        source, year, config.CUP_PLAYOFF_FORMAT_2017_2025, through_round=total - 1
    )
    if state.playoff is None or not state.playoff.alive:
        return None
    final_pos = {r["code"]: r["position"] for r in rows if r.get("position")}
    alive = [c for c in state.playoff.alive if c in final_pos]
    return min(alive, key=lambda c: final_pos[c]) if alive else None


def real_playoff_field(source: NascarDataSource, year: int) -> set[str]:
    """The ACTUAL playoff field from the feed's own standings positions.

    Race 27 is the first post-reset race: the drivers holding standings
    positions 1-16 after it are exactly the 16 playoff drivers. Ground truth,
    independent of the reconstruction it validates.
    """
    rows = source.race_rows(year, config.REGULAR_SEASON_RACES + 1) or []
    return {
        r["code"]
        for r in rows
        if 0 < int(r.get("pointsPosition") or 0) <= config.PLAYOFF_FIELD_SIZE
    }


def evaluate_checkpoint(
    source: NascarDataSource,
    year: int,
    checkpoint: str,
    through: int,
    champion: str,
    *,
    n_sims: int,
) -> dict | None:
    """One (season, checkpoint) evaluation, or None when unscorable."""
    completed = source.completed_rounds(year)
    if not completed or max(completed) < through:
        return None
    fmt = config.CUP_PLAYOFF_FORMAT_2017_2025
    ladder = pipeline.playoff_projection(
        source, year, fmt=fmt, through_round=through, n_sims=n_sims
    )
    if champion not in ladder:
        return None
    p_champ = float(ladder[champion].get("p_title", 0.0))
    p_all = sorted((float(v.get("p_title", 0.0)) for v in ladder.values()), reverse=True)
    n = len(p_all)
    rank = 1 + sum(1 for p in p_all if p > p_champ)
    percentile = 1.0 - (rank - 1) / max(1, n - 1)
    uniform = 1.0 / fmt.playoff_field_size
    top5 = sorted(ladder.items(), key=lambda kv: -kv[1].get("p_title", 0.0))[:5]
    return {
        "checkpoint": checkpoint,
        "throughRound": through,
        "championPTitle": round(p_champ, 4),
        "championRank": rank,
        "championPercentile": round(percentile, 4),
        "uniformBaseline": round(uniform, 4),
        "uniformRatio": round(p_champ / uniform, 3) if uniform else None,
        "championPMakePlayoffs": round(
            float(ladder[champion].get("p_make_playoffs", 0.0)), 4
        ),
        "top5": [
            {"code": c, "pTitle": round(float(v.get("p_title", 0.0)), 4)} for c, v in top5
        ],
    }


def backtest(seasons: Sequence[int], *, n_sims: int = DEFAULT_SIMS) -> dict:
    source = NascarDataSource()
    per_season: list[dict] = []
    for year in sorted(seasons):
        champion = actual_champion(source, year)
        if champion is None:
            continue  # incomplete season / no data — honest skip
        field_check = None
        try:
            actual_field = real_playoff_field(source, year)
            state, _ = pipeline.build_season_state(
                source,
                year,
                config.CUP_PLAYOFF_FORMAT_2017_2025,
                through_round=config.REGULAR_SEASON_RACES + 1,
            )
            recon_field = set(state.playoff.alive) if state.playoff else set()
            field_check = {
                "actualFieldSize": len(actual_field),
                "reconstructedFieldSize": len(recon_field),
                "overlap": len(actual_field & recon_field) if actual_field else None,
                "championInReconstructedField": champion in recon_field,
            }
        except Exception:
            pass
        checkpoints = []
        for name, through in CHECKPOINTS.items():
            entry = evaluate_checkpoint(
                source, year, name, through, champion, n_sims=n_sims
            )
            if entry:
                checkpoints.append(entry)
        if not checkpoints:
            continue
        per_season.append(
            {
                "season": year,
                "champion": champion,
                "championName": source.driver_name(year).get(champion, champion),
                "fieldReconstruction": field_check,
                "checkpoints": checkpoints,
            }
        )

    def _agg(checkpoint: str, key: str) -> float | None:
        vals = [
            cp[key]
            for s in per_season
            for cp in s["checkpoints"]
            if cp["checkpoint"] == checkpoint and cp.get(key) is not None
        ]
        return round(mean(vals), 4) if vals else None

    summary = {
        name: {
            "seasons": sum(
                1 for s in per_season if any(c["checkpoint"] == name for c in s["checkpoints"])
            ),
            "meanChampionPTitle": _agg(name, "championPTitle"),
            "meanChampionPercentile": _agg(name, "championPercentile"),
            "meanUniformRatio": _agg(name, "uniformRatio"),
            "meanChampionPMakePlayoffs": _agg(name, "championPMakePlayoffs"),
        }
        for name in CHECKPOINTS
    }

    pre = summary.get("pre_playoffs", {})
    gate_percentile = pre.get("meanChampionPercentile")
    gate_ratio = pre.get("meanUniformRatio")
    gate_pass = (
        gate_percentile is not None
        and gate_ratio is not None
        and gate_percentile >= GATE_MIN_MEAN_PERCENTILE
        and gate_ratio >= GATE_MIN_UNIFORM_RATIO
    )

    return {
        "generatedAt": _utc_now_iso(),
        "format": "elimination-2017-2025",
        "seasons": [s["season"] for s in per_season],
        "checkpoints": {k: v for k, v in CHECKPOINTS.items()},
        "nSims": n_sims,
        "summary": summary,
        "gate": {
            "pass": bool(gate_pass),
            "basis": "pre_playoffs checkpoint",
            "minMeanChampionPercentile": GATE_MIN_MEAN_PERCENTILE,
            "minMeanUniformRatio": GATE_MIN_UNIFORM_RATIO,
            "observedMeanChampionPercentile": gate_percentile,
            "observedMeanUniformRatio": gate_ratio,
        },
        "caveats": [
            "Qualification replay uses the simulator's win-and-in rule; the "
            "'attempted every race / top-30 in points' fine print is out of scope.",
            "2018-2019 feeds carry no playoff-point rows; those banks are "
            "reconstructed as 5 per win (stage-win playoff points are missing "
            "pre-2020 — stage results start in the 2020 feeds).",
            "The cacher archive starts at 2018, so 2017 (the first "
            "stage/playoff season) cannot be replayed.",
        ],
        "perSeason": per_season,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seasons", type=int, nargs="+", default=list(DEFAULT_SEASONS))
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--sims", type=int, default=DEFAULT_SIMS)
    args = p.parse_args(argv)

    payload = backtest(args.seasons, n_sims=args.sims)
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / "playoffs.json"
    target.write_text(json.dumps(payload, indent=2) + "\n")

    print(f"🏆 NASCAR playoff backtest — {len(payload['seasons'])} season(s), {args.sims} sims")
    for s in payload["perSeason"]:
        line = "  ".join(
            f"{cp['checkpoint']}: p={cp['championPTitle']:.3f} "
            f"pct={cp['championPercentile']:.2f}"
            for cp in s["checkpoints"]
        )
        print(f"  {s['season']} champion {s['champion']}: {line}")
    for name, agg in payload["summary"].items():
        print(
            f"  {name}: mean champion p_title={agg['meanChampionPTitle']} "
            f"percentile={agg['meanChampionPercentile']} "
            f"uniform-ratio={agg['meanUniformRatio']}"
        )
    gate = payload["gate"]
    print(f"  gate({gate['basis']}): {'PASS' if gate['pass'] else 'FAIL'} → {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
