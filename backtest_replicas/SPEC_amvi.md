# SPEC_amvi: AMVI Full MTF Strategy + FGF [Update 1] (key `amvi`), stage 1 brief

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Read first: `$W/REPLICA_SPEC.md` (stages, interface, data, windows, cost modes), `$W/SPEC_AH.md` (Pine
built-ins, the intrabar path = "rule 4"), `$W/SWEEP_AH_SPEC.md` section 2 (prepare / simulate, 'mag',
'stress', fair halves, the trailing exit), `$W/fgf.py` (docstring, `fgf_permissions`, `_atr`, `_bars`,
`tf_seconds`, `_take`) with `$W/reconcile_fgf.md`, and `$W/hrd.py` as the worked example of the broker
(`_walk`, `summary_fast`, `extra_fields`, `sub_bars`, `COSTS`).

Ground truth: `/home/user/master/AMVI_Full_MTF_Strategy_FGF.pine` at HEAD (894 lines; `Lnnn` below are its
line numbers). The unfused original is `/home/user/master/AMVI_Full_MTF_Strategy.pine` (262 lines; `Onnn`
are ITS line numbers). Where this brief and the Pine disagree, the Pine wins; say so in your notes. Builders
write `$W/amvi_a.py` / `$W/amvi_b.py` and `$W/amvi_<a|b>_notes.md`, without reading the other build. Never
edit an existing module. Never write inside `/home/user/master`. `python3 -I`, at most 2 processes, under
3 GB each.

The stage-1 probes are in `$W/amvi_spec_tmp/` (`probe_lib.py`, `probe_trig.py`, `probe_dims.py`,
`probe_filter.py`, `probe_misc.py`, `probe_time.py`). **Builders must NOT read them** (they would make the two builds share
their mistakes). Their numbers are quoted below as "probe, unverified": one implementation, no cross-check.
If your two builds agree with each other and not with a probe number, trust the builds and say so.

Nine facts shape everything below:

1. **The trigger has no direction.** AMVI measures volatility on up to 12 timeframes; a trigger is "one
   enabled timeframe crosses above High Vol while at least N are above it". The direction comes only from
   the filter: `fgfBuyOk and not fgfSellOk` = long, the reverse = short, neither = no trade (L777-778).
   The strategy reads three things of the filter block and nothing else: the input `fgfOn` and the two
   gates. `fgf.py` returns both (`buyOk`, `sellOk`). **No filter series is missing; nothing of the filter is
   reimplemented.**
2. **With the filter off the fused file places no order** (`amviDirUp` / `amviDirDn` start with `fgfOn
   and`; the header says so). So REPLICA_SPEC's "`fgfOn` False reproduces the original" cannot hold
   literally. The replica therefore has a replica-only parameter `dirSource`: 'fgf' (default = the fused
   file) or 'orig' (= the unfused original's direction code, O143-163: EMA / candle / Donchian, `tradeDir`,
   `allowReverse`). Everything outside the direction lines is byte-identical in the two files (checked with
   `diff`: calculation, MTF requests, crosses, trigger, exits, sizing). **"Filter off" in the runner and in
   the calibration means `dirSource='orig'`**, not `fgfOn=False`.
3. **`inv` IS the script's own input `amviTradeDir == "Inverted"`** (L108, L779), older than Update 1.
   Update 1 changed the `strategy()` title line and header comments only (checked with `git diff 6c59b9f
   HEAD`: one code line, the title). Section 8 says exactly what the Pine does with it.
4. **Every request is read "as of the chart bar's OPEN"** (`noRepaint` true, the default:
   `request.security(tf, calc_amvi()[1], lookahead_on)`). One rule covers higher, equal and lower
   timeframes (section 4.2). So a trigger seen at the close of bar j uses volatility known at the close of
   bar j-1, the filter gate of bar j's close, and fills at the open of bar j+1.
5. **Seconds timeframes are on by default (five of the twelve toggles) and cannot be reproduced**: no data
   below 1 minute. In the replica their values are na, which is exactly what the script does with a
   disabled timeframe (`on ? v : na`): the replica reproduces the Pine run with `en1s = en5s = en15s =
   en30s = en45s = false`.
6. **Orders are market orders placed at a bar close and filled at the next open**
   (`process_orders_on_close` not set). The bracket is sent with the entry at ABSOLUTE prices measured from
   the SIGNAL bar's close, and re-sent on every later bar measured from the real average entry price. So
   the fill bar has one pair of levels and every later bar another (section 6.2).
7. **One script run per bar** (`calc_on_every_tick`, `calc_on_order_fills` not set = false). No extra-run
   question.
8. **`strategy()` charges 0.04 % per fill and 1 tick of slippage**: with cost 'tv' fill PRICES move (market
   and stop fills, not limit fills), as in `danny.py`.
9. **Few trades.** Defaults give 59 triggers (XAU 240) to 1,523 (BTC 1) in the whole window, and 49 to
   1,124 trades (probe). One `simulate` is cheap; `prepare` is the cost.

---------------------------------------------------------------------------------------------------

## 1. What the file is made of

| part | lines | replica |
|---|---|---|
| `strategy()` | 2-4 | section 2 |
| header (Update 1 text, FGF build notes) | 6-67 | read it; its statements are tests (section 8) |
| inputs of the strategy | 70-130 | section 3 |
| colours | 133-134 | ignored |
| FlashGold Direction Filter block | 136-716 | `$W/fgf.py`, never reimplemented. Checked with `diff`: identical to the block of `FlashGold_Direction_Filter_v1_2.pine` and to the block `fgf.py` replicates (trailing-TP XPW file) except the `FGF_FORCE_OVERLAY` line (drawing). Every input default equals `fgf.DEFAULTS`, `fgfOn = true` included (L142) |
| `normalize`, `calc_amvi`, `get_mtf`, the 12 requests | 719-741 | `prepare`, sections 4.1-4.2 |
| crosses | 744-747 | `prepare`, 4.3 |
| `ta.valuewhen`, `no_stairs` | 750-755 | drawing only |
| `hot` / `val` / `cnt`, counts, `avgAmvi`, `trigger` | 760-770 | `prepare`, 4.3 |
| direction, `amviInv`, `goLong` / `goShort` | 776-783 | `prepare` (zones) + `simulate` (swap, position test), 4.4 and 7 |
| FGD Data Window plots | 786-795 | summary counters (section 12) |
| `atrX`, `entryAtr`, entries | 797-805 | `simulate`, section 7 |
| trail ticks, brackets | 808-826 | `simulate`, sections 6-7 |
| volatility collapse, time stop | 829-835 | `simulate`, section 7 |
| plots | 842-894 | ignored |

`request.security` calls of the whole file (26): the twelve `get_mtf` requests, timeframes **"1S", "5S",
"15S", "30S", "45S", "1", "5", "15", "30", "60", "240", "D"** (a disabled one requests `timeframe.period`
and its result is discarded); the filter's outer request on `fgfTfEff` (default "60"); inside it the parent
(`fgfParentTf`, "60") and two requests per child zone (`fgfZTf1..6`: "60", "120", "240", "480", "1", "2";
zones 4-6 are off by default, their requests are still made and their values unused). The filter's are
inside `fgf.py`.

The unfused original, outside the identical code: inputs `tradeDir` (O53), `dirMode` (O55), `emaLen` (O56),
`dcLen` (O57), `allowReverse` (O58); `minConfluence` and the date range sit in another input group (same
defaults); the bias lines O144-154 and the signal lines O156-163. No filter block, no `amviTradeDir`.

---------------------------------------------------------------------------------------------------

## 2. The `strategy()` call (L2-4)

```
strategy("Adaptive Market Volatility Indicator (AMVI) - Full MTF Strategy [Update 1]",
  shorttitle="AMVI Full+ Strat U1", overlay=false, precision=2, initial_capital=10000,
  default_qty_type=strategy.percent_of_equity, default_qty_value=10,
  commission_type=strategy.commission.percent, commission_value=0.04, slippage=1, pyramiding=0)
```

| argument | meaning for the replica |
|---|---|
| `initial_capital=10000` | `INITIAL_CAPITAL = 10000.0` (not the 1,000,000 of SPEC_AH rule 7) |
| `default_qty_type=percent_of_equity`, `default_qty_value=10` | no `strategy.entry` passes `qty`: every entry is 10 % of `strategy.equity`, converted at the close of the bar that places the order: `qty = 0.10 * equity / close` (A6, section 9) |
| `commission_type=percent`, `commission_value=0.04` | cost 'tv': 0.04 % of the fill value on every fill (entry and exit) |
| `slippage=1` | cost 'tv': 1 tick = 0.01 in price, against the order, on every MARKET fill and every STOP fill (stop loss, trailing stop); LIMIT fills (the target) get none. Section 9 |
| `pyramiding=0` | one entry per side. The script never sends a same-side entry while in a position (`goLong` needs `position_size <= 0`). An opposite `strategy.entry` that fills while a position is open closes it and opens the new one (reversal, A9) |
| not set: `process_orders_on_close` | false: a market order placed in the run of bar i fills at the OPEN of bar i+1 (SPEC_AH rule 1) |
| not set: `calc_on_every_tick`, `calc_on_order_fills` | false: one run per bar at its close; no extra run after a fill |
| not set: `margin_long`, `margin_short` | Pine v6 default 100 %. A 10 % position never needs more: not modelled, cannot bind |
| not set: `close_entries_rule`, `backtest_fill_limits_assumption`, `use_bar_magnifier` | FIFO (irrelevant, one trade at a time); 0 (a limit fills on touch); false = path 'tv' (path 'mag', stage 3, = Bar Magnifier on) |
| `overlay`, `precision`, titles | drawing: ignored |

Symbol constants: `syminfo.mintick = 0.01`, `syminfo.pointvalue = 1`, both pairs. `time` = `t_open` (the
replica keeps seconds). `bar_index` = the row number in the data file; only differences are used.

---------------------------------------------------------------------------------------------------

