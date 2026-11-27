# reconcile_danny: stage 3 for Danny Phantom FX V10.21.1 LiveSafe + FGF [Update 1]

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Ground truth: `/home/user/master/DannyPhantomFX_V10_21_1_LiveSafe_FGF.pine` at HEAD (`Lnnn` = its lines).
The two stage-2 builds as delivered are kept in `$W/reconcile_danny_orig/`; `$W/danny_a.py` and
`$W/danny_b.py` are those builds after the fixes below; `$W/danny.py` is the canonical module.

## Result

- The two builds, written independently, gave **the same trades in every case of round 0**: 658 cases on 10
  cells, 1,531,346 trades, every column of `trades()`. The largest relative difference of a float column was
  1.4e-12 (the builds add the two costs of a fill in a different order).
- They disagreed on one summary counter (`qty_capped`, 88 cases) and on two inputs outside the default paths
  (a session string with a day suffix; a window that starts on the first rows of the data file).
- Two places were found where BOTH builds followed SPEC_danny.md and the Pine does something else. Both act
  only after a decision sized to zero (a ruined account). Each builder had flagged its half in its notes. The
  Pine wins: all three modules now follow it.
- After the fixes: **728 cases, 1,598,945 trades, 0 differences** between A, B and the canonical module
  (`tests_danny.py` T1); canonical against A is bitwise equal.

## What was compared (`$W/reconcile_danny_cmp.py PAIR TF --mods a,b,c --extra`)

Cells: BTC and XAU, charts 1, 5, 15, 60, 240, full windows. Per cell:

| group | cases | content |
|---|---|---|
| fixed | 32 (XAU 5: 40) | filter {on, off} x `dpInv` {off, on} x cost {tv, ours, stress} x `varRollback` {True, False}; and `signalDirection` "Original (un-inverted)" x filter x `dpInv` x cost {tv, ours}; XAU 5 also with `presetMode` "Manual" |
| random | 8 (80 in all) | settings drawn from the calibration grid of SPEC_danny.md section 14 (zone length, delta, EMA, filter, `signalDirection`, `dpInv`, stop multiple, target, time stop, dead exit, trailing pair of the cell), each with a random cost mode and `varRollback` |
| extra | 25 | outside the grid: breakeven, tight trailing, Points mode, no stop / no target, Fixed quantity, risk and margin inputs, loss-cluster inputs, `varRollback` False with the reset / cooldown switches, entry mode, zone-trend, zone age / retest / invalidation, blackouts off, ATR length, session and entry-window filters, forced XAUUSD 5m preset with and without its profile, filter inputs |
| edge | 7 | windows at the first rows of the data file (ATR, SMA and `close[1]` na), 2-month windows inside the pair's window, session strings with a `:days` suffix |

Every column of `trades()` (floats to a relative 1e-9, the rest exactly) and every field of `summary()`.
Logs: round 0 `$W/reconcile_danny_r0_<PAIR>_<TF>.log` (A, B as delivered; groups fixed, random, extra),
round 1 `$W/reconcile_danny_r1_<PAIR>_<TF>.log` (A, B fixed and the canonical; all four groups), last run:
`$W/tests_danny.log`.

| cell | round 0: cases / differ / trades | after the fixes: cases / differ / trades |
|---|---|---|
| BTC 1 | 65 / 25 / 729,042 | 72 / 0 / 746,359 |
| BTC 5 | 65 / 1 / 317,687 | 72 / 0 / 323,628 |
| BTC 15 | 65 / 1 / 151,800 | 72 / 0 / 154,412 |
| BTC 60 | 65 / 0 / 59,230 | 72 / 0 / 60,167 |
| BTC 240 | 65 / 0 / 16,666 | 72 / 0 / 16,973 |
| XAU 1 | 65 / 60 / 105,060 | 72 / 0 / 139,371 |
| XAU 5 | 73 / 0 / 28,080 | 80 / 0 / 28,149 |
| XAU 15 | 65 / 1 / 84,870 | 72 / 0 / 89,346 |
| XAU 60 | 65 / 0 / 30,159 | 72 / 0 / 31,440 |
| XAU 240 | 65 / 0 / 8,752 | 72 / 0 / 9,100 |

All 88 differing cases of round 0 differ in `qty_capped` only.

The four remaining cells of the runner (charts 30 and 120), compared after the fixes only
(`$W/reconcile_danny_r2_<PAIR>_<TF>.log`): BTC 30 72 / 0 / 94,345; XAU 30 72 / 0 / 58,065; BTC 120
72 / 0 / 32,643; XAU 120 72 / 0 / 18,129. All 14 cells together: 1,016 cases (112 random grid settings),
1,802,127 trades, 0 differences.

## The disagreements, one by one

### D1. `qty_capped` (summary counter; 88 cases; no trade affected)

