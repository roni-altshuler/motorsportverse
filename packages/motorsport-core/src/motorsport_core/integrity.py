"""Integrity checks over a project's PUBLISHED data tree.

Every project's ``export.py`` is the single producer of its site's JSON, and
each site reads that JSON as fact. Schema tests
(``tests/test_website_data_schema.py``) already prove each *file* is
well-formed. **These checks ask whether the corpus is right** — a question no
row-level schema can answer, because every row can be valid while the set of
them is wrong.

Every check here exists because the corresponding failure is real: it has
happened in this repo, or in the sibling soccer/NBA projects whose conventions
this borrows. Each returns a :class:`Finding` naming the file and the fact,
never a bare boolean.

The checks, and what each is really asking:

``round_files_contiguous``
    Are rounds 1..N all present, with each file's ``round`` field matching its
    own name? A silently-skipped round leaves a hole nothing surfaces — the
    accuracy page just averages over fewer rounds and looks fine.
``chronological``
    Do calendar dates increase with round number? Elo and every rolling feature
    read the future the moment a stream is out of order, and the output looks
    entirely normal.
``no_future_results``
    Is a round dated ahead of the export marked completed? That is a wrong-event
    write or a clock problem, and it publishes a "result" nobody ran.
``no_duplicate_competitors``
    Does one round list the same competitor twice? Two rows for one driver
    double-count points and quietly break a championship simulation.
``no_placeholder_entrants``
    Did a bracket slot, ``TBD``, ``TBA`` or an empty name become a competitor?
    A junk entrant row is permanent and competes with every later lookup.
``probability_range``
    Is every published probability inside [0, 1]?
``probability_mass``
    Does each market's probability sum to the mass it must have — 1 for win, 3
    for podium, 6 for top-six, 10 for top-ten? **Per-competitor calibration
    does not preserve the simplex**, so this is checked on the calibrated
    values a reader actually sees, not only on the raw ones.
``baselines_published``
    Does every scored round carry a baselines block? Round 1 legitimately has
    none (there is no previous race); any later round missing one is a metric
    with nothing to compare against, which ``docs/EVIDENCE.md`` forbids.
``calibration_gate_honest``
    Does ``applied: true`` actually have real rounds behind it? A gate that
    opens on synthetic data is the single most misleading thing this repo could
    publish.
``season_manifest``
    Is ``seasons.json``'s ``current`` actually in ``available``, and is every
    archived season distinct from it?
``drift_vocabulary``
    Does ``model_health.json`` use the known severity words? A typo'd severity
    is a silently-ignored alarm.

Public API
----------
- :func:`check_published_data` — run everything over one project's data dir.
- :func:`Finding` / :func:`Report` — the result types.
- :data:`MARKET_MASS` — expected probability mass per market.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

#: The mass each market's probabilities must sum to across the field. A "podium"
#: probability per driver sums to three because exactly three drivers finish on
#: the podium; the same reasoning gives 6 and 10.
MARKET_MASS: dict[str, float] = {
    "win": 1.0,
    "podium": 3.0,
    "top6": 6.0,
    "top10": 10.0,
}

#: Tolerance on that mass, as a fraction of the expected value. Sampling noise
#: from the Monte Carlo is well inside 2%; anything past it is structural.
MASS_TOLERANCE = 0.02

#: Names that are slots, not competitors.
PLACEHOLDER_NAMES = {"", "-", "--", "?", "??", "tbd", "tba", "n/a", "na", "none", "null", "unknown"}

#: Severities `motorsport_core.drift` emits. Anything else is a typo that turns
#: an alarm into silence.
DRIFT_SEVERITIES = {"ok", "warn", "warning", "alarm"}

#: Real rounds required before a calibration gate may be open.
MIN_CALIBRATION_ROUNDS = 3

_ROUND_FILE = re.compile(r"^round_(\d+)\.json$")


@dataclass(frozen=True)
class Finding:
    """One integrity violation, or one passing check."""

    check: str
    ok: bool
    message: str
    path: str | None = None

    def __str__(self) -> str:  # pragma: no cover - display only
        mark = "PASS" if self.ok else "FAIL"
        where = f" [{self.path}]" if self.path else ""
        return f"{mark:4} {self.check:26} {self.message}{where}"


@dataclass
class Report:
    """The result of running every check over one project."""

    project: str
    findings: list[Finding] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if not f.ok]

    @property
    def ok(self) -> bool:
        return not self.failures

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def to_json(self) -> dict:
        return {
            "project": self.project,
            "ok": self.ok,
            "checks": len(self.findings),
            "failures": [
                {"check": f.check, "message": f.message, "path": f.path}
                for f in self.failures
            ],
            "skipped": self.skipped,
        }


def _read_json(path: Path) -> object | None:
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:  # pragma: no cover - defensive
        return str(path)


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    for parse in (datetime.fromisoformat, lambda s: datetime.strptime(s, "%Y-%m-%d")):
        try:
            parsed = parse(text)
        except ValueError:
            continue
        return parsed.date()
    return None


def _round_number(path: Path) -> int | None:
    match = _ROUND_FILE.match(path.name)
    return int(match.group(1)) if match else None


def _numbered_round_files(directory: Path) -> list[tuple[int, Path]]:
    if not directory.is_dir():
        return []
    pairs = [(n, p) for p in sorted(directory.iterdir()) if (n := _round_number(p)) is not None]
    return sorted(pairs)


# ---------------------------------------------------------------------------
# individual checks
# ---------------------------------------------------------------------------


def check_round_files_contiguous(directory: Path, root: Path, label: str) -> list[Finding]:
    pairs = _numbered_round_files(directory)
    if not pairs:
        return []
    numbers = [n for n, _ in pairs]
    findings: list[Finding] = []

    expected = list(range(1, max(numbers) + 1))
    missing = sorted(set(expected) - set(numbers))
    if missing:
        findings.append(
            Finding(
                "round_files_contiguous",
                False,
                f"{label}: rounds {missing} are missing between 1 and {max(numbers)} — "
                f"a hole here silently shrinks every average computed over the set",
                _rel(directory, root),
            )
        )
    else:
        findings.append(
            Finding(
                "round_files_contiguous",
                True,
                f"{label}: rounds 1-{max(numbers)} all present",
                _rel(directory, root),
            )
        )

    for number, path in pairs:
        payload = _read_json(path)
        if not isinstance(payload, dict):
            findings.append(
                Finding("round_files_contiguous", False, f"{label}: unreadable", _rel(path, root))
            )
            continue
        declared = payload.get("round")
        if isinstance(declared, int) and declared != number:
            findings.append(
                Finding(
                    "round_files_contiguous",
                    False,
                    f"{label}: file is named round {number} but declares round "
                    f"{declared} — one of the two is what a consumer indexes on",
                    _rel(path, root),
                )
            )
    return findings


def check_calendar(payload: Mapping, path: str) -> list[Finding]:
    calendar = payload.get("calendar")
    if not isinstance(calendar, list) or not calendar:
        return [Finding("chronological", True, "no calendar published; nothing to order", path)]

    findings: list[Finding] = []
    dated: list[tuple[int, date]] = []
    for entry in calendar:
        if not isinstance(entry, Mapping):
            continue
        rnd = entry.get("round")
        if not isinstance(rnd, int):
            continue
        # Series name their date field differently (raceDate / featureDate /
        # date); take the earliest parseable one so a sprint weekend orders on
        # the same day the calendar renders.
        candidates = [
            parsed
            for key, value in entry.items()
            if key.lower().endswith("date") and (parsed := _parse_date(value)) is not None
        ]
        if candidates:
            dated.append((rnd, min(candidates)))

    out_of_order = [
        (a_rnd, b_rnd)
        for (a_rnd, a_date), (b_rnd, b_date) in zip(sorted(dated), sorted(dated)[1:])
        if b_date < a_date
    ]
    if out_of_order:
        findings.append(
            Finding(
                "chronological",
                False,
                f"calendar dates decrease at round pair(s) {out_of_order} — any rolling "
                f"feature computed over this order reads the future",
                path,
            )
        )
    else:
        findings.append(
            Finding("chronological", True, f"{len(dated)} dated rounds increase with round number", path)
        )

    today = datetime.now(timezone.utc).date()
    future_completed = [
        entry.get("round")
        for entry in calendar
        if isinstance(entry, Mapping)
        and entry.get("completed") is True
        and (d := min((p for k, v in entry.items() if k.lower().endswith("date") and (p := _parse_date(v))), default=None))
        is not None
        and d > today
    ]
    if future_completed:
        findings.append(
            Finding(
                "no_future_results",
                False,
                f"round(s) {future_completed} are dated in the future and marked "
                f"completed — that is a wrong-event write, not a result",
                path,
            )
        )
    else:
        findings.append(
            Finding("no_future_results", True, "no future-dated round is marked completed", path)
        )
    return findings


def _competitor_names(payload: Mapping) -> dict[str, list[tuple[str, str]]]:
    """``{table_key: [(code, name), …]}`` for every standings-like list.

    Detection is by SHAPE, not by key name: a list whose entries carry an
    identity (``code`` / ``name`` / ``team`` / ``manufacturer``) alongside a
    ``position`` or ``points``. The flagship names its tables ``drivers`` and
    ``teams`` while every other series names them ``driverStandings`` and
    ``teamStandings``, and a name-matching version of this check silently
    examined five sites and skipped the sixth.

    Tables are kept SEPARATE because a driver and a constructor may legitimately
    share a name (Ferrari the team, no driver called Ferrari — but Red Bull and
    Racing Bulls both appear in two tables), and pooling them would invent
    duplicates that are not duplicates.
    """
    out: dict[str, list[tuple[str, str]]] = {}
    for key, value in payload.items():
        if not isinstance(value, list) or not value:
            continue
        rows: list[tuple[str, str]] = []
        for entry in value:
            if not isinstance(entry, Mapping):
                continue
            if "position" not in entry and "points" not in entry:
                continue
            code = entry.get("code") or entry.get("team") or entry.get("manufacturer")
            name = entry.get("name") or entry.get("team") or entry.get("manufacturer")
            if code is None and name is None:
                continue
            rows.append((str(code or ""), str(name or "")))
        if rows:
            out[key] = rows
    return out


def check_competitors(payload: Mapping, path: str) -> list[Finding]:
    findings: list[Finding] = []
    tables = _competitor_names(payload)
    if not tables:
        return findings

    duplicates: list[str] = []
    total = 0
    for table, pairs in tables.items():
        seen: dict[str, int] = {}
        for code, name in pairs:
            identity = (code or name).strip().lower()
            if identity:
                seen[identity] = seen.get(identity, 0) + 1
        total += len(seen)
        duplicates.extend(
            f"{table}.{identity}" for identity, count in sorted(seen.items()) if count > 1
        )

    if duplicates:
        findings.append(
            Finding(
                "no_duplicate_competitors",
                False,
                f"duplicate competitor key(s) {duplicates} within one standings table — "
                f"points are double-counted downstream",
                path,
            )
        )
    else:
        findings.append(
            Finding(
                "no_duplicate_competitors",
                True,
                f"{total} distinct competitors across {len(tables)} table(s)",
                path,
            )
        )

    # A competitor is a placeholder when the identity it PRESENTS is one. A
    # missing `code` beside a real `name` is not a placeholder — the fantasy
    # projects' standings carry names without codes, and an earlier version of
    # this check reported twelve real drivers as junk rows because the empty
    # string is in the token set. Judge the identity, not each field.
    explicit = PLACEHOLDER_NAMES - {""}
    placeholders = sorted(
        {
            (name or code or "(blank)")
            for pairs in tables.values()
            for code, name in pairs
            if (not (code or "").strip() and not (name or "").strip())
            or (code or "").strip().lower() in explicit
            or (name or "").strip().lower() in explicit
        }
    )
    if placeholders:
        findings.append(
            Finding(
                "no_placeholder_entrants",
                False,
                f"placeholder entrant(s) {placeholders} were published as competitors — "
                f"a slot is not a driver and a junk row is permanent",
                path,
            )
        )
    else:
        findings.append(Finding("no_placeholder_entrants", True, "no placeholder entrants", path))
    return findings


def _normalise_market(entries: object) -> dict[str, Mapping] | None:
    """``{competitor: {probability, rawProbability}}`` from either published form.

    Three shapes exist in this repo and all three are real:

    - F2/F3/FE/NASCAR/IndyCar: ``{race_type: {markets: {market: {code: {...}}}}}``
    - F1: ``{markets: {market: [{driver, probability, rawProbability}, …]}}`` —
      a LIST, because the flagship's export predates the shared shape.

    Normalising here rather than special-casing the flagship is what lets one
    check cover every series; the alternative is a check that silently examines
    five sites and skips the sixth, which is the failure mode this module
    exists to prevent.
    """
    if isinstance(entries, Mapping):
        return {k: v for k, v in entries.items() if isinstance(v, Mapping)}
    if isinstance(entries, list):
        out: dict[str, Mapping] = {}
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            key = entry.get("driver") or entry.get("code") or entry.get("competitor")
            if isinstance(key, str):
                out[key] = entry
        return out or None
    return None


def _market_blocks(payload: Mapping) -> Iterable[tuple[str, str, Mapping]]:
    """``(race_type, market, {competitor: {...probabilities}})`` triples."""
    # F1 shape: markets sit at the top level, with no race-type wrapper.
    top_markets = payload.get("markets")
    if isinstance(top_markets, Mapping):
        for market, entries in top_markets.items():
            normalised = _normalise_market(entries)
            if normalised:
                yield "race", market, normalised

    for race_type, block in payload.items():
        if race_type == "markets" or not isinstance(block, Mapping):
            continue
        markets = block.get("markets")
        if not isinstance(markets, Mapping):
            continue
        for market, entries in markets.items():
            normalised = _normalise_market(entries)
            if normalised:
                yield race_type, market, normalised


def check_probabilities(payload: Mapping, path: str) -> list[Finding]:
    findings: list[Finding] = []
    out_of_range: list[str] = []
    mass_problems: list[str] = []
    checked = 0

    for race_type, market, probs in _market_blocks(payload):
        calibrated: list[float] = []
        raw: list[float] = []
        for competitor, entry in probs.items():
            if not isinstance(entry, Mapping):
                continue
            for field_name, bucket in (("probability", calibrated), ("rawProbability", raw)):
                value = entry.get(field_name)
                if not isinstance(value, (int, float)):
                    continue
                bucket.append(float(value))
                if not 0.0 <= float(value) <= 1.0:
                    out_of_range.append(f"{race_type}.{market}.{competitor}.{field_name}={value}")
        if not calibrated and not raw:
            continue
        checked += 1

        expected = MARKET_MASS.get(market)
        if expected is None:
            continue
        for label, values in (("calibrated", calibrated), ("raw", raw)):
            if not values:
                continue
            total = sum(values)
            if abs(total - expected) > expected * MASS_TOLERANCE:
                mass_problems.append(
                    f"{race_type}.{market} {label} sums to {total:.4f}, expected {expected:.0f}"
                )

    if out_of_range:
        findings.append(
            Finding(
                "probability_range",
                False,
                "probabilities outside [0,1]: " + "; ".join(out_of_range[:5]),
                path,
            )
        )
    elif checked:
        findings.append(
            Finding("probability_range", True, f"{checked} market(s) inside [0,1]", path)
        )

    if mass_problems:
        findings.append(
            Finding(
                "probability_mass",
                False,
                "; ".join(mass_problems[:6])
                + " — per-competitor calibration does not preserve the simplex, so the "
                "published numbers do not add up to the field they describe",
                path,
            )
        )
    elif checked:
        findings.append(
            Finding("probability_mass", True, f"{checked} market(s) carry the right mass", path)
        )
    return findings


def check_baselines(directory: Path, root: Path) -> list[Finding]:
    pairs = _numbered_round_files(directory)
    if not pairs:
        return []
    missing: list[int] = []
    for number, path in pairs:
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        # Round 1 has no previous race, so a last-race baseline genuinely does
        # not exist for it. Any later round without one is a metric with
        # nothing to compare against.
        if number == 1:
            continue
        baselines = payload.get("baselines")
        if not isinstance(baselines, Mapping) or not any(
            isinstance(v, Mapping) and v for v in baselines.values()
        ):
            missing.append(number)
    if missing:
        return [
            Finding(
                "baselines_published",
                False,
                f"scored round(s) {missing} carry no baseline — an accuracy number "
                f"with no baseline is a number about the calendar",
                _rel(directory, root),
            )
        ]
    return [
        Finding(
            "baselines_published",
            True,
            f"every scored round after round 1 carries a baseline ({len(pairs)} rounds)",
            _rel(directory, root),
        )
    ]


def check_calibration_gate(payload: Mapping, path: str) -> list[Finding]:
    applied = payload.get("applied")
    training_rounds = payload.get("trainingRounds")
    limitation = str(payload.get("dataLimitation") or "")

    if applied is not True:
        return [
            Finding(
                "calibration_gate_honest",
                True,
                "gate is closed; probabilities must be presented as uncalibrated",
                path,
            )
        ]
    if not isinstance(training_rounds, int) or training_rounds < MIN_CALIBRATION_ROUNDS:
        return [
            Finding(
                "calibration_gate_honest",
                False,
                f"gate is OPEN on trainingRounds={training_rounds!r} — fewer than the "
                f"{MIN_CALIBRATION_ROUNDS} real rounds a calibration claim requires",
                path,
            )
        ]
    if "synthetic" in limitation.lower():
        return [
            Finding(
                "calibration_gate_honest",
                False,
                "gate is OPEN while dataLimitation still says the data is synthetic — "
                "calibration is never claimed on synthetic data",
                path,
            )
        ]
    return [
        Finding(
            "calibration_gate_honest",
            True,
            f"gate open on {training_rounds} real rounds",
            path,
        )
    ]


def check_seasons(payload: Mapping, path: str) -> list[Finding]:
    current = payload.get("current")
    available = payload.get("available")
    archived = payload.get("archived")
    findings: list[Finding] = []

    if isinstance(available, list) and current is not None and current not in available:
        findings.append(
            Finding(
                "season_manifest",
                False,
                f"current season {current} is not in available {available} — the season "
                f"switcher will offer a season the site cannot load",
                path,
            )
        )
    elif isinstance(available, list):
        findings.append(
            Finding("season_manifest", True, f"current {current} is available", path)
        )

    if isinstance(archived, list) and current in archived:
        findings.append(
            Finding(
                "season_manifest",
                False,
                f"season {current} is both current and archived",
                path,
            )
        )
    return findings


def check_model_health(payload: Mapping, path: str) -> list[Finding]:
    bad: list[str] = []
    for entry in payload.get("featureDrift") or []:
        if isinstance(entry, Mapping):
            severity = entry.get("severity")
            if severity is not None and str(severity).lower() not in DRIFT_SEVERITIES:
                bad.append(f"featureDrift.{entry.get('feature')}={severity!r}")
    output_drift = payload.get("outputDrift")
    if isinstance(output_drift, Mapping):
        severity = output_drift.get("severity")
        if severity is not None and str(severity).lower() not in DRIFT_SEVERITIES:
            bad.append(f"outputDrift={severity!r}")
    if bad:
        return [
            Finding(
                "drift_vocabulary",
                False,
                "unknown drift severity: " + ", ".join(bad) + " — an unrecognised "
                "severity is an alarm nothing will act on",
                path,
            )
        ]
    return [Finding("drift_vocabulary", True, "drift severities are recognised", path)]


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------


def check_published_data(
    data_dir: Path | str,
    *,
    project: str | None = None,
    root: Path | str | None = None,
) -> Report:
    """Run every check over one project's ``website/public/data`` directory.

    Missing optional artifacts are **skipped, not failed** — a scaffolded series
    has no forward-eval yet and that is a maturity level, not a defect. A file
    that exists and is wrong is always a failure.
    """
    data_dir = Path(data_dir)
    root = Path(root) if root is not None else data_dir
    report = Report(project=project or data_dir.parent.name)

    if not data_dir.is_dir():
        report.skipped.append("no published data directory")
        return report

    # The per-sport summary file: <slug>.json, identified by carrying a
    # calendar rather than by guessing the slug from the path.
    for candidate in sorted(data_dir.glob("*.json")):
        payload = _read_json(candidate)
        if isinstance(payload, dict) and isinstance(payload.get("calendar"), list):
            rel = _rel(candidate, root)
            report.findings.extend(check_calendar(payload, rel))
            report.findings.extend(check_competitors(payload, rel))
            break
    else:
        report.skipped.append("no season summary file with a calendar")

    rounds_dir = data_dir / "rounds"
    report.findings.extend(check_round_files_contiguous(rounds_dir, root, "rounds"))
    if not rounds_dir.is_dir():
        report.skipped.append("rounds/")

    probabilities_dir = data_dir / "probabilities"
    report.findings.extend(
        check_round_files_contiguous(probabilities_dir, root, "probabilities")
    )
    if probabilities_dir.is_dir():
        for _, path in _numbered_round_files(probabilities_dir):
            payload = _read_json(path)
            if isinstance(payload, dict):
                report.findings.extend(check_probabilities(payload, _rel(path, root)))
    else:
        report.skipped.append("probabilities/")

    forward_eval_dir = data_dir / "forward_eval"
    report.findings.extend(
        check_round_files_contiguous(forward_eval_dir, root, "forward_eval")
    )
    if forward_eval_dir.is_dir():
        report.findings.extend(check_baselines(forward_eval_dir, root))
    else:
        report.skipped.append("forward_eval/")

    for name, checker in (
        ("calibration_summary.json", check_calibration_gate),
        ("seasons.json", check_seasons),
        ("model_health.json", check_model_health),
    ):
        path = data_dir / name
        payload = _read_json(path) if path.is_file() else None
        if isinstance(payload, dict):
            report.findings.extend(checker(payload, _rel(path, root)))
        else:
            report.skipped.append(name)

    return report


def summarise(reports: Sequence[Report]) -> str:  # pragma: no cover - display only
    lines: list[str] = []
    for report in reports:
        status = "OK" if report.ok else f"{len(report.failures)} FAILURE(S)"
        lines.append(f"{report.project:28} {len(report.findings):3} checks  {status}")
        for finding in report.failures:
            lines.append(f"    {finding}")
    return "\n".join(lines)


__all__ = [
    "MARKET_MASS",
    "MASS_TOLERANCE",
    "PLACEHOLDER_NAMES",
    "DRIFT_SEVERITIES",
    "MIN_CALIBRATION_ROUNDS",
    "Finding",
    "Report",
    "check_published_data",
    "check_calendar",
    "check_competitors",
    "check_probabilities",
    "check_baselines",
    "check_calibration_gate",
    "check_seasons",
    "check_model_health",
    "check_round_files_contiguous",
    "summarise",
]