## 3. Inputs

### 3.1 SIGNAL inputs -> `prepare(pair, chart_tf, params)` (per-bar arrays; nothing here depends on a position)

| Pine name (line) | default | used for |
|---|---|---|
| `fastATRPeriod`, `slowATRPeriod` (70-71) | 14, 50 | `calc_amvi`: ATR normalisation and the ATR ratio |
| `stdDevPeriod`, `candleRangePeriod` (72-73) | 20, 10 | `calc_amvi`: `ta.stdev(close)`, `ta.sma(high - low)` |
| `normalizationPeriod` (74) | 200 | the min-max window of the three normalised parts |
| `noRepaint` (75) | true | which bar of each requested timeframe is read (section 4.2) |
| `aatrWeight`, `vrWeight`, `nsdWeight`, `acrWeight` (78-81) | 0.35, 0.25, 0.25, 0.15 | the weighted sum (each in [0, 1]) |
| `highVolThreshold` (83) | 70.0 | crosses and `hot` |
| `minConfluence` (85) | 3 | `trigger` (1..12) |
| `en1`, `en5`, `en15`, `en30`, `en60`, `en240`, `enD` (94-100) | all true | the seven timeframes that have data |
| `useDateRange`, `startTime`, `endTime` (103-105) | false, 1577836800, 4102358400 | `inRange`. `timestamp("2020-01-01T00:00:00")` / `("2099-12-31T00:00:00")` are UTC (A17); the replica takes epoch SECONDS and compares with `t_open`. Default off. Note: with it on and the default dates the gold window (2017-2018) has no trade |
| `fgfOn` (142) and every other trading input of the filter block (143-152, 166-203) | `fgf.DEFAULTS` (`fgfOn` **true**) | `dirSource` 'fgf': passed unchanged to `fgf.fgf_permissions`; `fgfOn` False = no direction, no trade |
| replica: `dirSource` | 'fgf' | 'fgf' = the fused file; 'orig' = the unfused original's direction (fact 2) |
| original only: `dirMode` (O55), `emaLen` (O56), `dcLen` (O57) | "Trend (EMA)", 50, 20 | `dirSource` 'orig': `upBias` / `dnBias`. Options exactly "Trend (EMA)", "Candle", "Breakout (Donchian)" |
| replica: `ltfRule` | 'first' | A2: 'first' or 'last' (sensitivity control for the lower-timeframe requests) |
| replica: `start`, `end` | the pair's window | window by `t_close`, as `hrd._window` |

### 3.2 ORDER / EXIT inputs -> `simulate(P, x)` (also accepted by `run` in one dict)

| Pine name (line) | default | used for |
|---|---|---|
| `amviTradeDir` (108), alias `inv` | "Follow the filter" (`inv` False) | "Inverted" = `inv` True (section 8). Raise if both are given and disagree |
| `exitAtrLen` (112) | 14 | `atrX = ta.atr(exitAtrLen)` of the CHART: an ATR cache per length in `P` (from row 0 of the file, on demand) |
| `slMult` (113) | 1.5 | stop distance = `slMult x entryAtr`; 0 = no stop |
| `tpMult` (114) | 3.0 | target distance = `tpMult x entryAtr`; 0 = no target |
| `useTrail` (115) | false | trailing stop in the same `strategy.exit` |
| `trailActMul`, `trailOffMul` (116-117) | 1.5, 1.0 | `trail_points` / `trail_offset` in ticks (section 7, C2) |
| `useVolExit` (118) | true | `strategy.close_all` on `volCollapse` |
| `lowVolThreshold` (84) | 30.0 | only use: `volCollapse = ta.crossunder(avgAmvi, lowVolThreshold)`. Computed by `simulate` from `P['avgAmvi']` (a cache per value inside `P` is fine); `P`'s signal arrays do not depend on it |
| `maxBars` (119) | 0 | time stop, bars; 0 = off |
| original only: `tradeDir` (O53), `allowReverse` (O58) | "Both", true | only with `dirSource` 'orig'. With 'fgf' they must be at these defaults (else `ValueError`: the fused file has no such inputs) |
| replica: `revClose` | 'void' | A11: 'void' or 'closes' |
| replica: `path` | 'tv' | 'tv'; 'mag' raises `NotImplementedError` until stage 3 |
| replica: `cost` | 'tv' | 'tv' / 'ours' / 'stress' (section 9) |

`simulate` raises if `x` holds a 3.1 key that differs from `P`'s (as `hrd.simulate`). Validate as the Pine
inputs do: option strings exactly as written; periods and `exitAtrLen` integers `>= 1`; weights in [0, 1];
`minConfluence` an integer in 1..12; `slMult`, `tpMult`, `trailActMul`, `trailOffMul` `>= 0`; `maxBars` an
integer `>= 0`; `emaLen`, `dcLen` integers `>= 1`. Any unknown key: `ValueError`.

### 3.3 Accepted, no effect in the replica (say so in the notes)

`en1s`, `en5s`, `en15s`, `en30s`, `en45s` (L89-93, all **true** in the Pine): the seconds timeframes. No data:
their values are na on every bar, which is identical to switching them off. Keep the Pine defaults in
`DEFAULTS`, ignore them, and report `seconds_ignored` (how many of the five were left true) in the summary.
Section 11 says what TradingView does instead.

### 3.4 Drawing only: listed once, ignored

`showOverlay`, `showLabels`, `showLevels`, `showL1s` .. `showLD` (L122-130); the colours; `fgfShowBg`,
`fgfShowLv`, `fgfSigMark`, `fgfShowTbl`, `fgfTblPos`, `fgsShow`, `fgsWin`, `fgsH`, `FGF_FORCE_OVERLAY`;
`ta.valuewhen` / `no_stairs` (L750-755) and every `plot`, `plotshape`, `plotchar`, `hline`, `bgcolor`; the
order comments ("AMVI L nTF", "L SL", "L TP", "L Trail", "Vol Collapse", "Time Stop": they become the exit
kinds of section 12 and the `hot` column). There are no alerts.

---------------------------------------------------------------------------------------------------

## 4. `prepare`: AMVI per timeframe, the requests, the trigger, the direction

Window rows of `$W/data/<PAIR>_<TF>.parquet`: `w0 = searchsorted(t_close, start, 'left')`, `w1 =
searchsorted(t_close, end, 'right')`, `n = w1 - w0`, window bar `j` = file row `w0 + j`. Every series is
computed from row 0 of its own file (warm-up); every file starts in 2011 / 2012, years before the windows, so
no AMVI value is na inside a window (assert it for the enabled timeframes).

### 4.1 `calc_amvi()` on ONE timeframe's own bars (L719-729)

On the bars of `$W/data/<PAIR>_<T>.parquet`, `T` in "1", "5", "15", "30", "60", "240", "D", float64, in this
operation order:

```
fATR = fgf._atr(high, low, close, fastATRPeriod)            # ta.atr = rma(tr(true)); na before row len-1
sATR = fgf._atr(high, low, close, slowATRPeriod)
vr   = min(2.0, max(0.5, fATR / sATR))  if sATR > 0  else 1.0     # sATR na or 0 -> 1.0; sATR > 0 and fATR na -> na
nVR  = (vr - 0.5) / 1.5
sd   = stdev(close, stdDevPeriod)                           # population: m = (sum of the window, oldest first) / len;
                                                            # sqrt((sum of (x - m)^2, oldest first) / len); na before row len-1
cr   = sma(high - low, candleRangePeriod)                   # (sum of the window, oldest first) / len; na before row len-1
nATR = normalize(fATR, normalizationPeriod) ; nSD = normalize(sd, ...) ; nCR = normalize(cr, ...)
amvi = (aatrWeight * nATR + vrWeight * nVR + nsdWeight * nSD + acrWeight * nCR) * 100.0      # left to right

normalize(x, L)[i]:  na if i < L - 1 or any of x[i-L+1 .. i] is na (A4)
                     lo = min, hi = max of x[i-L+1 .. i] (the current bar included)
                     0.0 if hi <= lo else (x[i] - lo) / (hi - lo)
```

