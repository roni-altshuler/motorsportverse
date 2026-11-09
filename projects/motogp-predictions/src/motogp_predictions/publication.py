"""Fail closed when snapshot round identities cannot safely feed publication.

The raw snapshot is retained as evidence. A hold replaces the generated numeric
corpus, rather than leaving stale forecasts available behind a warning banner.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from . import config

STATUS_FILE = "publication_status.json"
EXPORT_RECEIPT = "publication_export.json"
_IDENTITY = ("shortName", "venue", "country", "date")
_REFERENCES = [
    "https://www.motogp.com/en/calendar/2026",
    "https://www.motogp.com/en/news/2026/10/25/farewell-phillip-island-from-motogp-ceo-carmelo-ezpeleta/1180981",
]


def snapshot_issues(snapshot: dict) -> list[dict]:
    """Identity and supported-coverage checks, independent of result values."""
    full = snapshot.get("fullCalendar") or snapshot.get("calendar") or []
    completed = snapshot.get("calendar") or []
    ids = snapshot.get("completedRounds") or []
    if not isinstance(full, list) or not isinstance(completed, list) or not isinstance(ids, list):
        return [{"code": "invalid-calendar", "message": "Snapshot calendar metadata is malformed."}]
    if not full or not all(isinstance(e, dict) for e in full + completed):
        return [{"code": "invalid-calendar", "message": "A complete event calendar is unavailable."}]
    rounds = [e.get("round") for e in full]
    if any(type(r) is not int for r in rounds) or rounds != list(range(1, len(full) + 1)):
        return [{"code": "invalid-calendar", "message": "Scheduled round identities are not unique and ordered."}]
    if any(type(r) is not int or r < 1 for r in ids) or len(set(ids)) != len(ids):
        return [{"code": "invalid-completed-rounds", "message": "Completed round IDs are malformed or duplicated."}]
    if any(type(e.get("round")) is not int for e in completed):
        return [{"code": "invalid-calendar", "message": "Completed event round IDs are malformed."}]
    issues = []
    results = snapshot.get("results")
    if not isinstance(results, dict) or set(results) != {str(r) for r in ids}:
        issues.append({"code": "result-coverage-mismatch", "message": "Result keys and completed event IDs disagree."})
    if sorted(e.get("round", -1) for e in completed) != sorted(ids):
        issues.append({"code": "completed-calendar-mismatch", "message": "Completed IDs and event records disagree."})
    for event in completed:
        rnd = event.get("round")
        scheduled = full[rnd - 1] if type(rnd) is int and 1 <= rnd <= len(full) else {}
        matching = [e["round"] for e in full if all(event.get(k) == e.get(k) for k in _IDENTITY)]
        if (not scheduled or any(not event.get(k) or event.get(k) != scheduled.get(k) for k in _IDENTITY)
                or (event.get("eventId") is not None and event.get("eventId") != scheduled.get("eventId"))):
            issues.append({
                "code": "event-identity-mismatch", "round": rnd,
                "scheduled": {k: scheduled.get(k) for k in ("name", *_IDENTITY)},
                "recorded": {k: event.get(k) for k in ("name", *_IDENTITY)},
                "matchingScheduledRounds": matching,
                "message": f"Round {rnd} is paired with a different scheduled event.",
            })
    # Existing numerical consumers still use a count as a round bound. A UUID
    # repair must not silently hand those consumers a sparse completed set.
    if sorted(ids) != list(range(1, max(ids, default=0) + 1)):
        issues.append({"code": "unsupported-completed-round-gap", "message":
                       "Completed event IDs contain a gap; publication requires explicit coverage support."})
    return issues


def current_hold() -> dict | None:
    path = config._DATA_DIR / f"official_{config.SEASON}.json"
    raw = b""
    try:
        raw = path.read_bytes()
        snapshot = json.loads(raw)
        if not isinstance(snapshot, dict) or snapshot.get("season") != config.SEASON:
            raise ValueError("snapshot season does not match the active season")
        issues = snapshot_issues(snapshot)
        if config._SNAP != snapshot:
            issues.append({"code": "loaded-snapshot-changed", "message":
                           "The snapshot changed after configuration was loaded; use a fresh process."})
    except (OSError, ValueError) as exc:
        snapshot = {}
        issues = [{"code": "snapshot-unavailable", "message": str(exc)}]
    if not issues:
        return None
    full = snapshot.get("fullCalendar") or []
    riders = snapshot.get("riders") or []
    return {
        "schemaVersion": 1, "sport": "MotoGP", "season": config.SEASON,
        "status": "held", "reasonCode": "snapshot-event-identity",
        "message": "MotoGP forecasts and season figures are withheld while event identities and round coverage are verified.",
        "issues": issues,
        "sourceSnapshot": f"projects/motogp-predictions/data/official_{config.SEASON}.json",
        "snapshotSha256": hashlib.sha256(raw).hexdigest(),
        "references": _REFERENCES if config.SEASON == 2026 else [],
        "recovery": "Restore verified event-matched session inputs and supported completed-round coverage before publication resumes.",
        # Preserve existing deep links without exposing any numerical claims.
        "routes": {
            "rounds": [e["round"] for e in full if isinstance(e, dict) and type(e.get("round")) is int],
            "riders": [r["code"] for r in riders if isinstance(r, dict) and isinstance(r.get("code"), str)],
        },
    }


def write_hold_if_needed(data_dir: Path) -> Path | None:
    hold = current_hold()
    if hold is None:
        return None
    data_dir.mkdir(parents=True, exist_ok=True)
    for name in ("rounds", "probabilities", "forward_eval", "historical_backtest", "reliability_plots"):
        path = data_dir / name
        if path.is_symlink():
            path.unlink()
        elif path.exists():
            shutil.rmtree(path)
    for name in ("motogp.json", "calibration_summary.json", "model_health.json",
                 "promotion_status.json", "evidence.json", "seasons.json", EXPORT_RECEIPT):
        (data_dir / name).unlink(missing_ok=True)
    path = data_dir / STATUS_FILE
    path.write_text(json.dumps(hold, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _export_files() -> list[str]:
    return ["motogp.json", "calibration_summary.json", "seasons.json", *[
        f"{folder}/round_{rnd:02d}.json"
        for folder in ("rounds", "probabilities") for rnd in range(1, len(config.CALENDAR) + 1)
    ]]


def write_export_receipt(data_dir: Path) -> None:
    """Rebuild completion evidence, never evidence of pre-race publication."""
    snapshot = config._DATA_DIR / f"official_{config.SEASON}.json"
    raw = snapshot.read_bytes()
    if json.loads(raw) != config._SNAP:
        raise ValueError("Snapshot changed during export")
    receipt = {
        "schemaVersion": 1,
        "snapshotSha256": hashlib.sha256(raw).hexdigest(),
        "artifacts": {name: hashlib.sha256((data_dir / name).read_bytes()).hexdigest()
                      for name in _export_files()},
    }
    (data_dir / EXPORT_RECEIPT).write_text(json.dumps(receipt, indent=2) + "\n")


def require_current_export(data_dir: Path) -> None:
    """A standalone evaluator cannot release a hold using stale/absent exports."""
    try:
        receipt = json.loads((data_dir / EXPORT_RECEIPT).read_text())
        snapshot = config._DATA_DIR / f"official_{config.SEASON}.json"
        if (receipt["schemaVersion"] != 1
                or receipt["snapshotSha256"] != hashlib.sha256(snapshot.read_bytes()).hexdigest()
                or set(receipt["artifacts"]) != set(_export_files())
                or any(hashlib.sha256((data_dir / name).read_bytes()).hexdigest() != digest
                       for name, digest in receipt["artifacts"].items())):
            raise ValueError("Export bytes do not match the current snapshot and completion record")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError("Cannot release MotoGP hold without a complete export matching the current snapshot") from exc
