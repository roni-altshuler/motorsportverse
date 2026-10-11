"""A withdrawn forecast needs an explicit, auditable pre-race release.

No scheduled caller supplies a review. A deliberate caller must pin the exact
official input snapshot and current model source, and the generation must use
those times and the full post-penalty grid. This does not assess model accuracy.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from event_identity import published_matches

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def model_code_sha256():
    """Pin the local Python implementation without claiming a fitted artifact."""
    files = sorted(path for directory in ("src", "models", "features")
                   for path in (PROJECT_ROOT / directory).rglob("*.py"))
    return _digest({str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in files})


def _time(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("timezone required")
        return stamp.astimezone(timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ValueError("publication hold: a valid UTC provenance timestamp is required") from exc


def official_input_snapshot(state):
    sessions = {session.get("key"): session for session in
                (state.get("weekendResults") or {}).get("sessions", [])}
    return {"event": {key: state.get(key) for key in ("round", "name", "gpKey", "circuit", "date")},
            "qualifying": sessions.get("qualifying"), "startingGrid": sessions.get("startingGrid")}


def prepare_reviewed_release(state, round_num, calendar, review, *, now=None):
    """Reject automatic generation; validate an explicit review before work."""
    if not state or not state.get("publicationHold"):
        if review is not None:
            raise ValueError("publication release requires an existing withdrawn forecast")
        return None
    if not isinstance(review, dict):
        raise ValueError("publication hold: automatic regeneration is blocked; an audited release is required")
    if not published_matches(state, round_num, calendar):
        raise ValueError("publication hold: reviewed snapshot has the wrong event identity")
    now = now or datetime.now(timezone.utc)
    start = _time(calendar[round_num].get("race_start_utc"))
    if now >= start:
        raise ValueError("publication hold: cannot release a new forecast after race start")
    snapshot = official_input_snapshot(state)
    if review.get("sourceSnapshotSha256") != _digest(snapshot):
        raise ValueError("publication hold: reviewed official input snapshot changed")
    if review.get("modelCodeSha256") != model_code_sha256():
        raise ValueError("publication hold: reviewed model implementation changed")
    if not str(review.get("reviewNote", "")).strip():
        raise ValueError("publication hold: an explicit audit note is required")
    reviewed_at = _time(review.get("reviewedAt"))
    original = state["publicationHold"].get("originalForecast") or {}
    if reviewed_at > now or reviewed_at <= _time(original.get("generatedAt", state.get("generatedAt"))):
        raise ValueError("publication hold: review must follow the withdrawn forecast and precede release")
    if reviewed_at < _time(state["publicationHold"].get("reviewedAt")):
        raise ValueError("publication hold: explicit review must follow the withdrawal")
    sources = []
    official_event = calendar[round_num].get("official_results_event")
    if not official_event:
        raise ValueError("publication hold: the official results event must be independently verified")
    official_base = f"https://www.formula1.com/en/results/{state['date'][:4]}/races/{official_event}"
    for key, suffix in (("qualifying", "/qualifying"), ("startingGrid", "/starting-grid")):
        session = snapshot.get(key) or {}
        source = str(session.get("sourceUrl", ""))
        if (session.get("status") != "official" or not session.get("rows")
                or session.get("source") not in {"Formula1.com", "Formula1.com official classification"}
                or source != official_base + suffix):
            raise ValueError("publication hold: verified official qualifying and starting grid are required")
        sources.append(source.removesuffix(suffix))
        captured_at = _time(session.get("fetchedAt") or session.get("verifiedAt") or state["weekendResults"].get("generatedAt"))
        if captured_at > reviewed_at or captured_at >= start:
            raise ValueError("publication hold: review must cover the source snapshot before race start")
        if captured_at <= _time(original.get("generatedAt", state.get("generatedAt"))):
            raise ValueError("publication hold: official inputs must be newer than the withdrawn forecast")
    if sources[0] != sources[1]:
        raise ValueError("publication hold: official sessions refer to different events")
    return {"snapshot": snapshot, "review": dict(review), "originalHold": state["publicationHold"],
            "raceStartUtc": start}


def validate_generated_inputs(release, qualifying_times, grid, merged):
    """Check values actually passed into the model, including penalty changes."""
    if release is None:
        return
    from f1_prediction_utils import _parse_laptime_to_seconds
    snapshot = release["snapshot"]
    expected_times = {}
    for row in snapshot["qualifying"]["rows"]:
        values = [_parse_laptime_to_seconds(row.get(k)) for k in ("q3", "q2", "q1")]
        values = [v for v in values if v is not None]
        if not values:
            values = [_parse_laptime_to_seconds(row.get("time"))]
            values = [v for v in values if v is not None]
        if values:
            expected_times[row["driver"]] = min(values)
    expected_grid = {row["driver"]: row["position"] for row in snapshot["startingGrid"]["rows"]}
    drivers = list(merged["Driver"])
    if (len(snapshot["startingGrid"]["rows"]) != len(drivers)
            or len(drivers) != len(set(drivers)) or set(expected_grid) != set(drivers)
            or sorted(expected_grid.values()) != list(range(1, len(drivers) + 1))):
        raise ValueError("publication hold: official grid must cover the entire generated field")
    qualifying_drivers = [row["driver"] for row in snapshot["qualifying"]["rows"]]
    if len(qualifying_drivers) != len(drivers) or set(qualifying_drivers) != set(drivers):
        raise ValueError("publication hold: official qualifying must cover the entire generated field")
    if (not expected_times or set(qualifying_times) != set(expected_times)
            or any(not math.isfinite(float(qualifying_times[d]))
                   or abs(float(qualifying_times[d]) - t) > 0.001 for d, t in expected_times.items())):
        raise ValueError("publication hold: generated qualifying inputs differ from the reviewed source")
    used_grid = merged.set_index("Driver")["QualifyingRank"].to_dict()
    if dict(grid) != expected_grid or used_grid != expected_grid:
        raise ValueError("publication hold: generation must use the verified post-penalty starting grid")


def release_provenance(release, generated_at, model_config, *, now=None):
    """A new release keeps the withdrawn claim separate and immutable."""
    now = now or datetime.now(timezone.utc)
    generated = _time(generated_at)
    review = release["review"]
    if model_code_sha256() != review["modelCodeSha256"]:
        raise ValueError("publication hold: model implementation changed during generation")
    if now >= release["raceStartUtc"] or not _time(review["reviewedAt"]) <= generated <= now:
        raise ValueError("publication hold: generation is outside the reviewed pre-race window")
    return {**review, "releasedAt": now.isoformat().replace("+00:00", "Z"),
            "generatedAt": generated_at, "modelConfigSha256": _digest(model_config),
            "withdrawnForecast": release["originalHold"].get("originalForecast"),
            "withdrawalReason": release["originalHold"]["reason"]}
