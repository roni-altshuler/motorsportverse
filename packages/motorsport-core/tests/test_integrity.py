"""Tests for the published-data integrity checks.

Each test names the real failure the check exists to catch. A check whose test
only proves it runs is a check that will be deleted the first time it is
inconvenient.
"""
from __future__ import annotations

import json

import pytest

from motorsport_core import integrity


def _findings(findings, check):
    return [f for f in findings if f.check == check]


def _failed(findings, check):
    return [f for f in _findings(findings, check) if not f.ok]


# --------------------------------------------------------------------------- #
# round file contiguity
# --------------------------------------------------------------------------- #


def test_a_missing_round_is_a_hole_not_a_shorter_season(tmp_path):
    for rnd in (1, 2, 4):
        (tmp_path / f"round_{rnd:02d}.json").write_text(json.dumps({"round": rnd}))
    findings = integrity.check_round_files_contiguous(tmp_path, tmp_path, "rounds")
    assert _failed(findings, "round_files_contiguous")
    assert "[3]" in _failed(findings, "round_files_contiguous")[0].message


def test_a_file_that_lies_about_its_own_round_number_fails(tmp_path):
    (tmp_path / "round_01.json").write_text(json.dumps({"round": 1}))
    (tmp_path / "round_02.json").write_text(json.dumps({"round": 7}))
    findings = integrity.check_round_files_contiguous(tmp_path, tmp_path, "rounds")
    failures = _failed(findings, "round_files_contiguous")
    assert any("declares round 7" in f.message for f in failures)


def test_contiguous_rounds_pass(tmp_path):
    for rnd in (1, 2, 3):
        (tmp_path / f"round_{rnd:02d}.json").write_text(json.dumps({"round": rnd}))
    findings = integrity.check_round_files_contiguous(tmp_path, tmp_path, "rounds")
    assert not _failed(findings, "round_files_contiguous")


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _held_f1_season(data_dir):
    """R18 settles after two explicit holds; R19–23 remain unscored previews."""
    calendar = []
    for number in range(1, 24):
        entry = {
            "round": number, "name": f"Race {number}", "gpKey": f"GP{number}",
            "circuit": f"Circuit {number}", "date": f"2026-01-{number:02d}",
        }
        calendar.append(entry)
        state = dict(entry, classification=[{"code": "AAA", "position": 1}])
        if number in (16, 17):
            state["classification"] = []
            state["publicationHold"] = {
                "reason": "no-pre-race-forecast" if number == 16 else "event-mismatch",
                "message": "No usable pre-race forecast; no prediction grade.",
                "reviewedAt": "2026-10-11T05:15:33Z",
                "sourceUrl": "https://www.formula1.com/en/racing/2026",
            }
        _write_json(data_dir / "rounds" / f"round_{number:02d}.json", state)
        _write_json(data_dir / "probabilities" / f"round_{number:02d}.json", {"round": number})
        if number <= 18 and number not in (16, 17):
            _write_json(data_dir / "forward_eval" / f"round_{number:02d}.json", {
                "round": number, "baselines": {"last_race": {"mean_position_error": 1}},
            })
    _write_json(data_dir / "season.json", {
        "calendar": calendar, "completedRounds": list(range(1, 19)),
        "forecastRounds": [n for n in range(1, 24) if n not in (16, 17)],
    })


def test_only_explicit_holds_exempt_forward_eval_and_previews_need_no_grade(tmp_path):
    _held_f1_season(tmp_path)
    report = integrity.check_published_data(tmp_path)
    assert report.ok, report.failures
    assert _findings(report.findings, "forecast_exclusions")
    assert not any((tmp_path / "forward_eval" / f"round_{n:02d}.json").exists()
                   for n in range(19, 24))


def test_a_genuinely_missing_r14_still_fails_between_verified_holds(tmp_path):
    _held_f1_season(tmp_path)
    (tmp_path / "forward_eval/round_14.json").unlink()
    report = integrity.check_published_data(tmp_path)
    assert any("rounds [14]" in f.message for f in report.failures)


def test_omitting_r14_from_availability_cannot_excuse_its_missing_grade(tmp_path):
    _held_f1_season(tmp_path)
    path = tmp_path / "season.json"
    summary = json.loads(path.read_text())
    summary["forecastRounds"].remove(14)
    _write_json(path, summary)
    path = tmp_path / "rounds/round_14.json"
    state = json.loads(path.read_text())
    state["classification"] = []
    _write_json(path, state)
    (tmp_path / "forward_eval/round_14.json").unlink()
    report = integrity.check_published_data(tmp_path)
    assert any("rounds [14]" in f.message for f in report.failures)


