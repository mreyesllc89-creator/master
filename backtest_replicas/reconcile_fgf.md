# Component 1 (direction filter): reconciliation of fgf_a and fgf_b

The ground truth is the Pine block between `BEGIN FLASHGOLD DIRECTION FILTER` and `END FLASHGOLD
DIRECTION FILTER` in `/home/user/master/xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine` (lines
305-885). It is identical to `fgf_block.pine` apart from `FGF_FORCE_OVERLAY`, which only affects
display.

**Result: after one fix, `fgf_a.py` and `fgf_b.py` agree on 100% of rows, on every common column, in
every case run.** That covers the 7 required cases, a 2-year 1m window, and 164 non-default
configurations.

- **Canonical module:** `fgf.py`, a copy of `fgf_b.py` (the faster one). Only its docstring header
  differs.
- **Comparison scripts:** `reconcile_fgf_cmp.py` (`python3 -I reconcile_fgf_cmp.py [long] [extra]`)
  and `reconcile_fgf_more.py`. Every run also asserts that `fgf.py` returns a DataFrame equal to
  `fgf_b.py`'s.

## How the outputs were compared

- **Columns.** The 23 columns both implementations return:
  - The 10 required columns: `t_close, buyOk, sellOk, level, upLv, dnLv, open_, sigDir, newSig, band`.
  - 13 diagnostic columns: `zone, sigOk, armed, expired, sigId, sigAt, sigBar, idx, value, sigAtr,
    par, al, ac`.
  - Only fgf_a has `t_open`, `sel`, `fEnd` and `endBar`, so those are not compared.
- **Equality test.** Values are cast to float64. Two cells match when they are exactly equal or both
  na. There is no tolerance.
- **Index.** The two indexes (chart-file row numbers) are asserted equal.

## Agreement table (default params)

| Case | Window (t_close, epoch s) | Rows | Common cols | Cells compared | Mismatching cells | newSig | buyOk | sellOk |
|---|---|---|---|---|---|---|---|---|
| BTC chart "60" | 1735689600..1740787200 | 1,417 | 23 | 32,591 | 0 | 306 | 627 | 584 |
| BTC chart "5" | 1735689600..1736899200 | 4,031 | 23 | 92,713 | 0 | 65 | 1821 | 1475 |
| BTC chart "240" | 1731801600..1763337600 | 2,191 | 23 | 50,393 | 0 | 1350 | 949 | 877 |
| BTC chart "1" | 1738368000..1738972800 | 10,021 | 23 | 230,483 | 0 | 45 | 4569 | 3884 |
| BTC chart "120" | 1748736000..1756684800 (2025-06-01..2025-09-01) | 1,105 | 23 | 25,415 | 0 | 413 | 445 | 445 |
| XAU chart "60" | 1488326400..1496275200 (2017-03-01..2017-06-01) | 1,428 | 23 | 32,844 | 0 | 287 | 654 | 534 |
| XAU chart "15" | 1488326400..1489536000 (2017-03-01..2017-03-15) | 878 | 23 | 20,194 | 0 | 48 | 342 | 310 |
| BTC chart "1" (timing window) | 1731801600..1794873600 | 1,039,430 | 23 | 23,906,890 | 0 | 3800 | 417969 | 393349 |

The defaults agreed on the first run, before any fix.

## Non-default configurations

All of these give 0 mismatching cells after fix R1.

### `reconcile_fgf_cmp.py extra`: 80 configurations

These are 20 parameter sets, each run on BTC 60, BTC 5, BTC 240 and XAU 60:

- **Check price on:** Candle open; Candle close.
- **Permission lasts:** Minutes 90; Candles 3; Candles 1 + Candle open; Minutes 45 + Candle open.
- **Band and level:** band 0 + Signal close; band 0 + against the signal off.
- **Sides:** buys off.
- **Signal:**
  - Hold bars 2 + drift + any combo.
  - Points unit.
- **Zones:**
  - Flat parent + min aligned 3.
  - HtfClosed off.
  - A 30S zone with IgnoreNa off.
  - Zones 4 ("480", built from 1m) and 6 ("2") on.
  - Trade-zone filter off + RSI 10 / fast 3.
- **Filter timeframe:** filter 240; filter 15 with zones on 15/60/D; `fgfTf=""`.
- **Filter off.**

### `reconcile_fgf_more.py`: 72 configurations

These are 9 parameter sets on XAU 5 / 240 / D / 1 and BTC D / W / 30 / 15:

