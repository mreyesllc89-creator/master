# Component 2 (XPW ladder and labels): reconciliation of xpw_a.py and xpw_b.py

Ground truth: `/home/user/master/xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine`, from
`// PER-RUNG WINDOWS` (line 901) through the end of `SIGNAL RUNGS` (line 1371), plus the
"both sides cancel" lines at the top of STRATEGY (1380-1384).

Canonical module: `xpw.py`. It is a copy of `xpw_a.py` with only the module docstring changed.
It has the same interface: `xpw_signals(pair, chart_tf, start, end, params=None)`.
A was picked because it was slightly faster on the 2-year 1m run (7.1-7.6 s against 7.7 s, fresh
process, numba cache warm) and used slightly less memory (2.4 GB against 2.5 GB peak RSS).
The two implementations give identical output on every case below.

Harness (all in this directory, run with `python3 -I`):
- `reconcile_xpw_cmp.py` runs both implementations on the required cases and compares every common column row by row.
  Lists are compared element by element and in order.
- `reconcile_xpw_extra.py` covers non-default parameters and full-history windows.
- `reconcile_xpw_rung.py` compares the 7 rungState outputs on every rung timeframe's own full series.
- `reconcile_xpw_time.py <module> [every]` times the 2-year BTC 1m window in a fresh process.

## Agreement table (default params, 65 common columns)

The common columns are t_close, chartIdx, readAt, nLongRaw, nShortRaw, nLong, nShort, longSrc, shortSrc,
exitL, exitS, exitLSrc, exitSSrc, and pos_/orient_/inh_/shape_ for rungs 0..12.
A also has `baseDir` and `events`, which B does not have.

| case | window | rows | chartIdx | rows agree (before fix) | rows agree (after fix) | bars with an entry label | long / short raw | long / short after cancel | both-side cancels | exitL / exitS | readAt set |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BTC 60 | 2025-01-01..2025-03-01 | 1417 | 4 | 1417 (100%) | 1417 (100%) | 325 | 184 / 159 | 177 / 152 | 7 | 0 / 0 | 362 |
| BTC 5 | 2025-01-01..2025-01-15 | 4031 | 7 | 4031 (100%) | 4031 (100%) | 455 | 235 / 229 | 231 / 225 | 4 | 0 / 0 | 414 |
| BTC 240 | 2024-11-17..2025-11-17 | 2191 | 3 | 2191 (100%) | 2191 (100%) | 562 | 292 / 298 | 275 / 281 | 17 | 0 / 0 | 751 |
| BTC 1 | 2025-02-01..2025-02-08 | 10021 | 8 | 10021 (100%) | 10021 (100%) | 658 | 388 / 270 | 388 / 270 | 0 | 0 / 0 | 887 |
| BTC 120 | 2025-06-01..2025-09-01 | 1105 | 3 | 1105 (100%) | 1105 (100%) | 252 | 110 / 152 | 104 / 146 | 6 | 0 / 0 | 363 |
| XAU 60 | 2017-03-01..2017-06-01 | 1428 | 4 | 1428 (100%) | 1428 (100%) | 301 | 130 / 183 | 125 / 178 | 5 | 0 / 0 | 368 |
| XAU 15 | 2017-03-01..2017-03-15 | 878 | 6 | 878 (100%) | 878 (100%) | 156 | 94 / 69 | 91 / 66 | 3 | 0 / 0 | 124 |

"long / short raw" is the summed array sizes of longSrc / shortSrc.
exitL / exitS are always 0 with the defaults because every act* defaults to "enter".
`xpw.py` itself was also compared with `xpw_b.py` on all 7 cases and agrees on 100% of rows.

### Extra coverage (all at 100% of rows after the fix)

- **Non-default parameters.** 6 parameter sets on BTC 60, BTC 5, BTC 240, XAU 60 and XAU 15 (30 runs):
  - sigRung = every rung
  - sigRung = 15 Min
  - sigRung = 1 Day
  - reverseAll with enter opposite, exit only and off
  - every rung with DIV / END set to exit only and actL2 = off
  - lblRead off with scaleWin off, flatWin 15, areaLen 4, areaFrac 0.5, trendLen 10, rsiLen 10
