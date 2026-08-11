"""CLI: print the IMSA WeatherTech forecast for the next (or a given) round, per class.

Human-readable sibling of :mod:`imsa_predictions.export` (which writes the website
JSON). Handy for a quick look at what the model says.

    PYTHONPATH=src python -m imsa_predictions.predict            # next round
    PYTHONPATH=src python -m imsa_predictions.predict --round 5
"""
from __future__ import annotations

import argparse

from . import config
from .datasource import ImsaDataSource
from .model import forecast_round


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--round", type=int, default=None, help="round to forecast (default: next)")
    ap.add_argument("--year", type=int, default=config.SEASON)
    ap.add_argument("--top", type=int, default=6, help="entries to show per class")
    args = ap.parse_args()

    source = ImsaDataSource()
    rnd = args.round or config.next_round()
    fc = forecast_round(source, args.year, rnd)

    print(f"\n{config.SPORT} {args.year} — Round {rnd}: {fc.place} "
          f"({fc.country or 'TBA'})\n")
    for cf in fc.classes:
        print(f"  {config.class_label(cf.cls)}")
        for pos, code in enumerate(cf.order[:args.top], start=1):
            meta = config.ENTRY_META.get(code, {})
            name = f"#{meta.get('number', '?')} {meta.get('team', '')}".strip()
            pwin = cf.markets.p_win.get(code, 0.0)
            ppod = cf.markets.p_podium.get(code, 0.0)
            print(f"    {pos:>2}. {name:<34} win {pwin:5.1%}  podium {ppod:5.1%}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# Backwards-compatible alias (the scaffold exported ``SportPredictor``). The IMSA
# backend forecasts per-class via :mod:`imsa_predictions.model`; this thin shim
# keeps the scaffold's import contract satisfied.
from motorsport_core.interfaces import Predictor, RoundForecast as _CoreRoundForecast  # noqa: E402
from motorsport_core.interfaces import Venue as _Venue  # noqa: E402


class ImsaPredictor(Predictor):
    def fit(self, source: ImsaDataSource, season: int, upto_round: int) -> None:  # noqa: D401
        return None

    def predict(self, source: ImsaDataSource, season: int, round: int) -> _CoreRoundForecast:
        fc = forecast_round(source, season, round)
        # flatten the per-class orders into a single ranked map (class-blocked)
        order: dict[str, int] = {}
        pos = 1
        for cf in fc.classes:
            for code in cf.order:
                order[code] = pos
                pos += 1
        return _CoreRoundForecast(
            season=season, round=round,
            venue=_Venue(key=str(fc.place), name=str(fc.event)),
            predicted_order=order,
        )


SportPredictor = ImsaPredictor
