"""Convert one already-loaded FastF1 session window to browser-local NDJSON.

No provider requests, interpolation, map generation or weather alignment occur
in the converter. The optional CLI loads only a user's trusted offline cache.
Software licensing does not certify the rights or accuracy of the supplied data.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

MAX_SECONDS = 120
MAX_FRAMES = 2000
MAX_BYTES = 4 * 1024 * 1024
SOURCES = {"car", "pos", "interpolation", "interpolated"}
SESSIONS = ("Race", "Qualifying", "Sprint", "Sprint Qualifying",
            "Practice 1", "Practice 2", "Practice 3")


def _number(value: Any, minimum: float, maximum: float) -> float | None:
    if isinstance(value, (bool, str)) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and minimum <= number <= maximum else None


def _seconds(value: Any) -> float | None:
    # Never substitute slice-relative Time for the documented SessionTime.
    if not hasattr(value, "total_seconds"):
        return None
    return _number(value.total_seconds(), 0, 1e7)


def _channels(row: dict) -> dict:
    gear = _number(row.get("nGear"), 0, 8)
    brake = row.get("Brake")
    # DataFrame.to_dict normalizes numpy bools to Python bools. Numeric/string
    # flags and missing values must not become a pressure or a truthy boolean.
    return {
        "speed_kph": _number(row.get("Speed"), 0, 500),
        "rpm": _number(row.get("RPM"), 0, 30000),
        "throttle_pct": _number(row.get("Throttle"), 0, 100),
        "gear": int(gear) if gear is not None and gear.is_integer() else None,
        "brake": brake if isinstance(brake, bool) else None,
    }


def capture_from_session(
    session: Any, *, driver: str, season: int, round_number: int,
    session_name: str, start_s: float, end_s: float,
    software_version: str = "unknown",
) -> str:
    """Export native independent car/position samples for one driver, <=120s.

    Stable chronological ordering retains duplicates and original order within
    each channel; car samples precede position samples at equal timestamps.
    Channels are never merged, carried forward, resampled or gap-filled.
    """
    if (not re.fullmatch(r"\d{1,3}", driver) or session_name not in SESSIONS
            or not 2018 <= season <= 2100 or not 1 <= round_number <= 30):
        raise ValueError("Choose an F1 driver number, season, round and supported session.")
    if (_number(start_s, 0, 1e7) is None or _number(end_s, 0, 1e7) is None
            or not 0 < end_s - start_s <= MAX_SECONDS):
        raise ValueError("Choose a session-time window greater than 0 and at most 120 seconds.")
    if (getattr(session.event, "year", None) != season
            or session.event.get("RoundNumber") != round_number
            or session.name != session_name):
        raise ValueError("Session identity does not match the requested season, round and session.")
    identity = session.get_driver(driver)
    code = identity.get("Abbreviation")
    if (not isinstance(code, str) or not re.fullmatch(r"[A-Z0-9_-]{1,12}", code)
            or code in {"__PROTO__", "CONSTRUCTOR", "PROTOTYPE"}):
        code = driver
    name = identity.get("FullName")
    name = name.strip() if isinstance(name, str) and 0 < len(name.strip()) <= 80 else None
    color = identity.get("TeamColor")
    color = f"#{color}" if isinstance(color, str) and re.fullmatch(r"[a-fA-F0-9]{6}", color) else None
    samples = []
    for kind, mapping in (("car", session.car_data), ("pos", session.pos_data)):
        data = mapping.get(driver)
        if data is None or data.empty:
            continue
        if "SessionTime" not in data.columns or "Source" not in data.columns:
            raise ValueError("Samples need SessionTime and Source; slice-relative Time is unsupported.")
        for order, row in enumerate(data.to_dict(orient="records")):
            time = _seconds(row["SessionTime"])
            if time is None:
                raise ValueError("Invalid SessionTime; cannot place a sample within the selected window.")
            if not start_s <= time <= end_s:
                continue
            source = row["Source"]
            if source not in SOURCES or (source in {"car", "pos"} and source != kind):
                raise ValueError("Sample Source does not match its car/position channel.")
            x = _number(row.get("X"), -1e8, 1e8) if kind == "pos" else None
            y = _number(row.get("Y"), -1e8, 1e8) if kind == "pos" else None
            value = {
                "x": x / 10 if x is not None and y is not None else None,
                "y": y / 10 if x is not None and y is not None else None,
                "sample_source": source,
                "telemetry": _channels(row) if kind == "car" else None,
            }
            if name:
                value["name"] = name
            samples.append((time, 0 if kind == "car" else 1, order, value))
    samples.sort(key=lambda sample: sample[:3])
    if not samples:
        raise ValueError("No native car or position samples are available in this window.")
    if len(samples) > MAX_FRAMES:
        raise ValueError("More than 2000 native samples; choose a shorter window. No samples dropped.")
    metadata = {
        "provider": "FastF1", "schema_version": 1, "series": "Formula 1",
        "season": season, "round": round_number, "session": session_name,
        "software_version": str(software_version)[:40],
        "time_basis": "session-relative-seconds", "coordinate_units": "metres",
        "sampling": "native-independent", "data_rights": "not-certified",
    }
    lines = []
    for index, (time, _, _, value) in enumerate(samples):
        message = {"frame_index": index, "frame": {"t": time, "drivers": {code: value}}}
        if color:
            message["driver_colors"] = {code: color}
        if index == 0:
            message["capture_metadata"] = metadata
        lines.append(json.dumps(message, allow_nan=False, ensure_ascii=False, separators=(",", ":")))
    text = "\n".join(lines) + "\n"
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Capture exceeds 4 MiB; choose a shorter window.")
    return text


def _outside_git(path: Path) -> Path:
    path = path.expanduser().resolve()
    # An empty sandbox .git sentinel is not a repository. Real Git directories
    # have HEAD; linked worktrees use a .git file. Resolve symlinks first.
    if any((parent / ".git").is_file() or (parent / ".git" / "HEAD").is_file()
           for parent in (path, *path.parents)):
        raise ValueError("Keep trusted caches and local exports outside every Git working tree.")
    return path


def load_cached_session(cache: Path, season: int, round_number: int, session_name: str):
    """Optional FastF1 boundary. Offline mode is enabled before event lookup.

    Cache files must be trusted: FastF1's own parsed-cache format uses pickle.
    Missing cached resources fail locally; this CLI has no online-mode option.
    """
    import fastf1

    fastf1.Cache.enable_cache(str(cache))
    fastf1.Cache.offline_mode(True)
    session = fastf1.get_session(season, round_number, session_name, backend="fastf1")
    session.load(laps=False, telemetry=True, weather=False, messages=False)
    return session, fastf1.__version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True, help="Your existing trusted offline cache")
    parser.add_argument("--output", type=Path, required=True, help="New local NDJSON file outside Git")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--round", dest="round_number", type=int, required=True)
    parser.add_argument("--session", choices=SESSIONS, required=True)
    parser.add_argument("--driver", required=True, help="Session driver number")
    parser.add_argument("--start", dest="start_s", type=float, required=True)
    parser.add_argument("--end", dest="end_s", type=float, required=True)
    parser.add_argument("--acknowledge-data-terms", action="store_true", required=True,
                        help="Confirm lawful local use; this does not grant data rights")
    args = parser.parse_args(argv)
    try:
        cache, output = _outside_git(args.cache), _outside_git(args.output)
        if not cache.is_dir() or output.exists() or not output.parent.is_dir():
            raise ValueError("Use an existing trusted cache and a new output in an existing directory.")
        session, version = load_cached_session(cache, args.season, args.round_number, args.session)
        text = capture_from_session(
            session, driver=args.driver, season=args.season, round_number=args.round_number,
            session_name=args.session, start_s=args.start_s, end_s=args.end_s,
            software_version=version,
        )
        with output.open("x", encoding="utf-8") as handle:
            handle.write(text)
    except Exception as exc:  # CLI boundary: missing/corrupt caches must fail locally and clearly.
        parser.exit(1, f"Local capture unavailable: {exc}\n")
    print(f"Wrote {output}. F1 only; sparse native samples, no circuit outline or certified rights.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
