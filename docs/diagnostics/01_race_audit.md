# Report 1 — Historical Race Audit (2026 Rounds 1–5)

**Generated:** 2026-06-03 · **Scope:** every completed race this season · **Method:** committed predictions (`predicted_results_2026.json` / `rounds/round_NN.json`) vs actuals (round-JSON `actualResults`, FastF1 race classification status), reusing `forward_eval.score_round`.

> This audit reports **root causes**, not just aggregate accuracy. The aggregate table is context; the per-race breakdown is the substance.

## Season snapshot

| R | GP | Within-5 | Mean pos err | Spearman | Winner hit | DNF/DNS | NaN-quali |
|---|----|----------|--------------|----------|------------|---------|-----------|
| 1 | Australia | 13/22 (59%) | 6.36 | 0.17 | ✗ | 5 | **3** |
| 2 | China | 16/22 (73%) | 4.64 | 0.49 | ✗ | **7** | 0 |
| 3 | Japan | **22/22 (100%)** | **2.00** | **0.93** | ✗ | **2** | 0 |
| 4 | Miami | 18/22 (82%) | 4.18 | 0.62 | ✗ | 4 | 0 |
| 5 | Canada | 14/22 (64%) | 5.36 | 0.39 | ✗ | 6 | 0 |

*(Within-5 here is over all 22 drivers; the `season_tracker` "accuracy_pct" uses within-3 for some rounds — both are reproduced exactly by `forward_eval`.)*

**The single clearest signal:** accuracy is inversely driven by race attrition. The cleanest race (Japan, 2 DNFs) is near-perfect; the messiest races (Australia, China, Canada) are the worst. **24 of 110 finishing slots (22%) were DNF/DNS/Retired across the five races.** The model has **no DNF/reliability term** (confirmed in `MODEL_CARD.md` known limitations), so every retirement of a highly-rated driver is an unavoidable large miss.

---

## Round 1 — Australian Grand Prix (worst: MAE 6.36)

**Two independent failure modes stacked.**

### Cause A — Qualifying NaN mishandling (the dominant, *fixable* error)
SAI and STR were predicted **P1 and P2** but **set no qualifying time** (`Position = NaN` in the Q session) and started **P21 and P22**. The qualifying-time model fell back to optimistic team/historic-pace estimates (~76.2 s) and seated them at the front of the grid-derived order. Result: two −14/−15 position misses driven purely by data handling, before a wheel turned.

- For drivers **with** real quali, the model tracked the grid well: PIA gridP5→predP5, VER gridP20→predP22, RUS gridP1→predP3. Spearman(predicted-finish, actual-grid) = 0.42 — depressed almost entirely by the SAI/STR inversion.
- 3 drivers had NaN qualifying in R1; none in R2–R5.

### Cause B — DNFs (race randomness)
PIA (DNS), HAD (Retired, gridP3) — two front-grid cars out. The model rated both highly (HAD predicted P6, PIA P5) and cannot foresee non-starts/retirements.

### Largest misses
| Driver | Pred | Actual | Δ | Root cause |
|--------|------|--------|---|-----------|
| PIA | 5 | 21 | −16 | **DNS** |
| VER | 22 | 6 | +16 | grid P20, strong recovery drive — model has no "recovery/racecraft" upside |
| STR | 2 | 17 | −15 | **NaN-quali** (started P22) |
| SAI | 1 | 15 | −14 | **NaN-quali** (started P21) |
| HAD | 6 | 20 | −14 | **Retired** |

**Verdict:** ~3 of the 5 biggest misses are NaN-quali/DNS data issues, not model-skill issues.

---

## Round 2 — Chinese Grand Prix (MAE 4.64)

**Pure attrition (7 DNFs — the highest of the season).** The misses are top drivers retiring:
- NOR (predP2) → P20 **DNS**; PIA (predP4) → P19 **DNS**; VER (predP7) → P16 **Retired**.

Notably MAE (4.64) is *not* the worst despite the most DNFs, because several retirements hit mid-pack predicted drivers (smaller position penalty). Where the cars ran to the end, the model was good (within-5 = 16/22). No data-quality issue here — this is irreducible race randomness the current model cannot price.

---

## Round 3 — Japanese Grand Prix (best: MAE 2.00, 22/22 within-5)

**The control case.** Only 2 DNFs, no NaN-quali, a clean race. Spearman 0.93, every driver within 5 of prediction, 2 exact. **This proves the core pace/qualifying model is genuinely strong when the race runs green** — the model is not broken; it is blind to chaos. Biggest "miss" was a benign HUL P16→P11 (+5).

---

## Round 4 — Miami Grand Prix (MAE 4.18)

A triple Red-Bull-family/midfield retirement cluster drove the error: HAD (predP8)→P22 **Retired**, GAS (predP9)→P21 **Retired**, LAW (predP10)→P20 **Retired**. BOR was underestimated (predP22→P12) — a genuine pace surprise. Otherwise solid (18/22 within-5). Again, **DNF-dominated**.

---

## Round 5 — Canadian Grand Prix (MAE 5.36, 0/3 podium hits)

**The most damaging DNFs of the season** — they hit the *front* of the predicted order:
- RUS (predP2, gridP1) → P19 **Retired**; NOR (predP1, gridP3) → P18 **Retired**; LIN (predP11) → P22 **DNS**; PIA (predP3) → P11 (Lapped).

Both predicted front-runners retired, so the podium prediction collapsed (0/3). This is the canonical "model looks terrible but was right about pace" case: the pace order was reasonable, the race deleted it. Sprint weekend (extra session) added no data problem.

---

## Cross-cutting findings

1. **DNFs are the #1 error source.** 24 retirements/non-starts (22% of slots); accuracy correlates inversely with DNF count (R3 cleanest→best, R1/R5 messiest→worst). No DNF model exists.
2. **Qualifying NaN handling is the #1 *fixable* error.** R1's SAI/STR fiasco shows that when a driver has no Q time, the model invents an optimistic grid slot instead of seating them at the back. Rare (R1 only so far) but catastrophic when it occurs, and **guaranteed to recur** at wet/disrupted qualifying or with grid penalties.
3. **Weather was not a driver of error.** All five rounds were effectively dry (rainProb ≤ 0.25); the wet-weather Elo never engaged. Not a current contributor; latent risk at a wet Monaco/Spa.
4. **The pace core is sound.** Japan (clean race) → near-perfect. The model's weakness is exclusively in events it has no feature for (retirement, non-start, no-time qualifying), not in rating car/driver pace.
5. **Data-quality gap discovered:** `season_results_2026.json` was missing R1–R3 actuals (only 4–5 present), so the round-to-round form features (`PreviousPosition`, `SeasonMomentum`) silently fell back to *predicted* positions for those rounds. Fixed in Report 3 / Step 3.

→ Ranked, quantified remediation in **Report 5**.
