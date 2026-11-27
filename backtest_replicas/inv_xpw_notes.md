# XPW v2.8 trailing-TP replica: Update 1 "Inverted direction" (xpwInv)

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Ground truth: `/home/user/master/xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine` at HEAD `d28ba97`;
its Update 1 diff is `git -C /home/user/master diff 6c59b9f d28ba97 -- xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine`.
Nothing was written inside `/home/user/master`. `xpw.py`, `fgf.py`, `run_tf.py`, `sweep.py` and every other
strategy's module are unchanged.

## 1. What changed

| file | change |
|---|---|
| `engine.py` | new parameter `xpwInv` (alias `inv`), default `False`, in `DEFAULTS` / `_params`; kernel `_run(..., cap, ocap, inv=False)`; `backtest_bars` (allow flags, ids, comments, `sig_dir`, summary flag); docstring |
| `sweep_core.py` | `prep(pair, tf, sig, perm, filter_on, inv=False, xpwInv=None)` stores `P['inv']`; `run_cfg(P, cfg, path, sub=None, inv=None)` (None = `P['inv']`); kernel `_run_mag(..., cap, ocap, inv=False)` with the same step-2 text as `engine._run` (`check_mag_sync()` passes); `check_mag_equiv` now checks both values of the flag; docstring |
| `inv_tests_xpw.py` | new: tests R1-R4 of the spec plus R5 (independent pure-Python reference) |
| `run_inv_xpw.py` | new: the by-timeframe runner, writes `out/inv_xpw_<PAIR>_<TF>.json` |
| `inv_mut_xpw.py` | new: mutation check of the tests (12 one-line breaks of the option, each must be caught) |
| `pre_inv_backup/engine.py`, `pre_inv_backup/sweep_core.py` | the modules as they were before the change (sha256 `02b4ab52...` and `1b89e628...`); test R1c runs them |

Logs: `inv_tests_xpw.log` (the tests), `inv_xpw_existing_tests.log` (the pre-existing suites on the changed
modules, run by `inv_xpw_existing_tests.sh`), `inv_mut_xpw.log` (mutation check), `run_inv_xpw_BTC_60.log`,
`run_inv_xpw_XAU_240.log` (runner).

### The kernel change (identical text in `engine._run` and `sweep_core._run_mag`, step 2)

```python
pos = pos_dir                    # sign of strategy.position_size (the real position)
posn = -pos if inv else pos      # Pine xpwPosN: the position in the normal frame
...
if (posn > 0 and cL[i]) or (posn < 0 and cS[i]):      # closeL / closeS -> strategy.close_all
    ...
    bar_close[i] = 1 if posn > 0 else 2               # which of closeL / closeS fired (for the comment)
room = maxOpen - opent
for side in range(2):            # goLong entries, then goShort entries (d = +1 / -1, normal frame)
    ...
    dr = -d if inv else d        # the side really traded (Pine realLong)
    for k in range(cnt):
        if room > 0 or posn == -d:
            if pos_dir == -dr:   # strategy.entry against the real position: reversal
                ...
            if pos_dir == dr and n_open >= pyr:        # pyramiding on the real side
                bar_pyr[i] += 1
            else:
                t_dir[j] = dr                          # the trade list carries the REAL side
                e = dr * c[i]                          # exit levels in the real side's "long space"
                ...
                pos_dir = dr
```

Step 1 (the exit orders, `sgn = float(pos_dir)`) needed no change: `pos_dir` is the real position, so the
trailing TP and the stop of an inverted trade are walked on the side really open, in both kernels. The
signal arrays `goL / goS / nL / nS / cL / cS` stay in the normal (decision) frame. With `inv` false every
expression reduces to the old one (`posn = pos`, `dr = d`); the flag is the last argument with a default,
so an old-style call without it still works.

Speed (R1c, same arrays, min of 5): BTC 1 tv default `pre-change 0.0167 s, new with the flag off 0.0163 s (x0.98), new inverted 0.0157 s`; grid setting `pre-change 0.0420 s, new with the flag off 0.0419 s (x1.00), new inverted 0.0401 s`; BTC 60 mag
`pre-change 0.0022 s, new with the flag off 0.0022 s (x0.99), new inverted 0.0019 s`. The existing T4 timing (full grid, BTC 1, single process) gives 0.065 s per setting against
0.059 s in the pre-change sweep log, measured this time next to the other strategies' jobs.

## 2. The Update 1 diff, line by line

