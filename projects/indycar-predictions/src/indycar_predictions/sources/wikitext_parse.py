"""Wikitext parsers for IndyCar season + per-race articles.

VENDORED from ``scripts/parse.py`` (the curation pipeline that produced and
verified every committed ``data/history_<year>.json`` — see
``data/CURATION_REPORT.md``). The parsers are the proven contract: do not
change regexes here without re-running the curation verification. The only
adaptation is the alias-table path, which resolves through
:data:`indycar_predictions.config._DATA_DIR` so the package works installed
and under the test data-dir seam.

Strategy (see CURATION_REPORT.md):
  * season page "Schedule" table  -> per-round date / venue / track_type
  * season page "Results" table    -> ordered per-round article titles + winner
  * season page driver-standings grid -> official final standings (verify target)
  * per-race article "Race classification" tables -> full results incl. awarded
    points (a double-header article carries two such tables = two rounds)

Everything is regex on wikitext. Parsing is strict: callers assert car counts,
no duplicate positions, and that #race-classifications == #schedule-rounds.
"""
from __future__ import annotations

import json
import re

from .. import config as _config

_ALIASES_FP = _config._DATA_DIR / "driver_aliases.json"

TRACK_TYPE = {"O": "oval", "R": "road", "S": "street"}


# ---------------------------------------------------------------- text cleaning
def _strip_templates(s: str) -> str:
    """Remove {{...}} templates, innermost-first, so nested braces (e.g. an efn
    footnote wrapping a cite-web) are fully consumed."""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    return s


_FOOTNOTE_RE = re.compile(r"\{\{\s*(?:efn|refn|sfn|NoteTag|Ref\b)", re.I)


def _strip_footnotes(s: str) -> str:
    """Remove footnote templates ({{efn|...}}, {{refn|...}}, {{sfn|...}}) with
    balanced braces. These are annotations that often embed their own wikilinks,
    so they must go before we extract the cell's real wikilink value."""
    while True:
        m = _FOOTNOTE_RE.search(s)
        if not m:
            return s
        i = m.start()
        depth = 0
        j = i
        while j < len(s) - 1:
            two = s[j : j + 2]
            if two == "{{":
                depth += 1
                j += 2
                continue
            if two == "}}":
                depth -= 1
                j += 2
                if depth == 0:
                    break
                continue
            j += 1
        s = s[:i] + s[j:]


def _strip_refs(s: str) -> str:
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    return _strip_footnotes(s)


def _wikilink(s: str) -> str:
    """Return display text of the first [[wikilink]] in s, else cleaned s."""
    m = re.search(r"\[\[([^\]]+)\]\]", s)
    if m:
        inner = m.group(1)
        return inner.split("|")[-1].strip()
    return s.strip()


def clean_cell(s: str) -> str:
    s = _strip_refs(s)
    # {{Tooltip|Pos|Position}} / {{abbr|No.|Car Number}} -> first arg
    s = re.sub(r"\{\{(?:Tooltip|abbr|tooltip|Abbr)\|([^|}]+)(?:\|[^}]*)?\}\}", r"\1", s)
    s = re.sub(r"\{\{flagicon\|[^}]*\}\}", "", s, flags=re.I)
    s = re.sub(r"\{\{flag[^}]*\}\}", "", s, flags=re.I)
    s = re.sub(r"\{\{(?:Color box|colorbox|color box)\|[^}]*\}\}", "", s, flags=re.I)
    s = re.sub(r"<sup>.*?</sup>", "", s, flags=re.S)
    s = re.sub(r"<sub>.*?</sub>", "", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"'''''|'''|''", "", s)
    # extract the wikilink BEFORE stripping templates — a name can be wrapped in
    # {{nowrap|...}} / {{sort|...}}, and blind template removal would eat it.
    if "[[" in s:
        s = _wikilink(s)
    s = _strip_templates(s)  # leftover templates incl. nested efn footnotes
    s = re.sub(r"\[\[|\]\]", "", s)
    s = s.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()


