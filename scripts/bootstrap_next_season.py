#!/usr/bin/env python3
"""Bootstrap next season's calendar from FastF1 so rollover is fully hands-off.

F1 publishes the next year's schedule mid-prior-year. This script fetches it via
``fastf1.get_event_schedule``, derives a ``CALENDAR_<year>`` (plus a
carried-forward driver/team lineup) and writes it to
``generated_seasons/<year>.json``. ``f1_prediction_utils`` registers that file as
module globals, so the existing season scanner + ``season_rollover.py`` pick the
new season up automatically — no manual code edits.

Safety / hands-off guarantees:
- No-op (exit 0) when next year's schedule isn't published yet.
- A generated future calendar does NOT become the active season until its first
  race date passes — see ``_default_season_year`` in f1_prediction_utils.
- Idempotent: skips a year already generated unless ``--force``.
- The lineup is carried forward from the active season and flagged
  ``lineup_provisional``; the live pipeline self-corrects it from the official
  entry list once the new season's first session is published.

Usage:
    python scripts/bootstrap_next_season.py                 # auto: active year + 1
    python scripts/bootstrap_next_season.py --year 2027 --force
    python scripts/bootstrap_next_season.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

GEN_DIR = ROOT / "generated_seasons"

# FastF1 reports the host city in ``Location``; that disambiguates the cases
# where ``Country`` is ambiguous (the USA hosts 3 rounds, Italy 2). Map the
# known F1 venues to the project's stable ``gp_key`` vocabulary.
_LOCATION_TO_GP_KEY = {
    "Melbourne": "Australia",
    "Shanghai": "China",
    "Suzuka": "Japan",
    "Sakhir": "Bahrain",
    "Jeddah": "Saudi Arabia",
    "Miami": "Miami",
    "Imola": "Emilia Romagna",
    "Monaco": "Monaco",
    "Monte Carlo": "Monaco",
    "Montréal": "Canada",
    "Montreal": "Canada",
    "Barcelona": "Spain",
    "Catalunya": "Spain",
    "Madrid": "Madrid",
    "Spielberg": "Austria",
    "Silverstone": "Great Britain",
    "Budapest": "Hungary",
    "Spa-Francorchamps": "Belgium",
    "Spa": "Belgium",
    "Zandvoort": "Netherlands",
    "Monza": "Italy",
    "Baku": "Azerbaijan",
    "Marina Bay": "Singapore",
    "Singapore": "Singapore",
    "Austin": "United States",
    "Mexico City": "Mexico",
    "São Paulo": "Brazil",
    "Sao Paulo": "Brazil",
    "Interlagos": "Brazil",
    "Las Vegas": "Las Vegas",
    "Lusail": "Qatar",
    "Yas Marina": "Abu Dhabi",
    "Yas Island": "Abu Dhabi",
    "Abu Dhabi": "Abu Dhabi",
}

# Country names that map to a stable gp_key when the host city isn't recognised
# (FastF1 sometimes reports the venue differently year to year).
_COUNTRY_ALIASES = {
    "United Arab Emirates": "Abu Dhabi",
}

# Reasonable defaults when a brand-new circuit has no historical specs to copy.
# Race distance ≈ 305 km / lap length gives a usable lap count for the simulator;
# these are logged loudly so a human can refine them later.
_DEFAULT_CIRCUIT_KM = 5.0
_DEFAULT_RACE_KM = 305.0
_DEFAULT_SPRINT_KM = 100.0


def _resolve_gp_key(location, country, event_name) -> str:
    """Map a FastF1 event to the project's stable gp_key."""
    loc = (location or "").strip()
    if loc in _LOCATION_TO_GP_KEY:
        return _LOCATION_TO_GP_KEY[loc]
    ctry = (country or "").strip()
    if ctry in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[ctry]
    # Country is unique enough for single-race nations.
    if ctry and ctry not in {"United States", "Italy"}:
        return ctry
    # Last resort: derive from the event name ("Bahrain Grand Prix" -> "Bahrain").
    name = (event_name or "").replace("Grand Prix", "").strip()
    return name or loc or ctry or "Unknown"


def _known_circuit_specs() -> dict:
    """Union of (laps, circuit_km, sprint_laps) per gp_key across every known
    CALENDAR_<year> — newer seasons override older so specs stay current."""
    import f1_prediction_utils as fpu
    specs: dict[str, dict] = {}
    for year in fpu._available_season_years("CALENDAR"):
        for entry in fpu.get_calendar(year).values():
            key = entry.get("gp_key")
            if not key:
                continue
            specs[key] = {
                "laps": entry.get("laps"),
                "circuit_km": entry.get("circuit_km"),
                "sprint_laps": entry.get("sprint_laps"),
            }
    return specs


