"""Phase 2 honest calibration gate: off on synthetic, on once real rounds exist."""

import json

from f3_predictions import config, export
from f3_predictions.datasource import F3DataSource
from f3_predictions.sources import CompositeF3Source, SyntheticF3Source


class _FakeRealSource:
    """Serves the synthetic order but tagged as a real feed, to exercise the gate."""

    name = "fastf1"  # in CompositeF3Source.REAL_SOURCES

    def __init__(self):
        self._syn = SyntheticF3Source()

    def results(self, year, round, race_index=1):
        res = self._syn.results(year, round, race_index)
        return res if res else None


def _live_real_source() -> F3DataSource:
    src = F3DataSource(live=True)
    src._source = CompositeF3Source([_FakeRealSource(), SyntheticF3Source()])
    return src


def test_gate_closed_on_synthetic():
    # A synthetic-only source is never treated as real → gate stays closed.
    synthetic = F3DataSource(source=SyntheticF3Source())
    calibrator, real_rounds = export.build_calibrator(synthetic, config.SEASON)
    assert calibrator is None
    assert real_rounds == 0


def test_gate_open_on_real_snapshot():
    # The default source serves the committed real snapshot, so the gate opens.
    calibrator, real_rounds = export.build_calibrator(F3DataSource(), config.SEASON)
    assert real_rounds == config.COMPLETED_ROUNDS
    assert calibrator is not None and calibrator.is_fitted()


def test_gate_opens_once_enough_real_rounds():
    calibrator, real_rounds = export.build_calibrator(_live_real_source(), config.SEASON)
    assert real_rounds == config.COMPLETED_ROUNDS
    assert real_rounds >= config.MIN_REAL_ROUNDS_FOR_CALIBRATION
    assert calibrator is not None
    assert calibrator.is_fitted()


def test_export_reports_calibration_applied_with_real_data(tmp_path, monkeypatch):
    # Make export.write use the real-tagged source.
    monkeypatch.setattr(export, "F3DataSource", _live_real_source)
    export.write(tmp_path)

    summary = json.loads((tmp_path / "calibration_summary.json").read_text())
    assert summary["applied"] is True
    assert summary["trainingRounds"] == config.COMPLETED_ROUNDS

    probs = json.loads((tmp_path / "probabilities" / "round_08.json").read_text())
    assert probs["calibration"]["applied"] is True
    # Every market still carries both the calibrated and the raw probability.
    win = next(iter(probs["feature"]["markets"]["win"].values()))
    assert "probability" in win and "rawProbability" in win