# ------------------------------------------------------------------- alias table
def load_aliases() -> dict[str, str]:
    if _ALIASES_FP.exists():
        return json.loads(_ALIASES_FP.read_text())
    return {}


def save_aliases(a: dict[str, str]) -> None:
    _ALIASES_FP.write_text(json.dumps(dict(sorted(a.items())), indent=2) + "\n")


def norm_driver(name: str, aliases: dict[str, str]) -> str:
    n = clean_cell(name)
    return aliases.get(n, n)


# ------------------------------------------------------------------ section grab
def section(w: str, name: str, level: int = 2) -> str | None:
    eq = "=" * level
    m = re.search(rf"^{eq}\s*{re.escape(name)}\s*{eq}\s*$", w, re.M)
    if not m:
        return None
    start = m.end()
    nxt = re.search(rf"^={{1,{level}}}[^=]", w[start:], re.M)
    return w[start : start + nxt.start()] if nxt else w[start:]


def _tables(text: str) -> list[str]:
    """Return every wikitable body, including nested ones.

    Scans ``{|`` / ``|}`` markers with a depth stack. A top-level table's span
    is emitted, and nested inner tables are emitted too (so a classification
    table wrapped in a layout table is still found).
    """
    markers = []
    for m in re.finditer(r"\{\||\|\}", text):
        markers.append((m.start(), m.group()))
    out = []
    stack = []
    for pos, tok in markers:
        if tok == "{|":
            stack.append(pos)
        elif tok == "|}" and stack:
            start = stack.pop()
            out.append(text[start : pos + 2])
    return out


def _split_rows(table: str) -> list[str]:
    return re.split(r"\n\s*\|-", table)


_PIPE = "\x00"  # sentinel for pipes protected inside templates/links


def _mask_pipes(s: str) -> str:
    """Replace ``|`` inside {{...}} and [[...]] with a sentinel so cell-splitting
    on ``||`` is not fooled by template params (e.g. ``{{Color box|gold|W||...}}``)."""
    out = []
    depth = 0
    i = 0
    while i < len(s):
        two = s[i : i + 2]
        if two in ("{{", "[["):
            depth += 1
            out.append(two)
            i += 2
            continue
        if two in ("}}", "]]"):
            depth = max(0, depth - 1)
            out.append(two)
            i += 2
            continue
        if s[i] == "|" and depth > 0:
            out.append(_PIPE)
        else:
            out.append(s[i])
        i += 1
    return "".join(out)


def _split_cells(row: str, expand_colspan: bool = False) -> list[str]:
    """Split a wikitable row into cell payloads (both ! and | leading, and !!/|| inline).

    With ``expand_colspan`` a ``colspan="N"`` cell is emitted N times so that
    column indices stay aligned across rows — essential for reading the
    standings grid where a driver may have a colspan cell (e.g. a shared "DNS").
    """
    cells = []
    for line in row.split("\n"):
        line = line.strip()
        if not line or line.startswith("{|") or line.startswith("|}") or line.startswith("|+"):
            continue
        if line[0] not in "!|":
            continue
        body = _mask_pipes(line[1:])
        parts = re.split(r"\|\||!!", body)
        parts = [p.replace(_PIPE, "|") for p in parts]
        for p in parts:
            span = 1
            # strip a leading style attribute segment: `style=".." | value`
            if "|" in p and re.match(r'^[^|]*(?:style|align|scope|class|colspan|rowspan|bgcolor|width)\s*=', p, re.I):
                attrs, p = p.split("|", 1)
                if expand_colspan:
                    m = re.search(r'colspan\s*=\s*"?(\d+)', attrs, re.I)
                    if m:
                        span = int(m.group(1))
            val = p.strip()
            cells.extend([val] * span)
    return cells


