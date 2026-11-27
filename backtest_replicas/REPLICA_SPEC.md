# Python replica of a fused Pine strategy (common brief for every strategy of stage 3)

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Python 3, numpy, pandas, numba, pyarrow. Run Python as `python3 -I`. Shared 4-CPU / 15 GB
machine, other agents and long sweeps run at the same time: at most 2 processes each, keep
memory under 3 GB per process, never leave a process running when you finish.
NEVER write inside `/home/user/master` (the repository is read-only for you: no edits, no git
command that changes anything). Do not edit files you were not asked to write: the modules
`fgf.py`, `xpw.py`, `engine.py`, `sweep_core.py`, `apex.py`, `hrd.py`, `run_tf.py` are verified
and used by running jobs. There is NO TradingView here: nothing can be compiled or backtested
in TradingView, so the Pine text is the only ground truth and every interpretation of
TradingView's behaviour must be written down.

## Goal

A verified Python replica `$W/<key>.py` of one fused strategy (a Pine strategy that carries the
FlashGold Direction Filter block and the Update 1 option "Inverted direction: opposite side at
the same entries"), good enough to (1) report what the script does on every timeframe with the
option off and on, and (2) calibrate its inputs per pair and timeframe (`$W/CALIB_SPEC.md`).
"Verified" here means: two implementations written independently from the Pine agree trade by
trade, every disagreement was resolved by reading the Pine, and an independent auditor then
looked for readings both shared.

Ground truth: the Pine file named in your task, as it is at the repository HEAD (it contains
Update 1; read its header, `/home/user/master/UPDATES.md`, and `$W/../inv/INVERT_SPEC.md` for
what the option means: decisions in the normal frame on the mirrored position, orders on the
other side at the same price, stop <-> limit entries swapped, exits with the same distances
mirrored). Where a spec and the Pine disagree, the Pine wins; say so.

## What already exists (read before writing anything)

- `$W/SPEC_AH.md`: data files, windows, the `request.security` rule on history, Pine built-in
  semantics (rsi, ema, pivots, na), TradingView's broker on history (rules 1-7), sizing, cost
  modes 'tv' / 'ours'. Those rules apply here unless the strategy's own `strategy()` call says
  otherwise (process_orders_on_close, calc_on_order_fills, pyramiding, default_qty_type,
  initial_capital, commission, slippage, margin: read the call and state each one).
- `$W/SWEEP_AH_SPEC.md` section 2: the `prepare` / `simulate` split, the 'mag' path (1-minute
  Bar Magnifier fills), cost mode 'stress', the fair halves `h1r_pct` / `h2r_pct`, trailing
  exits as TradingView evaluates them.
- `$W/SPEC.md` (XPW replica spec: stop / limit ENTRY orders, pyramiding, ids, FIFO) and
  `$W/engine.py`, `$W/apex.py`, `$W/hrd.py` as worked examples of the broker in numba.
- `$W/fgf.py`: the direction filter, verified. `fgf.fgf_permissions(pair, chart_tf, start, end,
  params)` returns per chart bar `buyOk`, `sellOk` (read its docstring for the other columns
  and for the filter's own signals). Use it; never reimplement the filter block.
- `$W/xpw.py`: the XPW ladder and labels (signals), verified; used by the XPW strategies.
- Data: `$W/data/<PAIR>_<TF>.parquet` (open, high, low, close, t_open, t_close, sess) and
  `<PAIR>_<TF>_vol.parquet` (volume; XAU = tick count), PAIR in BTC, XAU; TF in 1, 5, 15, 30,
  60, 120, 240, D, W, M (`$W/build_bars.py` builds other minute timeframes the same way if a
  script needs one, e.g. 3, 10, 45; write new files only under `$W/data/` with a new name).
  No data below 1 minute: anything on seconds timeframes cannot be reproduced; say so.
- Windows: BTC 1731801600..1794873600 (2024-11-17..2026-11-17), XAU 1483315200..1529366400
  (2017-01-02..2018-06-19) by t_close; warm indicators up from the start of the data;
  positions start flat at the window start. mintick 0.01, pointvalue 1 for both.
- Costs: 'tv' = the script's own Properties (commission / slippage of its `strategy()` call);
  'ours' = XAU $0.30 per ounce per round trip, BTC 0.02% of the fill value per fill + $0.20 per
  unit per round trip, replacing the script's commission and slippage; 'stress' = XAU $0.50 per
  ounce per round trip + 1 tick per fill, BTC 0.035% per fill + $0.20 per round trip + 1 tick
  per fill.

## The stages

### 1. Strategy spec `$W/SPEC_<key>.md` (one agent)

Read the whole Pine and write the strategy-specific brief the two builders will work from:
- the `strategy()` call, argument by argument, and what each means for the broker;
- every input that changes trading, by Pine variable name, with its default, split into SIGNAL
  inputs (change which candles give signals: go to `prepare`) and ORDER / EXIT inputs (go to
  `simulate`); inputs that only change drawing or alerts are listed once and ignored;
- the logic in order of execution on a bar: series, higher-timeframe requests (which rule),
  state variables (`var`), signals, gates (the filter gate `fgfBuyOk` / `fgfSellOk`, sessions,
  daily limits, cooldowns: note every timezone and day boundary), orders (market / stop /
  limit, ids, `strategy.exit` brackets, trailing in ticks or price, `strategy.close*`,
  `strategy.cancel*`), hand-coded exits (breakeven, time stop, trailing by hand), the Update 1
  mirroring line by line, any older reverse / direction option and how it differs;
- every place where TradingView's behaviour must be assumed (same-bar entry and exit, order
  priority, an exit re-sent with the same id, stop and limit both touched, gaps, `na` prices,
  `calc_on_every_tick` or `barstate.isrealtime` code that only matters live: history runs once
  per bar at its close): state the assumption both builders must make, and why;
- what cannot be reproduced with this data (seconds timeframes, real volume on gold, sessions
  of another broker, anything live-only) and what the replica does instead;
- the trade record (exit kinds this strategy has) and the summary fields beyond the common
  ones; the money model (sizing as the script does it; R = the stop distance where it has one);
- a CALIBRATION GRID proposal for `$W/CALIB_SPEC.md`: named dimensions with values (ordinal /
  categorical), signal dimensions x filter {off, on, on without the blocked close if the script
  has that switch} x direction {normal, inverted} x exit dimensions, 8,000-25,000 settings per
  cell, built around the inputs that matter most, the defaults being one grid point; trailing
  offsets not below 0.1% of price on BTC / 0.05% on gold.
Do not write code in this stage beyond small probes.

### 2. Two independent builds `$W/<key>_a.py`, `$W/<key>_b.py` (two agents, in parallel)

From the Pine and `SPEC_<key>.md`, without reading the other implementation. Interface:

    prepare(pair, chart_tf, params=None) -> P      # signals, gates, filter permissions: everything
                                                   # that does not depend on the order / exit inputs
    simulate(P, x=None) -> R                       # orders and exits; x: the ORDER / EXIT inputs by
                                                   # Pine name, plus path ('tv'), cost ('tv' | 'ours' |
                                                   # 'stress'), inv (Update 1, default False)
    trades(P, R) -> DataFrame                      # dir (REAL side), entry_time, entry_px, qty,
                                                   # exit_time, exit_px, exit_kind, pnl (after costs),
                                                   # entry_bar, exit_bar, eq_before
    summary(P, R) -> dict                          # trades, net_pct, pf, win_pct, max_dd_pct, long,
                                                   # short, raw / blocked signals per side, exit_<kind>
                                                   # counts, avg_bars_held, exposure, half1_pct,
                                                   # half2_pct, h1r_pct, h2r_pct, h1_trades, h2_trades
    run(pair, chart_tf, params=None) -> (trades, summary)   # prepare + simulate with one dict

`fgfOn` (default as in the Pine) is a `prepare` parameter. The 'tv' path only at this stage
(TradingView's bar path, SPEC_AH.md rule 4). Hot loops in numba: one `simulate` on BTC "1"
(about 1.04M bars) well under 1 s after compilation, `prepare` under 2 minutes.
Self-checks: hand-trace at least 3 trades of each exit kind with the bars printed; `fgfOn`
False reproduces the original (unfused) script's logic; `inv` False vs True on 5 single
decisions (the mirror property); save `$W/out/<key>_<a|b>_<PAIR>_<TF>.parquet` trade lists for
BTC 60, BTC 5, XAU 60, XAU 15 with default inputs (cost 'tv'), filter on and off, inv off and
on; write `$W/<key>_<a|b>_notes.md` (every interpretation, everything not implemented).

### 3. Reconcile, canonical module, Bar Magnifier path (one agent)

- Compare A and B trade by trade (every column) on BTC and XAU, charts 1, 5, 15, 60 and 240,
  full windows: default inputs; filter off; inv on (filter on and off); each cost mode; and at
  least 60 random settings drawn from the SPEC's calibration grid (signal and exit inputs).
  For every disagreement find which one follows the Pine (hand-trace the bars), fix the wrong
  one, repeat until 100% of trades agree. Write `$W/reconcile_<key>.md`.
- Canonical module `$W/<key>.py` (the better one, same interface) and add `path='mag'` as
  SWEEP_AH_SPEC.md section 2 defines it: every exit order (stop, limit, trailing, and any exit
  the script places as a price order) walks the 1-minute sub-bars of the chart bar in time
  order; stop / limit ENTRY orders also fill along the sub-bars; market orders, `strategy.close`
  and the script's own bar-close logic stay on the chart bars. Chart "1": mag == tv.
- Tests `$W/tests_<key>.py` (print PASS / FAIL, exit non-zero on failure): A == B == canonical
  on the cases above; mag on chart 1 == tv; mag with one fake sub-bar per chart bar == tv;
  mag against a slow pure-Python reference of the exits written for the test, on 30 random
  settings over 2-month windows; fair halves and each cost mode against a direct recomputation
  from the trade list; `inv` properties stated in the Pine header (e.g. with the filter off,
  inverted == the script's older reverse option where the header says so); timing.
- Runner `$W/run_inv_<key>.py PAIR TF [TF ...]` exactly as `$W/INV_BT_SPEC.md` item 3 (direction
  {normal, inverted} x filter {off, on} x path {tv, mag} x cost {script, ours}; output
  `$W/out/inv_<key>_<PAIR>_<TF>.json` with `runs['<direction>/<filter>/<path>/<cost>']` = the
  full summary). Run all 14 cells and report the table.
- `$W/<key>_notes.md`: the final list of interpretations and limits.

### 4. Audit (one agent, sceptic)

The two builds agree, so hunt for SHARED misreadings: go through the Pine line by line against
`$W/<key>.py` (na handling, `[n]` offsets, `var` state, request.security mapping, order timing
and priority, exit replacement, sizing on equity, the filter gate, the Update 1 mirroring, day
/ session boundaries), write your own small reference for at least two mechanisms from the
Pine alone and compare, mutate the module in a sandbox copy to confirm the tests can fail,
sanity-check the by-timeframe results (trade counts per year, win rates, whether the
TradingView view differs from the 1-minute view for a reason you can name). Fix every confident
defect in the canonical module, re-run the tests and the 14 cells, and report each defect with
its impact on the numbers.
