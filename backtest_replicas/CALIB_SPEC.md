# Calibration per pair and timeframe, with the direction (Normal / Inverted) as a calibrated input

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Python 3, numpy, pandas, numba, pyarrow. `python3 -I`. Shared 4-CPU / 15 GB machine: a sweep may
use 3 worker processes; anything else at most 2 processes. Never write inside /home/user/master.

## Goal

For each strategy, pair (BTC, XAU) and chart timeframe (1, 5, 15, 30, 60, 120, 240 minutes): run
a grid over the strategy's own inputs (signal inputs, exits), the direction filter (off / on /
on without the blocked-signal close where the strategy has that switch) and the Update 1 option
"Inverted direction" (off / on), score every setting on realistic fills, and let a fixed rule
(below, the same for every strategy) decide whether any setting is defensible.

Each strategy has a verified replica module `$W/<strategy>.py` with
`prepare(pair, chart_tf, params)` (signals + filter permissions; reusable across exit settings)
and `simulate(prepared, exit_params)` (orders and exits; `path` 'tv' or 'mag' = 1-minute Bar
Magnifier fills; `cost` 'tv' = the script's own Properties, 'ours', 'stress'; `inv` = the
Inverted direction option), and a summary with the fair halves `h1r_pct` / `h2r_pct` (trades
entered in each half of the window, each half compounded from a fresh start), `h1_trades`,
`h2_trades`, trades, net_pct, pf, win_pct, max_dd_pct, exit-kind counts. Read the module's
docstring, `$W/SPEC_AH.md`, `$W/SWEEP_AH_SPEC.md`, `$W/INV_BT_SPEC.md` and the existing sweep
runner `$W/sweep_<strategy>.py` (the pattern to follow: grid(), exit_params(), fork workers
after the prepared inputs exist, deterministic output).

Windows (unchanged): BTC 1731801600..1794873600 (2024-11-17..2026-11-17), XAU
1483315200..1529366400 (2017-01-02..2018-06-19), split in two halves at the middle.

## The runner `$W/calib_<strategy>.py PAIR TF [TF ...] [--workers 3]`

- Defines the grid as two lists: SIGNAL settings (parameters of `prepare`, including the filter
  on / off) and EXIT settings (parameters of `simulate`, including `inv` and the blocked-close
  switch), and a description of every swept dimension:
  `DIMS = [{'name': ..., 'values': [...], 'kind': 'ordinal' | 'categorical'}, ...]`.
  A combination that cannot differ from another (e.g. the blocked-close switch with the filter
  off, trailing distances with trailing off) is listed once, with the unused dimensions set to
  the value None.
- Scores every setting with `path='mag'`, `cost='ours'`.
- Writes `$W/out/calib_<strategy>_<PAIR>_<TF>.parquet`: one row per setting; one column
  `p_<name>` per dimension, plus every summary field; and `$W/out/calib_<strategy>_dims.json`
  (DIMS). Deterministic across worker counts; prints timing; safe to re-run (overwrites).
- Provides `python3 -I calib_<strategy>.py --one PAIR TF '<json of p_ values>' [--path tv|mag]
  [--cost tv|ours|stress]` printing the full summary of one setting as JSON (used by the
  analysis for the stressed-cost and TradingView views of a pick).
- Tests `$W/calib_tests_<strategy>.py`: (1) the grid is the full product described, keys unique;
  (2) the row of the script's default setting equals the saved default result of the module
  (same path and cost); (3) 30 random rows recomputed one at a time through `--one` equal the
  sweep rows; (4) 1 worker vs 3 workers identical on XAU 240; (5) timing of one BTC 1 pass
  extrapolated to the full grid (the whole grid for BTC 1 must stay under 45 minutes with 3
  workers: thin the grid if not, and say what was thinned).

## Grids

ApexForge (`apex.py`), 12,312 settings per cell:
- signals: zoneLookback {10, 20, 30} x minBodyStr {0.5, 0.65, 0.8} x volMultiplier {1.2, 1.7, 2.2}
  (htfTimeframe stays "15")
- filter: off; on with the blocked-opposite close; on without it
- direction: normal; inverted
- exits: rrRatio {1.5, 2, 3, 5} x [trailing off | trailing on with activation {0.3, 1, 3} % x
  offset {0.2, 0.5, 1.5} % x target kept / dropped]

HRD (`hrd.py`), 23,328 settings per cell:
- signals: pivotStrength {3, 5, 8} x maxDivLookback {30, 60, 120} x divergences {all four,
  regular only, hidden only} (the show* inputs gate the signals; breakouts always trade)
- filter: off; on with the blocked-opposite close; on without it
- direction: normal; inverted ("Reverse Trading" stays off)
- exits: InpSlPct {1, 2, 4} x InpTpPct {0, 4} x InpExitCandles {5, 20, 100} x hybrid exit
  {on, off} x [trailing off | trailing on with (activation, offset) in {(0.5, 0.15), (1, 0.5),
  (2, 1)} %]

Other strategies: the grid is given in the task prompt.

## The rule (rule C, applied by the orchestrator's `calib_analyze.py`; the runner only produces the rows)

Scored on 1-minute fills with our costs, on the fair halves.
1. Pool: every grid setting; trailing offsets below the 1-minute noise floor (BTC 0.1%, XAU
   0.05%) are not in the grids. Settings with identical results count once.
2. Candidates: positive in both halves, at least 30 trades entered in each half.
3. Pick: among the 40 best candidates by worst half, the best by 0.5 x worst half + 0.5 x the
   mean worst half of its grid neighbours (settings that differ in exactly one dimension: one
   step for an ordinal dimension, any other value for a categorical one; at least 5 neighbours
   with a positive mean).
4. Hold-outs, both directions with the same bar: the 40 best settings by one half must, on the
   other half, beat 95% of random 40-setting draws from the pool, be at least 60% positive and
   have a positive mean.
5. Direction control: the pick must beat the same setting with the direction flipped (normal
   <-> inverted) in both halves.
6. Stressed costs: the pick must stay positive in both halves.
A pick that passes 1-6 is then attacked by independent sceptics before any file is published.