# ---------------------------------------------------------------------- schedule
def parse_schedule(w: str) -> list[dict]:
    """Return championship rounds: {round, date_md, race_name, venue, track_type}."""
    sec = section(w, "Schedule")
    if sec is None:
        raise ValueError("no Schedule section")
    tabs = _tables(sec)
    # pick the table whose header contains 'Rd' and 'Location' (skip the legend)
    sched = None
    for t in tabs:
        head = t[:600]
        if re.search(r"!\s*Rd", head) and "Location" in t:
            sched = t
            break
    if sched is None:
        # fallback: the largest table
        sched = max(tabs, key=len)
    rounds = []
    last_tt = None
    last_venue = None
    for row in _split_rows(sched)[1:]:
        rd_m = re.search(r"!\s*(?:[^|\n]*\|)?\s*(NC|\d+)\b", row)
        if not rd_m:
            continue
        rd = rd_m.group(1)
        tt_m = re.search(r"[Cc]olor ?box\|(?:\w+)\|([ORS])\b", row)
        date_m = re.search(r"\|\s*([A-Z][a-z]+ \d+)(?:\s*[-–]\s*\d+)?", row)
        # venue: the text after the color-box template — a [[wikilink]] or plain
        # text ("Streets of Markham"). Take the remainder of that cell line.
        venue = None
        vm = re.search(r"[Cc]olor ?box\|[^}]*\}\}\s*([^\n]+)", row)
        if vm:
            venue = clean_cell(vm.group(1)) or None
        track_type = TRACK_TYPE.get(tt_m.group(1)) if tt_m else None
        if track_type is None:
            track_type = last_tt  # double-header 2nd race inherits (rowspan)
        if venue is None:
            venue = last_venue  # rowspan double-header 2nd race
        last_tt, last_venue = track_type, venue
        # race name: first wikilink after the date column that isn't the venue
        name_m = re.search(r"\|\s*\[\[([^\]]+)\]\]", row)
        race_name = name_m.group(1).split("|")[-1].strip() if name_m else None
        rounds.append(
            {
                "sched_rd": rd,
                "date_md": date_m.group(1) if date_m else None,
                "race_name": race_name,
                "venue": venue,
                "track_type": track_type,
            }
        )
    # keep only championship rounds (numeric Rd), in order
    champ = [r for r in rounds if r["sched_rd"] != "NC"]
    for i, r in enumerate(champ, 1):
        r["round"] = i
    return champ


# ----------------------------------------------------------------- results table
def parse_results_articles(w: str, year: int) -> list[str]:
    """Ordered per-round championship article titles (skips NC rows)."""
    sec = section(w, "Results")
    if sec is None:
        raise ValueError("no Results section")
    table = _tables(sec)[0]
    articles = []
    for row in _split_rows(table)[1:]:
        rd_m = re.search(r"!\s*(?:[^|\n]*\|)?\s*(NC|\d+)\b", row)
        rep_m = re.search(r"\[\[([^\|\]]+)\|Report\]\]", row)
        if rd_m and rep_m:
            if rd_m.group(1) == "NC":
                continue
            articles.append(rep_m.group(1).strip())
    return articles


# ----------------------------------------------------- per-race classification(s)
_HEADER_MAP = [
    ("pos", r"\bpos\b|position|\bfinish\b|\bfin\b|\bplace\b"),
    ("no", r"\bno\.?\b|car ?number|\bcar\b"),
    ("driver", r"driver"),
    ("team", r"team|entrant"),
    ("engine", r"^engine$|manufacturer"),
    ("laps", r"^laps$|\blaps\b(?!.*led)"),
    ("status", r"time/retired|retired|status|time"),
    ("grid", r"\bgrid\b|\bstart\b|qual"),
    ("laps_led", r"laps ?led|led"),
    ("points", r"\bpts\b|points"),
]


def _classify_header(cells: list[str]) -> dict[str, int]:
    idx = {}
    for i, c in enumerate(cells):
        cc = clean_cell(c).lower()
        for key, pat in _HEADER_MAP:
            if key in idx:
                continue
            if re.search(pat, cc):
                idx[key] = i
                break
    return idx


