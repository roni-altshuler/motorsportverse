"""Export one archived timing comparison from a committed, offline lap snapshot.

No session loading or provider access occurs here. Sectors always belong to the
same stored row; without lap/tyre/accuracy flags this is not a clean-lap ranking.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / "features/data/lap_cache/2025_Monaco_R.parquet"
OUTPUT = PROJECT / "website/public/data/session-comparison/2025_Monaco_R.json"
TIMING_COLUMNS = ["LapTime (s)", "Sector1Time (s)", "Sector2Time (s)", "Sector3Time (s)"]


def driver_names() -> dict[str, str]:
    """Read the shared identity constants without importing the model pipeline."""
    tree = ast.parse((PROJECT / "src/f1_prediction_utils.py").read_text())
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) else []
        )
        if any(
            isinstance(target, ast.Name) and target.id == "DRIVER_FULL_NAMES"
            for target in targets
        ):
            names = ast.literal_eval(node.value)
            # Archived participant absent from the current-season identity list.
            # Verified against the official 2025 Monaco race-result page.
            return {**names, "TSU": "Yuki Tsunoda"}
    raise ValueError("Shared driver identities are unavailable")


def select_laps(frame: pd.DataFrame, names: dict[str, str]) -> list[dict]:
    """Select each driver's fastest complete, internally consistent stored row."""
    required = {"Driver", "Year", *TIMING_COLUMNS}
    if not required.issubset(frame.columns):
        raise ValueError(f"Missing timing columns: {sorted(required - set(frame.columns))}")
    if not frame["Year"].eq(2025).all():
        raise ValueError("The snapshot must contain only the 2025 session")

    drivers = []
    for code, rows in frame.groupby("Driver", sort=True, dropna=False):
        if not isinstance(code, str) or code not in names:
            raise ValueError(f"Unverified driver identity: {code}")
        complete = []
        for values in rows[TIMING_COLUMNS].itertuples(index=False, name=None):
            if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in values):
                continue
            milliseconds = tuple(round(v * 1000) for v in values)
            if min(milliseconds) <= 0 or abs(milliseconds[0] - sum(milliseconds[1:])) > 2:
                continue
            complete.append(milliseconds)
        if not complete:
            continue
        # Tie-break by the sector tuple, never mix independent sector minima.
        lap, s1, s2, s3 = min(complete)
        portrait = f"/headshots/{code}.webp"
        drivers.append({
            "code": code, "fullName": names[code],
            "portraitPath": portrait if (PROJECT / "website/public" / portrait[1:]).is_file()
            else None,
            "lapMs": lap, "sectorMs": [s1, s2, s3],
            "storedRows": len(rows), "completeRows": len(complete),
        })
    return sorted(drivers, key=lambda d: (d["lapMs"], d["code"]))


def export_payload() -> dict:
    """Build a deterministic artifact from the fixed local source."""
    return {
        "schemaVersion": 1,
        "session": {
            "id": "2025_Monaco_R", "season": 2025, "event": "Monaco Grand Prix",
            "kind": "Race", "date": "2025-05-25",
        },
        "source": {
            "provider": "FastF1", "path": SOURCE.relative_to(PROJECT).as_posix(),
            "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "selection": "fastest-complete-stored-row",
            "missingFields": ["lapNumber", "tyre", "pitStatus", "accuracy", "trackStatus"],
        },
        "drivers": select_laps(pd.read_parquet(SOURCE), driver_names()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check the committed artifact unchanged")
    args = parser.parse_args()
    encoded = json.dumps(export_payload(), indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text() != encoded:
            parser.exit(1, "Archived comparison differs; rerun this offline exporter.\n")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