@pytest.mark.parametrize("number", [16, 17])
def test_a_withheld_round_cannot_retain_a_grade(tmp_path, number):
    _held_f1_season(tmp_path)
    _write_json(tmp_path / "forward_eval" / f"round_{number:02d}.json", {
        "round": number, "baselines": {"last_race": {"mean_position_error": 1}},
    })
    report = integrity.check_published_data(tmp_path)
    assert any("grade despite an explicit forecast hold" in f.message for f in report.failures)


@pytest.mark.parametrize("manifest", [None, [1, True], [1, "18"], [1, 1], [24], [1]])
def test_invalid_availability_manifest_grants_no_exceptions(tmp_path, manifest):
    _held_f1_season(tmp_path)
    path = tmp_path / "season.json"
    summary = json.loads(path.read_text())
    summary["forecastRounds"] = manifest
    _write_json(path, summary)
    report = integrity.check_published_data(tmp_path)
    assert _failed(report.findings, "forecast_exclusions")
    assert any("rounds [16, 17]" in f.message for f in report.failures)


@pytest.mark.parametrize("mutation", ["absent", "unreadable", "no_manifest"])
def test_missing_coverage_metadata_retains_strict_continuity(tmp_path, mutation):
    _held_f1_season(tmp_path)
    path = tmp_path / "season.json"
    if mutation == "absent":
        path.unlink()
    elif mutation == "unreadable":
        path.write_text("not json")
    else:
        summary = json.loads(path.read_text())
        del summary["forecastRounds"]
        _write_json(path, summary)
    report = integrity.check_published_data(tmp_path)
    assert any("rounds [16, 17]" in f.message for f in report.failures)


@pytest.mark.parametrize("mutation", ["hold", "reason", "reason_type", "identity", "ranking", "listed"])
def test_inconsistent_hold_metadata_fails_closed(tmp_path, mutation):
    _held_f1_season(tmp_path)
    path = tmp_path / "rounds/round_16.json"
    state = json.loads(path.read_text())
    if mutation == "hold":
        state["publicationHold"] = {}
    elif mutation == "reason":
        state["publicationHold"]["reason"] = "unknown"
    elif mutation == "reason_type":
        state["publicationHold"]["reason"] = []
    elif mutation == "identity":
        state["gpKey"] = "Wrong event"
    elif mutation == "ranking":
        state["classification"] = [{"code": "AAA", "position": 1}]
    else:
        summary_path = tmp_path / "season.json"
        summary = json.loads(summary_path.read_text())
        summary["forecastRounds"].append(16)
        _write_json(summary_path, summary)
    _write_json(path, state)
    report = integrity.check_published_data(tmp_path)
    assert _failed(report.findings, "forecast_exclusions")
    assert any("rounds [16, 17]" in f.message for f in report.failures)


@pytest.mark.parametrize("url", [
    "https://", "http://", "https:// bad host", "https:///results", "https://bad_host/results",
    "https://example..com/results", "https://-bad.example/results", "https://example.com:bad/results",
    "https://example.com:65536/results", "https://[invalid]/results", "https://example.com/\nresults",
])
def test_malformed_hold_source_urls_grant_no_exclusions(tmp_path, url):
    _held_f1_season(tmp_path)
    path = tmp_path / "rounds/round_16.json"
    state = json.loads(path.read_text())
    state["publicationHold"]["sourceUrl"] = url
    _write_json(path, state)
    report = integrity.check_published_data(tmp_path)
    assert _failed(report.findings, "forecast_exclusions")
    assert any("rounds [16, 17]" in f.message for f in report.failures)


@pytest.mark.parametrize("url", [
    "https://www.formula1.com/en/racing/2026/bahrain",
    "https://www.formula1.com/en/racing/2026/singapore",
])
def test_existing_hold_source_urls_remain_valid_without_network_access(tmp_path, url):
    _held_f1_season(tmp_path)
    path = tmp_path / "rounds/round_16.json"
    state = json.loads(path.read_text())
    state["publicationHold"]["sourceUrl"] = url
    _write_json(path, state)
    report = integrity.check_published_data(tmp_path)
    assert report.ok, report.failures


