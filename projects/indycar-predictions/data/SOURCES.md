# Data sources & attribution

All curated IndyCar history in this directory is derived from **English
Wikipedia**, retrieved via the MediaWiki `action=parse&prop=wikitext` API
(`https://en.wikipedia.org/w/api.php`) with a descriptive User-Agent, cached
under `raw_cache/` (gitignored). Wikipedia text is licensed
**CC BY-SA 4.0** — this dataset is a derivative work under the same license.

## What was parsed per season

For each season `history_{year}.json` is built from:

1. **Season article** `"{year} IndyCar Series"`
   - the *Schedule* table → round number, date, venue, track type
     (oval / road / street, from the O/R/S colour-box legend);
   - the *Results* table → the ordered list of per-race article titles;
   - the driver-standings **grid** → the official final standings (champion +
     points, the verification target) and the per-round finishing-position
     backbone.
2. **Per-race articles** (one per championship event, linked from the season
   *Results* table), e.g. `"{year} Indianapolis 500"`,
   `"{year} Firestone Grand Prix of St. Petersburg"` → the *Race classification*
   table: position, car no., driver, team, engine, laps, time/retired, grid,
   laps led, and **points as officially awarded**.

Points are taken verbatim from the classification tables (they already encode
the era's rules — pole/laps-led bonuses, the double-points Indy 500, etc.) and
are **never recomputed** from finishing position.

## Per-season primary pages

| Season | Wikipedia season article |
|---|---|
| 2012 | [2012 IndyCar Series](https://en.wikipedia.org/wiki/2012_IndyCar_Series) |
| 2013 | [2013 IndyCar Series](https://en.wikipedia.org/wiki/2013_IndyCar_Series) |
| 2014 | [2014 IndyCar Series](https://en.wikipedia.org/wiki/2014_IndyCar_Series) |
| 2015 | [2015 IndyCar Series](https://en.wikipedia.org/wiki/2015_IndyCar_Series) |
| 2016 | [2016 IndyCar Series](https://en.wikipedia.org/wiki/2016_IndyCar_Series) |
| 2017 | [2017 IndyCar Series](https://en.wikipedia.org/wiki/2017_IndyCar_Series) |
| 2018 | [2018 IndyCar Series](https://en.wikipedia.org/wiki/2018_IndyCar_Series) |
| 2019 | [2019 IndyCar Series](https://en.wikipedia.org/wiki/2019_IndyCar_Series) |
| 2020 | [2020 IndyCar Series](https://en.wikipedia.org/wiki/2020_IndyCar_Series) |
| 2021 | [2021 IndyCar Series](https://en.wikipedia.org/wiki/2021_IndyCar_Series) |
| 2022 | [2022 IndyCar Series](https://en.wikipedia.org/wiki/2022_IndyCar_Series) |
| 2023 | [2023 IndyCar Series](https://en.wikipedia.org/wiki/2023_IndyCar_Series) |
| 2024 | [2024 IndyCar Series](https://en.wikipedia.org/wiki/2024_IndyCar_Series) |
| 2025 | [2025 IndyCar Series](https://en.wikipedia.org/wiki/2025_IndyCar_Series) |
| 2026 | [2026 IndyCar Series](https://en.wikipedia.org/wiki/2026_IndyCar_Series) (in progress) |

The exact per-race article titles used are recorded in each season file under
`per_article_race_counts`.

## Cross-checks

- The **champion + final top-5** is verified for every season (see
  `CURATION_REPORT.md`); Indy 500 winners 2012–2025 were spot-checked against
  well-known results and all match.
- Racing-Reference (racing-reference.info) was **not** scraped — Wikipedia
  season + race tables were complete enough (its ToU limits automated access;
  it remains the fallback for any future gap-filling, at a handful of requests).

## Reproduce

```bash
python scripts/curate_all.py --years 2012-2026   # → history_*.json + CURATION_REPORT.md
python scripts/build_calendar.py --year 2026     # → calendar_2026.json
python scripts/load_history.py                   # → DuckDB load check
```