def _is_race_table(header: dict[str, int]) -> bool:
    """A race-classification header has Pos+Driver+Points and Grid or Laps-led —
    which separates it from qualifying (no points), championship-standings-after
    (no grid/laps-led) and practice/top-speed tables (no points)."""
    return (
        "pos" in header
        and "driver" in header
        and "points" in header
        and ("grid" in header or "laps_led" in header)
    )


def parse_race_classifications(w: str, aliases: dict[str, str]) -> list[list[dict]]:
    """Return a list (one per race, in document order) of result-row lists.

    Section-name agnostic: scans every wikitable and keeps the ones whose header
    signature is a race classification. Handles articles that title the table
    "Race classification", "Race results", or leave it untitled under "Race",
    and double-header articles carrying two such tables.
    """
    races = []
    for tab in _tables(w):
        rows = _split_rows(tab)
        if len(rows) < 3:
            continue
        # the header row is the first row whose cells name a Driver column — it
        # may be preceded by a `|-` and a `|+ caption`, so it is not always row 0
        h_idx = None
        header = {}
        for j, row in enumerate(rows[:3]):
            hh = _classify_header(_split_cells(row))
            if "driver" in hh:
                h_idx, header = j, hh
                break
        if h_idx is None or not _is_race_table(header):
            continue
        results = []
        for row in rows[h_idx + 1 :]:
            if "colspan" in row.lower() and "sortbottom" in row.lower():
                continue
            cells = _split_cells(row)
            if len(cells) <= header.get("driver", 99):
                continue
            pos_raw = clean_cell(cells[header["pos"]])
            drv = norm_driver(cells[header["driver"]], aliases)
            if not drv or not pos_raw:
                continue

            def g(key):
                i = header.get(key)
                return clean_cell(cells[i]) if i is not None and i < len(cells) else None

            pos = int(pos_raw) if pos_raw.isdigit() else None
            grid = g("grid")
            laps = g("laps")
            pts = g("points")
            pts_m = re.match(r"(\d+(?:\.\d+)?)", pts) if pts else None
            pts_val = float(pts_m.group(1)) if pts_m else None
            results.append(
                {
                    "position": pos,
                    "position_raw": pos_raw,
                    "driver": drv,
                    "team": g("team"),
                    "engine": g("engine"),
                    "grid": int(grid) if grid and grid.isdigit() else None,
                    "laps": int(laps) if laps and laps.isdigit() else None,
                    "status": g("status"),
                    "points": pts_val,
                }
            )
        if results:
            races.append(results)
    return races


# ------------------------------------------------------------ driver standings
def _parse_standings_grid(grid: str, aliases: dict[str, str]) -> list[dict]:
    rows = _split_rows(grid)
    # locate header row (Pos + Driver + Pts) within the first few rows
    h_idx = None
    header = {}
    for j, row in enumerate(rows[:3]):
        hh = _classify_header(_split_cells(row))
        if "driver" in hh and "pos" in hh and "points" in hh:
            h_idx, header = j, hh
            break
    if h_idx is None:
        return []
    out = []
    seen = set()
    for row in rows[h_idx + 1 :]:
        cells = _split_cells(row)
        if len(cells) < 3:
            continue
        pos_raw = clean_cell(cells[header["pos"]]) if header["pos"] < len(cells) else ""
        if not pos_raw.isdigit():
            continue
        drv_cell = cells[header["driver"]] if header["driver"] < len(cells) else ""
        if "[[" not in drv_cell:
            continue
        driver = norm_driver(drv_cell, aliases)
        if not driver or driver in seen:
            continue
        seen.add(driver)
        pts_raw = clean_cell(cells[-1])
        pts = float(pts_raw) if re.fullmatch(r"\d+(?:\.\d+)?", pts_raw) else None
        out.append({"pos": int(pos_raw), "driver": driver, "points": pts})
    return out