A counted the ORDERS PLACED whose quantity `maxQtyS3` or the margin cap reduced. B counted every sizing call
in which a cap reduced the quantity, including the calls that end at zero. On a ruined account the margin
cap `equity / (close x 1 %)` is below the risk quantity at almost every decision, and the result then floors
to zero: XAU 1, filter off, cost 'tv': A 3, B 1,178 (the account takes 297 trades and has 35,647 decisions
sized to zero). The Pine has no such counter (`f_qty`, L1196-1205, only returns the quantity); SPEC_danny
section 7 says "the max or the margin cap reduced q". A's definition is kept because the two counters then
do not overlap: a decision is either an order (`qty_capped` if a cap bit) or `zero_qty`. B changed
(`if capped and q > 0.0`).

### D2. Session string with a day suffix (`nySession`, `entryWindowIn`, e.g. "0930-1600:23456")

A dropped everything after the colon; B applied the days (Pine numbering, 1 = Sunday). The Pine passes the
string to `time(timeframe.period, session)` (L939-940), which honours a day list. B follows the Pine; A
changed (`_parse_session`, `_in_session`). Both session inputs are off by default and outside the
calibration grid; the reading of `time()` itself is assumption E12. Edge cases 5 and 6 cover it.

### D3. A window that starts within the first `atrLenS2 - 1` rows of the data file

A raised `NotImplementedError`; B ran it. In the Pine `ta.atr` is na there: `slDistNow` is na, `f_qty`
returns 0 in Risk mode (`stopCash > 0` is false, L1201), so no order; with a Fixed quantity the trade has
no bracket (L1415-1416). B follows the Pine; A's refusal was removed and its kernel, which already handled
na distances, gives B's trades (edge cases 0 to 2: 22, 21 and 45 trades, equal).

### P1. Both builds against the Pine: the reset of a zero-quantity decision on a bracket-fill candle

SPEC_danny B12: the one-entry-per-zone reset persists whenever the decision's quantity is <= 0 ("no fill
follows, the run is not repeated"). That is right on a candle with no bracket fill. On a candle where the
bracket filled, the brief's own reading E3 puts the decision in the run that follows the intrabar fill. The
bar-close run comes after it, starts from the variables of the end of the previous bar (the reset is gone)
and cannot decide again: `lastEntryDecisionBar` is `varip` (L1231, L1241-1243, L1311). Both builders noted
it and kept the brief; builder A's literal several-runs reference shows the difference.

Hand trace (`$W/danny_s3_trace_zero.log`): XAU 15, filter off, `dpInv` on, cost 'tv', equity about $0.11.

| candle | open | high | low | close | what happens |
|---|---|---|---|---|---|
| 139735 | 1240.302 | 1240.509 | 1239.871 | 1239.919 | a normal BUY is placed as a SELL at 1239.169; stop 1240.103, target 1235.277 |
| 139736 | 1239.918 | 1240.289 | 1236.128 | 1238.068 | (high - open) 0.371 < (open - low) 3.790: the path goes up first, 1240.289 >= 1240.103: stop fill on the first leg. The run after that fill sees a supply retest (high >= key bottom 1239.919, bearish candle): normal BUY, `f_qty` = 0, no order. The short block resets the SUPPLY zone (`dpLongFromDemand` true, L1340-1345). The bar-close run rolls that back |
| 139747 | 1240.179 | 1240.451 | 1239.568 | 1239.642 | the long of 139745 is stopped (low 1239.568 <= 1240.030). Supply retest again (high 1240.451 >= 1239.919, close < open, close < close[1]) |

With the brief's rule the supply zone is gone at 139736, there is no signal at 139747 and the next trade
is a long at 139748. With the Pine's run order the zone is still there: trade 929 is a short at 139747
(entry 1238.892, stopped at 139748). 956 trades either way, net -99.9969 % either way.

### P2. Both builds against the Pine: the `pending*` variables after a zero-quantity decision

SPEC_danny E7: "NOT replicated (ruin corner)". The Pine writes `pendingLongAtr / pendingShortAtr /
pendingSlDist / pendingTpDist` before `strategy.entry` whatever the quantity (L1304-1307, L1329-1332). With
no fill there is no further run, so nothing rolls them back. `pendingSlDist / pendingTpDist` are cleared in
the same run when flat (L1400-1401); the pending ATR is not, and the next filled entry on that side takes
it (L1372, L1384). Only the breakeven trigger reads `longAtrAtEntry / shortAtrAtEntry`.

Hand trace (same log): BTC 5, filter off, cost 'ours', `useBreakeven` on, equity about $19.57.

| candle | close | ATR(14) | what happens |
|---|---|---|---|
| 1316310 | 116620.0 | 168.8135 | normal SELL; `f_qty`: risk quantity 19.5716 x 1 % / 202.5762 = 0.000966, floored to 0: no order. `pendingShortAtr := 168.8135` stays |
| 1316316 | 116786.0 | 162.0427 | normal SELL, quantity 0.001, short at 116786.0, stop 116980.45, target 115975.78. In the run after the fill `shortAtrAtEntry := pendingShortAtr` = 168.8135 (L1384), not this candle's 162.0427 |
| 1316321 | 116622.0 | | breakeven needs close <= 116786.0 - 168.8135 = 116617.19: not armed. (With 162.0427 the level is 116623.96: armed, stop moved to 116786.0, hit at 1316323, high 116802.0) |
| 1316325 | 116567.0 | | armed; stop 116786.0 |
| 1316327 | 116104.0 | | low 115684.0: target 115975.78 filled |

