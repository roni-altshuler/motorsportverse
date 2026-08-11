"""CLI: print the FIA WEC forecast for the next (or a given) round, per class.

Human-readable sibling of :mod:`wec_predictions.export` (which writes the website
JSON). Handy for a quick look at what the model says.

    PYTHONPATH=src python -m wec_predictions.predict            # next round
    PYTHONPATH=src python -m wec_predictions.predict --round 5
"""
from __future__ import annotations

import argparse

from . import config
from .datasource import WecDataSource
from .model import forecast_round


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--round", type=int, default=None, help="round to forecast (default: next)")
    ap.add_argument("--year", type=int, default=config.SEASON)
    ap.add_argument("--top", type=int, default=6, help="entries to show per class")
    args = ap.parse_args()

    source = WecDataSource()
    rnd = args.round or config.next_round()
    fc = forecast_round(source, args.year, rnd)

    print(f"\n{config.SPORT} {args.year} — Round {rnd}: {fc.place} "
          f"({fc.country or 'TBA'})\n")
    for cf in fc.classes:
        print(f"  {config.class_label(cf.cls)}")
        for pos, code in enumerate(cf.order[:args.top], start=1):
            meta = config.ENTRY_META.get(code, {})
            name = f"#{meta.get('number','?')} {meta.get('team','')}".strip()
            pwin = cf.markets.p_win.get(code, 0.0)
            ppod = cf.markets.p_podium.get(code, 0.0)
            print(f"    {pos:>2}. {name:<34} win {pwin:5.1%}  podium {ppod:5.1%}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