def _find_driver_grid(w: str) -> str | None:
    """Return the raw wikitext of the driver-standings grid (Pos+Driver+…+Pts),
    the largest such table that is not the manufacturer/entrant standings."""
    sec = section(w, "Points standings") or section(w, "Championship standings") or w
    best = None
    best_rows = 0
    for t in _tables(sec):
        if t.count("{|") > 1:
            continue  # layout wrapper containing a nested grid — skip to the inner
        rows = _split_rows(t)
        if not rows:
            continue
        is_manu = any(
            "manufacturer" in clean_cell(c).lower() or clean_cell(c).lower() == "entrant"
            for row in rows[:3]
            for c in _split_cells(row)
        )
        if is_manu:
            continue
        has_header = any(
            {"driver", "pos", "points"} <= set(_classify_header(_split_cells(row)))
            for row in rows[:3]
        )
        if has_header and len(rows) > best_rows:
            best, best_rows = t, len(rows)
    return best


def parse_standings(w: str, aliases: dict[str, str]) -> list[dict]:
    """Official final standings: {pos, driver, points} from the driver grid."""
    grid = _find_driver_grid(w)
    if grid is None:
        raise ValueError("no standings grid")
    out = _parse_standings_grid(grid, aliases)
    if not out:
        raise ValueError("no standings grid")
    return out


# codes in a standings-grid cell that are not a finishing position
_GRID_CODES = {
    "RET": "Retired", "DNS": "Did not start", "DNQ": "Did not qualify",
    "DNP": "Did not practice", "NS": "Did not start", "WTH": "Withdrawn",
    "DSQ": "Disqualified", "EX": "Excluded", "C": "Cancelled", "DNF": "Retired",
}


def parse_grid(w: str, aliases: dict[str, str]) -> dict:
    """Parse the driver grid into standings + a per-round position matrix.

    Returns ``{"standings": [...], "n_races": int, "rounds": [[{driver, position,
    status}]]}``. The matrix is the authoritative positional backbone for every
    season — it is present even when per-race articles are stubs. Cells are the
    columns strictly between Driver and Pts; double-headers are already split
    into separate data cells, so ``n_races`` counts actual races.
    """
    grid = _find_driver_grid(w)
    if grid is None:
        raise ValueError("no standings grid")
    rows = _split_rows(grid)
    h_idx = None
    header = {}
    for j, row in enumerate(rows[:3]):
        hh = _classify_header(_split_cells(row))
        if {"driver", "pos", "points"} <= set(hh):
            h_idx, header = j, hh
            break
    if h_idx is None:
        raise ValueError("no grid header")

    driver_col = header["driver"]
    # position columns are those strictly between driver and the final Pts cell
    per_round: list[list[dict]] = []
    standings: list[dict] = []
    seen = set()
    n_races = 0
    for row in rows[h_idx + 1 :]:
        cells = _split_cells(row, expand_colspan=True)
        if len(cells) < driver_col + 2:
            continue
        pos_raw = clean_cell(cells[header["pos"]]) if header["pos"] < len(cells) else ""
        drv_cell = cells[driver_col]
        if "[[" not in drv_cell or not pos_raw.isdigit():
            continue
        driver = norm_driver(drv_cell, aliases)
        if not driver or driver in seen:
            continue
        seen.add(driver)
        pts_raw = clean_cell(cells[-1])
        pts = float(pts_raw) if re.fullmatch(r"\d+(?:\.\d+)?", pts_raw) else None
        standings.append({"pos": int(pos_raw), "driver": driver, "points": pts})
        round_cells = cells[driver_col + 1 : -1]
        n_races = max(n_races, len(round_cells))
        for i, rc in enumerate(round_cells):
            if len(per_round) <= i:
                per_round.append([])
            val = clean_cell(rc)
            if not val:
                continue  # driver did not contest this round
            m = re.match(r"(\d+)", val)
            if m:
                per_round[i].append(
                    {"driver": driver, "position": int(m.group(1)), "status": None}
                )
            else:
                code = re.sub(r"[^A-Za-z]", "", val).upper()
                per_round[i].append(
                    {
                        "driver": driver,
                        "position": None,
                        "status": _GRID_CODES.get(code, code or "DNF"),
                    }
                )
    return {"standings": standings, "n_races": n_races, "rounds": per_round}
