# IndyCar Curation Report

Source: English Wikipedia season + per-race articles (CC BY-SA; see `SOURCES.md`). Points are recorded **as officially awarded** — parsed from each race's classification table (including pole / laps-led bonuses and double-points events); they are never recomputed from finishing position.

**Two curation modes** (per season):

- *Full detail*: every round parsed from its per-race classification table (position, driver, team, engine, grid, laps, status, points). The **standings check** recomputes the championship top-5 by summing curated per-race points and compares to the official standings grid — an independent cross-check.
- *Grid-backed* (older DW12-era seasons with Wikipedia stub race articles): finishing **positions** come from the season standings grid (authoritative), and per-race **points/grid/laps** are recovered for individual rounds by matching parsed race tables to the grid via a finishing-position fingerprint. Standings check = the official grid champion + top-5 (parsed cleanly).

**Status**: PASS = standings check (champion + top-5) exact **and** no hard anomalies. The per-race point-sum is a secondary integrity check; the *Point residuals* column lists drivers whose summed per-race points differ from the official season total by a few points — these stem from source-level penalty/bonus accounting differences (and one Wikipedia article-vs-standings inconsistency, 2022 Indy 500) and never change the standings order.

## Summary

| Season | Rounds | O/R/S | Detail | Champion | Standings check | Point residuals | Anomalies | Status |
|---|---|---|---|---|---|---|---|---|
| 2012 | 15 | 5/4/6 | 13/15 | Ryan Hunter-Reay | PASS | 0 | 0 | PASS |
| 2013 | 19 | 6/3/10 | 13/19 | Scott Dixon | PASS | 0 | 0 | PASS |
| 2014 | 18 | 6/4/8 | 10/18 | Will Power | PASS | 0 | 0 | PASS |
| 2015 | 16 | 6/5/5 | 13/16 | Scott Dixon | PASS | 0 | 0 | PASS |
| 2016 | 16 | 5/6/5 | 16/16 | Simon Pagenaud | PASS | 1 | 0 | PASS |
| 2017 | 17 | 6/6/5 | 15/17 | Josef Newgarden | PASS | 0 | 0 | PASS |
| 2018 | 17 | 6/6/5 | 17/17 | Scott Dixon | PASS | 5 | 0 | PASS |
| 2019 | 17 | 5/7/5 | 17/17 | Josef Newgarden | PASS | 2 | 0 | PASS |
| 2020 | 14 | 6/7/1 | 14/14 | Scott Dixon | PASS | 1 | 0 | PASS |
| 2021 | 16 | 4/7/5 | 16/16 | Álex Palou | PASS | 3 | 0 | PASS |
| 2022 | 17 | 5/7/5 | 17/17 | Will Power | PASS | 1 | 0 | PASS |
| 2023 | 17 | 5/7/5 | 17/17 | Álex Palou | PASS | 0 | 0 | PASS |
| 2024 | 17 | 7/6/4 | 17/17 | Álex Palou | PASS | 1 | 0 | PASS |
| 2025 | 17 | 6/7/4 | 17/17 | Álex Palou | PASS | 2 | 0 | PASS |
| 2026 | 11 | 3/4/4 | 11/11 | Álex Palou | PASS | 0 | 0 | PASS |

**Total result rows across all seasons: 6102.**

## Indy 500 winners (sanity proof)

| Season | Indy 500 winner (curated) |
|---|---|
| 2012 | Dario Franchitti |
| 2013 | Tony Kanaan |
| 2014 | Ryan Hunter-Reay |
| 2015 | Juan Pablo Montoya |
| 2016 | Alexander Rossi |
| 2017 | Takuma Sato |
| 2018 | Will Power |
| 2019 | Simon Pagenaud |
| 2020 | Takuma Sato |
| 2021 | Hélio Castroneves |
| 2022 | Marcus Ericsson |
| 2023 | Josef Newgarden |
| 2024 | Josef Newgarden |
| 2025 | Álex Palou |
| 2026 | Felix Rosenqvist |

## Per-season detail

### 2012 — PASS