| Pine (HEAD) | what it does | replica |
|---|---|---|
| header block `UPDATE 1 (2026-11-23)`, `INVERTED vs REVERSE`, the reworded paragraphs | documentation | none (its statements are what R2 tests) |
| `strategy("... [Update 1]", shorttitle="XPW-OTDI8 S U1", ...)` | title only; same `process_orders_on_close`, `pyramiding=100`, 10% of equity | none |
| tooltips of `tradeDir`, `entryFill` | text | none |
| `xpwInv = input.bool(false, "Inverted direction: ...")` | the option, off by default | `engine.DEFAULTS['xpwInv'] = False`, alias `inv` (`_params` raises if the two disagree); `sweep_core.prep(..., inv=)` / `run_cfg(..., inv=)` |
| `bool allowLong = xpwInv ? tradeDir != "Long only (buy only)" : tradeDir != "Short only (sell only)"` and `allowShort` | "Trade direction" restricts the orders really placed | `engine.backtest_bars` and `sweep_core.prep`: the same two tests swapped when `inv` (with `Both`, the only mode `prep` serves, both are true either way) |
| `sigLong`, `fgfBlkL`, `goLong`, `oppL`, `oppS` (unchanged lines) | the gate and the opposite-signal flags, normal frame, on the new allow flags | unchanged vectorised code of `backtest_bars` / `prep` (reads the allow flags above) |
| `float xpwPosN = xpwInv ? -strategy.position_size : strategy.position_size` | the position as the decisions see it | kernel `posn = -pos if inv else pos` |
| `closeL = xpwPosN > 0 and ...`, `closeS = xpwPosN < 0 and ...` | closes act on the mirrored position | kernel `(posn > 0 and cL[i]) or (posn < 0 and cS[i])`; `cL / cS` (the position-free part) unchanged; `strategy.close_all` closes whatever is really open |
| close comments `fgfBlkS ? (xpwInv ? "filter blocked LONG (inv), close | " : "filter blocked SHORT, close | ") + firstShort` (and the mirror) | comment names the side really traded | `backtest_bars`: `blkS_txt` / `blkL_txt`, chosen by `bar_close` (1 = closeL, 2 = closeS) |
| `placeEntry`: `realLong = xpwInv ? not isLong : isLong`; `strategy.entry(id, realLong ? long : short, limit=xpwInv ? na : lim, stop=xpwInv ? lim : na, ...)` | the order goes in on the other side; Signal tick: `lim` is na, so a market order either way | kernel `dr = -d if inv else d`: reversal test, pyramiding test, `t_dir`, `pos_dir` on `dr` |
| `placeEntry`: `cmt = (realLong ? "ENTER LONG" : "ENTER SHORT") + (xpwInv ? " (inv)" : "") + ... + " | " + src` | comment | `backtest_bars`: `'ENTER LONG' + tag + ' | ' + s` by the real side, `tag = ' (inv)'`; `src` is read from the list of the label's own (normal-frame) side |
| `strategy.exit("X " + id, from_entry=id, trail_points=trPts, trail_offset=trOff, loss=slPts, ...)` (unchanged) | same tick distances, attached to the trade really open | kernel `e = dr * c[i]`: activation `e + trp*mt`, offset, stop `e - slp*mt` in the real side's long space; step 1 walks the real side |
| `if room > 0 or xpwPosN < 0` / `xpwPosN > 0` | "Max open entries" and the reversing entries, normal frame | kernel `if room > 0 or posn == -d` |
| `string id = (xpwInv ? "S" : "L") + str.tostring(bar_index) + "-" + ...` (and `"L" : "S"`) | the id letter is the side really traded | `backtest_bars`: `'L%d-%d'` / `'S%d-%d'` by the real `dir` |
| `fgfLimL / fgfLimS` comment, `stop=xpwInv ? lim : na`, `" stop @ label"` | limit mode: sell stop / buy stop at the limit's price | NOT in the replica (limit mode never was: `entryFill` other than "Signal tick" still raises `NotImplementedError`) |
| READ HERE table: `"  |  ORDERS INVERTED (Update 1): opposite side"` | display | none |
| FGD diagnostics (unchanged lines; header: "the sides are the filter's") | counts on the filter's side | summary `raw_long`, `blocked_long`, `go_long_bars`, ... unchanged (normal frame); `long_entries`, `short_entries`, `gross_pl_long`, `gross_pl_short` are real sides |

## 3. Interpretations

1. History only, one script run per chart bar at its close (as before): `strategy.position_size` and
   `strategy.opentrades` are the values after that bar's exit orders, before its market fills; `doneL / doneS`
   never equal `bar_index` beforehand. The option changes none of this.
