# Trailing-exit sweep for XPW v2.8 (trailing-TP variant) +/- the FlashGold Direction Filter

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Python 3 with numpy, pandas, numba, pyarrow. Run Python as `python3 -I`. Machine: 4 CPUs,
15 GB RAM. Other jobs may be running, so never use more than 3 worker processes.

Ground truth for the trading logic: the Pine strategy
`/home/user/master/xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine` (inputs at lines
290-303, entries / exits at lines 1377-1520), already replicated and reconciled in the
canonical modules `$W/xpw.py` (signals), `$W/fgf.py` (filter permissions) and `$W/engine.py`
(strategy + TradingView broker emulator; read its docstring, `_walk`, `_run`,
`backtest_bars`). `$W/run_tf.py` holds the windows (`WINDOWS`), the money model and the
reference metrics (`metrics()`). `$W/SPEC.md` holds the broker rules. Do NOT edit xpw.py,
fgf.py, engine.py or run_tf.py.

## Goal

For every pair (BTC, XAU) and chart timeframe ("1","5","15","30","60","120","240"), for
filter off and filter on (defaults, `fgfBlkClose` true), backtest every trailing-exit
setting of the grid below and record the metrics. Two intrabar path models:

- `tv`: exactly what TradingView's Strategy Tester does without Bar Magnifier (the
  canonical engine: one O-H-L-C or O-L-H-C path per chart bar, SPEC rule 2).
- `mag`: TradingView's Bar Magnifier with 1-minute data. Exit orders are evaluated
  along the 1-minute sub-bars of each chart bar, in time order, each sub-bar with its
  own rule-2 path (open -> high -> low -> close if (high - open) < (open - low), else
  open -> low -> high -> close). The script itself still runs once at the chart bar
  close, entries / close_all / reversals still fill at the chart bar close, and an
  entry's exits are still active only from the next chart bar. The trailing state
  (armed, best price) carries from sub-bar to sub-bar. A stop crossed by a jump between
  one sub-bar's close and the next sub-bar's open fills at that next sub-bar's open (the
  gap rule applied to every sub-bar's open). For chart "1" `mag` is identical to `tv`
  (each chart bar is its own single sub-bar), so for "1" run `tv` only and copy it.
  The sub-bars of chart bar r are the rows of `data/<PAIR>_1.parquet` with
  `t_open >= bars.t_open[r]` and `t_open < bars.t_close[r]` (the chart bars were built
  from exactly these 1-minute bars by `build_bars.py`).

## Grid (units = percent of the entry price, Pine `trailUnit = "percent"`)

- activation `trailAct` (%): 0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5
- offset `trailOff` (%): 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5
- `trailOn` true for those 196 pairs, plus one `trailOn` false row
- stop loss: `slOn` false, or `slOn` true with `slDist` (%) 0.1, 0.25, 0.5, 1, 2, 4
- => 197 x 7 = 1379 exit settings per (pair, TF, filter, path)
- plus one reference row per (pair, TF, filter, path): the script's own defaults
  (`trailUnit "price"`, `trailAct 2.0`, `trailOff 1.0`, `slOn` false), tagged `default`.

All other inputs at the Pine defaults (tradeDir Both, oppCloses true, maxOpen 20,
pyramiding 100, entryFill "Signal tick", mintick 0.01).

## Money and metrics

Exactly `run_tf.metrics()` (10,000 initial capital, each entry 10% of closed equity at
entry, compounding; `tv0` = no costs, `cost` = XAU $0.30 per ounce round trip, BTC 0.02%
of price per side + $0.20 per coin round trip), for both `tv0` and `cost`: trades,
net_pct, pf, win_pct, max_dd_pct (closed-trade equity), half1_pct, half2_pct (P/L
realised in the first / second half of the window, % of initial capital; the halves
split at `start + (end - start) // 2`), max_concurrent. Plus:
- `exit_trail`, `exit_sl`, `exit_close_all`, `exit_reverse`, `exit_end` counts;
- `max_expo`: the largest (sum over open trades of qty x entry price) / closed equity,
  checked right after each entry (qty as in metrics());
- `avg_bars_held`.

## Files to produce

1. `$W/sweep_core.py`
   - `load_inputs(pair, tf)`: sig = `xpw.xpw_signals(pair, tf, start, end, {})`,
     perm = `fgf.fgf_permissions(pair, tf, start, end, {})` for `run_tf.WINDOWS[pair]`,
     cached as pickles in `$W/cache_sweep/` keyed by pair, tf and the mtimes of xpw.py and
     fgf.py (a stale cache must never be used).
   - `prep(pair, tf, sig, perm, filter_on)`: the arrays `engine._run` needs, computed
     exactly as `engine.backtest_bars` does (goLong, goShort, nL, nS, cL, cS, OHLC, times).
   - `sub_bars(pair, tf, rows)`: `ptr` (int64, n+1) and contiguous 1-minute OHLC arrays.
   - `run_cfg(P, cfg, path)`: `path == 'tv'` calls `engine._run` itself (import it, do not
     copy it); `path == 'mag'` calls `_run_mag`, a numba kernel identical to `engine._run`
     except for step 1 (it should call `engine._walk` once per sub-bar). Returns the trade
     arrays (dir, entry row, entry px, exit row, exit px, exit kind) and the summary
     counts.
   - `metrics_fast(...)`: a numba version of `run_tf.metrics()` for both cost modes plus
     the extra fields. Must equal `run_tf.metrics()` (relative 1e-9 on floats, exact on
     counts) on every test below.
2. `$W/sweep.py PAIR TF [TF ...] [--paths tv,mag] [--workers 3]`: loads / caches inputs,
   runs the whole grid for filter off and on and both paths, 3 worker processes at most
   (fork after the inputs and sub-bars are built so workers share them), and writes
   `$W/out/sweep_<PAIR>_<TF>.parquet`: one row per (filter, path, setting) with columns
   pair, tf, filter ("off"/"on"), path ("tv"/"mag"), tag ("grid"/"default"), trailOn,
   trailUnit, trailAct, trailOff, slOn, slDist, and every metric for tv0 and cost
   (prefix `tv0_` / `cost_`). Prints progress and timing per TF.
3. `$W/sweep_tests.py`: the tests below; prints PASS / FAIL per test and exits non-zero on
   any failure.

## Tests that must pass (run them, show the output)

- T1 `tv` == canonical: at least 60 random settings (random units ticks / price / percent,
  activation, offset, trailOn, slOn, slDist, filter on / off) on BTC "60" 2025-01-01 ->
  2025-03-01, BTC "5" 2025-01-01 -> 2025-01-15, XAU "60" and XAU "15" on
  2018-01-02 -> 2018-03-01 (use `run_tf.WINDOWS` style epoch seconds): the sweep's trade
  arrays equal `engine.backtest(...)`'s trades (entry / exit rows, prices, kinds, dirs)
  exactly, and `metrics_fast` equals `run_tf.metrics(pair, trades, start, end, cost)` for
  both cost modes.
- T2 `mag` on chart "1" equals `tv` on chart "1" exactly (BTC and XAU, 20 settings each).
- T3 `mag` with a fake sub-bar table in which every chart bar is its own single sub-bar
  equals `tv` exactly (BTC "60", XAU "60", 20 settings each).
- T4 timing: one full-grid run of BTC "1" filter off, `tv` path, single process: report
  seconds per setting; and one `mag` setting on BTC "60" over the full window.
</content>
</invoke>
