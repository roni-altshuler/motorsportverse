"""Winner correctness must never substitute shared P2 for an absent original P1."""
import json

import pytest

from advanced_models import SeasonTracker


@pytest.mark.parametrize("predicted,actual,expected", [
    ({"A": 1, "B": 2}, {"A": 1, "B": 2}, True),
    ({"A": 1, "B": 2}, {"C": 1, "B": 2}, False),
    ({"B": 2}, {"B": 2}, None),
    ({"A": 1, "B": 2}, {"B": 2}, None),
    ({"B": 2}, {"A": 1, "B": 2}, None),
    ({"A": 1, "B": 1}, {"A": 1, "B": 2}, None),
    ({"A": 1, "B": 2}, {"A": 1, "B": 1}, None),
])
def test_original_unique_p1_is_required_before_grading(predicted, actual, expected):
    tracker = SeasonTracker.__new__(SeasonTracker)
    tracker.data = {"rounds": {"1": {
        "predicted": {driver: {"position": position} for driver, position in predicted.items()},
        "actual": {driver: {"position": position} for driver, position in actual.items()},
    }}, "accuracy": {}}
    report = tracker.get_round_report(1)
    assert report is not None
    assert report["winnerHit"] is expected


@pytest.mark.parametrize("flags,hits,settled,percentage", [
    ([True, False, None], 1, 2, 50.0),
    ([None], 0, 0, None),
    ([], 0, 0, None),
])
def test_export_uses_scored_winner_denominator_without_rewriting_forecasts(
        tmp_path, monkeypatch, flags, hits, settled, percentage):
    import baselines
    import export_website_data as export

    monkeypatch.setattr(export, "DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(export, "PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(baselines, "compute_season_baselines", lambda *_args: {})
    export._write_gp_accuracy_report({
        "overallAccuracy": {"roundsWithActual": len(flags)},
        "gpReports": [{"round": i + 1, "winnerHit": flag} for i, flag in enumerate(flags)],
    })
    overall = json.loads((tmp_path / "data/gp_accuracy_report.json").read_text())["overallAccuracy"]
    assert overall["seasonWinnerHits"] == hits
    assert overall["seasonWinnerRoundsScored"] == settled
    assert overall["seasonWinnerHitPct"] == percentage
    if None in flags:
        assert "Not scored" in (tmp_path / "reports/season_accuracy_report.md").read_text()
