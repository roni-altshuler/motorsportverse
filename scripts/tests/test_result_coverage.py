"""Regression: a no-work poll must not hide old, unimported calendar rounds."""
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "check_result_coverage.py"
spec = importlib.util.spec_from_file_location("coverage_audit", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def summary(*entries):
    return {"season": 2026, "generatedAt": "2026-10-06T12:00:00Z", "calendar": list(entries)}


def entry(rnd, date="2026-10-03", completed=False, key="featureDate"):
    return {"round": rnd, key: date, "completed": completed}


def test_old_gap_is_detected_even_with_later_import_and_fresh_export():
    report = module.audit(summary(entry(1), entry(2, completed=True), entry(3, "2026-12-06")),
                          datetime(2026, 10, 6, tzinfo=timezone.utc))
    assert report["pastDueRounds"] == [1]
    assert report["importedRounds"] == [2]
    assert report["sourceAvailability"] == "not checked"


@pytest.mark.parametrize("key", ["featureDate", "raceDate"])
def test_full_race_day_and_48_hour_grace(key):
    data = summary(entry(1, key=key))
    assert module.audit(data, datetime(2026, 10, 5, 23, 59, tzinfo=timezone.utc))["pastDueRounds"] == []
    assert module.audit(data, datetime(2026, 10, 6, tzinfo=timezone.utc))["pastDueRounds"] == [1]


def test_invalid_date_is_unknown_not_fresh_and_all_imported_is_not_source_verified():
    assert module.audit(summary(entry(1, "bad")), datetime.now(timezone.utc))["status"] == "unknown"
    report = module.audit(summary(entry(1, completed=True)), datetime.now(timezone.utc))
    assert report["status"] == "no-past-due-gaps"
    assert report["sourceAvailability"] == "not checked"


@pytest.mark.parametrize("data", [summary(), summary(entry(1), entry(1))])
def test_invalid_calendar_is_rejected(data):
    with pytest.raises(ValueError):
        module.audit(data, datetime.now(timezone.utc))


def test_cli_fails_for_stale_no_work_poll_and_writes_summary(tmp_path):
    data = tmp_path / "data.json"
    data.write_text(json.dumps(summary(entry(1))))
    job_summary = tmp_path / "summary.md"
    import os
    result = subprocess.run([sys.executable, str(SCRIPT), "f2", "--data", str(data),
                             "--as-of", "2026-10-06T00:00:00Z"], capture_output=True, text=True,
                            env={**os.environ, "GITHUB_STEP_SUMMARY": str(job_summary)})
    assert result.returncode == 1
    assert '"pastDueRounds": [\n    1' in result.stdout
    assert "Source availability not checked" in job_summary.read_text()


def test_no_overdue_work_returns_success_and_bad_input_fails(tmp_path):
    data = tmp_path / "data.json"
    data.write_text(json.dumps(summary(entry(1, "2026-12-06"))))
    command = [sys.executable, str(SCRIPT), "indycar", "--data", str(data),
               "--as-of", "2026-10-06T00:00:00Z"]
    assert subprocess.run(command, capture_output=True).returncode == 0
    data.write_text("broken")
    assert subprocess.run(command, capture_output=True).returncode == 2


@pytest.mark.parametrize("series", ["f2", "f3", "indycar"])
def test_workflow_audits_even_when_predict_job_has_no_work_or_fails(series):
    text = (SCRIPT.parents[1] / f".github/workflows/{series}-update-predictions.yml").read_text()
    job = text.split("\n  coverage:\n", 1)[1].split("\n  deploy:\n", 1)[0]
    assert "    needs: predict\n    if: always()" in job
    assert "ref: ${{ github.ref }}" in job
    assert f"run: python scripts/check_result_coverage.py {series}" in job
    assert "continue-on-error" not in job
    assert "should_run" not in job
    assert "\n  deploy:\n    needs: predict" in text


@pytest.mark.parametrize("series", ["f2", "f3", "indycar"])
def test_source_failure_can_return_no_work_but_cannot_hide_past_due_coverage(series, monkeypatch):
    # Reproduce the existing boolean gate's failure path without any network.
    # The independent audit must still report a known coverage gap.
    import importlib
    monkeypatch.syspath_prepend(str(SCRIPT.parents[1] / f"projects/{series}-predictions/src"))
    weekend = importlib.import_module(f"{series}_predictions.race_weekend")
    monkeypatch.setattr(weekend, "_live_source", lambda: None)
    assert weekend.check_work_pending(1, 2026) is False
    report = module.audit(summary(entry(1)), datetime(2026, 10, 6, tzinfo=timezone.utc))
    assert report["status"] == "past-due"
    assert report["pastDueRounds"] == [1]