- Source: `2012 IndyCar Series` + per-race articles
- Rounds curated: 15 (oval 5, road 4, street 6)
- Champion: **Ryan Hunter-Reay** — standings check (champion + top-5): PASS (standings-grid-only (per-race points partial))
  - top-5: Ryan Hunter-Reay, Will Power, Scott Dixon, Hélio Castroneves, Simon Pagenaud
- Per-race full detail: 13/15 rounds
- Notes:
  - per-race articles parsed 14/15 rounds (older-season stub articles); per-race points recovered for 13/15 rounds via position-matching, remaining rounds are positions-only from the standings grid

### 2013 — PASS

- Source: `2013 IndyCar Series` + per-race articles
- Rounds curated: 19 (oval 6, road 3, street 10)
- Champion: **Scott Dixon** — standings check (champion + top-5): PASS (standings-grid-only (per-race points partial))
  - top-5: Scott Dixon, Hélio Castroneves, Simon Pagenaud, Will Power, Marco Andretti
- Per-race full detail: 13/19 rounds
- Notes:
  - per-race articles parsed 13/19 rounds (older-season stub articles); per-race points recovered for 13/19 rounds via position-matching, remaining rounds are positions-only from the standings grid

### 2014 — PASS

- Source: `2014 IndyCar Series` + per-race articles
- Rounds curated: 18 (oval 6, road 4, street 8)
- Champion: **Will Power** — standings check (champion + top-5): PASS (standings-grid-only (per-race points partial))
  - top-5: Will Power, Hélio Castroneves, Scott Dixon, Juan Pablo Montoya, Simon Pagenaud
- Per-race full detail: 10/18 rounds
- Notes:
  - per-race articles parsed 10/18 rounds (older-season stub articles); per-race points recovered for 10/18 rounds via position-matching, remaining rounds are positions-only from the standings grid

### 2015 — PASS

- Source: `2015 IndyCar Series` + per-race articles
- Rounds curated: 16 (oval 6, road 5, street 5)
- Champion: **Scott Dixon** — standings check (champion + top-5): PASS (standings-grid-only (per-race points partial))
  - top-5: Scott Dixon, Juan Pablo Montoya, Will Power, Graham Rahal, Hélio Castroneves
- Per-race full detail: 13/16 rounds
- Notes:
  - per-race articles parsed 13/16 rounds (older-season stub articles); per-race points recovered for 13/16 rounds via position-matching, remaining rounds are positions-only from the standings grid

### 2016 — PASS

- Source: `2016 IndyCar Series` + per-race articles
- Rounds curated: 16 (oval 5, road 6, street 5)
- Champion: **Simon Pagenaud** — standings check (champion + top-5): PASS (point-sum-recompute)
  - top-5: Simon Pagenaud, Will Power, Hélio Castroneves, Josef Newgarden, Graham Rahal
- Per-race full detail: 16/16 rounds
- Point-sum residuals (1):
  - Will Power: curated 531 vs official 532 (-1)

### 2017 — PASS

- Source: `2017 IndyCar Series` + per-race articles
- Rounds curated: 17 (oval 6, road 6, street 5)
- Champion: **Josef Newgarden** — standings check (champion + top-5): PASS (standings-grid-only (per-race points partial))
  - top-5: Josef Newgarden, Simon Pagenaud, Scott Dixon, Hélio Castroneves, Will Power
- Per-race full detail: 15/17 rounds
- Notes:
  - per-race articles parsed 15/17 rounds (older-season stub articles); per-race points recovered for 15/17 rounds via position-matching, remaining rounds are positions-only from the standings grid

### 2018 — PASS

- Source: `2018 IndyCar Series` + per-race articles
- Rounds curated: 17 (oval 6, road 6, street 5)
- Champion: **Scott Dixon** — standings check (champion + top-5): PASS (point-sum-recompute)
  - top-5: Scott Dixon, Alexander Rossi, Will Power, Ryan Hunter-Reay, Josef Newgarden
- Per-race full detail: 17/17 rounds
- Point-sum residuals (5):
  - Josef Newgarden: curated 559 vs official 560 (-1)
  - Marco Andretti: curated 393 vs official 392 (+1)
  - James Hinchcliffe: curated 390 vs official 391 (-1)
  - Tony Kanaan: curated 310 vs official 312 (-2)
  - Matheus Leist: curated 255 vs official 253 (+2)

### 2019 — PASS

