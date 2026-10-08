"""Original synthetic Session fixtures; no telemetry cache/provider is read."""
from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import export_local_capture as exporter


class Event(dict):
    year = 2025


def synthetic_session():
    car = pd.DataFrame({
        "SessionTime": pd.to_timedelta([102, 100, 100, 101], unit="s"),
        "Time": pd.to_timedelta([2, 0, 0, 1], unit="s"),
        "Source": ["car", "car", "car", "interpolation"],
        "Speed": [np.nan, 123, 124, 125], "RPM": [np.nan, 9000, 9100, 9200],
        "Throttle": [104, 0, 50, 100], "nGear": [np.nan, 0, 4, 5],
        "Brake": [None, False, np.bool_(True), "false"],
    })
    pos = pd.DataFrame({
        "SessionTime": pd.to_timedelta([101, 100, 103], unit="s"),
        "Time": pd.to_timedelta([1, 0, 3], unit="s"),
        "Source": ["pos", "pos", "pos"],
        "X": [np.nan, 125, 130], "Y": [50, -250, 70],
    })
    return SimpleNamespace(
        event=Event(RoundNumber=1), name="Race", car_data={"1": car}, pos_data={"1": pos},
        get_driver=lambda number: {"Abbreviation": "AAA", "FullName": "Original Sample Driver",
                                   "TeamColor": "ABCDEF"},
    )


def capture(session=None, **extra):
    args = dict(driver="1", season=2025, round_number=1, session_name="Race",
                start_s=100, end_s=102, software_version="synthetic")
    return exporter.capture_from_session(session or synthetic_session(), **(args | extra))


def messages(text):
    return [json.loads(line) for line in text.splitlines()]


def test_independent_clocks_order_duplicates_units_and_determinism():
    text = capture()
    assert text == capture()
    data = messages(text)
    assert [d["frame"]["t"] for d in data] == [100, 100, 100, 101, 101, 102]
    assert [d["frame_index"] for d in data] == list(range(6))
    samples = [d["frame"]["drivers"]["AAA"] for d in data]
    assert [s["sample_source"] for s in samples] == ["car", "car", "pos", "interpolation", "pos", "car"]
    assert samples[0]["x"] is None  # no nearest/forward-filled position on car timestamps
    assert samples[2]["x"] == 12.5 and samples[2]["y"] == -25
    assert samples[2]["telemetry"] is None  # no nearest/forward-filled car channels
    assert samples[4]["x"] is None and samples[4]["y"] is None
    assert all(d["driver_colors"] == {"AAA": "#ABCDEF"} for d in data)
    assert all("track_geometry" not in d for d in data)
    assert "NaN" not in text and "weather" not in text
    meta = data[0]["capture_metadata"]
    assert meta["coordinate_units"] == "metres"
    assert meta["time_basis"] == "session-relative-seconds"
    assert meta["data_rights"] == "not-certified"


def test_brake_is_boolean_not_pressure_and_missing_values_remain_null():
    samples = [d["frame"]["drivers"]["AAA"] for d in messages(capture())]
    assert samples[0]["telemetry"]["brake"] is False
    assert samples[1]["telemetry"]["brake"] is True
    assert samples[3]["telemetry"]["brake"] is None
    assert samples[5]["telemetry"] == dict(speed_kph=None, rpm=None, throttle_pct=None,
                                          gear=None, brake=None)
    assert samples[0]["telemetry"]["gear"] == 0
    assert samples[0]["telemetry"]["throttle_pct"] == 0


@pytest.mark.parametrize("field,value", [("season", 2024), ("round_number", 2),
                                          ("session_name", "Qualifying")])
def test_identity_mismatch_fails_closed(field, value):
    with pytest.raises(ValueError, match="identity"):
        capture(**{field: value})


@pytest.mark.parametrize("start,end", [(0, 121), (102, 100), (float("nan"), 102)])
def test_window_bounds(start, end):
    with pytest.raises(ValueError, match="window"):
        capture(start_s=start, end_s=end)


