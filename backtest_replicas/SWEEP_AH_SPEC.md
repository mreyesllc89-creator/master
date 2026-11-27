# Trailing sweep for ApexForge + FGF and HRD v1.03 + FGF

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Python 3, numpy, pandas, numba. `python3 -I`. Shared 4-CPU machine: at most 3 worker
processes for the sweep, at most 2 processes otherwise.

Context: `$W/SPEC_AH.md` (the replica spec), the verified replicas `$W/apex.py` and `$W/hrd.py`
(reconcile notes `$W/reconcile_apex.md`, `$W/reconcile_hrd.md`), their runners
`$W/run_apex.py`, `$W/run_hrd.py` and saved results `$W/out/apex_*.json`, `$W/out/hrd_*.json`,
`$W/out/apex_trades/`, `$W/out/hrd_trades/`. Read `$W/SWEEP_SPEC.md` too: the XPW trailing
sweep this one mirrors (its 'mag' Bar Magnifier path and its engine `$W/sweep_core.py`,
whose `_walk` handles a trailing stop + stop loss along a path).

## 1. The Pine change being replicated

Both fused files gained an optional trailing take profit, off by default (read the new
inputs, the header section TRAILING TAKE PROFIT and the strategy.exit calls):
- `/home/user/master/ApexForge_Flow_Resonance_Strategy_FGF.pine`: inputs apxTrailOn (false),
  apxTrailAct (%), apxTrailOff (%), apxUseTarget (true). Trail ticks = max(close x act /100 /
  mintick, 0) and max(close x off /100 /mintick, 1), computed on the bar whose entry opens a
  new trade (position flat or opposite), stored, and re-sent unchanged when a later same-side
  signal re-sets the stop / target (strategy.exit with the same id).
- `/home/user/master/HRD_Full_Divergence_Strategy_v1_03_FGF.pine`: inputs hrdTrailOn (false),
  hrdTrailAct, hrdTrailOff; ticks from estimatedEntryPrice (the signal close), set with the
  entry's own strategy.exit. Target off = InpTpPct 0. Time exit = InpExitCandles.

TradingView trailing exit (same rule as SPEC.md rule 4 and sweep_core / engine `_walk`):
activation price = entry fill price +/- trail_points x mintick; once price reaches it, the stop
= best price since activation -/+ trail_offset x mintick, moving only in the trade's favour;
exit when touched, at the stop or at the open if the bar opens beyond it; trail_points 0 =
armed at the fill with best = fill price. With a stop and / or limit in the same exit, the
first level touched along the path wins. Active from the entry fill (the next bar's open) on,
along the rest of that bar's path, like the existing bracket. When a same-side signal re-sends
the exit (Apex), the stop / limit change from the next bar on and the trailing state (armed,
best) and distances are kept (an assumption: TradingView's handling cannot be checked here;
say so in the notes).

## 2. Engine extension (in place, defaults unchanged)

Extend `$W/apex.py` and `$W/hrd.py` with params:
- `trailOn`, `trailAct`, `trailOff` (percent; Apex names may also accept apxTrail*, HRD
  hrdTrail*), Apex `useTarget` (default True);
- `path` in {'tv' (default), 'mag'}: 'mag' = Bar Magnifier with the 1-minute data. Every exit
  order (stop, limit, trail) is evaluated along the 1-minute sub-bars of the chart bar in time
  order (sub-bars of chart row r = rows of data/<PAIR>_1.parquet with t_open in
  [t_open[r], t_close[r]); each sub-bar with its own rule-4 path; trailing state carries; a
  level crossed by a jump between sub-bars fills at the next sub-bar's open). Entries,
  close / close_all, reversals still fill at the chart bar open; the script still runs at the
  chart bar close. Chart "1": mag == tv.
- cost mode 'stress' in addition to 'tv' and 'ours': XAU $0.50 per ounce per round trip
  ($0.25 per fill) + 1 tick (0.01) per fill; BTC 0.035% of the fill value per fill + $0.10 per
  unit per fill + 1 tick per fill.
- summary fields added: `h1r_pct`, `h2r_pct` (fair halves: for the trades ENTERED in each half
  (entry_time <= mid / > mid, mid = start + (end-start)//2), the compounded product of
  (1 + pnl / equity just before that trade's entry fill) - 1, in %), `h1_trades`, `h2_trades`,
  exit-kind counts incl. 'trail', `avg_bars_held`. Trades get an `eq_before` column.
- Regression: with the defaults (trail off, Apex useTarget True, path 'tv') every saved result
  must reproduce exactly: all 14 cells x every variant in `$W/out/apex_*.json` / `hrd_*.json`
  (trade lists in out/*_trades/ where saved).
- Speed: signals and filter permissions must be computable once and reused across exit
  settings (e.g. a `prepare(pair, tf, params)` returning arrays and a `simulate(P, exit_params)`
  kernel), so that one exit setting on BTC "1" costs well under 0.5 s.

## 3. The sweep

Grid (percent of price):
- activation: 0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5
- offset: 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5
- plus trail off (the strategy's own exits).
- Apex: x useTarget {True, False} -> 394 settings.
- HRD: x InpTpPct {4.0 (default), 0.0 (off)} x InpExitCandles {5 (default), 20, 100} -> 1182.
Per (pair, TF): filter {off, on} x path {tv, mag} x labels {normal, rev} x cost {tv, ours}.
TF in 1, 5, 15, 30, 60, 120, 240; pairs BTC, XAU; windows as SPEC_AH.md.
`$W/sweep_<apex|hrd>.py PAIR TF [TF ...] --workers 3` writes
`$W/out/swah_<apex|hrd>_<PAIR>_<TF>.parquet`, one row per (filter, path, labels, cost,
setting) with the setting columns and every summary field (prefix none; the cost column says
which). Deterministic across worker counts. Print timing per TF.

## 4. Tests (write `$W/sweep_ah_tests.py`, run it, report real output)

- R1 regression (section 2).
- R2 trail on, tv path: on 30 random settings per strategy over BTC 60 / XAU 60 / BTC 5 (2-month
  windows are fine), the engine equals an independent pure-Python reference of the trailing
  exit written for the test (or `$W/mag_ref.py`-style), trade by trade.
- R3 mag on chart 1 == tv; mag with one fake sub-bar per chart bar == tv.
- R4 the fair halves equal a direct recomputation from the trade list; stress costs equal a
  direct recomputation.
- R5 timing of one full-grid pass on BTC 1 (tv) and one mag setting on BTC 60.