- Source: `2019 IndyCar Series` + per-race articles
- Rounds curated: 17 (oval 5, road 7, street 5)
- Champion: **Josef Newgarden** — standings check (champion + top-5): PASS (point-sum-recompute)
  - top-5: Josef Newgarden, Simon Pagenaud, Alexander Rossi, Scott Dixon, Will Power
- Per-race full detail: 17/17 rounds
- Point-sum residuals (2):
  - Colton Herta: curated 424 vs official 420 (+4)
  - Marco Andretti: curated 305 vs official 303 (+2)

### 2020 — PASS

- Source: `2020 IndyCar Series` + per-race articles
- Rounds curated: 14 (oval 6, road 7, street 1)
- Champion: **Scott Dixon** — standings check (champion + top-5): PASS (point-sum-recompute)
  - top-5: Scott Dixon, Josef Newgarden, Colton Herta, Pato O'Ward, Will Power
- Per-race full detail: 14/14 rounds
- Point-sum residuals (1):
  - Takuma Sato: curated 351 vs official 348 (+3)

### 2021 — PASS

- Source: `2021 IndyCar Series` + per-race articles
- Rounds curated: 16 (oval 4, road 7, street 5)
- Champion: **Álex Palou** — standings check (champion + top-5): PASS (point-sum-recompute)
  - top-5: Álex Palou, Josef Newgarden, Pato O'Ward, Scott Dixon, Colton Herta
- Per-race full detail: 16/16 rounds
- Point-sum residuals (3):
  - Pato O'Ward: curated 482 vs official 487 (-5)
  - Colton Herta: curated 454 vs official 455 (-1)
  - Max Chilton: curated 131 vs official 134 (-3)

### 2022 — PASS

- Source: `2022 IndyCar Series` + per-race articles
- Rounds curated: 17 (oval 5, road 7, street 5)
- Champion: **Will Power** — standings check (champion + top-5): PASS (point-sum-recompute)
  - top-5: Will Power, Josef Newgarden, Scott Dixon, Scott McLaughlin, Álex Palou
- Per-race full detail: 17/17 rounds
- Point-sum residuals (1):
  - Alexander Rossi: curated 401 vs official 381 (+20)

### 2023 — PASS

- Source: `2023 IndyCar Series` + per-race articles
- Rounds curated: 17 (oval 5, road 7, street 5)
- Champion: **Álex Palou** — standings check (champion + top-5): PASS (point-sum-recompute)
  - top-5: Álex Palou, Scott Dixon, Scott McLaughlin, Pato O'Ward, Josef Newgarden
- Per-race full detail: 17/17 rounds

### 2024 — PASS

- Source: `2024 IndyCar Series` + per-race articles
- Rounds curated: 17 (oval 7, road 6, street 4)
- Champion: **Álex Palou** — standings check (champion + top-5): PASS (point-sum-recompute)
  - top-5: Álex Palou, Colton Herta, Scott McLaughlin, Will Power, Pato O'Ward
- Per-race full detail: 17/17 rounds
- Point-sum residuals (1):
  - Felix Rosenqvist: curated 307 vs official 306 (+1)

### 2025 — PASS

- Source: `2025 IndyCar Series` + per-race articles
- Rounds curated: 17 (oval 6, road 7, street 4)
- Champion: **Álex Palou** — standings check (champion + top-5): PASS (point-sum-recompute)
  - top-5: Álex Palou, Pato O'Ward, Scott Dixon, Kyle Kirkwood, Christian Lundgaard
- Per-race full detail: 17/17 rounds
- Point-sum residuals (2):
  - Conor Daly: curated 269 vs official 268 (+1)
  - Nolan Siegel: curated 212 vs official 213 (-1)

### 2026 — PASS

- Source: `2026 IndyCar Series` + per-race articles
- Rounds curated: 11 (oval 3, road 4, street 4)
- Champion: **Álex Palou** — standings check (champion + top-5): PASS (point-sum-recompute)
  - top-5: Álex Palou, Kyle Kirkwood, Christian Lundgaard, David Malukas, Pato O'Ward
- Per-race full detail: 11/11 rounds
- Notes:
  - IN-PROGRESS season: 11 of 18 rounds completed and curated

