"""IndyCar Predictions — snapshot-primary IndyCar forecasting on the
MotorsportVerse core.

IndyCar has no public results API, so the committed, human-verified
``data/history_<year>.json`` files are the source of truth; live scraping is
only a strictly-validated refresh mechanism (see ``refresh.py``). The model's
dominant split is a dual oval / road-street Elo with a first-class,
track-type-aware DNF hazard.
"""

__version__ = "0.2.0"
SPORT = "IndyCar"
