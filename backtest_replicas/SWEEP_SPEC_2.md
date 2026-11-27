# Sweep extension (v2): label-reversal control, stressed costs, fair halves

Extends `$W/sweep_core.py` / `$W/sweep.py` (built from `$W/SWEEP_SPEC.md`). Everything
in SWEEP_SPEC.md still holds; the existing outputs and tests must keep passing.

## Why

The first by-timeframe run showed that on BTC the default trail produced the same profit
with every label reversed: the profit came from the intrabar path assumption, not from the
signals. Every sweep setting therefore needs the same control. The hold-out test that will
pick settings per timeframe also needs halves that do not leak: today half2_pct is P/L
realised in the second half on an equity that compounded through the first half, so a
setting that did well in half 1 trades larger in half 2.

## 1. Labels dimension

New column `labels` in {"normal", "rev"}. "rev" = the same run with the XPW input
"Reverse every label" on: sig = `xpw.xpw_signals(pair, tf, start, end, {'reverseAll': True})`
(cache it like the normal sig; perm is the same). `sweep.py` gets `--labels normal,rev`
(default both). Rows are keyed by (filter, path, labels, setting).

## 2. Stressed costs

A third cost mode `stress`, metric prefix `stress_`: XAU $0.50 per ounce round trip plus 1
tick (0.01) per side; BTC 0.035% of price per side + $0.20 per coin round trip + 1 tick per
side. (Per unit: XAU 0.50 + 0.02; BTC 0.00035 * (entry + exit) + 0.20 + 0.02.)

## 3. Fair halves

For each cost mode (`tv0`, `cost`, `stress`) add:
- `h1r_pct`, `h2r_pct`: the trades ENTERED in the first half (entry_time <= mid) and in the
  second half (entry_time > mid), each simulated with metrics()' money model from a fresh
  10,000 (compounding inside the half only). mid = start + (end - start) // 2 as in
  metrics().
- `h1_trades`, `h2_trades`: the number of trades entered in each half.
- `h1r_pf`, `h2r_pf`: profit factor inside each half.
The existing half1_pct / half2_pct stay unchanged.

## 4. Tests to add to sweep_tests.py (run them, show the output)

- T5 rev labels on the tv path equal `engine.backtest` with the reversed sig, on 20 random
  settings over the T1 windows.
- T6 h1r / h2r: equal a direct Python computation (split the trades by entry time, call
  `run_tf.metrics()` on each part with start/end set to that half) within 1e-9, on 20
  random settings over the T1 windows, all three cost modes (`run_tf.metrics` takes
  with_cost bool; for stress write a 3-line variant of its cost function in the test).
- T7 stress metrics: equal a direct Python computation on the same 20 settings.
- All of T1-T4 still pass.

## 5. Output

`$W/out/sweep_<PAIR>_<TF>.parquet` gains the `labels` column and the new metrics.
Expected rows per (pair, TF): 2 filters x 2 paths x 2 labels x 1380 (chart "1": `mag` rows
are a copy of `tv` with path "mag", as now).
