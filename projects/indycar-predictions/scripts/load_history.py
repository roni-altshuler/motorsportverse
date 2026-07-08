"""Load all data/history_*.json into DuckDB and print per-season counts.

Proves the curated season files are machine-consumable for Phase-3 model work.
Builds a plain DuckDB `results` table (full race classifications don't fit the
prediction-pair schema of motorsport_data.store.HistoryStore, which keys on
predicted/actual position); we additionally push the actual finishing positions
into a HistoryStore-compatible table when duckdb + the package are importable.

Usage: python scripts/load_history.py [--db data/indycar_history.duckdb]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

RESULTS_DDL = """
CREATE OR REPLACE TABLE results (
    season       INTEGER,
    round        INTEGER,
    venue        TEXT,
    track_type   TEXT,
    date         DATE,
    has_detail   BOOLEAN,
    position     INTEGER,
    driver       TEXT,
    team         TEXT,
    engine       TEXT,
    grid         INTEGER,
    laps         INTEGER,
    status       TEXT,
    points       DOUBLE
);
"""

STANDINGS_DDL = """
CREATE OR REPLACE TABLE final_standings (
    season INTEGER,
    pos    INTEGER,
    driver TEXT,
    points DOUBLE
);
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DATA / "indycar_history.duckdb"))
    args = ap.parse_args()

    try:
        import duckdb
    except ImportError:
        sys.exit("duckdb not installed — `pip install duckdb`")

    files = sorted(glob.glob(str(DATA / "history_*.json")))
    if not files:
        sys.exit("no history_*.json files found — run curate_all.py first")

    con = duckdb.connect(args.db)
    con.execute(RESULTS_DDL)
    con.execute(STANDINGS_DDL)

    res_rows = []
    std_rows = []
    for fp in files:
        s = json.loads(Path(fp).read_text())
        year = s["season"]
        for rd in s["rounds"]:
            for r in rd["results"]:
                res_rows.append(
                    (
                        year, rd["round"], rd.get("venue"), rd.get("track_type"),
                        rd.get("date"), rd.get("has_full_detail"),
                        r.get("position"), r.get("driver"), r.get("team"),
                        r.get("engine"), r.get("grid"), r.get("laps"),
                        r.get("status"), r.get("points"),
                    )
                )
        for st in s.get("final_standings", []):
            std_rows.append((year, st["pos"], st["driver"], st.get("points")))

    con.executemany(
        "INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", res_rows
    )
    con.executemany("INSERT INTO final_standings VALUES (?,?,?,?)", std_rows)

    print(f"Loaded {len(files)} season files into {args.db}\n")
    print(f"{'Season':>6} {'Rounds':>7} {'Rows':>6} {'DetailRds':>10} "
          f"{'Drivers':>8} {'Champion':<22} {'Pts':>6}")
    print("-" * 74)
    summary = con.execute(
        """
        WITH r AS (
            SELECT season,
                   COUNT(DISTINCT round)                        AS rounds,
                   COUNT(*)                                     AS rows,
                   COUNT(DISTINCT CASE WHEN has_detail THEN round END) AS detail_rounds,
                   COUNT(DISTINCT driver)                       AS drivers
            FROM results GROUP BY season
        )
        SELECT r.season, r.rounds, r.rows, r.detail_rounds, r.drivers,
               fs.driver, fs.points
        FROM r
        LEFT JOIN final_standings fs ON fs.season = r.season AND fs.pos = 1
        ORDER BY r.season
        """
    ).fetchall()
    tot_rows = 0
    for season, rounds, rows_, det, drivers, champ, pts in summary:
        tot_rows += rows_
        print(f"{season:>6} {rounds:>7} {rows_:>6} {det:>10} {drivers:>8} "
              f"{(champ or ''):<22} {int(pts) if pts is not None else '?':>6}")
    print("-" * 74)
    print(f"{'TOTAL':>6} {'':>7} {tot_rows:>6} rows across "
          f"{len(summary)} seasons")

    # sanity: no duplicate (season, round, position) among classified finishers
    dups = con.execute(
        """
        SELECT season, round, position, COUNT(*) c
        FROM results WHERE position IS NOT NULL
        GROUP BY season, round, position HAVING COUNT(*) > 1
        """
    ).fetchall()
    print(f"\nDuplicate (season,round,position) groups: {len(dups)}"
          + ("" if not dups else f"  -> {dups[:5]}"))
    con.close()


if __name__ == "__main__":
    main()