def test_no_slice_time_fallback_or_unknown_source():
    session = synthetic_session()
    session.pos_data["1"] = session.pos_data["1"].drop(columns="SessionTime")
    with pytest.raises(ValueError, match="SessionTime"):
        capture(session)
    session = synthetic_session()
    session.car_data["1"].loc[1, "Source"] = "pos"
    with pytest.raises(ValueError, match="Source"):
        capture(session)


def test_empty_missing_time_and_frame_byte_bounds(monkeypatch):
    session = synthetic_session()
    session.car_data["1"]["SessionTime"] = pd.NaT
    session.pos_data.clear()
    with pytest.raises(ValueError, match="Invalid SessionTime"):
        capture(session)
    session.car_data.clear()
    with pytest.raises(ValueError, match="No native"):
        capture(session)
    monkeypatch.setattr(exporter, "MAX_FRAMES", 5)
    with pytest.raises(ValueError, match="shorter window"):
        capture()
    monkeypatch.setattr(exporter, "MAX_FRAMES", 2000)
    monkeypatch.setattr(exporter, "MAX_BYTES", 100)
    with pytest.raises(ValueError, match="4 MiB"):
        capture()


def test_offline_cache_enabled_before_lookup_and_no_live_loading(tmp_path, monkeypatch):
    calls = []
    session = synthetic_session()
    session.load = lambda **kw: calls.append(("load", kw))
    fake = SimpleNamespace(
        Cache=SimpleNamespace(enable_cache=lambda path: calls.append(("cache", path)),
                              offline_mode=lambda enabled: calls.append(("offline", enabled))),
        get_session=lambda *args, **kwargs: (calls.append(("get_session", args, kwargs)) or session),
        __version__="synthetic",
    )
    monkeypatch.setitem(sys.modules, "fastf1", fake)
    result, version = exporter.load_cached_session(tmp_path, 2025, 1, "Race")
    assert result is session and version == "synthetic"
    assert [c[0] for c in calls] == ["cache", "offline", "get_session", "load"]
    assert calls[1] == ("offline", True)
    assert calls[2][2] == {"backend": "fastf1"}
    assert calls[3][1] == dict(laps=False, telemetry=True, weather=False, messages=False)


def test_cli_keeps_output_outside_git_and_never_overwrites(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    output = tmp_path / "capture.ndjson"
    monkeypatch.setattr(exporter, "load_cached_session", lambda *args: (synthetic_session(), "synthetic"))
    argv = ["--cache", str(cache), "--output", str(output), "--season", "2025",
            "--round", "1", "--session", "Race", "--driver", "1", "--start", "100",
            "--end", "102", "--acknowledge-data-terms"]
    assert exporter.main(argv) == 0
    assert output.read_text() == capture()
    with pytest.raises(SystemExit):
        exporter.main(argv)
    assert output.read_text() == capture()
    repo = tmp_path / "worktree"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: elsewhere")
    with pytest.raises(ValueError, match="outside"):
        exporter._outside_git(repo / "public" / "capture.ndjson")
    link = tmp_path / "alias"
    link.symlink_to(repo, target_is_directory=True)
    with pytest.raises(ValueError, match="outside"):
        exporter._outside_git(link / "capture.ndjson")


def test_installed_fastf1_empty_cache_cannot_send_network_requests(tmp_path):
    if importlib.util.find_spec("fastf1") is None:
        pytest.skip("Optional FastF1 dependency is unavailable; fake Session converter tests still run")
    # Isolate FastF1's process-global cache setting. A real empty cache read is
    # exercised, but every network send is denied before any request can leave.
    program = '''
import sys, requests
from export_local_capture import load_cached_session
attempts = []
def denied(*args, **kwargs):
    attempts.append(True)
    raise AssertionError("Network send prohibited")
requests.Session.send = denied
try:
    load_cached_session(sys.argv[1], 2025, 1, "Race")
except Exception:
    pass
else:
    raise AssertionError("An empty cache must not yield a session")
assert not attempts, "Offline cache miss attempted network I/O"
'''
    result = subprocess.run([sys.executable, "-c", program, str(tmp_path)],
                            cwd=exporter.Path(exporter.__file__).parent,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