@pytest.mark.parametrize("stream", ["forward_eval", "rounds", "probabilities"])
@pytest.mark.parametrize("content", ['{"round": 99}', 'not json'])
def test_verified_holds_do_not_hide_wrong_round_or_unreadable_files(tmp_path, stream, content):
    _held_f1_season(tmp_path)
    (tmp_path / stream / "round_14.json").write_text(content)
    report = integrity.check_published_data(tmp_path)
    failures = _failed(report.findings, "round_files_contiguous")
    assert any(f.path == f"{stream}/round_14.json" for f in failures)


@pytest.mark.parametrize("stream", ["rounds", "probabilities"])
def test_forward_eval_exceptions_never_relax_ordinary_streams(tmp_path, stream):
    _held_f1_season(tmp_path)
    (tmp_path / stream / "round_16.json").unlink()
    report = integrity.check_published_data(tmp_path)
    assert any(f.path == stream and "rounds [16]" in f.message for f in report.failures)


def test_r18_requires_a_baseline_despite_earlier_forecast_holds(tmp_path):
    _held_f1_season(tmp_path)
    _write_json(tmp_path / "forward_eval/round_18.json", {"round": 18})
    report = integrity.check_published_data(tmp_path)
    failures = _failed(report.findings, "baselines_published")
    assert any("[18]" in f.message for f in failures)


# --------------------------------------------------------------------------- #
# calendar ordering and future results
# --------------------------------------------------------------------------- #


def test_dates_that_go_backwards_are_caught():
    """Elo over an unordered stream reads the future and looks entirely normal."""
    payload = {
        "calendar": [
            {"round": 1, "raceDate": "2026-03-08"},
            {"round": 2, "raceDate": "2026-02-01"},
        ]
    }
    findings = integrity.check_calendar(payload, "season.json")
    assert _failed(findings, "chronological")


def test_a_future_round_marked_completed_is_a_wrong_event_write():
    payload = {"calendar": [{"round": 1, "raceDate": "2099-01-01", "completed": True}]}
    findings = integrity.check_calendar(payload, "season.json")
    assert _failed(findings, "no_future_results")


def test_a_future_round_not_marked_completed_is_just_the_schedule():
    payload = {"calendar": [{"round": 1, "raceDate": "2099-01-01", "completed": False}]}
    findings = integrity.check_calendar(payload, "season.json")
    assert not _failed(findings, "no_future_results")


def test_a_sprint_weekend_orders_on_its_earliest_session():
    payload = {
        "calendar": [
            {"round": 1, "sprintDate": "2026-03-07", "featureDate": "2026-03-08"},
            {"round": 2, "sprintDate": "2026-03-21", "featureDate": "2026-03-22"},
        ]
    }
    findings = integrity.check_calendar(payload, "season.json")
    assert not _failed(findings, "chronological")


# --------------------------------------------------------------------------- #
# competitor identity
# --------------------------------------------------------------------------- #


def test_a_repeated_driver_double_counts_points():
    payload = {"driverStandings": [
        {"position": 1, "code": "VER", "name": "Verstappen", "points": 100},
        {"position": 2, "code": "VER", "name": "Verstappen", "points": 90},
    ]}
    findings = integrity.check_competitors(payload, "f1.json")
    assert _failed(findings, "no_duplicate_competitors")


def test_the_same_name_in_two_different_tables_is_not_a_duplicate():
    """Red Bull is a team AND a manufacturer. Pooling tables invents duplicates."""
    payload = {
        "teamStandings": [{"position": 1, "team": "Red Bull", "points": 400}],
        "manufacturerStandings": [{"position": 1, "manufacturer": "Red Bull", "points": 400}],
    }
    findings = integrity.check_competitors(payload, "f1.json")
    assert not _failed(findings, "no_duplicate_competitors")


def test_a_tbd_bracket_slot_is_refused_as_a_competitor():
    payload = {"driverStandings": [
        {"position": 1, "code": "VER", "name": "Verstappen", "points": 100},
        {"position": 2, "code": "TBD", "name": "TBD", "points": 0},
    ]}
    findings = integrity.check_competitors(payload, "f1.json")
    assert _failed(findings, "no_placeholder_entrants")


