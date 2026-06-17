"""Phase 2 honest calibration gate: off on synthetic, on once real rounds exist."""

import json

from f2_predictions import config, export
from f2_predictions.datasource import F2DataSource
from f2_predictions.sources import CompositeF2Source, SyntheticF2Source


class _FakeRealSource:
    """Serves the synthetic order but tagged as a real feed, to exercise the gate."""

    name = "fastf1"  # in CompositeF2Source.REAL_SOURCES

    def __init__(self):
        self._syn = SyntheticF2Source()

    def results(self, year, round, race_index=1):
        res = self._syn.results(year, round, race_index)
        return res if res else None


def _live_real_source() -> F2DataSource:
    src = F2DataSource(live=True)
    src._source = CompositeF2Source([_FakeRealSource(), SyntheticF2Source()])
    return src


def test_gate_closed_on_synthetic():
    calibrator, real_rounds = export.build_calibrator(F2DataSource(), config.SEASON)
    assert calibrator is None
    assert real_rounds == 0


def test_gate_opens_once_enough_real_rounds():
    calibrator, real_rounds = export.build_calibrator(_live_real_source(), config.SEASON)
    assert real_rounds == config.COMPLETED_ROUNDS
    assert real_rounds >= config.MIN_REAL_ROUNDS_FOR_CALIBRATION
    assert calibrator is not None
    assert calibrator.is_fitted()


def test_export_reports_calibration_applied_with_real_data(tmp_path, monkeypatch):
    # Make export.write use the real-tagged source.
    monkeypatch.setattr(export, "F2DataSource", _live_real_source)
    export.write(tmp_path)

    summary = json.loads((tmp_path / "calibration_summary.json").read_text())
    assert summary["applied"] is True
    assert summary["trainingRounds"] == config.COMPLETED_ROUNDS

    probs = json.loads((tmp_path / "probabilities" / "round_08.json").read_text())
    assert probs["calibration"]["applied"] is True
    # Every market still carries both the calibrated and the raw probability.
    win = next(iter(probs["feature"]["markets"]["win"].values()))
    assert "probability" in win and "rawProbability" in win