- Defaults.
- Candle open.
- Candles 2 + Candle open.
- Minutes 120 + Candle open.
- Candles 2.
- Filter 240 + Candle open + Candles 1.
- Filter 5 with zones on 5/15/60.
- W and M zones.
- Band 0 + Signal close + Candle open.

These charts cover the cases where the chart bar is longer than the filter bar (`fgfSel == 0`), XAU
session gaps, and D / W charts.

### `reconcile_fgf_more.py`: 12 empty-timeframe configurations

Parent or zone timeframe set to `""` ("Chart"), on BTC 5, BTC 240 and XAU 60. These found the only
disagreement (fix R1).

## Fixes

### R1: an empty ("Chart") parent or zone timeframe inside the nested request (fgf_a fixed)

- **Disagreement.** When `fgfParentTf` or `fgfZTfN` is `""` and the filter timeframe differs from the
  chart's, the two implementations disagreed. Before the fix, for example:

  | Case | Rows with a different `buyOk` | Rows with a different `sellOk` | Rows with a different `level` |
  |---|---|---|---|
  | BTC 5, `fgfParentTf=""` | 913 | 804 | 1873 |
  | BTC 240, `fgfZTf2=""` | 840 | 824 | 1213 |

  XAU 60 agreed, because there chart = filter.
- **Pine lines.**
  - `fgfSignal()` calls `request.security(syminfo.tickerid, fgfParentTf, fgfTdiDir(), ...)` and
    `fgfZoneDir(fgfZTfN, ctxSec)`.
  - `fgfZoneDir` calls `request.security(syminfo.tickerid, tf, ...)` and
    `timeframe.in_seconds(tf) > ctxSec`.
  - All of these run inside `fgfRead()`, which is itself evaluated by
    `request.security(syminfo.tickerid, fgfTfEff, fgfRead(), ...)`.
- **Pine semantics.**
  - In Pine, a `""` timeframe means the timeframe of the *current context*, i.e. `timeframe.period`.
  - Inside a request.security call, the current context is the requested one: nested requests run in
    the outer request's context, and `timeframe.period` there is the requested timeframe.
  - So inside `fgfRead()`, a `""` parent or zone timeframe is the **filter timeframe**, not the chart's.
  - Likewise, `timeframe.in_seconds("")` is the filter timeframe's seconds (= `ctxSec`), so such a zone
    is never "higher" and uses `dNow`, which is the filter bar itself.
- **Which one was wrong.**
  - fgf_a resolved `""` to the chart timeframe for the parent and zones as well.
  - fgf_b resolved it to the filter (context) timeframe, which matches the Pine.
- **Fix.** In `fgf_a.py`, `_resolve_tf(tf, ctx_tf)` is now called with `tf_eff` (the filter timeframe)
  for the parent and the zones. `fgfTf` still resolves to the chart. `fgf_a_notes.md` item 8 was
  updated, and fgf_a's own reference check (`fgf_a_check.py ref`, 36 configurations) still passes.
- **Spec vs Pine.** SPEC.md says timeframe strings are "as in Pine (... "" = chart)". That holds for
  `fgfTf`, which is the outer call. For the parent and zone inputs evaluated inside the filter
  request, the Pine's context rule makes `""` the filter timeframe. Following the spec's own rule (the
  Pine wins), the Pine reading is used.
- **Impact.** This reading cannot be checked without TradingView. It never matters with the default
  inputs (parent and zones "60" / "120" / "240" ...).

### Non-functional edit to fgf_b.py

This edit makes `fgf.py` a true copy of `fgf_b.py`.

- **Change.** The `__main__` block imported `fgf_b` by name, and the self-check wrote
  `out/fgf_b_BTC_60.parquet` under a hard-coded name. Both now use `_MODNAME`, which is derived from the
  file name.
- **Effect on results.** None. `fgf.py`'s self-check writes `out/fgf_BTC_60.parquet`, and that file is
  equal to `out/fgf_b_BTC_60.parquet` (checked with `DataFrame.equals`).

## Shared readings reviewed against the Pine

Both implementations agree on all of these.

- **History.** `barstate.isconfirmed` is true on every historical bar. So "Candle close" equals "Tick",
  the clock is `time_close`, and the live / `timenow` branches are dead.
- **Outer request (`lookahead_off`).** Each chart bar reads the last filter bar with `t_close <=` the
  chart bar's `t_close`. `fq` is the filter bar before it. `fpIdx` is the filter row number; only
  differences of it are used.
- **Parent and same-or-lower zones (`dNow`, `lookahead_off`).** These are mapped onto the filter bars
  by the same last-closed rule.
