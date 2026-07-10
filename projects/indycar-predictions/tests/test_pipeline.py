"""Pipeline: standings (points AS AWARDED), championship, round predictions."""
from __future__ import annotations

from indycar_predictions import config, pipeline

SEASON = config.SEASON


def test_official_standings_match_summed_awarded_points(real_source):
    """The curated official grid and the per-race awarded-points sum must
    agree — the same verification the curation pipeline enforced (2026 has
    zero point residuals per data/CURATION_REPORT.md)."""
    official = pipeline.official_standings(real_source, SEASON)
    assert official is not None
    summed = pipeline.awarded_points_by_driver(real_source, SEASON)
    for row in official:
        assert abs(summed.get(row["code"], 0.0) - row["points"]) <= 0.5, row["code"]


def test_current_points_leader_is_palou(real_source):
    pts = pipeline.current_driver_points(real_source, SEASON)
    assert max(pts, key=pts.get) == "ALPALOU"
    assert pts["ALPALOU"] == 404.0


def test_project_title_shape_and_leader(real_source):
    rows = pipeline.project_title(real_source, SEASON, n_samples=500)
    assert rows and rows[0].p_title == max(r.p_title for r in rows)
    assert abs(sum(r.p_title for r in rows) - 1.0) < 1e-6
    leader = rows[0]
    assert leader.key == "ALPALOU"  # 56-point lead with 7 to run
    assert leader.p_title > 0.3
    assert leader.proj_mean >= leader.current_points  # points only accumulate
    # Indy-500-only scorers stay in the simulation (they hold points).
    keys = {r.key for r in rows}
    assert "CODALY" in keys or "TASATO" in keys


def test_predict_round_compact_projection(real_source):
    pred = pipeline.predict_round(real_source, SEASON, 12, n_samples=500)
    assert pred.round == 12 and pred.venue_key == "nashville-superspeedway"
    assert len(pred.race_order) == len(set(pred.race_order))
    assert abs(sum(pred.p_win.values()) - 1.0) < 0.02


def test_standings_fallback_without_snapshot():
    """Synthetic-only runs fall back to recomputed (base-table) standings."""
    from indycar_predictions.datasource import IndycarDataSource
    from indycar_predictions.sources.synthetic import SyntheticIndycarSource

    source = IndycarDataSource(source=SyntheticIndycarSource())
    assert pipeline.official_standings(source, SEASON) is None
    pts = pipeline.current_driver_points(source, SEASON)
    assert pts and max(pts.values()) > 0