- **Full history.** Every bar of the file for BTC D / 240 / W / M and XAU D / 240 / W / M (8 runs).
  These runs start at row 0, so they use the Pine's own initial prevPosA = "" and prevReadAt = -1.
  This group exposed the one disagreement (see below). Before the fix, BTC D full history agreed on
  only 5115 of 5432 rows.
- **Rung state.** All 7 outputs on all 9 data rungs, full series, BTC and XAU: identical after the fix.
- **2-year BTC 1m window** (1731801600..1794873600, 1,039,430 rows), defaults and every rung:
  1,039,430 of 1,039,430 rows agree.
- The implementers' own self-checks still pass after the fix:
  - `xpw_a_check.py ref`: 0 mismatches.
  - `xpw_b_check.py`: ALL REFERENCE / WARM-UP CHECKS PASSED. Its slow reference was updated to the new rule.

## Disagreements found and fixed

### 1. ta.lowest / ta.highest on `fast` while `fast` still has its leading na (B fixed)

- **Where.** In `rungState`, these calls see `fast = ta.sma(ta.rsi(close, 13), 2)`:
  - `ta.lowest(fast, h)` and `ta.highest(fast, h)`, plus their `[h]`
  - `ta.highest(fast, areaLen) - ta.lowest(fast, areaLen)` (rngShort)

  `fast` is na on the first rsiLen + fastLen - 1 = 14 bars of each rung series.
- **The two readings.**
  - B (original) ignored na inside the h-bar window. It returned a value as soon as one non-na value
    was in the window, so the value came from a partial window.
  - A returns na while the window holds an na, so it gives na until h non-na values exist.
- **Effect.** The 7 rungState outputs disagreed on the first ~2h+15 bars of every rung series:
  - BTC: M up to 2014-10, W to 2012-11, D to 2012-02, intraday rungs within the first week of 2012
  - XAU: M up to 2015-07, W to 2012-03, D to 2011-08

  Through the ladder this changed pos/orient/readAt/longSrc/shortSrc on chart bars in those years.
  No required window was affected: nothing after 2015-08 differs.
- **Pine reading.** Pine documents its na-skipping ta functions this way (ta.sma, ta.stdev):
  "na values in the source series are ignored; the function calculates on the length quantity
  of non-na values".
  - ta.highest / ta.lowest also return na until `length` bars exist on an na-free series.
  - So na is treated as a missing bar, and the result is na until h non-na values exist.

  A matches that reading. B's partial window treated "no bar yet" (na) differently from
  "bar with an na value" (value), which is inconsistent with that rule.
- **Fix.** In `xpw_b.py`, `_lowest`, `_highest` and the inline rngShort loop now use `_ext_at`.
  `_ext_at` walks back over the last n non-na values and returns na if fewer than n exist.
  The `xpw_b_check.py` reference was updated to match (`dropna().rolling(n)`), and
  `xpw_b_notes.md` item 5 was rewritten.
  - On these inputs this equals A's "na while the window holds an na": low and high have no na, and
    `fast` has leading na only. A was not changed.
  - The pre-reconciliation files are kept in `reconcile_orig/`: `xpw_b.py.orig`, `xpw_a.py.orig`
    and `xpw_b_notes.md.orig`. The original `xpw_b_check.py` reference used
    `rolling(n, min_periods=1)`.

No other disagreement appeared in any case.

## Pine points both implementations share (audited against the Pine; no change needed)

- **request.security.** Each rung's value is the last rung bar with t_close <= the chart bar's t_close
  (spec rule), and seconds rungs are always na. All 7 outputs are v6 bools or `dir`, so they are never
  na on the rung's own bars. `avail = not na(rlA[i])` therefore means "the rung has a bar".
- **ta.rsi.** Wilder RMA seeded by the SMA of the first 13 changes. The first value is at bar rsiLen.
  down == 0 gives 100 and up == 0 gives 0.
- **ta.sma.** A direct window sum, na while the window holds an na. Only `fast` and `basis` leave
  tdiCore, so `slowLen` and `bbMult` have no effect.