- **Higher zones with HtfClosed on.** `dPrev` is `fgfTdiDirPrev()` with `lookahead_on`: the `d[1]` of
  the zone bar that contains the filter bar's open (SPEC wording). It stays fixed for the whole zone
  bar, and it is na when the containing bar is the zone series' first bar.
- **Indicators.**
  - `ta.rsi` is a Wilder RMA seeded by the SMA of bars 1..len, giving 100 when the down average is 0
    and 0 when the up average is 0.
  - `ta.atr`: TR[0] = high - low, then the RMA.
  - `fgfTdiDir` is 0 while `f` or `f[1]` is na.
- **Signal state machine.**
  - `canFire` is evaluated once, before both branches.
  - If both sides fire on one bar, the buy takes priority in `signalPx` and `aDir`.
  - The hold reset runs after both branches.
- **Arm.** The level is `nz(sPx, close)` and is not tick-rounded. The band edges use `ceil`/`floor`
  with 1e-9, and the comparison uses ±mintick/2.
- **Time units.** `fgfMinutes * 60000` ms becomes `* 60` s.
- **Pick logic.** `fgfSel` covers all three cases, including the previous chart bar's close-time pick
  when `fgfSel == 0`.

## Canonical module and timing

- **Choice.** `fgf.py` is a copy of `fgf_b.py`.
- **Interface.** `fgf_permissions(pair, chart_tf, start, end, params=None) -> DataFrame`, the same as
  both implementations.
- **Why fgf_b.** Measured in fresh processes with a warm numba cache:

  | Measure | fgf_b | fgf_a |
  |---|---|---|
  | 2-year BTC 1m, first call | 1.03-1.06 s | 1.41-1.53 s |
  | 2-year BTC 1m, repeat call | 0.40 s | 0.85-0.88 s |
  | Peak RSS | 1.73 GB | 2.1 GB |

**Timing of `fgf.py`** on BTC chart "1", window 1731801600..1794873600 (2024-11-17..2026-11-17),
default params:

| Run | First call | Later calls (same process) | Whole process |
|---|---|---|---|
| Warm numba cache, fresh process, run 1 | 1.25 s | 0.38 / 0.33 s | 2.46 s (import 0.48 s) |
| Warm numba cache, fresh process, run 2 | 1.05 s | 0.48 / 0.39 s | 2.48 s |
| Cold numba cache (empty `NUMBA_CACHE_DIR`) | 2.63 s | 0.39 / 0.36 s | 3.89 s |

- **Output of the 2-year run.** 1,039,430 rows: 3800 newSig, 417,969 buyOk, 393,349 sellOk, 228,112
  with neither.
- **Peak RSS** is about 1.76 GB, mostly the 1m parquet read.
- The first call includes reading the 1m file and computing the 60 / 120 / 240 series. Later calls
  reuse the cached bars and filter series.

## Residuals (not disagreements)

1. **TDI float ties.** TradingView's internal summation order for `ta.sma` and the RMA seed is not
   known. Both implementations use the documented formulas operation by operation, so they agree with
   each other.
   - **Pine-documentation order** (`sum += x[i]/len`, newest first): the direction flips on 1 BTC 60
     bar (2012) and on no other bar of any 1 / 5 / 60 / 120 / 240 series, for either pair.
   - **Running-sum SMA:**

     | Series | Flipped bars | Years |
     |---|---|---|
     | BTC 60 | 99 | 2012-2016, plus 1 in 2022 |
     | BTC 120 | 29 | 2012-2016 |
     | BTC 240 | 10 | 2012 |
     | XAU 60 / 120 / 240 | 0 | |
     | BTC 1 | 48,974 | all years |
     | BTC 5 | 4,076 | all years |
     | XAU 1 | 2,447 | |
     | XAU 5 | 51 | |

   - **Impact.** With the default 60 / 120 / 240 setup, no flipped bar falls inside any test window.
     A 1m or 5m filter, parent or zone timeframe (non-default) is sensitive to this.
2. **Fix R1** rests on Pine's documented nested-context rule. It was not verified on TradingView.
3. **Timeframe strings `input.timeframe` never produces.** These were not reconciled:
   - `"1H"`: fgf_b accepts it as 60 minutes; fgf_a rejects it.
   - `"1440"`: fgf_a maps it to "D"; fgf_b builds it from 1m bars, which gives the same bars.
4. **Live-bar paths** (`timenow`, `close[1]` of a forming bar, `fgfDOpen`) are not implemented. This
   is history only, as the spec says.