def test_a_real_name_without_a_code_is_not_a_placeholder():
    """The fantasy projects carry names without codes; twelve were flagged once."""
    payload = {"driverStandings": [
        {"position": 1, "name": "Dash Calloway", "points": 100},
        {"position": 2, "name": "Nova Okafor", "points": 90},
    ]}
    findings = integrity.check_competitors(payload, "chrome-valley.json")
    assert not _failed(findings, "no_placeholder_entrants")


def test_standings_are_found_by_shape_not_by_key_name():
    """The flagship names its table `drivers`; every clone names it `driverStandings`."""
    payload = {"drivers": [{"position": 1, "code": "TBD", "name": "TBD", "points": 0}]}
    findings = integrity.check_competitors(payload, "season.json")
    assert _failed(findings, "no_placeholder_entrants")


# --------------------------------------------------------------------------- #
# probabilities
# --------------------------------------------------------------------------- #


def _market(values, key="probability"):
    return {f"D{i}": {key: v, "rawProbability": v} for i, v in enumerate(values)}


def test_a_win_market_that_does_not_sum_to_one_fails():
    """Per-competitor calibration breaks the simplex; the reader adds up to 160%."""
    payload = {"race": {"markets": {"win": _market([0.8, 0.5, 0.3])}}}
    findings = integrity.check_probabilities(payload, "probabilities/round_01.json")
    assert _failed(findings, "probability_mass")


def test_a_coherent_win_market_passes():
    payload = {"race": {"markets": {"win": _market([0.5, 0.3, 0.2])}}}
    findings = integrity.check_probabilities(payload, "probabilities/round_01.json")
    assert not _failed(findings, "probability_mass")


def test_podium_mass_is_three_not_one():
    payload = {"race": {"markets": {"podium": _market([0.9, 0.8, 0.7, 0.6])}}}
    findings = integrity.check_probabilities(payload, "probabilities/round_01.json")
    assert not _failed(findings, "probability_mass")


def test_a_probability_above_one_fails():
    payload = {"race": {"markets": {"win": _market([1.4, -0.4])}}}
    findings = integrity.check_probabilities(payload, "probabilities/round_01.json")
    assert _failed(findings, "probability_range")


def test_the_flagship_list_shape_is_checked_too():
    """F1 publishes markets as a LIST; a dict-only check silently skips it."""
    payload = {
        "markets": {
            "win": [
                {"driver": "VER", "probability": 0.8, "rawProbability": 0.5},
                {"driver": "NOR", "probability": 0.7, "rawProbability": 0.5},
            ]
        }
    }
    findings = integrity.check_probabilities(payload, "probabilities/round_01.json")
    assert _failed(findings, "probability_mass")


def test_a_market_with_no_fixed_set_size_is_left_alone():
    """`dnf` has no target sum — it is not a top-N set."""
    payload = {"race": {"markets": {"dnf": _market([0.3, 0.4, 0.9])}}}
    findings = integrity.check_probabilities(payload, "probabilities/round_01.json")
    assert not _failed(findings, "probability_mass")


# --------------------------------------------------------------------------- #
# baselines
# --------------------------------------------------------------------------- #


def test_round_one_needs_no_baseline_but_round_two_does(tmp_path):
    (tmp_path / "round_01.json").write_text(json.dumps({"round": 1}))
    (tmp_path / "round_02.json").write_text(json.dumps({"round": 2}))
    findings = integrity.check_baselines(tmp_path, tmp_path)
    failures = _failed(findings, "baselines_published")
    assert failures and "[2]" in failures[0].message


def test_a_baseline_on_every_later_round_passes(tmp_path):
    (tmp_path / "round_01.json").write_text(json.dumps({"round": 1}))
    (tmp_path / "round_02.json").write_text(
        json.dumps({"round": 2, "baselines": {"lastRace": {"mean_position_error": 6.0}}})
    )
    assert not _failed(integrity.check_baselines(tmp_path, tmp_path), "baselines_published")


def test_an_empty_baselines_block_does_not_count(tmp_path):
    (tmp_path / "round_02.json").write_text(json.dumps({"round": 2, "baselines": {"lastRace": {}}}))
    assert _failed(integrity.check_baselines(tmp_path, tmp_path), "baselines_published")


# --------------------------------------------------------------------------- #
# calibration gate
# --------------------------------------------------------------------------- #