- **Ladder.**
  - D2 (baseDir): the first rung with okA == 1. If none has it, baseDir = +1.
  - Shape and pos: the if/else chains are copied literally. `pp` for rung 0 is "".
  - Inherited pos follows the UNREADABLE rule.
  - D1: only a rung's OWN END FIRST LEG flips the side, and only its OWN FIRST LEG resets the flip.
- **chartIdx and READ HERE.** chartIdx is the last rung with tfSec >= timeframe.in_seconds
  (120 -> 4 Hour, 60 -> 1 Hour, 15 -> 15 Min, 1 -> 1 Min). D3 runs from chartIdx down and accepts only
  an own FIRST / SECOND LEG.
- **Signal loop.**
  - active / isRead: isRead requires `not active`.
  - prev is reset to "" when readAt != prevReadAt.
  - mark: " *" takes priority over " <<".
  - `src = tfName + mark + " " + what`.
  - wasSecond is taken from the possibly-reset prev.
  - "MID SECOND LEG" and "UNAVAILABLE" changes raise no event.
  - labelAction direction and act tables, enter opposite and reverseAll, exit only on the opposite
    side, exit*Src: the last rung wins.
  - prevPosA is set for all 13 rungs every bar.
- **Labels are display only.** showLbl and the tick boxes never gate an event. The info events
  (look for / staircase) trade with actInf = "enter" by default, even though lblInfo = false hides them.
- **Agreement.** With agreeOn = false, `ok` is always true and no AGREE entry is pushed.
  agreeOn = True raises NotImplementedError.
- **Warm-up.** One chart bar before the window. This is exact: the only state carried from bar to bar
  is prevPosA, which equals the previous bar's posA, and prevReadAt, which equals the previous bar's
  readAt. Both implementers checked that 1 bar, 2000 bars and the data start give identical output.

## Timing of the canonical module

BTC chart "1", 2024-11-17..2026-11-17 (1731801600..1794873600), default params, fresh process:

| run | rows | run time | peak RSS |
|---|---|---|---|
| first run after a fresh numba compile of xpw.py | 1,039,430 | 9.2 s | 2.4 GB |
| numba cache warm (3 runs) | 1,039,430 | 7.35 / 7.43 / 7.46 s | 2.4 GB |
| sigRung = every rung, numba cache warm | 1,039,430 | 7.3 s | 2.4 GB |

Results for that window (defaults):

| quantity | value |
|---|---|
| bars with an entry label | 63,358 |
| longSrc entries | 33,071 |
| shortSrc entries | 30,287 |
| both-side cancels | 0 |
| bars with READ HERE set | 81,784 |

The run spends about 2.9 s on rungState over the full history of the 9 rung files (6.5 M bars on the
1m rung) and 0.4 s reading parquet. About 2.1 s goes to building the pandas DataFrame, mostly
converting the 26 string columns to the pandas `str` dtype. Rung states are cached per process
(`xpw._RUNG_CACHE`), so later calls in the same process are faster.

## Residuals and open issues

- **The ta.highest / ta.lowest na rule** (fix 1) is a reading of Pine's documentation. It could not
  be confirmed on TradingView. It only matters for the first ~2h+15 bars of each rung series, i.e.
  chart bars before 2015-08 (XAU) or 2014-10 (BTC).
- **Floating-point ties.** Both implementations sum SMA windows directly. TradingView's internal
  summation order (probably a running sum) can differ in the last bit. That could flip an exact tie in:
  - `fast` window comparisons
  - `close` vs `smaC`
  - `rngShort / rngLong` vs `areaFrac`

  This cannot be checked without TradingView.
- **History depth.** Rung series are computed from the first bar of each data file (BTC 2012-01,
  XAU 2011-05), as the spec requires. TradingView's feed starts elsewhere (Bitstamp 2011), and on
  intraday charts TradingView limits history. That can change the RSI seed and how long M / W rungs
  stay in warm-up. The RMA seed decays away; window warm-up is at most 2h+15 rung bars.
- **Not implemented.** Live / realtime behaviour (varip tickPx, label rollback) and AGREEMENT
  with agreeOn = true are out of scope, as the spec says.