2. A market `strategy.entry` on the side opposite to the REAL position reverses it (all open trades close at
   this close, kind `reverse`, comment = the reversing entry's comment). Inverted, that is a LONG label
   arriving while the script is really long (it holds the mirror of a short), exactly the header's "a LONG
   label stacks on an open short and a SHORT label is its opposite signal".
3. `pyramiding=100` counts open entries on the real side, as TradingView does (same rule as before; with the
   default "Max open entries" 20 it never binds).
4. Exit distances are the same tick counts (`toTicks` on this close), laid out from the fill on the real
   side: a real long arms at entry + activation and trails below the best high; a real short the mirror. The
   levels are not rounded to the tick grid (as before).
5. Trade list: `dir`, the id letter and "ENTER LONG / SHORT (inv)" are the REAL side. With the option on the
   frame gets one more column, `sig_dir` (the side of the label / the filter, = -dir), and the summary a key
   `xpwInv: True`. Both are added ONLY when the option is on, so that the default frame and summary are the
   pre-Update-1 ones, key for key (R1a compares them with the saved files).
6. `bar_close` (kernel output) now means "closeL fired" (1) / "closeS fired" (2), i.e. the normal-frame side.
   With the option off that is "a long was closed" / "a short was closed" as before.
7. Money model, costs, windows: unchanged (`run_tf.metrics` / `sweep_core.metrics_fast` read `dir` = real side).
8. "script" cost for xpw = none (`tv0`), "ours" = the existing `cost` mode.

## 4. Not reproduced

- "Limit at label price" with the option on (buy limit -> sell stop, sell limit -> buy stop, the pending
  list in the normal frame): the replica only has "Signal tick", as before.
- Live behaviour (ticks inside a candle, `calc_on_every_tick`, `varip`): history only, as before.
- Display: labels, the table text, the order-fill alert texts beyond the comment strings.
- AGREE entries: `xpw.py` supports `agreeOn = false` only (the default), as before.
- TradingView itself was not run (no compiler in this workspace): "reproduces the Pine" means the replica
  follows the Pine source and the broker rules of `SPEC.md`, as verified for the pre-Update-1 version. The
  known limits of that version carry over unchanged (see `reconcile_engine.md`, e.g. the per-entry exits
  against TradingView's FIFO close rule counted by `audit_engine_fifo.py`).

## 5. Tests: `python3 -I inv_tests_xpw.py` (all pairs, all timeframes, full windows)

What each test establishes:

- **R1** option off = before. (a) all 70 saved `out/run_<PAIR>_<TF>.json` variants: tv0 / cost metrics and the
  engine summary equal, and the trade list equal to the saved `out/trades_*.parquet` column for column;
  explicit `xpwInv=False` / `inv=False` identical. (b) 672 sampled rows of the 14 `out/sweep_*.parquet`
  (default row + 5 random grid rows per filter x path x labels): all 66 metrics identical, tv and mag.
  (c) the pre-change kernels from `pre_inv_backup/` against the new ones with the flag off and omitted: all
  17 returned arrays bit-identical on 288 tv + 288 mag runs; `backtest_bars` old == new on 72 inputs; speed.
- **R2** the header's INVERTED vs REVERSE section. Filter off: inverted == "Reverse every label" trade by
  trade on every pair / timeframe, tv and mag; both on == both off; through `engine.backtest` the two lists
  differ only in the comments (" (inv)") and the FGD sides; Long only / Short only: inverted == reversed
  labels in the same mode, and its entries are those of the other one-side mode without the option, on the
  opposite side. Where the header says they differ, every difference is of the stated kind: with the filter
  on the inverted run equals the reversed-label run judged in the OPPOSITE zones (`buyOk` / `sellOk`
  swapped), and with "exit only" rows it equals the reversed-label run whose "exit only" rows close the other
  side. The plain reversed-label run does differ there (208 of 208 runs with the filter on).
- **R3** 2800 single decisions on sampled real bars (their labels and permissions, plus forced "exit only"
  rows, several labels per bar, random permissions, Trade direction, Opposite ENTER closes, Blocked entry
  closes, Max open entries 1 / 2 / 3 / 20, pyramiding 2 / 100, random exits) from a prepared position: the
  decision with the option on from real position p == the mirror of the decision with it off from -p (Long
  only <-> Short only swapped): same closes, same entries on the other side, ids with the other letter,
  mirrored exit distances, same counters; and each equals `ref_step`, a transcription of the Pine's STRATEGY
  section at HEAD.
- **R4** option on: mag == tv on chart "1" (BTC and XAU, full windows, real 1-minute sub-bars); mag with one
  sub-bar per bar == tv; mag with real sub-bars == `engine._run` on the 1-minute series;
  `check_mag_sync()` / `check_mag_equiv()` pass.
- **R5** (extra) 144 `engine.backtest` runs and 48 `run_cfg` mag runs against a pure-Python reference written
  from the Pine at HEAD (`ref_step`) and `mag_ref.py`'s exit walker (no kernel, longs and shorts written
  out, its own sub-bar table): ids, real sides, prices, exit kinds, comments, levels and counters equal,
  with the option on and off, reversed labels, "exit only" rows, one-side modes, small Max open entries,
  pyramiding 2. The reference with the opposite flag is rejected (24 of 24).

Output (`inv_tests_xpw.log`):

```
inv_tests_xpw: engine.py 1795485054681536298 sweep_core.py 1795485095028228913 xpw.py 1794967352682004273 fgf.py 1794967200513189999 (mtime ns); pairs BTC,XAU, timeframes 1,5,15,30,60,120,240
R1 ...
  R1a BTC 1   1039430 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (197878 trades) (33.9s)
  R1a BTC 5    210155 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (74862 trades) (8.0s)
  R1a BTC 15    70058 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (37118 trades) (3.7s)
  R1a BTC 30    35032 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (22298 trades) (2.1s)
  R1a BTC 60    17518 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (12805 trades) (1.2s)
  R1a BTC 120    8760 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (6006 trades) (0.6s)
  R1a BTC 240    4381 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (3574 trades) (0.4s)
  R1a XAU 1    493819 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (93161 trades) (19.7s)
  R1a XAU 5     98787 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (34786 trades) (5.7s)
  R1a XAU 15    32935 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (17259 trades) (2.3s)
  R1a XAU 30    16471 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (10045 trades) (1.4s)
  R1a XAU 60     8238 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (5832 trades) (0.6s)
  R1a XAU 120    4493 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (2804 trades) (0.4s)
  R1a XAU 240    2246 bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists (1776 trades) (0.2s)
  R1b BTC 1  : 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (9.9s)
  R1b BTC 5  : 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (2.7s)
  R1b BTC 15 : 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (1.6s)
  R1b BTC 30 : 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (1.0s)
  R1b BTC 60 : 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (0.4s)
  R1b BTC 120: 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (0.4s)
  R1b BTC 240: 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (0.6s)
  R1b XAU 1  : 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (5.7s)
  R1b XAU 5  : 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (1.5s)
  R1b XAU 15 : 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (1.2s)
  R1b XAU 30 : 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (0.6s)
  R1b XAU 60 : 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (0.6s)
  R1b XAU 120: 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (0.3s)
  R1b XAU 240: 48 sampled rows of out/sweep parquet (8 groups x 6) recomputed: every metric identical (0.6s)
  R1c pre-change modules: pre_inv_backup/engine.py sha256 02b4ab521f013dc1.., sweep_core.py 1b89e628c423f893..
  R1c BTC 60 : 12 settings x 4 (labels, filter): new kernels (flag off and omitted) == pre-change kernels, tv and mag; backtest_bars old == new on 12 inputs (5.7s)
  R1c BTC 5  : 12 settings x 4 (labels, filter): new kernels (flag off and omitted) == pre-change kernels, tv and mag; backtest_bars old == new on 12 inputs (16.5s)
  R1c XAU 240: 12 settings x 4 (labels, filter): new kernels (flag off and omitted) == pre-change kernels, tv and mag; backtest_bars old == new on 12 inputs (1.1s)
  R1c XAU 15 : 12 settings x 4 (labels, filter): new kernels (flag off and omitted) == pre-change kernels, tv and mag; backtest_bars old == new on 12 inputs (3.1s)
  R1c BTC 240: 12 settings x 4 (labels, filter): new kernels (flag off and omitted) == pre-change kernels, tv and mag; backtest_bars old == new on 12 inputs (2.0s)
  R1c XAU 60 : 12 settings x 4 (labels, filter): new kernels (flag off and omitted) == pre-change kernels, tv and mag; backtest_bars old == new on 12 inputs (2.0s)
  R1c speed BTC 1 tv default            1039430 bars: pre-change 0.0167s, new flag off 0.0163s (x0.98), new inverted 0.0157s
  R1c speed BTC 1 tv grid 0.3/0.1 sl 1  1039430 bars: pre-change 0.0420s, new flag off 0.0419s (x1.00), new inverted 0.0401s
  R1c speed BTC 60 mag default: 17518 bars, 1039488 sub-bars: pre-change 0.0022s, new flag off 0.0022s (x0.99), new inverted 0.0019s
R1 PASS (140.8s): option off: 70 run-json variants (520204 trades) == saved json and saved trade lists; 672 sweep rows (336 tv, 336 mag) == saved parquet; new kernels == pre-change kernels on 288 tv + 288 mag runs, backtest_bars on 72
R2 ...
  R2 BTC 1   tv: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 1191057 trades (inv != rev with the filter on in 8 of 8 runs, inv != normal in 8) (12.9s)
  R2 BTC 5   tv+mag: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 902414 trades (inv != rev with the filter on in 16 of 16 runs, inv != normal in 16) (7.5s)
  R2 BTC 15  tv+mag: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 448094 trades (inv != rev with the filter on in 16 of 16 runs, inv != normal in 16) (2.7s)
  R2 BTC 30  tv+mag: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 268950 trades (inv != rev with the filter on in 16 of 16 runs, inv != normal in 16) (1.8s)
  R2 BTC 60  tv+mag: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 153262 trades (inv != rev with the filter on in 16 of 16 runs, inv != normal in 16) (1.3s)
  R2 BTC 120 tv+mag: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 72016 trades (inv != rev with the filter on in 16 of 16 runs, inv != normal in 16) (1.1s)
  R2 BTC 240 tv+mag: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 42776 trades (inv != rev with the filter on in 16 of 16 runs, inv != normal in 16) (0.4s)
  R2 XAU 1   tv: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 563608 trades (inv != rev with the filter on in 8 of 8 runs, inv != normal in 8) (8.0s)
  R2 XAU 5   tv+mag: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 420992 trades (inv != rev with the filter on in 16 of 16 runs, inv != normal in 16) (3.5s)
  R2 XAU 15  tv+mag: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 207958 trades (inv != rev with the filter on in 16 of 16 runs, inv != normal in 16) (1.8s)
  R2 XAU 30  tv+mag: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 120674 trades (inv != rev with the filter on in 16 of 16 runs, inv != normal in 16) (1.2s)
  R2 XAU 60  tv+mag: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 69750 trades (inv != rev with the filter on in 16 of 16 runs, inv != normal in 16) (0.9s)
  R2 XAU 120 tv+mag: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 33624 trades (inv != rev with the filter on in 16 of 16 runs, inv != normal in 16) (0.6s)
  R2 XAU 240 tv+mag: 8 settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the zones swapped; 21360 trades (inv != rev with the filter on in 16 of 16 runs, inv != normal in 16) (0.7s)
  R2 BTC 60  engine.backtest, 3 exits: comments differ only by " (inv)", FGD sides swapped; one-side modes; "exit only" rows (138 exitL, 172 exitS bars) close the mirrored side (7.6s)
  R2 XAU 240 engine.backtest, 3 exits: comments differ only by " (inv)", FGD sides swapped; one-side modes; "exit only" rows (20 exitL, 12 exitS bars) close the mirrored side (1.6s)
  R2 BTC 15  engine.backtest, 3 exits: comments differ only by " (inv)", FGD sides swapped; one-side modes; "exit only" rows (651 exitL, 616 exitS bars) close the mirrored side (21.1s)
  R2 XAU 30  engine.backtest, 3 exits: comments differ only by " (inv)", FGD sides swapped; one-side modes; "exit only" rows (159 exitL, 124 exitS bars) close the mirrored side (4.8s)
R2 PASS (79.5s): filter off: inv == rev on 208 runs, both on == both off on 208; filter on: inv == rev with the zones swapped on 208 (4516535 trades in all; plain rev differs with the filter on in 208 of 208); engine.backtest: 48 pairs of lists (comments, FGD sides), 96 one-side-mode cases, 72 "exit only" cases (plain rev differs in 11)
R3 ...
  R3 BTC 60 : 700 decisions on sampled bars: option on from p == mirror of option off from -p; both == Pine step (9.9s)
  R3 XAU 240: 700 decisions on sampled bars: option on from p == mirror of option off from -p; both == Pine step (11.7s)
  R3 BTC 15 : 700 decisions on sampled bars: option on from p == mirror of option off from -p; both == Pine step (11.4s)
  R3 XAU 5  : 700 decisions on sampled bars: option on from p == mirror of option off from -p; both == Pine step (10.6s)
R3 PASS (43.5s): 2800 single decisions (real position with the option on: short 855, flat 1154, long 791): 397 closed the position (close_all), 276 reversed it, 965 entries placed, 525 with entries held back by Max open entries, 685 with a blocked side, 714 with an "exit only" row, 1584 did nothing; setup not allowed by Trade direction in 560
R4 ...
  R4 BTC 1  1039430 bars = 1039430 sub-bars: 20 settings, option on: mag == tv (772865 trades; inverted != normal in 20) (7.5s)
  R4 XAU 1  493819 bars = 493819 sub-bars: 20 settings, option on: mag == tv (406230 trades; inverted != normal in 20) (4.7s)
  R4 BTC 60  17518 bars, 1039488 sub-bars: 12 settings, option on: mag(one sub-bar per bar) == tv; mag(real sub-bars) == engine._run on the 1-minute series (34157 trades) (0.8s)
  R4 BTC 5   210155 bars, 1039434 sub-bars: 12 settings, option on: mag(one sub-bar per bar) == tv; mag(real sub-bars) == engine._run on the 1-minute series (180723 trades) (2.5s)
  R4 XAU 240 2246 bars, 493699 sub-bars: 12 settings, option on: mag(one sub-bar per bar) == tv; mag(real sub-bars) == engine._run on the 1-minute series (5336 trades) (0.3s)
  R4 XAU 120 4493 bars, 493819 sub-bars: 12 settings, option on: mag(one sub-bar per bar) == tv; mag(real sub-bars) == engine._run on the 1-minute series (6604 trades) (0.2s)
  R4 XAU 15  32935 bars, 493819 sub-bars: 12 settings, option on: mag(one sub-bar per bar) == tv; mag(real sub-bars) == engine._run on the 1-minute series (39258 trades) (0.5s)
R4 PASS (16.7s): option on: chart "1" mag == tv on 40 settings; one sub-bar per bar: mag == tv on 60; real sub-bars: mag == engine._run on the 1-minute series on 60 (mag != tv in 47); 1445173 trades; check_mag_sync and check_mag_equiv pass
R5 ...
  R5 BTC 60  1417 bars: 36 engine.backtest runs (tv) and 12 run_cfg runs (mag + tv) == pure-Python reference (2.2s)
  R5 BTC 5   4031 bars: 36 engine.backtest runs (tv) and 12 run_cfg runs (mag + tv) == pure-Python reference (2.8s)
  R5 XAU 60  919 bars: 36 engine.backtest runs (tv) and 12 run_cfg runs (mag + tv) == pure-Python reference (1.4s)
  R5 XAU 15  3668 bars: 36 engine.backtest runs (tv) and 12 run_cfg runs (mag + tv) == pure-Python reference (3.3s)
R5 PASS (9.6s): 144 tv runs (engine.backtest: ids, real sides, prices, exit kinds, comments, levels, counters) and 48 mag runs == the reference, 33339 trades; exit kinds {'trail': 7431, 'sl': 4105, 'reverse': 3793, 'close_all': 5022, 'end': 97}; of the tv runs: inverted 94, one-side mode 83, "exit only" rows 57, reversed labels 65, Max open entries < 20 85 (entries held back in 65), pyramiding 2 48 (orders ignored in 23), close_all in 98; opposite flag rejected in 24 / 24
OK: 5 / 5 tests passed
```

### The existing suites on the changed modules (`inv_xpw_existing_tests.log`)

`sweep_tests.py` (its sweep pool capped at 2 workers instead of 3, to stay within two processes; the test
text still says "3 workers"), `verify_v2.py`, `mag_ref.py compare --workers 2`, `audit_engine_synth.py`,
`audit_engine_fifo.py`:

```
== sweep_tests.py (all tests; sweep.MAX_WORKERS patched 3 -> 2) ==
T1 PASS (19.2s): 240 settings, 67219 trades: trade arrays identical, metrics identical (tv0 and cost)
T2 PASS (10.0s): 40 settings: mag (real 1-minute sub-bars) == tv on chart "1"
T3 PASS (0.2s): 40 settings: mag (one sub-bar per chart bar) == tv; _run_mag steps 2-3 == engine._run source
TM PASS (3.5s): 60 settings, 275458 trades: mag == engine._run on the sub-bar series (mag != tv in 50 of them)
TX PASS (37.8s): 800 synthetic trade sets (BTC and XAU costs) x tv0 / cost / stress: metrics_fast == run_tf.metrics, max_expo == reference, fair halves == metrics() per half
T5 PASS (5.4s): 80 rev settings on the T1 windows + 8 on full windows, 29749 trades: trade arrays identical to engine.backtest with the reversed sig, metrics identical
TC PASS (0.2s): XAU 240, empty cache, both orders, 3 passes: 18 loads == fresh frames of their own labels; one file per labels, distinct keys, never rewritten on a read
T6 PASS (9.7s): 160 runs (40772 trades) x tv0 / cost / stress: h1r / h2r pct, pf, trades == run_tf.metrics() per half; unrounded 1920 / 1920 values bit-equal (rest within 1e-9)
T7 PASS (4.9s): 160 runs (40772 trades): stress metrics == run_tf.metrics() with the stressed cost function (every field, exit counts, avg_bars_held, max_expo); unrounded 1120 / 1120 values bit-equal
TS PASS (64.3s): sweep.py output: XAU 240 full grid (structure, unique keys, default row per filter / path / labels, 72 rows checked against fresh inputs, 1 worker == 3 workers); XAU 1 mag == tv copy per labels
T4 PASS (272.6s): BTC 1 full grid tv, single process, per pass: normal/off 90.2s = 0.065 s/setting, normal/on 40.1s = 0.029 s/setting, rev/off 89.0s = 0.065 s/setting, rev/on 46.9s = 0.034 s/setting (1380 settings each); BTC 60 mag: 0.014 s/setting
OK: 11 / 11 tests passed
sweep_tests exit 0
== verify_v2.py ==
== tv: 30 grid settings x labels x filters per window ==
== mag: BTC 60 full window, 10 settings x labels x filters ==
== parquet: /tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/out/sweep_XAU_120.parquet (mtime Wed Nov 18 04:28:56 2026) ==
== neg: mutated references must be rejected (XAU 120 parquet, 6 tv rows) ==
== 540 runs, 93038 checks, 0 failures; max rel diff on unrounded floats 6.14e-13; 0 rounding ties accepted; 253.9s ==
VERIFY PASS
verify_v2 exit 0
== mag_ref.py compare --workers 2 ==
TOTAL 416 runs, 0 with a mismatch, 99320 trades compared (kinds [38984, 19273, 8906, 31872, 285]), 307 runs where mag differs from tv; 17s
mag_ref exit 0
== audit_engine_synth.py ==
audit_engine_synth exit 0
== audit_engine_fifo.py ==
audit_engine_fifo exit 0
ALL DONE
```

### Mutation check (`python3 -I inv_mut_xpw.py`, `inv_mut_xpw.log`)

One line of the option broken at a time in a private copy; `inv_tests_xpw.py R2 R3 R4 R5 --tfs 60,240` must
fail (R1 cannot see these: it runs with the option off):

```
none      control: the unmutated copy                                                      -> all pass (52s)
posn      decisions read the real position (xpwPosN = strategy.position_size)              -> caught by R2 R3 R4 R5 (13s)
          first failure: R2 FAIL (4.3s): BTC 60 tv {'tag': 'default', 'trailOn': True, 'trailUnit': 'price', 'trailAct': 2.0, 'trailOff': 1.0, 'slOn': False, 'slDist': nan} filter on: inverted != reversed labels in the opposite zones: xrow differs at trad
side      the order is not sent on the other side (realLong = isLong)                      -> caught by R2 R3 R5 (15s)
          first failure: R2 FAIL (3.7s): BTC 60 tv {'tag': 'default', 'trailOn': True, 'trailUnit': 'price', 'trailAct': 2.0, 'trailOff': 1.0, 'slOn': False, 'slDist': nan} filter off: inverted != reversed labels: dir differs at trade 0: np.int8(-1) vs np
reverse   the reversal is tested on the normal side instead of the side really traded      -> caught by R2 R3 R5 (15s)
          first failure: R2 FAIL (3.4s): BTC 60 tv {'tag': 'default', 'trailOn': True, 'trailUnit': 'price', 'trailAct': 2.0, 'trailOff': 1.0, 'slOn': False, 'slDist': nan} filter off: inverted != reversed labels: xrow differs at trade 17: np.int64(85) vs
levels    trailing TP / stop distances laid out on the normal side (e = d * close)         -> caught by R2 R3 R5 (15s)
          first failure: R2 FAIL (3.4s): BTC 60 tv {'tag': 'default', 'trailOn': True, 'trailUnit': 'price', 'trailAct': 2.0, 'trailOff': 1.0, 'slOn': False, 'slDist': nan} filter off: inverted != reversed labels: xrow differs at trade 5: np.int64(48) vs 
room      "room > 0 or xpwPosN < 0" reads the real position                                -> caught by R2 R3 R5 (16s)
          first failure: R2 FAIL (3.8s): BTC 60 tv {'tag': 'grid', 'trailOn': True, 'trailUnit': 'percent', 'trailAct': 3.0, 'trailOff': 0.75, 'slOn': True, 'slDist': 4.0} filter off: inverted != reversed labels: trade count 3885 vs 3886
close     closeL / closeS read the real position                                           -> caught by R2 R3 R5 (15s)
          first failure: R2 FAIL (3.3s): BTC 60 tv {'tag': 'default', 'trailOn': True, 'trailUnit': 'price', 'trailAct': 2.0, 'trailOff': 1.0, 'slOn': False, 'slDist': nan} filter on: inverted != reversed labels in the opposite zones: xrow differs at trad
tradedir  "Trade direction" keeps its pre-Update-1 tests when inverted (engine.backtest_bars) -> caught by R2 R3 R5 (19s)
          first failure: R2 FAIL (9.2s): BTC 60 Long only (buy only) oppCloses True filter False, inv vs rev: rows 1882 vs 2004
comment   the "(inv)" tag is missing from the entry comments                               -> caught by R2 R3 R5 (14s)
          first failure: R2 FAIL (8.7s): BTC 60 filter off, inv vs rev: an inverted entry comment without " (inv)"
blktext   the blocked-close comment names the filter side instead of the real side         -> caught by R2 R3 R5 (15s)
          first failure: R2 FAIL (9.0s): BTC 60 filter on (blkClose True), inv vs rev + swapped zones: exit_comment differs beyond " (inv)" at trade 21: 'filter blocked SHORT (inv), close | 1 Hour * look for SHORTS' vs 'filter blocked LONG, close | 1 Hour
srclist   the entry is credited to the label list of its REAL side                         -> caught by R2 R3 R5 (14s)
          first failure: R2 FAIL (8.7s): list index out of range
magonly   only the Bar Magnifier kernel forgets to flip the order                          -> caught by R2 R4 R5 (33s)
          first failure: R2 FAIL (3.3s): BTC 60 mag {'tag': 'default', 'trailOn': True, 'trailUnit': 'price', 'trailAct': 2.0, 'trailOff': 1.0, 'slOn': False, 'slDist': nan} filter off: inverted != reversed labels: dir differs at trade 0: np.int8(-1) vs n
runcfg    run_cfg does not pass the flag to the Bar Magnifier kernel                       -> caught by R2 R4 R5 (30s)
          first failure: R2 FAIL (3.7s): BTC 60 mag {'tag': 'default', 'trailOn': True, 'trailUnit': 'price', 'trailAct': 2.0, 'trailOff': 1.0, 'slOn': False, 'slDist': nan} filter off: inverted != reversed labels: dir differs at trade 0: np.int8(-1) vs n
OK: 12 mutations, 12 caught, control all pass
```

## 6. Runner: `python3 -I run_inv_xpw.py PAIR TF [TF ...]`

Writes `out/inv_xpw_<PAIR>_<TF>.json`: `runs[direction][filter][path][cost]` with direction `normal` /
`inverted`, filter `off` / `on`, path `tv` / `mag`, cost `script` (no costs) / `ours` (XAU $0.30 per ounce
per round trip; BTC 0.02% per side + $0.20 per coin per round trip); `rev_labels[filter][path][cost]` = the
existing reversed-label runs; `funnel` = the engine's entry funnel of the tv run; `checks` = verified while
running: the tv numbers equal `engine.backtest` + `run_tf.metrics` (both costs, exit kinds, the trade
arrays); filter off, inverted == reversed labels (tv and mag); the option-off numbers equal the saved
`out/run_*.json` and the default rows of the saved `out/sweep_*.parquet`. It raises if one of them fails.
Default inputs: trail activation 2.0 / offset 1.0 price units, no stop loss, Both, Max open entries 20,
Signal tick. Chart "1" also works (tried on XAU 1 in a scratch directory: 16.8 s, mag == tv).

Run on BTC 60 and XAU 240 (the orchestrator runs the others). h1r / h2r = the fair halves (trades entered
in each half, each from a fresh 10,000), with their trade counts.

### BTC 60 (17518 bars, window 1731801600..1794873600)

| path | filter | direction | trades (long / short) | cost | net % | PF | win % | max DD % | h1r % (trades) | h2r % (trades) | exits trail / sl / close_all / reverse / end | avg bars | max expo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tv | off | normal | 3886 (1882 / 2004) | script | 143.66 | 9.78 | 98.5 | 1.05 | 59.36 (2005) | 52.90 (1881) | 3823 / 0 / 0 / 63 / 0 | 1.32 | 0.40 |
| tv | off | normal | 3886 (1882 / 2004) | ours | 108.40 | 6.96 | 77.4 | 1.06 | 47.02 (2005) | 41.75 (1881) | 3823 / 0 / 0 / 63 / 0 | 1.32 | 0.40 |
| tv | off | inverted | 3886 (2004 / 1882) | script | 164.30 | 14.80 | 98.3 | 0.41 | 60.03 (2005) | 65.16 (1881) | 3816 / 0 / 0 / 70 / 0 | 1.23 | 0.30 |
| tv | off | inverted | 3886 (2004 / 1882) | ours | 126.06 | 9.78 | 76.8 | 0.41 | 47.64 (2005) | 53.12 (1881) | 3816 / 0 / 0 / 70 / 0 | 1.23 | 0.30 |
| tv | off | rev labels (ref.) | 3886 (2004 / 1882) | script | 164.30 | 14.80 | 98.3 | 0.41 | 60.03 (2005) | 65.16 (1881) | 3816 / 0 / 0 / 70 / 0 | 1.23 | 0.30 |
| tv | off | rev labels (ref.) | 3886 (2004 / 1882) | ours | 126.06 | 9.78 | 76.8 | 0.41 | 47.64 (2005) | 53.12 (1881) | 3816 / 0 / 0 / 70 / 0 | 1.23 | 0.30 |
| tv | on | normal | 1807 (897 / 910) | script | 50.61 | 6.87 | 98.0 | 1.05 | 25.71 (949) | 19.81 (858) | 1767 / 0 / 37 / 3 / 0 | 1.45 | 0.30 |
| tv | on | normal | 1807 (897 / 910) | ours | 40.05 | 5.17 | 76.9 | 1.06 | 21.01 (949) | 15.74 (858) | 1767 / 0 / 37 / 3 / 0 | 1.45 | 0.30 |
| tv | on | inverted | 1807 (910 / 897) | script | 57.79 | 14.70 | 98.3 | 0.41 | 25.50 (949) | 25.73 (858) | 1775 / 0 / 16 / 16 / 0 | 1.24 | 0.30 |
| tv | on | inverted | 1807 (910 / 897) | ours | 46.73 | 9.52 | 74.6 | 0.41 | 20.80 (949) | 21.46 (858) | 1775 / 0 / 16 / 16 / 0 | 1.24 | 0.30 |
| tv | on | rev labels (ref.) | 1419 (759 / 660) | script | 42.41 | 17.15 | 98.4 | 0.38 | 18.43 (733) | 20.25 (686) | 1396 / 0 / 16 / 7 / 0 | 1.22 | 0.20 |
| tv | on | rev labels (ref.) | 1419 (759 / 660) | ours | 34.51 | 10.89 | 77.9 | 0.38 | 14.99 (733) | 16.97 (686) | 1396 / 0 / 16 / 7 / 0 | 1.22 | 0.20 |
| mag | off | normal | 3886 (1882 / 2004) | script | 9.18 | 1.94 | 97.0 | 1.45 | 6.38 (2005) | 2.64 (1881) | 3828 / 0 / 0 / 58 / 0 | 1.31 | 0.40 |
| mag | off | normal | 3886 (1882 / 2004) | ours | -6.62 | 0.55 | 38.3 | 7.12 | -1.86 (2005) | -4.85 (1881) | 3828 / 0 / 0 / 58 / 0 | 1.31 | 0.40 |
| mag | off | inverted | 3886 (2004 / 1882) | script | 11.69 | 2.61 | 96.4 | 0.46 | 5.85 (2005) | 5.52 (1881) | 3818 / 0 / 0 / 68 / 0 | 1.22 | 0.30 |
| mag | off | inverted | 3886 (2004 / 1882) | ours | -4.47 | 0.64 | 38.5 | 4.55 | -2.35 (2005) | -2.17 (1881) | 3818 / 0 / 0 / 68 / 0 | 1.22 | 0.30 |
| mag | off | rev labels (ref.) | 3886 (2004 / 1882) | script | 11.69 | 2.61 | 96.4 | 0.46 | 5.85 (2005) | 5.52 (1881) | 3818 / 0 / 0 / 68 / 0 | 1.22 | 0.30 |
| mag | off | rev labels (ref.) | 3886 (2004 / 1882) | ours | -4.47 | 0.64 | 38.5 | 4.55 | -2.35 (2005) | -2.17 (1881) | 3818 / 0 / 0 / 68 / 0 | 1.22 | 0.30 |
| mag | on | normal | 1807 (897 / 910) | script | 1.68 | 1.25 | 96.2 | 1.39 | 2.38 (949) | -0.69 (858) | 1770 / 0 / 35 / 2 / 0 | 1.43 | 0.30 |
| mag | on | normal | 1807 (897 / 910) | ours | -5.45 | 0.40 | 37.7 | 5.61 | -1.45 (949) | -4.06 (858) | 1770 / 0 / 35 / 2 / 0 | 1.43 | 0.30 |
| mag | on | inverted | 1807 (910 / 897) | script | 5.28 | 2.52 | 96.8 | 0.48 | 2.57 (949) | 2.65 (858) | 1776 / 0 / 15 / 16 / 0 | 1.22 | 0.30 |
| mag | on | inverted | 1807 (910 / 897) | ours | -2.10 | 0.65 | 38.6 | 2.37 | -1.27 (949) | -0.84 (858) | 1776 / 0 / 15 / 16 / 0 | 1.22 | 0.30 |
| mag | on | rev labels (ref.) | 1419 (759 / 660) | script | 4.51 | 3.08 | 96.4 | 0.56 | 2.54 (733) | 1.93 (686) | 1397 / 0 / 15 / 7 / 0 | 1.21 | 0.20 |
| mag | on | rev labels (ref.) | 1419 (759 / 660) | ours | -1.28 | 0.69 | 39.1 | 1.40 | -0.44 (733) | -0.85 (686) | 1397 / 0 / 15 / 7 / 0 | 1.21 | 0.20 |

Entry funnel (tv run; candles on the filter's side, entries on the real side):

| run | filter | raw long / short | blocked long / short | go long / short | entries (real long / short) |
|---|---|---|---|---|---|
| normal | off | 1841 / 1961 | 0 / 0 | 1841 / 1961 | 3886 (1882 / 2004) |
| normal | on | 1841 / 1961 | 961 / 1070 | 880 / 891 | 1807 (897 / 910) |
| inverted | off | 1841 / 1961 | 0 / 0 | 1841 / 1961 | 3886 (2004 / 1882) |
| inverted | on | 1841 / 1961 | 961 / 1070 | 880 / 891 | 1807 (910 / 897) |
| rev_labels | off | 1961 / 1841 | 0 / 0 | 1961 / 1841 | 3886 (2004 / 1882) |
| rev_labels | on | 1961 / 1841 | 1217 / 1195 | 744 / 646 | 1419 (759 / 660) |

### XAU 240 (2246 bars, window 1483315200..1529366400)

| path | filter | direction | trades (long / short) | cost | net % | PF | win % | max DD % | h1r % (trades) | h2r % (trades) | exits trail / sl / close_all / reverse / end | avg bars | max expo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tv | off | normal | 544 (275 / 269) | script | 3.97 | 1.47 | 83.8 | 1.94 | 1.33 (280) | 2.60 (264) | 442 / 0 / 0 / 99 / 3 | 4.80 | 0.80 |
| tv | off | normal | 544 (275 / 269) | ours | 2.65 | 1.31 | 83.5 | 2.16 | 0.66 (280) | 1.97 (264) | 442 / 0 / 0 / 99 / 3 | 4.80 | 0.80 |
| tv | off | inverted | 544 (269 / 275) | script | 4.39 | 1.58 | 80.7 | 1.49 | 2.62 (280) | 1.72 (264) | 428 / 0 / 0 / 115 / 1 | 3.44 | 0.50 |
| tv | off | inverted | 544 (269 / 275) | ours | 3.06 | 1.40 | 80.1 | 1.58 | 1.94 (280) | 1.11 (264) | 428 / 0 / 0 / 115 / 1 | 3.44 | 0.50 |
| tv | off | rev labels (ref.) | 544 (269 / 275) | script | 4.39 | 1.58 | 80.7 | 1.49 | 2.62 (280) | 1.72 (264) | 428 / 0 / 0 / 115 / 1 | 3.44 | 0.50 |
| tv | off | rev labels (ref.) | 544 (269 / 275) | ours | 3.06 | 1.40 | 80.1 | 1.58 | 1.94 (280) | 1.11 (264) | 428 / 0 / 0 / 115 / 1 | 3.44 | 0.50 |
| tv | on | normal | 247 (124 / 123) | script | 1.55 | 1.40 | 81.4 | 0.90 | 0.79 (137) | 0.76 (110) | 193 / 0 / 33 / 20 / 1 | 4.75 | 0.50 |
| tv | on | normal | 247 (124 / 123) | ours | 0.96 | 1.24 | 81.0 | 1.04 | 0.46 (137) | 0.50 (110) | 193 / 0 / 33 / 20 / 1 | 4.75 | 0.50 |
| tv | on | inverted | 247 (123 / 124) | script | 1.86 | 1.59 | 79.8 | 0.83 | 1.21 (137) | 0.64 (110) | 191 / 0 / 26 / 29 / 1 | 3.46 | 0.30 |
| tv | on | inverted | 247 (123 / 124) | ours | 1.27 | 1.39 | 78.9 | 0.86 | 0.88 (137) | 0.39 (110) | 191 / 0 / 26 / 29 / 1 | 3.46 | 0.30 |
| tv | on | rev labels (ref.) | 194 (89 / 105) | script | 2.10 | 1.81 | 82.0 | 0.45 | 1.39 (95) | 0.71 (99) | 155 / 0 / 33 / 6 / 0 | 3.41 | 0.30 |
| tv | on | rev labels (ref.) | 194 (89 / 105) | ours | 1.64 | 1.61 | 81.4 | 0.47 | 1.16 (95) | 0.48 (99) | 155 / 0 / 33 / 6 / 0 | 3.41 | 0.30 |
| mag | off | normal | 544 (275 / 269) | script | -0.63 | 0.92 | 84.2 | 2.64 | -1.33 (280) | 0.71 (264) | 450 / 0 / 0 / 91 / 3 | 4.67 | 0.80 |
| mag | off | normal | 544 (275 / 269) | ours | -1.89 | 0.77 | 83.8 | 3.39 | -1.99 (280) | 0.10 (264) | 450 / 0 / 0 / 91 / 3 | 4.67 | 0.80 |
| mag | off | inverted | 544 (269 / 275) | script | -0.30 | 0.96 | 80.7 | 1.65 | -0.01 (280) | -0.30 (264) | 431 / 0 / 0 / 112 / 1 | 3.27 | 0.50 |
| mag | off | inverted | 544 (269 / 275) | ours | -1.57 | 0.79 | 80.0 | 2.19 | -0.67 (280) | -0.90 (264) | 431 / 0 / 0 / 112 / 1 | 3.27 | 0.50 |
| mag | off | rev labels (ref.) | 544 (269 / 275) | script | -0.30 | 0.96 | 80.7 | 1.65 | -0.01 (280) | -0.30 (264) | 431 / 0 / 0 / 112 / 1 | 3.27 | 0.50 |
| mag | off | rev labels (ref.) | 544 (269 / 275) | ours | -1.57 | 0.79 | 80.0 | 2.19 | -0.67 (280) | -0.90 (264) | 431 / 0 / 0 / 112 / 1 | 3.27 | 0.50 |
| mag | on | normal | 247 (124 / 123) | script | -0.48 | 0.87 | 81.4 | 1.22 | -0.36 (137) | -0.13 (110) | 197 / 0 / 31 / 18 / 1 | 4.64 | 0.40 |
| mag | on | normal | 247 (124 / 123) | ours | -1.06 | 0.73 | 81.0 | 1.59 | -0.68 (137) | -0.38 (110) | 197 / 0 / 31 / 18 / 1 | 4.64 | 0.40 |
| mag | on | inverted | 247 (123 / 124) | script | 0.08 | 1.03 | 79.8 | 0.89 | 0.19 (137) | -0.11 (110) | 192 / 0 / 25 / 29 / 1 | 3.33 | 0.30 |
| mag | on | inverted | 247 (123 / 124) | ours | -0.49 | 0.85 | 78.9 | 0.93 | -0.13 (137) | -0.36 (110) | 192 / 0 / 25 / 29 / 1 | 3.33 | 0.30 |
| mag | on | rev labels (ref.) | 194 (89 / 105) | script | 0.04 | 1.01 | 82.0 | 0.67 | 0.29 (95) | -0.25 (99) | 157 / 0 / 31 / 6 / 0 | 3.18 | 0.30 |
| mag | on | rev labels (ref.) | 194 (89 / 105) | ours | -0.42 | 0.84 | 81.4 | 0.87 | 0.06 (95) | -0.48 (99) | 157 / 0 / 31 / 6 / 0 | 3.18 | 0.30 |

Entry funnel (tv run; candles on the filter's side, entries on the real side):

| run | filter | raw long / short | blocked long / short | go long / short | entries (real long / short) |
|---|---|---|---|---|---|
| normal | off | 273 / 258 | 0 / 0 | 273 / 258 | 544 (275 / 269) |
| normal | on | 273 / 258 | 151 / 141 | 122 / 117 | 247 (124 / 123) |
| inverted | off | 273 / 258 | 0 / 0 | 273 / 258 | 544 (269 / 275) |
| inverted | on | 273 / 258 | 151 / 141 | 122 / 117 | 247 (123 / 124) |
| rev_labels | off | 258 / 273 | 0 / 0 | 258 / 273 | 544 (269 / 275) |
| rev_labels | on | 258 / 273 | 172 / 168 | 86 / 105 | 194 (89 / 105) |

Reading the two cells (not a judgement of the strategy, only what the numbers show):

- Filter off, inverted is the reversed-label run to the last digit, on both paths (the header's statement,
  and the runner checks it trade by trade).
- Inverted and normal take the same entries (same candles, same count), on opposite sides; they differ in
  what happens after (the trail and the stop sit on the other side), so the exit mix and the holding time
  differ.
- BTC 60: on the tv path every variant shows a large profit (normal 143.66%, inverted 164.30% with the
  filter off; 50.61% and 57.79% with it on, no costs), reversed labels alike; on the 1-minute path the same
  runs give 9.18% / 11.69% and 1.68% / 5.28% without costs and are all negative with ours (-6.62% / -4.47%,
  -5.45% / -2.10%). That is what `SWEEP_SPEC_2.md` already recorded for this strategy before Update 1 (on
  BTC the default trail earns the same with every label reversed: the tv profit comes from the
  one-path-per-bar assumption, not from the signals); the option does not change it.
- XAU 240: every run is between -1.89% and +4.39% over the window. On the 1-minute path with our costs the
  four normal / inverted runs are all negative (filter off -1.89% / -1.57%, filter on -1.06% / -0.49%), on
  544 and 247 trades; the reversed-label reference with the filter on is at -0.42% on 194 trades.

## 7. Things to know

- `cache_sweep/*.pkl` (the sweep's input cache) was rewritten by `sweep_core.load_inputs` itself the first
  time each cell was loaded: its key lists every `data/<PAIR>_*.parquet`, and the `*_vol.parquet` files added
  on Nov 18 for the other strategies made the old keys stale. The recomputed inputs reproduce every saved
  result (R1a / R1b), so the content is the same; only the key changed.
- `inv_tests_xpw.py` imports `sweep_tests.py` and `mag_ref.py` for their helpers (random settings, the
  pure-Python exit walker); it does not modify them.
- `engine_a.py` / `engine_b.py` (the two pre-reconciliation implementations) were not touched and do not have
  the option.