def test_a_closed_gate_is_always_honest():
    findings = integrity.check_calibration_gate({"applied": False}, "calibration_summary.json")
    assert not _failed(findings, "calibration_gate_honest")


def test_a_gate_open_on_too_few_rounds_fails():
    payload = {"applied": True, "trainingRounds": 1}
    assert _failed(
        integrity.check_calibration_gate(payload, "calibration_summary.json"),
        "calibration_gate_honest",
    )


def test_a_gate_open_on_synthetic_data_fails():
    """Calibration is never claimed on synthetic data."""
    payload = {
        "applied": True,
        "trainingRounds": 9,
        "dataLimitation": "Runs on a synthetic source until real results land.",
    }
    assert _failed(
        integrity.check_calibration_gate(payload, "calibration_summary.json"),
        "calibration_gate_honest",
    )


def test_a_gate_open_on_real_rounds_passes():
    payload = {"applied": True, "trainingRounds": 9, "dataLimitation": "Calibrated on real results."}
    assert not _failed(
        integrity.check_calibration_gate(payload, "calibration_summary.json"),
        "calibration_gate_honest",
    )


# --------------------------------------------------------------------------- #
# season manifest and drift vocabulary
# --------------------------------------------------------------------------- #


def test_a_current_season_missing_from_available_fails():
    payload = {"current": 2027, "available": [2026]}
    assert _failed(integrity.check_seasons(payload, "seasons.json"), "season_manifest")


def test_a_season_cannot_be_current_and_archived():
    payload = {"current": 2026, "available": [2026], "archived": [2026]}
    assert _failed(integrity.check_seasons(payload, "seasons.json"), "season_manifest")


def test_an_unknown_drift_severity_is_a_silently_ignored_alarm():
    payload = {"featureDrift": [{"feature": "pWin", "severity": "critcal"}]}
    assert _failed(integrity.check_model_health(payload, "model_health.json"), "drift_vocabulary")


def test_known_drift_severities_pass():
    payload = {
        "featureDrift": [{"feature": "pWin", "severity": "alarm"}],
        "outputDrift": {"severity": "ok"},
    }
    assert not _failed(integrity.check_model_health(payload, "model_health.json"), "drift_vocabulary")


# --------------------------------------------------------------------------- #
# the runner
# --------------------------------------------------------------------------- #


def test_an_unpublished_project_is_skipped_not_failed(tmp_path):
    """A scaffolded series has no data. That is a maturity level, not a defect."""
    report = integrity.check_published_data(tmp_path / "missing", project="wec")
    assert report.ok is True
    assert report.skipped


def test_a_full_clean_tree_passes(tmp_path):
    data = tmp_path / "data"
    (data / "rounds").mkdir(parents=True)
    (data / "probabilities").mkdir()
    (data / "forward_eval").mkdir()

    (data / "series.json").write_text(json.dumps({
        "calendar": [{"round": 1, "raceDate": "2026-03-08", "completed": True}],
        "driverStandings": [{"position": 1, "code": "AAA", "name": "Driver A", "points": 25}],
    }))
    (data / "rounds" / "round_01.json").write_text(json.dumps({"round": 1}))
    (data / "probabilities" / "round_01.json").write_text(json.dumps(
        {"round": 1, "race": {"markets": {"win": _market([0.5, 0.3, 0.2])}}}
    ))
    (data / "forward_eval" / "round_01.json").write_text(json.dumps({"round": 1}))
    (data / "calibration_summary.json").write_text(json.dumps({"applied": False}))
    (data / "seasons.json").write_text(json.dumps({"current": 2026, "available": [2026]}))
    (data / "model_health.json").write_text(json.dumps({"outputDrift": {"severity": "ok"}}))

    report = integrity.check_published_data(data, project="series", root=tmp_path)
    assert report.ok, [str(f) for f in report.failures]
    assert report.findings


def test_the_report_serialises_its_failures(tmp_path):
    data = tmp_path / "data"
    (data / "rounds").mkdir(parents=True)
    (data / "rounds" / "round_01.json").write_text(json.dumps({"round": 1}))
    (data / "rounds" / "round_03.json").write_text(json.dumps({"round": 3}))
    report = integrity.check_published_data(data, project="series", root=tmp_path)
    payload = report.to_json()
    assert payload["ok"] is False
    assert payload["failures"][0]["check"] == "round_files_contiguous"