`min` / `max` must propagate na (use `np.minimum` / `np.maximum`, not Python's). Call `fgf._atr`; do not
rewrite it. The window min / max may use any exact algorithm; the sums must be in the stated order so that
the two builds agree to the last bit (the result is compared with thresholds). With the default weights
(sum 1.0) `amvi` lies in [0, 100].

Cache the four normalised parts per `(pair, T, fastATRPeriod, slowATRPeriod, stdDevPeriod,
candleRangePeriod, normalizationPeriod)`: this is the only heavy step (BTC "1": 6.5 M rows; about 200 MB
per period set, so keep one set at a time on BTC "1"). First `prepare` of a pair: 5 to 20 s (probe: BTC "1"
17 s with a peak of 1.9 GB; a further trigger setting on BTC "1" about 0.15 s).

### 4.2 The twelve requests (L733-741): one rule

`get_mtf(tf, on)` = `request.security(syminfo.tickerid, on ? tf : timeframe.period,
calc_amvi()[noRepaint ? 1 : 0], gaps_off, lookahead = noRepaint ? lookahead_on : lookahead_off)`, then `on ?
v : na`. For chart file rows `r = w0 - 1 .. w1 - 1` (one row more than the window, for the `[1]` of the
crosses and of `avgAmvi`) and each timeframe `T` with data whose toggle is on:

```
Tref   = t_open[r]  if noRepaint  else t_close[r]
k      = searchsorted(T.t_close, Tref, side='right') - 1          # the last T bar closed by Tref
v_T[r] = amvi_T[k]    (na if k < 0)
```

A disabled timeframe and the five seconds timeframes: `v_T` = na on every row.

Why one rule (`noRepaint` true, `expr[1]` with lookahead on; A2):
- `T` HIGHER than the chart: the T bar that contains the chart bar, then its previous bar (SPEC_AH's
  rule) = the last T bar closed by the chart bar's open.
- `T` EQUAL to the chart: the chart's own series, `[1]` = the previous chart bar = the same rule.
- `T` LOWER than the chart: on history `request.security` with lookahead on returns the FIRST intrabar of
  the chart bar (with lookahead off the last one); `[1]` of the first intrabar is the last intrabar of the
  previous chart bar = the same rule.
- `noRepaint` false (`expr[0]`, lookahead off): the last T bar with `t_close <=` the chart bar's close, for
  every `T` (SPEC.md's rule). Identity to check: `v_off[r] == v_on[r + 1]` for every `T` and row.

Replica control `ltfRule = 'last'` (only with `noRepaint` true, only for `T` lower than the chart:
`fgf.tf_seconds(T) < fgf.tf_seconds(chart)`): `k = searchsorted(T.t_close, t_close[r], 'right') - 2`, i.e.
`[1]` of the LAST intrabar of the chart bar. It is what a live bar does (section 11) and the other possible
reading of history. It moves every lower-timeframe value one chart bar earlier: on XAU 240 the default
setting has 59 trigger bars with 'first', 40 with 'last', 10 on the same bar (probe). Default 'first'.

### 4.3 Crosses, counts, trigger (L744-747, 760-770)

`H = highVolThreshold`. On window rows (`[1]` = the previous file row), na compares false:

```
x_T      = v_T > H and v_T[1] <= H                      # ta.crossover(v_T, H)
hotCount = number of T with v_T not na and v_T > H
enCount  = number of T with v_T not na                   # NOT the number of toggles that are on
amviSum  = 0.0 + v_1 + v_5 + v_15 + v_30 + v_60 + v_240 + v_D     (na counts 0.0; this order)
avgAmvi  = amviSum / enCount  if enCount > 0  else na
anyCross = any x_T
trigger  = anyCross and hotCount >= minConfluence
inRange  = not useDateRange or (startTime <= t_open and t_open <= endTime)
```

`avgAmvi` is kept for rows `w0 - 1 .. w1 - 1` (the crossunder of the first window bar needs the row before).
`volCollapse[j] = avgAmvi[j] < lowVolThreshold and avgAmvi[j-1] >= lowVolThreshold` (L829; na -> false).

To know: with `noRepaint` true a higher timeframe's value changes on the first chart bar of each of its
bars, the chart's own timeframe is one bar late, and on a chart above 1 minute the lower timeframes are
sampled once per chart bar: a cross is "above H now, at or below it one chart bar ago", whatever happened
in between.

### 4.4 Direction

`dirSource` 'fgf' (L776-778), `fgfOn` true:

    F = fgf.fgf_permissions(pair, chart_tf, start, end, fgf_params)
    assert F.index[0] == w0 and len(F) == n
    dirUp = buyOk and not sellOk          # amviDirUp
    dirDn = sellOk and not buyOk          # amviDirDn

With the filter on `buyOk` and `sellOk` are never both true (assert it), so `dirUp = buyOk`, `dirDn =
sellOk`; write the literal expression anyway. `fgfOn` false: do NOT call `fgf`; `dirUp = dirDn =` all
False. History: `fgfCheck` "Tick" judges the chart bar's close.

`dirSource` 'orig' (O144-154), on the chart file from row 0:

```
ema  = ta.ema(close, emaLen):  ema[0] = close[0];  ema[i] = a * close[i] + (1 - a) * ema[i-1],  a = 2.0 / (emaLen + 1)
dcHi = highest(high, dcLen)[1] ;  dcLo = lowest(low, dcLen)[1]         # the dcLen bars BEFORE this one; na while short
"Trend (EMA)":           dirUp = close > ema ;   dirDn = close < ema
"Candle":                dirUp = close > open ;  dirDn = close < open
"Breakout (Donchian)":   dirUp = close > dcHi ;  dirDn = close < dcLo
```

Both sources, then: `trigUp = trigger and inRange and dirUp`, `trigDn = trigger and inRange and dirDn`
(never both true: assert). These are the NORMAL-frame signals; `inv`, `tradeDir` and the position test are
applied in `simulate`.

### 4.5 What `P` holds

`pair`, `tf`, `start`, `end`, `mid = start + (end - start) // 2`, `mid_j = searchsorted(t_close_window, mid,
'right') - 1`, `w0`, `w1`, `n`, window arrays `open high low close t_open t_close`, `trigger`, `inRange`,
`dirUp`, `dirDn`, `trigUp`, `trigDn`, `hotCount`, `avgAmvi` (n + 1 values), the ATR cache per `exitAtrLen`,
the resolved `prepare` parameters, and the counts `triggers = sum(trigger and inRange)`, `trig_up`,
`trig_dn`, `trig_none = triggers - trig_up - trig_dn` (the four "FGD" Data Window rows, L786-795). Nothing
in `P` may depend on a 3.2 input. Layer the caches: normalised parts (4.1) -> `v_T` on the chart per
(weights, `noRepaint`, `ltfRule`) -> crosses and counts per (`highVolThreshold`, the enabled set) ->
`trigger` per `minConfluence` -> direction per filter setting (`fgf` caches its own filter series), so that
a calibration pass of about 500 `prepare` settings per cell costs seconds, not minutes.

Reference counts, default inputs, full windows (probe, unverified):

| cell | window bars | triggers | BUY ZONE / SELL ZONE / no direction ('fgf') | up / down ('orig', EMA 50) |
|---|---|---|---|---|
| BTC 1 | 1,039,430 | 1,523 | 592 / 658 / 273 | 703 / 820 |
| BTC 5 | 210,155 | 1,219 | 502 / 517 / 200 | 538 / 681 |
| BTC 15 | 70,058 | 931 | 411 / 377 / 143 | 394 / 537 |
| BTC 30 | 35,032 | 628 | 270 / 244 / 114 | 248 / 380 |
| BTC 60 | 17,518 | 441 | 188 / 181 / 72 | 182 / 259 |
| BTC 120 | 8,760 | 285 | 131 / 119 / 35 | 120 / 165 |
| BTC 240 | 4,381 | 167 | 83 / 61 / 23 | 68 / 99 |
| XAU 1 | 493,819 | 428 | 168 / 199 / 61 | 206 / 222 |
| XAU 5 | 98,787 | 369 | 143 / 181 / 45 | 182 / 187 |
| XAU 15 | 32,935 | 291 | 134 / 134 / 23 | 154 / 137 |
| XAU 30 | 16,471 | 193 | 76 / 87 / 30 | 108 / 85 |
| XAU 60 | 8,238 | 128 | 53 / 56 / 19 | 71 / 57 |
| XAU 120 | 4,493 | 83 | 32 / 38 / 13 | 51 / 32 |
| XAU 240 | 2,246 | 59 | 26 / 29 / 4 | 39 / 20 |

(`anyCross` alone is 5 to 14 times more frequent: 474 bars on XAU 240, 11,428 on BTC 1. `volCollapse` at 30:
354 bars on XAU 240, 1,364 on BTC 60, 7,214 on BTC 1. The median `avgAmvi` is about 33 in every cell.)

---------------------------------------------------------------------------------------------------

## 5. How TradingView runs this script on history

History bars: the script runs once per bar at its close (`barstate.isconfirmed` true), nothing else. Orders
of that run are processed from the next bar on. Per window bar `j`:

    A. fills at the open of j        (the orders the run of j-1 placed: an entry / reversal, a close_all)
    B. the bracket of the open trade along the bar's path (also for a trade filled in A)
    C. the script run at the close of j, on the position and equity left by A and B
    D. the bar-close equity point

Same-bar exit: yes (the bracket is sent with the entry and is live from the fill; probe: 2 % to 12 % of the
default trades open and close in one bar). Same-bar re-entry: never (an entry is a market order of a close
run). A trade stopped inside bar j leaves the account flat at j's close, so a trigger ON bar j can open a
new trade at the open of j+1.

Live-only code: none in the strategy section. The filter's live branches (`fgfLiveBar`, `timenow`) are dead
on history and are not in `fgf.py`.

---------------------------------------------------------------------------------------------------

## 6. The broker inside a bar (path 'tv')

### 6.1 Orders the script can place (all of them)

| call (lines) | type | replica |
|---|---|---|
| `strategy.entry("Long", strategy.long)` (802) | market buy, default quantity | order `d = +1` |
| `strategy.entry("Short", strategy.short)` (805) | market sell, default quantity | order `d = -1` |
| `strategy.exit("L-Exit", "Long", stop, limit, trail_points, trail_offset)` (818) | bracket of "Long" at absolute prices + trail ticks; called on the signal bar AND on every bar with a long open | 6.2 |
| `strategy.exit("S-Exit", "Short", ...)` (825) | the same for "Short" | 6.2 |
| `strategy.close_all(comment="Vol Collapse")` (831) | market close at the next open | `close_req = 'vol'` |
| `strategy.close_all(comment="Time Stop")` (835) | market close at the next open | `close_req = 'time'` (if not already 'vol') |

Ids: "Long" is always a real buy, "Short" a real sell, also with Inverted. There is no `strategy.cancel`,
no `strategy.close(id)`, no stop / limit ENTRY order. One run places at most one entry (`goLong` and
`goShort` exclude each other) and at most one effective close.

An order: `{d (real side), sig (normal-frame side: +1 for a trigUp bar, -1 for trigDn), qty, a (the ATR of
the placing bar), SL0, TP0, actT, offT, hot (hotCount of the placing bar), placed bar}`.

### 6.2 A trade's levels

```
mintick = 0.01 ;  e = the entry fill price (with the 'tv' slippage inside) ;  d = real side ;  a = the order's ATR

fill bar k (levels sent on the SIGNAL bar j = k-1, measured from its close c_j):
    SL = c_j - d * (a * slMult)   if slMult > 0  else none          (order's SL0)
    TP = c_j + d * (a * tpMult)   if tpMult > 0  else none          (order's TP0)
every later bar (levels re-sent by the run of bar k, measured from e = strategy.position_avg_price):
    SL = e - d * (a * slMult) ;  TP = e + d * (a * tpMult)
trailing, if useTrail (ticks fixed with the order, measured from e, never re-anchored):
    A = e + d * (actT * mintick) ;  off = offT * mintick ;  armed = False ;  best = e
```

No rounding to the tick grid, no tolerance, inclusive comparisons (as `hrd._walk`). The stop in force for a
long is `S* = max(SL, best - off if armed)`; for a short `S* = min(SL, best + off if armed)`; a missing level
does not take part. A stop fill is kind 'trail' if the trailing stop is the level hit (long: armed and `best
- off >= SL`, or no `SL`), else 'sl'. If `slMult == 0 and tpMult == 0 and not useTrail` (`hasBracket` false,
L812) no `strategy.exit` is ever called: the trade has no bracket.

The re-anchored levels act from the open of bar k+1 on; they are never applied to the part of bar k already
traded (a price that passed the new level during bar k matters only through the gap test at the next open).
The Pine recomputes them on every bar from the same `e` and the same `entryAtr`, so computing them once, in
the first run after the fill, is identical (section 7, C3 explains the one bar where `entryAtr` changes and
why it cannot matter).

### 6.3 One bar `j`

`slip` = 0.01 with cost 'tv', else 0. A market or stop fill of an order that BUYS is at `price + slip`, one
that SELLS at `price - slip`; a limit fill is at its price. Closing a trade of side `p` by market or stop:
`px - p * slip`.

**A. The open `o`.** In placement order (entries are placed before the close_all calls, L800-805 then
L831 / L835):
- A1. An entry order waiting (`d`): if a position is open it is the opposite side (assert `pos == -d`): close
  it at `o - pos * slip`, kind 'reverse'. Then open the order's trade: `e = o + d * slip`, the order's
  `qty`, `SL0`, `TP0`, trail ticks (6.2), `entry_bar = j`. If a `close_req` is also waiting (then the fill
  was a reversal): `revClose` 'void' drops it (A11); 'closes' closes the NEW trade at `o - d * slip` with
  the kind of the `close_req` (a zero-length trade). Count `rev_close_same_run` either way.
- A2. Otherwise, `close_req` set and a position open: close it at `o - pos * slip`, kind 'vol' or 'time'.
- Clear the order and `close_req`.
- A3. The trade now open (old or just filled), long (a short with the inequalities turned and `min` for
  `max`): `S*` exists and `o <= S*` -> exit at `o - slip` ('sl' / 'trail'); else `TP` exists and `o >= TP`
  -> exit at `o` ('tp'); else, with `useTrail`: if `armed`, `best = max(best, o)`, else if `o >= A`: `armed
  = True`, `best = o`. For a trade filled in A1 the levels are `SL0` / `TP0` of the signal close, so a gap
  beyond them closes the new trade at its own fill open (zero-length).

**B. The path.** `v1, v2` = `high, low` if `(high - open) < (open - low)` else `low, high` (a tie goes low
first); three legs `o -> v1`, `v1 -> v2`, `v2 -> close`. On a leg from `p` to `b`, for a long (short
mirrored):

```
b > p (rising):   TP exists and b >= TP  -> exit at max(TP, p), 'tp'  (no slippage)
                  else with useTrail: if armed: best = max(best, b); elif b >= A: armed = True, best = b
b < p (falling):  S* as it is at the start of the leg (it does not move on an adverse leg)
                  S* exists and b <= S*  -> exit at min(S*, p) - slip, 'sl' / 'trail'
```

The walk uses the raw bar prices and the raw levels; `slip` only moves the fill price. On a rising leg the
target is tested before the trail arms. A3 followed by B is exactly `hrd._walk` in long space (negate a
short's prices); write your own.

Worked checks (gold-like numbers, cost 'ours' so that fills are raw; the 'tv' prices in brackets):
- Signal bar j: close 1,250.00, ATR(14) 2.00, defaults: `SL0` 1,247.00, `TP0` 1,256.00. Bar j+1: O 1,250.40
  H 1,250.90 L 1,246.80 C 1,247.50: long at 1,250.40 [1,250.41]; path O-H-L-C (0.50 < 3.60); the fall meets
  1,247.00: exit 1,247.00 [1,246.99], 'sl', same bar. Note the stop distance from the fill was 3.40, not
  3.00.
- The same entry, but bar j+1 has L 1,248.00, C 1,249.00: no exit. The run of j+1 re-anchors: `SL` 1,247.40,
  `TP` 1,256.40 [1,247.41 / 1,256.41] from bar j+2 on.
- Gap. Bar j+1 opens at 1,246.50 (below `SL0`): the long fills at 1,246.50 [1,246.51] and is stopped at
  1,246.50 [1,246.49] at once: 'sl', zero-length, P/L = minus the costs.
- Inverted, the same trigger: SHORT at 1,250.40 [1,250.39], `SL0` 1,253.00, `TP0` 1,244.00 on the fill bar
  (the long's levels mirrored about the signal close 1,250.00); then `SL` = `e` + 3.00, `TP` = `e` - 6.00.
- Trail. `useTrail`, 1.5 / 1.0, ATR 2.00: `actT = max(1, round(2.00 * 1.5 / 0.01)) = 300`, `offT = 200`:
  `A = e + 3.00`, `off = 2.00`. A long from 1,250.40 with `slMult` 1.5, `tpMult` 0: a later bar O 1,252.00 H
  1,254.60 L 1,251.00 C 1,253.00: path O-L-H-C; the rise to 1,254.60 arms it (`A` 1,253.40, `best`
  1,254.60); the fall to 1,253.00 does not reach 1,252.60: held, stop now 1,252.60 (above `SL` 1,247.40).
- Reversal. Long open; the run of bar j sees a trigger of the other side: a short order with the quantity,
  ATR and levels of bar j; bar j+1 opens at 1,251.00: the long closes at 1,251.00 [1,250.99] ('reverse'),
  the short opens at 1,251.00 [1,250.99] with `SL0` / `TP0` from the close of j.
- Time stop. `maxBars` 5, fill in bar k: the close order is placed in the run of bar k+5 and fills at the
  open of bar k+6.

**Window.** Flat, no order, no `close_req` at the first window bar; its run is the first decision, so the
first possible fill is at the open of the second window bar. On the last window bar A, B, C and D run; then
an open trade is closed at the last close (`close - pos * slip`, kind 'end', exit cost charged, `exit_time
= t_close`); an order or `close_req` placed there is dropped (`orders_unfilled_end`).

**Path 'mag' (stage 3, not built now; keep A3 and B in one function so that it can be swapped).** A1 and A2
stay on the chart bar's open. Then every 1-minute sub-bar of the chart bar (rows of `<PAIR>_1` with `t_open`
in `[t_open[j], t_close[j])`, `hrd.sub_bars`), in time order: A3 at its own open, then B on its own open /
high / low / close; the trailing state carries over; the levels are those of the CHART bar (the fill bar's
`SL0` / `TP0` on all its sub-bars, the re-anchored ones from the next chart bar). C and D stay on the chart
bar's close. Chart "1": 'mag' == 'tv'.

---------------------------------------------------------------------------------------------------

## 7. The script run at the close of bar `j` (step C), in the Pine's order

State it reads: the position after A and B (`pos` in 0 / +1 / -1, `qty`, `e`, `entry_bar`), `cash` (10,000 +
the closed trades' P/L after costs - the entry cost of the open trade), and its one `var`, `entryAtr`
(L798; na at the first window bar). `c = close[j]`, `equity = cash + pos * qty * (c - e)`
(`strategy.equity`, A14).

**C1. Signals (L779-783; original O157-163).** `up = trigUp[j]`, `dn = trigDn[j]`.
```
longSig  = (dn if inv else up) and allowLong          # allowLong  = (tradeDir != "Short Only"); True with 'fgf'
shortSig = (up if inv else dn) and allowShort         # allowShort = (tradeDir != "Long Only");  True with 'fgf'
goLong   = longSig  and pos <= 0 and (allowReverse or pos >= 0)
goShort  = shortSig and pos >= 0 and (allowReverse or pos <= 0)
```
With 'fgf' (`allowReverse` True) these are L782-783 to the letter. With 'orig' and `inv` False they are
O157-163 to the letter (`canLong = allowReverse or position_size >= 0`). `inv` with 'orig' is replica-only
(section 8). `goLong` and `goShort` are never both true: assert.

**C2. Entry (L800-805) and its exit (L808-826, the `goLong` / `goShort` operand).** If `goLong` or
`goShort`, with `d` = +1 / -1:
```
a = atr[j]                                   # entryAtr := atrX ; assert not na inside the window
q = 0.10 * equity / c                        # percent_of_equity 10 (A6); if q <= 0: zero_qty += 1 and no order
actT = max(1, floor(a * trailActMul / mintick + 0.5))      # math.max(1, math.round(...)); only if useTrail
offT = max(1, floor(a * trailOffMul / mintick + 0.5))
SL0 = c - d * (a * slMult)  if slMult > 0  else none       # ep = close because the position is not on that side yet
TP0 = c + d * (a * tpMult)  if tpMult > 0  else none
place the order {d, sig = +1 if up else -1, q, a, SL0, TP0, actT, offT, hot = hotCount[j], j}
```
The trail is at least 1 tick away in both distances: `trailActMul = 0` does NOT arm at the fill.

**C3. Re-anchor (L814-826, the `position_size > 0` / `< 0` operand).** If a trade is open and this is the
first run since its fill (`entry_bar == j`): `SL = e - pos * (a_t * slMult)` if `slMult > 0`, `TP = e + pos
* (a_t * tpMult)` if `tpMult > 0`, with `a_t` the ATR stored with that trade. They hold from bar j+1 until
the trade closes. Literal Pine: every run with a position recomputes the same two numbers from
`position_avg_price` and `entryAtr`. `entryAtr` changes only in C2, i.e. when flat (the new order's trade
is the next one to be open) or when an opposite entry is placed; in the second case the open trade's exit
is indeed re-sent with the NEW ATR and new trail ticks, but that trade is closed by the reversal at the
next open before any price is tested (A10), so those values never act. Keep `a_t` per trade and say so in
your notes.

**C4. Volatility collapse (L829-831).** `if useVolExit and pos != 0 and volCollapse[j]: close_req = 'vol'`.

**C5. Time stop (L834-835).** `if maxBars > 0 and pos != 0 and j - entry_bar >= maxBars`: `close_req =
'time'` unless it is already 'vol' (two `close_all` calls in one run = one close; the first placed names
it, A12). `entry_bar` is the bar of the open trade's fill (`strategy.opentrades.entry_bar_index(0)`).

To keep exactly:
- `pos` in C1, C4, C5 is the position AFTER this bar's fills and bracket exits. C4 and C5 can therefore
  not fire on a flat account that has just placed an entry; they CAN fire in the same run as a reversal
  entry (A11).
- A trigger on the side already held does nothing: no order, no new ATR, no new bracket; it is not
  remembered either (a trade closed at the next open by a collapse does not re-enter on it).
- The quantity and the ATR are those of the PLACING bar; `equity` at a reversal run includes the open P/L
  of the trade about to be closed, at this close.
- With `dirSource` 'orig' and `allowReverse` False an opposite trigger while in a trade is ignored
  (`goShort` needs `pos == 0`); with `tradeDir` "Long Only" no short is ever placed.

**D.** Bar-close equity `E[j] = cash + pos * qty * (c - e)`; exposure counts bars with `pos != 0` here.
Counters in C (normal frame): `taken_up` / `taken_dn` += an order placed from a `trigUp` / `trigDn` bar;
`ignored_held` += a bar with `longSig or shortSig` and no order because that side is already held (or
because of `allowReverse` False).

---------------------------------------------------------------------------------------------------

## 8. `inv` = "Trade direction: Inverted" (`amviInv`), line by line, and against INVERT_SPEC.md

| Pine | what it does | replica |
|---|---|---|
| L108 `amviTradeDir`, L779 `amviInv = amviTradeDir == "Inverted"` | the input (existed before Update 1; default "Follow the filter") | `inv` |
| L744-770 trigger, L776-778 `inRange`, `amviDirUp`, `amviDirDn` | never read `amviInv`: the trigger and the filter's zones stay in the normal frame (M1) | `P` is the same for both directions |
| L780-781 `longSig = trigger and (amviInv ? amviDirDn : amviDirUp) and inRange` (and `shortSig`) | the swap comes AFTER the filter: a trigger in the BUY ZONE becomes a short signal, in the SELL ZONE a long signal, in NO TRADE nothing | C1 |
| L782-783 `goLong = longSig and strategy.position_size <= 0` (and `goShort`) | read the REAL position against the swapped signal = the normal decision on the mirrored position (M1): a BUY-ZONE trigger is taken when the real position is flat or long, and then sells | C1 |
| L800-805 | market orders on the real side with the real side's id and comment ("Short" / "AMVI S nTF" for a BUY-ZONE trigger) (M2, M6); `entryAtr := atrX` either way | C2 |
| L808-809 trail ticks | side-agnostic tick distances (M3) | C2 |
| L814-826 brackets | written for the REAL side: a short always has `stop = ep + entryAtr * slMult`, `limit = ep - entryAtr * tpMult`, with `ep` = the signal close, later the real average price | 6.2 |
| L829-835 | `close_all` on the volatility collapse / the time stop: no side in them (M4) | C4, C5 |
| L786-795 FGD plots | normal frame (`amviDirUp` / `amviDirDn`): they describe the filter (M6) | `trig_up`, `trig_dn`, `trig_none` |

**How the bracket is mirrored: by re-anchoring, not by a `2R - S` formula.** The Pine has no mirroring
expression. It recomputes the real side's bracket from the same reference price and the same ATR distances.
The result EQUALS INVERT_SPEC's M3 mirror: on the fill bar about `R` = the signal candle's close (`c + a *
slMult = 2c - (c - a * slMult)`, `c - a * tpMult = 2c - (c + a * tpMult)`), afterwards about the raw fill
open (with cost 'tv' the two sides' average prices are `o + 0.01` and `o - 0.01`, so the levels are mirror
images about `o` itself). The stop distance stays the stop distance, the target distance the target
distance; the trail keeps its ticks and arms from the real entry price. M2's stop <-> limit entry swap has
nothing to convert (market entries only). M5: the fused file has no Long only / Short only input; the
filter's `fgfAllowBuy` / `fgfAllowSell` stay in the normal frame (they choose the ZONE: with Inverted,
"Allow buys" alone trades shorts only). So: the Update 1 definition, already met by the older code; nothing
else flips.

There is no other reverse or direction option in the fused file. The original's `tradeDir` (a side
restriction on the real orders) and `allowReverse` (whether an opposite signal reverses) are not direction
flips, and the fused file dropped both (a trigger in the opposite zone always reverses).

`inv` with `dirSource` 'orig' is a REPLICA-ONLY control (the original has no such input): the same swap,
`longSig = trigger and (inv ? dnBias : upBias) and tradeDir != "Short Only" and inRange` (and `shortSig`),
`tradeDir` restricting the real orders (M5). It exists so that every calibration row has a
direction-flipped twin; a pick that needs it cannot be published without adding the option to the original.

The inverted run is NOT the mirrored trade list in general: the stop (1.5 ATR) and the target (3 ATR)
change sides, so trades end elsewhere, the position differs, later triggers are taken or ignored
differently, equity and quantities differ.

Properties (stage 2 self-checks, stage 3 tests):
- P1, exact mirror. `slMult == tpMult > 0`, `useTrail` False, cost 'ours' or 'stress' (no price shift),
  any `useVolExit`, `maxBars`, `dirSource` (with `tradeDir` "Both"): `inv` True gives the trade list of
  `inv` False with `dir` negated, `sig` equal, 'sl' <-> 'tp' swapped, every bar, entry price, exit price and
  other kind equal (quantities and P/L differ: the equity path differs). With cost 'tv' it does not hold
  (stop fills slip, limit fills do not): show one example.
- P2, single decisions: from the same state with the position negated, the order placed with `inv` True is
  the order placed with `inv` False on the other side: same bar, same quantity, same ATR, `SL0` / `TP0`
  mirrored about the close; a `close_req` has the same kind.
- P3: the first trade of a run has the same signal bar, fill bar, raw open and quantity with `inv` False
  and True, opposite `dir` (default inputs).
- P4 (header: "with it off ... nothing trades"): `dirSource` 'fgf', `fgfOn` False: `trig_up = trig_dn = 0`,
  `trig_none = triggers > 0`, no trade, `net_pct` 0, both directions.
- P5 (header): every trade has `dir == sig` with `inv` False and `dir == -sig` with `inv` True; `sig` is the
  zone of `sig_bar` (`buyOk` -> +1, `sellOk` -> -1). With `fgfAllowSell` False: normal = longs only,
  inverted = shorts only.
- P6 (header: "measured from the signal candle's close during the candle of the fill, then from the entry
  price"): `sl0 == close[sig_bar] - dir * sl_dist`, `tp0 == close[sig_bar] + dir * tp_dist`; for a trade
  that outlives its fill bar `sl_px == entry_px - dir * sl_dist`, `tp_px == entry_px + dir * tp_dist`.
- P7: the five seconds toggles change nothing; all seven minute / day toggles off: no trigger.
- P8: `noRepaint` False: `trigger`, `hotCount`, `avgAmvi` equal the `noRepaint` True arrays shifted one bar
  earlier (`x_off[j] == x_on[j + 1]`), with `ltfRule` 'first'.
- P9: `qty` of every trade = `0.10 * equity / close` of `sig_bar`, the equity recomputed from the trade
  list (closed P/L, the open trade's entry cost and open P/L at that close).
- P10: `dirSource` 'orig', `allowReverse` False: no 'reverse' exit; `tradeDir` "Long Only": every `dir` +1,
  with `inv` False every `sig` +1, with `inv` True every `sig` -1.

---------------------------------------------------------------------------------------------------

## 9. Sizing, money, costs

`qty = 0.10 * equity / c` at the placing bar (C2), float64, not rounded, fixed at placement. A reversal
closes the old trade's own quantity and opens `qty`.

Per fill, per unit: `(fixed $, fraction of the fill value)` and the slippage in price:

| mode | fixed, fraction | `slip` | meaning |
|---|---|---|---|
| 'tv' | `(0, 0.0004)` both pairs | 0.01 | the script's Properties: 0.04 % per fill on the slipped fill price; market and stop fills move 1 tick against the order, limit fills do not |
| 'ours' | XAU `(0.15, 0)`, BTC `(0.10, 0.0002)` | 0 | replaces the commission AND the slippage |
| 'stress' | XAU `(0.26, 0)`, BTC `(0.11, 0.00035)` | 0 | the stress tick is a cost, prices stay raw (as hrd / gvl) |

- `cash` starts at 10,000. Cost of a fill = `qty * (fixed + fraction * fill_px)`, charged when the fill
  happens (a reversal = the closing fill and the opening fill). Costs reduce `cash`, so they change later
  quantities.
- `pnl_gross = dir * qty * (exit_px - entry_px)` (with 'tv' the slippage is inside the prices); `pnl =
  pnl_gross - entry cost - exit cost`. `slippage_paid` = sum of `slip * qty` over slipped fills.
- `eq_before` of a trade = `cash` just before its entry fill (after the closing leg of a reversal, before
  its own entry cost).
- R: `sl_dist = a * slMult` of the placing bar (the stop distance the script intends; NaN if `slMult ==
  0`), `tp_dist = a * tpMult`; `r_mult = pnl / (sl_dist * qty)`; summary `net_r`, `h1_r`, `h2_r`.
- No floor at zero; `q <= 0` places nothing (`zero_qty`; with 10 % positions it should stay 0: flag it).

What the Properties mean per unit, round trip (window medians: gold $1,280, BTC $88,000; stop = 1.5 x the
median ATR(14) at the default trigger bars, probe):

| chart | 1 | 5 | 15 | 60 | 240 |
|---|---|---|---|---|---|
| gold: stop distance $ | 0.96 | 1.97 | 2.84 | 4.54 | 8.03 |
| gold: 'tv' $1.04 (2 x (0.51 + 0.01)) / 'ours' $0.30, in R | 1.08 / 0.31 | 0.53 / 0.15 | 0.37 / 0.11 | 0.23 / 0.07 | 0.13 / 0.04 |
| BTC: stop distance $ | 195 | 415 | 627 | 1,045 | 1,878 |
| BTC: 'tv' $70.4 / 'ours' $35.4, in R | 0.36 / 0.18 | 0.17 / 0.09 | 0.11 / 0.06 | 0.07 / 0.03 | 0.04 / 0.02 |

So TradingView's own report charges about 3.5 times our gold cost and twice our BTC cost. With 10 % of
equity per trade a whole run moves the account by a few percent: report `net_r` next to `net_pct`.

---------------------------------------------------------------------------------------------------

## 10. Assumptions (one each; both builders implement exactly these)

| id | assumption | why |
|---|---|---|
| A1 | One script run per bar, at its close; no other run. | Neither `calc_on_*` flag is set; documented behaviour of history bars. |
| A2 | `request.security` on history: lookahead off = the last requested bar closed by the chart bar's CLOSE; lookahead on with `[1]` = the last requested bar closed by the chart bar's OPEN, for higher, equal AND lower timeframes (lower: lookahead on returns the first intrabar of the chart bar, `[1]` of it is the last intrabar of the previous chart bar). Control `ltfRule = 'last'`. | Pine user manual, "Other timeframes and data": on historical bars a lower-timeframe `request.security` returns the first intrabar with `lookahead_on` and the last with `lookahead_off`. The script's own tooltip says "uses the previous confirmed bar of each requested timeframe". Not testable here, and it moves every lower-timeframe trigger by one chart bar: hence the control. |
| A3 | Seconds timeframes: na on every bar = switched off. | No data below 1 minute; `on ? v : na` makes a disabled timeframe na too. Section 11. |
| A4 | `ta.highest` / `ta.lowest` over a window that still holds an na are na; `ta.sma`, `ta.stdev` are na before `length` bars exist; `ta.stdev` is the population deviation; `ta.ema` is seeded with the first value. | Reference manual; SPEC.md / SPEC_AH.md. Only the first 220 rows of each file depend on it (2011 / 2012). |
| A5 | AMVI is compared with the thresholds as computed in section 4.1's operation order. | TradingView's internal summation order is unknown; a different order could flip a comparison only on an exact tie. |
| A6 | A market order fills at the next bar's open (+/- `slip`). Its quantity is fixed when it is placed: 10 % x `strategy.equity` at that close / that close; no adjustment for commission, no rounding to a lot step. | `process_orders_on_close` false; SPEC_AH rule 1 and its sizing rule (the verified apex reading). TradingView may shave the size by the commission rate (0.04 %): immaterial. |
| A7 | The bracket is live from the entry fill: on the fill bar with the levels sent on the signal bar (gap test at the fill open, then the rest of the path); a `strategy.exit` re-sent with the same id replaces the stop / limit from the next bar's open on and is never applied backwards. An exit whose trade closed is gone. | SPEC_AH rule 3; the Pine comment L807 and header L21-25 say the same. |
| A8 | Trailing stop as SWEEP_AH_SPEC section 1: armed when price reaches the entry fill price + `trail_points` ticks, then stop = best price - `trail_offset` ticks, moving only in favour; the re-send on every bar with the same ticks keeps the state (armed, best); with a stop loss the nearer stop is the one hit; the target is tested before arming. | The verified reading of apex / hrd / xpw / gvl; calling `strategy.exit` on every bar is the usual way to run a trailing stop. |
| A9 | Intrabar path = SPEC_AH rule 4 (tie: low first); the first level reached wins; a level already passed at the open fills at the open (stop and target alike); a target fills on touch. A market `strategy.entry` against the open position closes it at the open (kind 'reverse') and opens exactly its own quantity. | Documented broker emulator; `pyramiding = 0` only limits same-side entries. |
| A10 | At an open: the script's market orders first, in placement order (the entry / reversal, then the close_all), then the gap test of the trade still open. | A market order and a stop gapped through at the same open give the same price and the same position: only the label differs, and with cost 'tv' at most 1 tick when the gap passes a target. TradingView's order is not documented; deterministic choice, as gvl G10 / fgds F6. |
| A11 | A `close_all` placed in the same run as a reversal entry does nothing: it was issued for the trade the reversal has just closed (`revClose = 'void'`). Control 'closes' = the `hrd.py` reading (it closes the trade the reversal just opened, zero-length). | `strategy.close_all` creates its order when called, for the position open then (it creates none when flat); a sell-to-close order cannot close a short that did not exist. `hrd.py` chose the other reading; neither is verifiable. Rare: 0 to 4 runs per cell even with a time stop of 12 bars on a loose trigger (probe); impossible with the default inputs in the replica (`maxBars` 0; three of seven values above 70 keep the average above 30). Counted. |
| A12 | Two `close_all` in one run (collapse and time stop) = one close, kind 'vol'. | One position; the first order placed fills it. |
| A13 | No rounding: levels are not rounded to the tick, quantities not to a lot step; XAU prices keep their 3 decimals; no margin logic. | As apex / hrd / gvl / fgds. Section 11 for what TradingView's lot step does on gold. |
| A14 | `strategy.equity` = `cash` + open P/L at the close (costs paid included); `strategy.position_avg_price` = the entry fill price, slippage included; `strategy.opentrades.entry_bar_index(0)` = the fill bar. | SPEC_AH rule 6. |
| A15 | `math.round` = `floor(x + 0.5)`; `math.max(1, n)`; ticks are integers. | Positive arguments only. |
| A16 | Trading starts flat with `entryAtr` na at the first window bar; the trigger of that bar uses the real previous row; orders of the last window bar do not fill; 'end' at the last close. | REPLICA_SPEC; SPEC_AH rule 5. |
| A17 | `timestamp("2020-01-01T00:00:00")` is UTC; `time` is the bar's open. | The string form of `timestamp` defaults to GMT+0. Off by default. |
| A18 | A `strategy.exit` whose stop, limit and trail are all na places nothing. | Only reachable with an na ATR, i.e. never inside a window (assert). |

Not an assumption, facts of this script: a stop and a target touched in one bar are settled by A9; `na`
prices only mean "no stop" / "no target"; there is no pending price entry, no cooldown, no session, no
daily limit, no time zone and no day boundary outside the filter and the daily bars.

---------------------------------------------------------------------------------------------------

## 11. What cannot be reproduced, and what the replica does instead

- **TradingView itself**: nothing can be compiled or backtested here. A2, A6-A11 are readings of its engine.
- **Seconds timeframes (1s, 5s, 15s, 30s, 45s)**: no data below 1 minute. Replica: na = off. On TradingView
  with the default toggles the script either stops with an error (plan without seconds data; the tooltip
  says to turn them off) or reads seconds bars that exist for a short recent stretch only, where five more
  series can cross and count toward `hotCount` and enter `avgAmvi`. The comparable TradingView run has
  **`en1s`, `en5s`, `en15s`, `en30s`, `en45s` switched off**.
- **TradingView's depth of lower-timeframe data.** A request for a timeframe below the chart's only has
  intrabars for the most recent part of a long chart (on a 4-hour chart the 1-minute series covers weeks,
  not years); before that it returns na and the timeframe silently stops counting. The replica has every
  1-minute bar of the window. A setting that keeps only timeframes at or above the chart's (`tfSet` 'ge' in
  the grid) does not depend on this and is the one that can be checked on TradingView.
- **Live bars**: a lower-timeframe request returns the latest intrabar on a realtime bar whatever the
  lookahead, so live values of the lower timeframes follow `ltfRule` 'last', not 'first': history and live
  differ by one chart bar for those timeframes although "Non-Repainting" is on.
- **TradingView's lot step and price rounding.** 10 % of 10,000 is $1,000: 0.011 BTC, but under 1 ounce of
  gold (0.78 oz at $1,280). On a gold symbol whose minimum size is 1 unit TradingView would trade nothing
  with the default capital. The replica does not round (A13).
- **Bars of another broker**: gold bars are 18:00-17:00 New York sessions with 240-minute bars anchored at
  18:00 and a daily bar per session; BTC bars are on a UTC grid (Bitstamp). Another feed changes the daily
  and 4-hour AMVI and the filter candles.
- **Volume**: not used anywhere in this script (gold's tick count is irrelevant).
- **`fgf.py`'s own residuals** (reconcile_fgf.md): TDI float ties on 1-minute and 5-minute filter
  timeframes; the `""` timeframe inside the nested request.
- **`/home/user/master/AMVI_by_timeframe/`** (README and the XAUUSD 15m copy): an earlier calibration on
  other data (VANTAGE gold 2025-2026, Bitfinex 2018-2019) with another replica. It shows which inputs
  mattered (enabled timeframes, `highVolThreshold`, `minConfluence`, ATR periods, `slMult`, `tpMult`,
  `useVolExit`, the filter's level / band / burst gate, the direction). Not a source of numbers.
- **Bar Magnifier inside TradingView**: path 'mag' is OUR 1-minute walk of the bracket, with decisions and
  market fills on the chart bars.

---------------------------------------------------------------------------------------------------

## 12. Interface, trade record, summary

    prepare(pair, chart_tf, params=None) -> P
    simulate(P, x=None) -> R
    trades(P, R) -> DataFrame
    summary(P, R) -> dict
    run(pair, chart_tf, params=None) -> (trades, summary)        # splits one dict into 3.1 / 3.2 keys

`DEFAULTS` = every Pine default of 3.1, 3.2 and 3.3 (so `fgfOn = True`, "Follow the filter", the seconds
toggles True), plus the replica controls (`dirSource` 'fgf', `dirMode` "Trend (EMA)", `emaLen` 50, `dcLen`
20, `tradeDir` "Both", `allowReverse` True, `ltfRule` 'first', `revClose` 'void', `path` 'tv', `cost` 'tv',
`inv` False). `INITIAL_CAPITAL = 10000.0`. One numba kernel for A, B, C, D over the window bars. Speed: one
`simulate` on BTC "1" (1,039,430 bars) well under 1 s after compilation (probe: 10 ms); first `prepare`
under 2 minutes; under 3 GB.

`KINDS = ['', 'sl', 'tp', 'trail', 'reverse', 'vol', 'time', 'end']`.

**Trades**, one row per entry fill, in fill order:

| column | content |
|---|---|
| `dir` | REAL side, +1 / -1 |
| `sig` | normal-frame side of the trigger (+1 = BUY ZONE / up bias); `= dir` with `inv` off, `-dir` with it on |
| `sig_bar`, `entry_bar`, `exit_bar` | file rows: where the order was placed (always `entry_bar - 1`), where it filled, where the trade closed |
| `entry_time`, `exit_time` | `t_open` of the fill bar / of the exit bar (chart bars, also in 'mag'); 'end': `t_close` |
| `entry_px`, `qty`, `exit_px` | fill price (slippage inside with 'tv'), units, exit fill price |
| `exit_kind` | 'sl', 'tp', 'trail' (bracket); 'reverse' (opposite entry); 'vol' ("Vol Collapse"); 'time' ("Time Stop"); 'end' |
| `pnl`, `pnl_gross`, `costs`, `eq_before` | section 9 |
| `atr`, `sl_dist`, `tp_dist`, `r_mult` | the order's ATR, `atr * slMult`, `atr * tpMult` (NaN if the multiplier is 0), `pnl / (sl_dist * qty)` |
| `sl0`, `tp0`, `sl_px`, `tp_px` | the fill bar's levels (from the signal close); the re-anchored levels (NaN if the trade ended on its fill bar or the level does not exist) |
| `hot` | `hotCount` of the signal bar (the number in the entry comment) |
| `rev` | True when the fill that opened the trade also closed the previous one |

**Summary.** The common fields exactly as `hrd.summary_fast` + `hrd.extra_fields` compute them, with
`INITIAL_CAPITAL = 10000`: `start, end, bars, trades, net_pct, pf, win_pct, max_dd_pct, max_dd_init_pct,
long, short, raw_long, raw_short, blocked_long, blocked_short, half1_pct, half2_pct, exposure,
final_equity, exit_sl, exit_tp, exit_trail, exit_reverse, exit_vol, exit_time, exit_end, zero_length,
h1r_pct, h2r_pct, h1_trades, h2_trades, avg_bars_held, costs`.
- `long` / `short`: real sides. `raw_long = trig_up`, `raw_short = trig_dn` (normal frame, window bars).
  `blocked_long = blocked_short = 0` always: a trigger has no side before the filter, so the filter cannot
  block "a long"; the triggers it leaves without direction are `trig_none` (kept apart).
- Equity curve for `max_dd_pct` / `max_dd_init_pct`: 10,000, then `E[0] .. E[n-2]`, then the final equity
  (after the 'end' close and its cost) in place of `E[n-1]`; running peak starts at 10,000. `half1_pct` /
  `half2_pct` from `E[mid_j]` (10,000 if `mid_j < 0`), as `hrd`.
- Fair halves: trades ENTERED in each half by `entry_time <= mid` / `> mid`, `100 * (prod(1 + pnl /
  eq_before) - 1)`, 0 for an empty half. `avg_bars_held = mean(exit_bar - entry_bar)`; `zero_length` =
  trades with `entry_bar == exit_bar`.

Fields of this strategy: `triggers`, `trig_up`, `trig_dn`, `trig_none` (from `P`); `taken_up`, `taken_dn`,
`ignored_held`, `orders_unfilled_end`, `zero_qty`, `rev_close_same_run`, `slippage_paid`, `net_r`, `h1_r`,
`h2_r` (sum of `r_mult`, NaN rows skipped: all trades / the trades entered in each half), `min_trail_off_pct`
(the smallest `offT * mintick / entry_px` in % over the trades, NaN without `useTrail`: the calibration's
noise-floor check), `seconds_ignored`.

Comparing A and B: bars, kinds, flags and counts exactly; prices, quantities, P/L and equity fields to a
relative 1e-9.

---------------------------------------------------------------------------------------------------

## 13. Builders: outputs, self-checks, sanity numbers

- Saved trade lists (cost 'tv', path 'tv', default inputs): `$W/out/amvi_<a|b>_<PAIR>_<TF>.parquet` for BTC
  60, BTC 5, XAU 60, XAU 15, one file per cell with a column `variant` in `on_normal`, `on_inv`
  (`dirSource` 'fgf'), `off_normal`, `off_inv` (`dirSource` 'orig', the original's defaults: "Trend (EMA)"
  50, "Both", reverse on). Also all their summaries, plus the literal `fgfOn = False` run (zero trades), in
  `$W/out/amvi_<a|b>_summaries.json`.
- "`fgfOn` False reproduces the original" becomes: (a) P4; (b) `dirSource` 'orig' is the original: show
  that C1 with `inv` False is O157-163 token for token and that 4.4 is O144-154; (c) kernel tests on
  INJECTED arrays, independent of `fgf` and of AMVI: build small inputs by hand (10 to 40 bars of OHLC, ATR,
  `trigUp`, `trigDn`, `avgAmvi`) and check the kernel against the bar-by-bar expectation written out in the
  test, for: an entry and its stop in the same bar; a gap through `SL0` at the fill open; a target on the
  fill bar; the re-anchored levels on the next bar (a stop that would not have been hit with `SL0`); a
  reversal; a 'vol' close; a 'time' close; a trigger on the side already held (ignored); a reversal and a
  collapse in one run, both `revClose` values; `allowReverse` False; `tradeDir`.
- Hand traces from real data with the bars printed, at least 3 trades each: 'sl' (one on the fill bar, one
  later at the re-anchored level), 'tp', 'trail' (`useTrail`, `tpMult` 0), 'reverse', 'vol', 'time'
  (`maxBars` 5), 'end'; a trade with cost 'tv' showing every slipped price; sizing against P9.
- AMVI checks: for one bar of each of three timeframes print the four parts and the sum from the raw bars;
  on chart "15" print one row with the seven `v_T`, the bar of each timeframe they come from (its
  `t_close` <= the chart bar's `t_open`), `hotCount`, `avgAmvi`; P8; P7.
- The asserts of sections 4 and 6-7 (never both zones; never both signals; a reversal order meets the
  opposite side; no na AMVI or ATR inside a window).
- P1 to P10 of section 8; the mirror property on 5 single decisions (P2).
- Sanity numbers (probe, plain single implementation, unverified, order of magnitude only; default inputs,
  cost 'tv', path 'tv'). Trades:

  | cell | on_normal | on_inv | off_normal | off_inv |
  |---|---|---|---|---|
  | BTC 1 / 5 / 15 / 30 | 1,124 / 850 / 638 / 434 | 1,117 / 883 / 654 / 425 | 1,332 / 959 / 666 / 437 | 1,353 / 1,000 / 709 / 466 |
  | BTC 60 / 120 / 240 | 303 / 206 / 132 | 288 / 200 / 125 | 313 / 208 / 136 | 342 / 223 / 149 |
  | XAU 1 / 5 / 15 / 30 | 323 / 265 / 214 / 127 | 327 / 267 / 216 / 128 | 377 / 280 / 209 / 144 | 376 / 284 / 213 / 144 |
  | XAU 60 / 120 / 240 | 91 / 61 / 49 | 90 / 61 / 51 | 105 / 73 / 55 | 109 / 74 / 51 |

  Exit kinds, `on_normal`: BTC 60: sl 144 / tp 43 / reverse 11 / vol 104 / end 1, 36 zero-length; XAU 15: sl
  96 / tp 47 / reverse 15 / vol 56, 20 zero-length; BTC 1: sl 734 / tp 378 / reverse 11 / vol 1; BTC 240: sl
  41 / tp 15 / reverse 6 / vol 69 / end 1 (on the 1-minute and 5-minute charts a trade is over long before
  the average AMVI falls under 30; from 60 minutes up the collapse is about as frequent as the stop, on 120
  and 240 more frequent). Exposure 1 % (1-minute charts) to 13 %. Net results are within a few percent of
  the account either way (10 % positions; -11 % to +2.5 % over the four variants and 14 cells).

Additions for stage 3 (beyond REPLICA_SPEC):
- Runner `run_inv_amvi.py`: the 16 keys `runs['<direction>/<filter>/<path>/<cost>']` with filter 'off' =
  `dirSource` 'orig' at the original's defaults and 'on' = the fused defaults; say so in the JSON
  (`filter_off_is: "AMVI_Full_MTF_Strategy.pine"`), and store once `fgf_off_literal` = the fused file with
  `fgfOn` False (zero trades). Add `runs_ltf_last[...]` (the 'on' keys with `ltfRule` 'last') so the weight
  of A2 is on the table. Print `net_r`, `rev_close_same_run`, `zero_qty` next to every row.
- Tests: P1 to P10; 'mag' on chart "1" == 'tv'; 'mag' with one fake sub-bar per chart bar == 'tv'; both
  `revClose` values equal whenever `rev_close_same_run == 0`; cost 'tv' against a recomputation from the
  trade list (which fills slip, the commission on the slipped price).
- The random reconcile settings must draw both `dirSource`s, the three `dirMode`s, `inv`, toggled
  timeframes (including a single one, and none), `minConfluence` 1..4, thresholds, another period set (7 /
  100 / 20), `noRepaint` False, `ltfRule` 'last', `useTrail`, `maxBars > 0`, `slMult` 0, `tpMult` 0, both 0
  with and without the trail, `useVolExit` off, `allowReverse` False, `tradeDir`, `useDateRange` (BTC), and
  filter settings outside the grid (`fgfCheck` "Candle open", `fgfAllowSell` off, `fgfLast` "Candles",
  `fgfTf` "").

---------------------------------------------------------------------------------------------------

## 14. Calibration grid proposal (for `$W/CALIB_SPEC.md`)

Scored as CALIB_SPEC says (path 'mag', cost 'ours'). **24,192 settings per cell on charts 5, 15, 30, 60;
12,096 on charts 1, 120, 240.** 504 (252) `prepare` settings x 48 `simulate` settings.

| # | dimension (Pine names) | values | kind | side | default |
|---|---|---|---|---|---|
| 1 | `highVolThreshold` | 50, 60, 70, 80 | ordinal | prepare | 70 |
| 2 | `minConfluence` | 1, 2, 3 | ordinal | prepare | 3 |
| 3 | `tfSet` (the toggles `en1` .. `enD`) | 'all' = the seven on; 'ge' = only the timeframes at or above the chart's. Charts 1, 120, 240: 'all' only (value None) | categorical | prepare | 'all' |
| 4 | `dirSource` (the filter off / on dimension) | 'orig' (off: the original's direction), 'fgf' (on) | categorical | prepare | 'fgf' |
| 5 | `dirMode` | "Trend (EMA)", "Candle", "Breakout (Donchian)" (None with 'fgf') | categorical | prepare | "Trend (EMA)" |
| 6 | `fgfTf` (moves the parent and the zones with it: `fgfParentTf = T`, `fgfZTf1 / 2 / 3 = T / 2T / 4T`) | "15" (15 / 30 / 60), "60" (60 / 120 / 240), "240" (240 / 480 / 960) (None with 'orig') | ordinal | prepare | "60" |
| 7 | `fgfBandAtr` | 0.0, 0.25, 0.75 (None with 'orig') | ordinal | prepare | 0.25 |
| 8 | `fgfLvMode` | "Entry price", "Signal close" (None with 'orig') | categorical | prepare | "Entry price" |
| 9 | `inv` (`amviTradeDir`) | False, True | categorical (the direction control) | simulate | False |
| 10 | `slMult` | 1.0, 1.5, 2.5 | ordinal | simulate | 1.5 |
| 11 | `exitStyle` = (`tpMult`, `useTrail`) | 'tp3' = (3.0, False); 'tp1.5' = (1.5, False); 'none' = (0.0, False); 'trail' = (0.0, True with the cell's pair below) | categorical | simulate | 'tp3' |
| 12 | `useVolExit` | True, False | categorical | simulate | True |

Count: trigger settings 4 x 3 x 2 = 24 (12 where `tfSet` is None); direction settings 3 ('orig') + 3 x 3 x
2 = 18 ('fgf') = 21; `simulate` settings 2 x 3 x 4 x 2 = 48. 24 x 21 x 48 = **24,192**; 12 x 21 x 48 =
**12,096**. Both script defaults are grid points: the fused file (70, 3, 'all', 'fgf', "60", 0.25, "Entry
price", normal, 1.5, 'tp3', collapse on) and the original (70, 3, 'all', 'orig', "Trend (EMA)", normal,
1.5, 'tp3', collapse on). Everything else at the script defaults (periods 14 / 50 / 20 / 10 / 200, weights,
`noRepaint` on, `lowVolThreshold` 30, `maxBars` 0, `exitAtrLen` 14, `emaLen` 50, `dcLen` 20, `tradeDir`
"Both", reverse on, the filter's other inputs, `ltfRule` 'first', `revClose` 'void'). `tfSet`, `exitStyle`
and dimension 6 are derived dimensions: write the Pine inputs they set as extra columns that do not start
with `p_`.

REPLICA_SPEC's "filter {off, on, on without the blocked close}" is dimension 4: off = the unfused original
(the fused file with `fgfOn` off trades nothing), on = the fused file; this script has no blocked-signal
close.

Trailing (`exitStyle` 'trail'): `trailOffMul = d`, `trailActMul = 1.5 d` (the script's own 1.5 : 1), with
`d` the smallest of {1, 1.75, 2.5, 3.5, 5, 6.5} for which `d x ATR(14) / close` at the 10th percentile of
ALL window bars is at least the floor (0.1 % BTC, 0.05 % gold); the same table as SPEC_fgds / SPEC_gvl /
SPEC_danny (same ATR, recomputed, probe):

| cell | BTC 1 | BTC 5 | BTC 15 - 240 | XAU 1 | XAU 5 | XAU 15 - 240 |
|---|---|---|---|---|---|---|
| 10th percentile of ATR(14) / close, % | 0.0157 | 0.0574 | 0.125 / 0.198 / 0.318 / 0.512 / 0.826 | 0.0101 | 0.0290 | 0.0599 / 0.094 / 0.145 / 0.203 / 0.311 |
| `d` | 6.5 | 1.75 | 1 | 5 | 1.75 | 1 |
| (`trailActMul`, `trailOffMul`) | (9.75, 6.5) | (2.625, 1.75) | (1.5, 1.0) | (7.5, 5) | (2.625, 1.75) | (1.5, 1.0) |

From 15 minutes up this is the script's own trail (1.5, 1.0). The table is conservative: triggers fire in
high volatility; the 10th percentile of ATR / close AT the default trigger bars is 1.2 (240-minute charts)
to 5 times (BTC 1) the window-wide one (0.080 % on BTC 1, 0.185 % on BTC 5, 0.032 % on XAU 1, 0.073 % on
XAU 5), so on the 1-minute charts the trail is nearly inert. The runner sets `floor_ok` False for a row whose `min_trail_off_pct` is
below the floor.

Why these dimensions (probe, default direction):
- The trigger is rare and the two thresholds set how rare: trigger bars on XAU 240 / XAU 15 / BTC 60 / BTC
  1 with 'all': (50, 1) 941 / 4,569 / 3,889 / 20,308; (60, 2) 391 / 1,893 / 1,917 / 8,402; (70, 3, the
  default) 59 / 291 / 441 / 1,523; (80, 3) 13 / 74 / 124 / 393. The default cannot give 30 trades per half
  on XAU 60, 120, 240; the looser corners can.
- The enabled timeframes decide what a trigger is. 'ge' on XAU 15: 870 to 13 trigger bars over the 12
  threshold pairs, 448 at (70, 1); on BTC 60: 417 to 2. It is also the configuration TradingView can
  reproduce (section 11) and the kind the earlier search ended on (15m / 1h / 4h on a 15m chart). On charts
  120 and 240 it leaves two timeframes and at most 90 trigger bars in the window: not in the grid.
- The direction source: the original's three modes are three rules; the filter's timeframe, band and level
  mode decide the zone at the trigger bar (XAU 15, 1,893 triggers at (60, 2): no-direction share 0 % / 15 %
  / 53 % for band 0 / 0.25 / 0.75 with "Entry price", 0 % / 29 % / 57 % with "Signal close").
- Exits: the volatility collapse ends 10 % (BTC 15) to 52 % (BTC 240) of the default trades from 15
  minutes up and almost none below, so on / off is a first-order choice there; the earlier pick was "stop
  or reversal only" = ('none', collapse off), a grid point.

Notes for the orchestrator:
- **A2 carries weight.** Every lower-timeframe value depends on the lookahead reading; with `ltfRule`
  'last' the trigger bars move one chart bar earlier on charts above 1 minute. A pick on a chart above 1
  minute with 'all' should be re-scored with `ltfRule` 'last' before it is trusted; a 'ge' pick and every
  chart-"1" pick do not depend on it.
- **`inv` with 'orig' is replica-only** (section 8): rule C's direction twin exists for every row, but a
  pick (orig, inverted) needs a new input in the original file; a pick (fgf, inverted) is the existing
  "Trade direction: Inverted".
- **Thin cells.** XAU 60 / 120 / 240 and BTC 240 reach 30 trades per half only in the looser trigger
  corners; 'ge' on chart 60 only at threshold 50-60 with confluence 1. Most rows there are computed but
  cannot be candidates. Rows with (80, 3) are thin everywhere above 15 minutes.
- **Identical rows.** With few triggers many exit settings give the same trades ('tp3' vs 'none' when no
  target is reached, collapse on / off on the 1-minute charts where it never fires first); rule C counts
  equal results once. On chart "60" with `fgfTf` "60" and on chart "240" with "240" the filter candle is
  the chart bar: legitimate, not degenerate.
- **Memory / speed.** One period set of normalised parts per pair (about 200 MB for BTC "1"); 6 filter
  series per cell (`fgf._FILTER`: timeframe set x level mode; the band is applied per chart bar); the "240"
  set builds "480" and "960" bars from the 1-minute file once per process. One `simulate` on BTC 1 is about
  10 ms and one further trigger setting about 0.15 s (probe), so the grid fits CALIB_SPEC's 45 minutes with
  a wide margin.
- **Units.** 10 % of equity per trade makes `h1r_pct` / `h2r_pct` small numbers (a few percent at most);
  the rule only compares them, but report `h1_r` / `h2_r` next to them.
- Left out to stay in budget, in order of expected weight: the ATR periods (7 / 100 with candle range 20
  adds 30 % to 50 % more trigger bars, two thirds of the default ones kept), `lowVolThreshold` 20 / 40,
  `maxBars`, the filter's burst gate / any combo / minimum aligned zones (the earlier pick's "signal on
  every filter candle": on a chart at the filter timeframe the zone is then fixed by construction: BTC 60,
  probe: "Entry price" gives every trigger a direction for band 0 and 0.25 and none for 0.75; "Signal
  close" none for any band above 0: degenerate rows), `fgfUseZones`, `fgfAgainst`, the weights,
  `normalizationPeriod`, `emaLen` / `dcLen`, `allowReverse`, `tradeDir`, `noRepaint`.