def _is_sprint(event_format) -> bool:
    return "sprint" in str(event_format or "").lower()


def build_calendar(year: int):
    """Fetch year's schedule from FastF1 and shape it into a CALENDAR dict.

    Returns ``(calendar, warnings)`` or ``(None, reason)`` when the schedule
    isn't available yet (so the caller can no-op cleanly).
    """
    import fastf1

    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
    except Exception as exc:  # noqa: BLE001 — any FastF1/network failure → no-op
        return None, f"schedule fetch failed: {exc}"

    if schedule is None or len(schedule) == 0:
        return None, "schedule not published yet (empty)"

    specs = _known_circuit_specs()
    calendar: dict[int, dict] = {}
    warnings: list[str] = []

    for _, row in schedule.iterrows():
        rnd = int(row["RoundNumber"])
        if rnd < 1:
            continue  # testing / pre-season entries
        gp_key = _resolve_gp_key(row.get("Location"), row.get("Country"),
                                 row.get("EventName"))
        event_date = row.get("EventDate")
        try:
            date_iso = event_date.date().isoformat()
        except Exception:  # noqa: BLE001
            date_iso = str(event_date)[:10]

        sprint = _is_sprint(row.get("EventFormat"))
        spec = specs.get(gp_key, {})
        circuit_km = spec.get("circuit_km")
        laps = spec.get("laps")
        sprint_laps = spec.get("sprint_laps")

        if circuit_km is None:
            circuit_km = _DEFAULT_CIRCUIT_KM
            warnings.append(f"R{rnd} {gp_key}: no known circuit_km — default {circuit_km}")
        if laps is None:
            laps = max(1, round(_DEFAULT_RACE_KM / circuit_km))
            warnings.append(f"R{rnd} {gp_key}: no known lap count — estimated {laps}")
        if sprint and not sprint_laps:
            sprint_laps = max(1, round(_DEFAULT_SPRINT_KM / circuit_km))
            warnings.append(f"R{rnd} {gp_key}: sprint weekend, estimated sprint_laps {sprint_laps}")

        entry = {
            "name": row.get("EventName") or f"{gp_key} Grand Prix",
            "gp_key": gp_key,
            "circuit": row.get("Location") or gp_key,
            "date": date_iso,
            "laps": laps,
            "circuit_km": circuit_km,
            "sprint": sprint,
        }
        if sprint:
            entry["sprint_laps"] = sprint_laps
        calendar[rnd] = entry

    if not calendar:
        return None, "schedule had no race rounds"
    return calendar, warnings


def _carried_forward_lineup():
    """Copy the active season's driver/team + numbers as a provisional lineup."""
    import f1_prediction_utils as fpu
    return dict(fpu.get_driver_team_map()), dict(fpu.get_driver_numbers_map())


def bootstrap(year: int | None, force: bool, dry_run: bool) -> int:
    import f1_prediction_utils as fpu

    if year is None:
        year = max(fpu._available_season_years("CALENDAR")) + 1

    out_path = GEN_DIR / f"{year}.json"
    if out_path.exists() and not force:
        print(f"✅ generated_seasons/{year}.json already exists — nothing to do "
              f"(use --force to regenerate).")
        return 0

    print(f"🔭 Bootstrapping season {year} from FastF1…")
    calendar, info = build_calendar(year)
    if calendar is None:
        print(f"⏭️  {year} not bootstrapped — {info}. (Will retry on the next run.)")
        return 0  # not an error: the schedule simply isn't out yet

    driver_team, driver_numbers = _carried_forward_lineup()
    payload = {
        "year": year,
        "source": "fastf1.get_event_schedule",
        "rounds": len(calendar),
        "lineup_provisional": True,
        "calendar": {str(k): v for k, v in sorted(calendar.items())},
        "driver_team": driver_team,
        "driver_numbers": driver_numbers,
    }

    print(f"   {len(calendar)} rounds, "
          f"{sum(1 for e in calendar.values() if e.get('sprint'))} sprints, "
          f"lineup carried forward ({len(driver_team)} drivers, provisional).")
    for w in (info if isinstance(info, list) else []):
        print(f"   ⚠️  {w}")

    if dry_run:
        print(f"   [dry-run] would write {out_path.relative_to(ROOT)}")
        return 0

    GEN_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"✅ Wrote {out_path.relative_to(ROOT)} — season {year} will roll over "
          f"automatically once its first race begins.")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=None,
                    help="Season to bootstrap (default: newest known calendar + 1).")
    ap.add_argument("--force", action="store_true",
                    help="Regenerate even if generated_seasons/<year>.json exists.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would be written without touching disk.")
    args = ap.parse_args()
    raise SystemExit(bootstrap(args.year, args.force, args.dry_run))


if __name__ == "__main__":
    main()