Brief's rule: trade 3225 ends 'be' at 1316323, pnl -0.047; Pine: 'tp' at 1316327, pnl +0.763. Whole run:
3,862 trades / -99.7773 % against 3,859 / -99.7768 %.

Rule now in the three kernels: with `varRollback` True a decision sized to zero on a candle without a
bracket fill keeps its reset and its four pending values; `pendingSlDist / pendingTpDist` are cleared at the
end of every flat candle; the next initialisation (not an inherited one) takes a pending ATR of its side
and, if `pendingSlDist` is set, the pending distances, then clears the two pending ATRs. With `varRollback`
False nothing changes (the entry run overwrites all four before they are read).

Check: `$W/reconcile_danny_zeroqty.py` (log next to it): 20 ruined runs x the three modules against builder
A's literal reference (`danny_a_ref.ref_run`, a run after every intrabar fill, `var` rollback, pending values
kept): 0 differences. `tests_danny.py` T7 repeats 12 such runs, including the two traced above.

Reach of P1 and P2: only runs with `zero_qty > 0`. In the 14 cells with default inputs those are the runs
flagged `ruined` (42 of the 224 in `runs`): with the script's costs XAU 1, XAU 15, XAU 30 filter off normal
and XAU 5 Manual; with our costs BTC 1, BTC 5 (all but inverted with the filter on), BTC 15 filter off
normal, XAU 1 and XAU 5 Manual. Every one of them has lost 98 % of the account or more.

## The canonical module

`$W/danny.py` = build A after the fixes + the 'mag' path. A was taken because its kernel returns the
per-candle state used by the traces (`full=True`) and it comes with a literal several-runs transliteration
of the Pine (`danny_a_ref.py`) that the canonical module is still tested against (T7). B is equal trade
for trade.

Path 'mag' (SWEEP_AH_SPEC.md section 2, SPEC_danny 5.3): the open trade's bracket walks the 1-minute
sub-bars of the chart candle in time order; each sub-bar gets the open test (stop before limit) and its own
path; the levels are constant during the candle. This script has no stop or limit ENTRY order; market
entries, reversals, the dead / time / blackout closes and the bar-close logic stay on the chart candle. One
function (`_walk`) serves both paths. A bracket exit on 'mag' is timed at the open of its sub-bar.

Other stage-3 changes to the module: none in the trading logic. `reentry` on 'mag' is 2 / 3 only when the
bracket filled in the last sub-bar of the candle, else 1 (danny_notes.md section 5).

## Tests, mutants, runner

- `python3 -I tests_danny.py` -> `$W/tests_danny.log`: 28 tests (T1 x 10 cells, T2 x 2, T3, T4, T5, T6 x 9,
  T7 x 2, T8 x 2), 28 PASS in 212 s. One test was wrong when first run and was corrected, not the module: it asked the first
  1-minute sub-bar of every candle to open at the candle's `t_open`; 2,099 of the candles checked start with
  a hole in the 1-minute data (the candle's open price is still that sub-bar's).
- `python3 -I danny_s3_mut.py` -> `$W/danny_s3_mut.log`: 12 copies of `danny.py` with one line changed (the
  'mag' loop, the path rule, slippage on a limit fill, the sign of the stop slippage, the Update 1 gate, the
  zone the reset clears under `dpInv`, the inherited state, a cost constant, the 'mag' exit time, the pending
  ATR, the reset rule of P1, the fair-half split), each run against T1 (two cells), T3 to T7: all 12 make
  at least one test fail.
- `python3 -I danny_s3_martingale.py [steps] [seeds]`: the kernel on a driftless random walk with zero
  costs. With 600 steps per candle the mean R per trade is within 1.7 standard errors of 0 in every run
  (both paths, option off and on, both `varRollback`, default exits and trail + breakeven): no look-ahead,
  no fill bias. With 60 coarse steps it is +0.02 to +0.04 R: a stop filling at its level while the path
  jumps over it (danny_notes.md section 10).
- `python3 -I run_inv_danny.py PAIR TF [TF ...]` -> `$W/out/inv_danny_<PAIR>_<TF>.json` for the 14 cells
  (logs `$W/out/run_inv_danny_<PAIR>_<TF>.log`); tables: `python3 -I inv_tables_danny.py [--aw|--manual|--full]`.
  Checks stored in every file: filter off, inverted == the other "Signal direction" trade for trade
  (true in all 14, and on XAU 5 Manual); filter on, they differ (true in 13; XAU 5 Auto has no trade);
  chart "1": every 'mag' run equals its 'tv' run (true for BTC and XAU).
