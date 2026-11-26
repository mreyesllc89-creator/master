# SPEC_gvl: GVLiveV2 Polymarket Pre-Candle + FGF (key `gvl`), stage 1 brief

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Read first: `$W/REPLICA_SPEC.md` (stages, interface, data, windows, cost modes), `$W/SPEC_AH.md` (Pine
built-ins, the intrabar path = "rule 4"), `$W/SWEEP_AH_SPEC.md` section 2 (prepare / simulate, 'mag',
'stress', fair halves, the trailing exit), `$W/hrd.py` (worked example: `_walk`, `summary_fast`,
`extra_fields`, `COSTS`).

Ground truth: `/home/user/master/GVLiveV2_Polymarket_PreCandle_Strategy_FGF.pine` at HEAD (1,467 lines;
`Lnnn` below are its line numbers). Where this brief and the Pine disagree, the Pine wins; say so in your
notes. Builders write `$W/gvl_a.py` / `$W/gvl_b.py` and `$W/gvl_<a|b>_notes.md`, without reading the other
build. Never edit an existing module. Never write inside `/home/user/master`. `python3 -I`, at most 2
processes, under 3 GB each.

The stage-1 probes are in `$W/gvl_spec_tmp/` (`probe_sig.py`, `probe_sim.py`, `probe_rsi.py`). **Builders
must NOT read them** (they would make the two builds share their mistakes). Their numbers are quoted below
as "probe, unverified": one implementation, no cross-check. If your two builds agree with each other and
not with a probe number, trust the builds and say so.

Seven facts shape everything below:

1. **The fused file is not "the original + the filter".** Its entry logic is the original's, but its exits
   and sizing are other code (groups "S2. Exits", "S3. Sizing"), and its defaults were re-calibrated
   (section 1). `fgfOn` False therefore does NOT reproduce the trades of
   `GVLiveV2_Polymarket_PreCandle_Strategy.pine`; it only makes the two gates true.
2. **`fgfOn` defaults to FALSE in this file** (L256). `fgf.DEFAULTS['fgfOn']` is True: pass it explicitly.
3. **Orders are placed at a bar close and fill on the next bar** (`process_orders_on_close=false`); the
   bracket is sent with the entry, in ticks from the FILL price, so a trade can open and close inside one bar.
4. **"Stop Next Candle" keeps pending price orders in two slots (id "Long", id "Short")**; they stay live
   while a position is open (the cancel rule needs a flat position), so a pending order can REVERSE a trade.
5. **The "vol score" contains no volume.** It is ATR(10) / ATR(30) rescaled (L848-852). Volume is read only
   by `f_rvol` (`preUseRvol`, default off) and by alert / plot text.
6. **Sizing caps bite.** Gold: "Risk %" wants 200 to 4,200 oz, `maxQty = 50` caps every single default trade
   at 50 oz (probe: 100 % of the arm candles on every gold chart). BTC: the default position is LARGER than
   the account on most candles (probe: 99.9 % of arm candles on the 5-minute chart, 88 % on 60, 13 % on 240),
   and `strategy()` sets no margin, so TradingView's default Margin 100 % would most likely refuse those
   entries (G14: not modelled by default; a switch and a counter exist).
7. **The daily lock is the dominant gate on low timeframes.** "Max Losing Trades Per Day" = 3 per New York
   calendar day is on by default; probe: the lock is in force on 68 % of the BTC 5-minute candles, 27 % on
   15, 2 % on 60. On a 1-minute chart only the first two minutes of every 5-minute window may place an order.

---------------------------------------------------------------------------------------------------

## 1. What the file is made of

| part | lines | replica |
|---|---|---|
| header (Update 1 text, the earlier calibration record) | 1-133 | read it; not a source of numbers |
| `strategy()` | 134 | section 2 |
| inputs of the strategy | 139-248 | section 3 |
| FlashGold Direction Filter block | 250-832 | `$W/fgf.py`, never reimplemented. Checked with `diff` against the block `fgf.py` replicates (trailing-TP XPW file, its lines 402-982): three differences, none of them logic: `FGF_FORCE_OVERLAY = false` (drawing), `fgfOn` default `false`, and the "FGF permission ended" plotshape is left out |
| `gvInv` (Update 1) | 835, 1041-1046, the `gvInv ? :` in 1058, 1124, 1143, 1240-1319, 1369-1370, 1406 | section 8 |
| series, radar, arms, signals | 840-939 | `prepare`, section 4 |
| sessions, 5-minute window, gates | 961-990 | `prepare`, section 4 |
| JSON / label helpers | 1048-1158 | ignored |
| sizing `f_get_qty` | 1160-1171 | `simulate`, section 9 |
| daily lock | 1176-1203 | `simulate`, section 7 |
| exit geometry, `can_enter`, the five order blocks | 1210-1319 | `simulate`, sections 6-7 |
| bars in trade, the four `strategy.close` blocks | 1322-1354 | `simulate`, section 7 |
| plots, tables, training capture | 1359-1467 | ignored. The file is at the 64-plot limit: it has NO "FGD" funnel plots, so `raw_*` / `blocked_*` are defined by this brief (section 7) |

Against the unfused original (`diff` of the code outside the filter block): identical are the series, the
radar, the arms, the EMA-cross signals, the sessions, the 5-minute window, the daily lock, the order of the
order blocks, the cancel rule, the bars-in-trade code. Different: (a) the four entry conditions end with
`and fgfBuyOk` / `and fgfSellOk`; (b) Update 1; (c) the original's exits (`stop=` / `limit=` at absolute
prices from the PLANNED entry, `ATR_SL_MULTIPLIER 2.0`, `ATR_TP_MULTIPLIER 2.0`, a trailing stop on by
default with price distances passed as ticks) are replaced by tick distances from the fill (L1210-1219);
(d) the original's sizing (`useDynamicRisk`, `tradeQty`, `minQty`) is replaced by `f_get_qty`; (e) a second
time stop `maxBarsHeld` (L1337-1342); (f) defaults: EMA 5/13 -> 8/21, radar Auto -> Chart, vol rise 0 -> 1,
close location 0.55 -> 0.65, `useMaxBarsExit` true -> false, `maxDailyLossCurrency` 150 -> 0.
So the REPLICA_SPEC self-check "`fgfOn` False reproduces the original" becomes here: with `fgfOn` False the
four entry conditions are, token for token, the original's L435 / L458 / L486 / L502, and `prepare` with
the original's signal defaults gives the original's arms and signals (same code). The original's exits and
sizing are not replicated. With `gvInv` false every `gvInv ? a : b` is `b` and the six `gv*` names are the
previous literals: the file is the pre-Update-1 file.

---------------------------------------------------------------------------------------------------

## 2. The `strategy()` call (L134)

```
strategy("GVLiveV2 | Crypto Polymarket Any-Chart Pre-Candle [Update 1]", shorttitle="GVLiveV2 Poly PreArm U1",
  overlay=true, initial_capital=100000, default_qty_type=strategy.fixed, default_qty_value=1,
  commission_type=strategy.commission.percent, commission_value=0, slippage=0,
  calc_on_every_tick=true, calc_on_order_fills=true, process_orders_on_close=false, pyramiding=0,
  max_labels_count=500, max_lines_count=500, max_bars_back=500)
```

| argument | meaning for the replica |
|---|---|
| `initial_capital=100000` | `INITIAL_CAPITAL = 100000.0` (not the 1,000,000 of SPEC_AH rule 7). Net % depends on it: `maxQty = 50` and `qtyStep = 0.001` are absolute |
| `default_qty_type=fixed`, `default_qty_value=1` | never used: every `strategy.entry` passes `qty=entry_qty` |
| `commission_value=0` (percent), `slippage=0` | cost mode 'tv' = NO cost at all, fills at the raw prices. TradingView's own report is cost-free |
| `process_orders_on_close=false` | a market order placed in the run of bar i fills at the OPEN of bar i+1 (SPEC_AH rule 1); a stop / limit order placed in that run is live from bar i+1 on |
| `calc_on_every_tick=true` | live only. History: one run per bar at its close |
| `calc_on_order_fills=true` | extra script runs right after every fill, also on history. Section 5, assumption G1 |
| `pyramiding=0` | one entry per side. The script never sends a same-side entry while in a position (`can_enter` needs a flat position). An opposite `strategy.entry` that fills while a position is open closes it and opens the new one (reversal, G8) |
| not set: `margin_long`, `margin_short` | Pine v6 default 100 %. Not modelled by default; replica switch `tvMargin` and counters (G14, section 9) |
| not set: `close_entries_rule` | FIFO; irrelevant (one trade open at a time) |
| not set: `backtest_fill_limits_assumption` | 0: a limit order fills when price touches it |
| not set: `use_bar_magnifier` | false = path 'tv'; path 'mag' (stage 3) = Bar Magnifier on |
| `overlay`, `max_*` | drawing / buffers: ignored |

Symbol constants: `syminfo.mintick = 0.01`, `syminfo.pointvalue = 1`, both pairs. `timeframe.period` =
the chart string ("1", "5", "15", "30", "60", "120", "240"); `timeframe.in_seconds` = minutes x 60.
`time` = `t_open` x 1000 (ms), `bar_index` = the row number in the data file.

---------------------------------------------------------------------------------------------------

## 3. Inputs

### 3.1 SIGNAL inputs -> `prepare(pair, chart_tf, params)` (per-bar arrays; nothing here depends on a position)

| Pine name (line) | default | used for |
|---|---|---|
| `devLen`, `fastVoVixLen`, `slowVoVixLen` (140-142) | 30, 10, 30 | `expansion_regime` (EMA-cross signals only) AND the vol score (`ta.atr(fastVoVixLen)`, `ta.atr(slowVoVixLen)`) |
| `fastEmaLen`, `slowEmaLen` (148-149) | 8, 21 | EMA cross (signals only); `fastEmaLen` also the radar EMA slope |
| `trendFilterLen` (150) | 100 | `upTrend` / `downTrend`: the signals, and the arms when `preUseTrend` |
| `useRsiFilter`, `rsiLen`, `rsiOverbought`, `rsiOversold` (156-159) | true, 14, 70, 30 | the EMA-cross signals ONLY (never the arms) |
| `usePreCandleArm` (216) | true | false = no arm |
| `radarTimeframeMode` (218) | "Chart" | "Auto", "Chart", "1", "3", "5", "15", "30", "60", "120", "240" (section 4.2) |
| `preMinVolScore`, `preMinVolRise` (220-221) | 35.0, 1.0 | `preVolOk` |
| `preCloseLocation` (222) | 0.65 | pressure test of the arm candle |
| `preUseTrend` (223) | true | arm needs `upTrend` / `downTrend` |
| `preUseEmaSlope` (224) | false | radar EMA slope sign |
| `preUseRvol`, `preRvolLength`, `preMinRvol` (225-227) | false, 20, 1.10 | relative volume (the only use of volume) |
| `preUseBodyAtr`, `preMinBodyAtr` (228-229) | false, 0.20 | body / ATR(14) |
| `preUseMicroBreak`, `preBreakoutLookback` (230-231) | false, 2 | close beyond the previous highs / lows |
| `allowAnyChartTimeframe`, `requiredSignalTimeframe` (207, 206) | true, "240" | `timeframe_ok` |
| `maxSignalSecondsAfterWindowStart` (208) | 90 | `poly_window_time_ok` (binds on chart "1" only) |
| `allowWeekendEntries` (213) | true | `weekday_ok` |
| `useSessionFilter`, `tradePreset`, `entry_session`, `morning_entry_session`, `flat_session` (244-248) | false, "Balanced", "0945-1530", "0945-1115", "0930-1545" | entry window, weak-bar block, `flat_window_ok` (G17) |
| `fgfOn` (256) and every other `fgf*` input | **false**; the rest as `fgf.DEFAULTS` | `fgf.fgf_permissions` -> `buyOk`, `sellOk`; with `fgfOn` False use all-True arrays and do not call it |
| replica: `start`, `end` | the pair's window | window by `t_close`, as `hrd.py` |
| replica: `risingRule` | 'any' | G15: 'any' or 'mono' |

### 3.2 ORDER / EXIT inputs -> `simulate(P, x)` (also accepted by `prepare` / `run` as defaults)

| Pine name (line) | default | used for |
|---|---|---|
| `preCandleEntryMode` (217) | "Market Next Candle" | "Signal Only" (arms place nothing), "Market Next Candle", "Stop Next Candle" |
| `preStopAtrBuffer` (232) | 0.03 | pending price = high + / low - `ta.atr(14)` x this |
| `preCancelAfterBars` (233) | 2 | cancel rule (1..10) |
| `oneSignalPerPolyWindow` (209) | true | one order per 5-minute window (state: set when an order is PLACED) |
| `ExitMode` (169) | "ATR" | "Points" / "ATR" |
| `slPoints`, `tpPoints` (170-171) | 16500, 82500 | Points mode, ticks; 0 = none |
| `atrLen` (172) | 14 | `exitAtr = ta.atr(atrLen)`: keep an ATR cache per length in `P` |
| `slAtrMult`, `tpR` (173-174) | 1.0, 5.0 | stop = mult x ATR; target = stop distance x `tpR` (0 = no target) |
| `useTrail` (175) | false | trailing stop in the same `strategy.exit` |
| `trailActPoints`, `trailPoints` (176-177) | 99000, 16500 | Points mode, ticks |
| `trailActAtr`, `trailDstAtr` (178-179) | 6.0, 1.0 | ATR mode |
| `maxBarsHeld` (180) | 0 | time stop, bars; 0 = off |
| `QtyMode`, `fixedQty`, `riskPct`, `maxQty`, `qtyStep`, `capMargin`, `marginPct` (183-189) | "Risk %", 10, 1.0, 50, 0.001, true, 1.0 | `f_get_qty` (section 9) |
| `brokerPreset`, `manualPointValue` (165-166) | "Manual / custom", 1.0 | the script's `pointValue` for SIZING only (P/L uses `syminfo.pointvalue` = 1) |
| `useMaxBarsExit`, `maxBarsInTrade` (193-194) | false, 1 | the older bar exit |
| `useDailyLossLock`, `maxDailyLossCurrency`, `maxDailyLosses` (195-197) | true, 0.0, 3 | daily lock (section 7 step C1) |
| `useMaxStopDistance`, `maxStopDistancePoints` (198-199) | false, 8.0 | `stop_distance_ok` (price units) |
| `gvInv` (835), alias `inv` | false | Update 1 (section 8). Raise if both are given and disagree |
| replica: `path` | 'tv' | 'tv'; 'mag' raises `NotImplementedError` until stage 3 |
| replica: `cost` | 'tv' | 'tv' / 'ours' / 'stress' (section 9) |
| replica: `tvMargin` | 0.0 | G14: 0 = TradingView's margin rules not modelled; 100.0 = entries larger than the account are refused |

`simulate` raises if `x` holds a 3.1 key (as `hrd.simulate`). Validate as the Pine inputs do: option
strings exactly as written (else `ValueError`), `preCancelAfterBars` 1..10, `maxDailyLosses >= 1`,
`maxBarsInTrade >= 1`, `atrLen >= 1`, `slAtrMult >= 0.01`, `preCloseLocation` 0.50..0.95,
`maxSignalSecondsAfterWindowStart` 0..299, every other number >= 0.

### 3.3 Accepted, no effect

- `preMinScore` (219, default 60): the arm requires all seven conditions (L933-934), and then the score is
  25 + 20 + 15 + 10 + 10 + 10 + 10 = 100 >= any allowed `preMinScore`. Inert. `preLongEntryArm =
  preLongArm and preLongScore >= preShortScore` (L1228) is therefore `preLongArm`; `preShortEntryArm`
  (L1229) is `preShortArm and preLongScore < 100`, i.e. `preShortArm and not preLongArm`. Implement the
  scores literally anyway (both arms can be true only with `preCloseLocation` 0.50, trend and slope off,
  on a candle with `closeLocation == 0.5`; then the LONG wins).
- `riskPercent = riskPct` (190): JSON only.

### 3.4 Drawing / alerts only: listed once, ignored

`maxLiveSpreadPoints`, `routerStrategyName`, `seriesSlug`, `routerTimeframe`, `paperStakeUsd`,
`sendEntryAlertsToWebhook`, `sendExitAlertsToWebhook`, `showPreDebug`, `collectTrainingData`,
`includeTrainingDataInAlerts`, `plotTrainingData`, `showTrainingLabels`, `trainingLabelHistory`; the
filter's `fgfShowBg`, `fgfShowLv`, `fgfSigMark`, `fgfShowTbl`, `fgfTblPos`, `fgsShow`, `fgsWin`, `fgsH`.
Also ignored: `f_training_json`, `f_training_label`, `f_alert_message`, the local `expected_entry`,
`stop_loss`, `take_profit` (alert text only: the real bracket is in ticks from the fill), the `training*`
variables, every plot, both tables. Any other unknown key: `ValueError`.

---------------------------------------------------------------------------------------------------

## 4. `prepare`: series, radar, arms, signals, gates

Every series is computed on the WHOLE data file from row 0 (`$W/data/<PAIR>_<TF>.parquet`, volume from
`<PAIR>_<TF>_vol.parquet`, same rows), then the window rows are kept (`w0 = searchsorted(t_close, start,
'left')`, `w1 = searchsorted(t_close, end, 'right')`). `x[1]` = the previous row of the file. na can only
occur in the first ~100 rows of a file (2011 / 2012), years before the windows, so for the finite-window
functions any consistent na handling gives the same window values. To keep the two builds bit-equal use
these formulas to the letter:

- `ta.atr(n)` = `ta.rma(ta.tr(true), n)`: `tr[0] = high[0] - low[0]`, `tr[i] = max(max(high - low,
  abs(high - close[i-1])), abs(low - close[i-1]))`; `atr[n-1]` = the plain mean of `tr[0..n-1]` summed in
  index order; then with `alpha = 1.0 / n`: `atr[i] = alpha * tr[i] + (1.0 - alpha) * atr[i-1]`; na before
  row `n-1` (this is `fgf._atr`).
- `ta.ema(x, n)`: `alpha = 2.0 / (n + 1)`, `ema[0] = x[0]`, `ema[i] = alpha * x[i] + (1.0 - alpha) * ema[i-1]`.
- `ta.rsi(close, n)`: `ch[i] = close[i] - close[i-1]` (i >= 1), `u = max(ch, 0)`, `d = max(-ch, 0)`; RMA of
  each seeded with the plain mean of rows 1..n (first value at row n), `alpha = 1.0 / n`; `rsi = 100 if d
  == 0 else 0 if u == 0 else 100 - 100 / (1 + u / d)`.
- `ta.sma(x, n)[i]` = `(x[i-n+1] + ... + x[i]) / n` summed oldest to newest (a fresh sum per row, no
  running sum); na if any term is na.
- `ta.stdev(x, n)[i]` (population): `m` = that mean; `sqrt((sum over the same rows, oldest to newest, of
  (x[k] - m)^2) / n)`.
- `ta.crossover(a, b)` = `a > b and a[1] <= b[1]`; `ta.crossunder(a, b)` = `a < b and a[1] >= b[1]`.
- `ta.highest(high[1], n)[i]` = `max(high[i-n .. i-1])`; `ta.lowest(low[1], n)[i]` = `min(low[i-n .. i-1])`.
- A comparison with na is false; `nz(x, y)` = `y` when `x` is na.

### 4.1 Chart series (L840-893, 916-917, 938-939)

```
atr_value = ta.atr(14)                                   # fixed 14: the pending price buffer, body/ATR
vsrc      = (ta.atr(fastVoVixLen) - ta.atr(slowVoVixLen)) / (ta.stdev(ta.atr(fastVoVixLen), devLen) + 1e-6)
dev       = ta.stdev(vsrc, devLen)
fastDEVMA = ta.sma(dev, fastVoVixLen) ; slowDEVMA = ta.sma(dev, slowVoVixLen)
expansion_regime = (fastDEVMA > slowDEVMA) or ta.rising(fastDEVMA, 2)          # G15
fastEma, slowEma, trendEma = ta.ema(close, fastEmaLen / slowEmaLen / trendFilterLen)
rsiVal    = ta.rsi(close, rsiLen)
rsiLongCondition  = not useRsiFilter or rsiVal < rsiOverbought
rsiShortCondition = not useRsiFilter or rsiVal > rsiOversold
bullCross = ta.crossover(fastEma, slowEma) ; bearCross = ta.crossunder(fastEma, slowEma)
upTrend   = close > trendEma ; downTrend = close < trendEma
barRange  = high - low
closeLocation = (close - low) / barRange  if barRange > 0  else 0.50
longCondition  = bullCross and upTrend   and expansion_regime and rsiLongCondition      -> sigL
shortCondition = bearCross and downTrend and expansion_regime and rsiShortCondition     -> sigS
```

### 4.2 The radar (L848-874, 895-914)

```
f_vol_score()  : fa = ta.atr(fastVoVixLen); sa = ta.atr(slowVoVixLen)
                 atrRatio = fa / sa  if sa > 0  else 1.0
                 max(0.0, min(100.0, (atrRatio - 0.50) / 1.50 * 100.0))
f_ema_slope(n) : e = ta.ema(close, n);  e - nz(e[1], e)
f_rvol(n)      : a = ta.sma(volume, n); 1.0 if (na(volume) or na(a) or a <= 0) else volume / a
f_body_atr()   : a = ta.atr(14);        abs(close - open) / a  if a > 0  else 0.0
f_break_long(n): close > ta.highest(high[1], n)      f_break_short(n): close < ta.lowest(low[1], n)
```

The radar timeframe: "Chart" = the chart; a number = that timeframe; "Auto" (L854-856) = "60" for a chart
of a day or more, "15" for >= 240 minutes, "5" for >= 60, "3" for >= 30, "1" for >= 15, else the chart.
`useRadarTimeframe = radarTimeframe != timeframe.period and radarSeconds < chartSeconds`: the radar is
read from another timeframe ONLY when that timeframe is strictly LOWER than the chart; otherwise the five
functions run on the chart bars (default "Chart": always the chart). When it is used: compute the function
on the radar timeframe's own bars from its row 0 (`fastEmaLen`, `preRvolLength`, `preBreakoutLookback`,
the VoVix lengths as given; volume = that timeframe's `_vol` file), then on a chart bar closing at `Tc`
take the value of the LAST radar bar with `t_close <= Tc` (SPEC.md rule; na if none). "3" has no file:
build it from the 1-minute file as `build_bars.py` does (`fgf._bars(pair, '3')` does that; for volume sum
the 1-minute volumes over the same groups). Then, on the chart series:

```
radarVolScore, radarSlope, radarRvol, radarBodyAtr, radarBreakLong, radarBreakShort   (radar or chart)
radarVolRise = radarVolScore - nz(radarVolScore[1], radarVolScore)      # [1] = the previous CHART bar
```

### 4.3 The arms (L919-934)

```
preVolOk  = radarVolScore >= preMinVolScore and radarVolRise >= preMinVolRise
preRvolOk = not preUseRvol    or radarRvol    >= preMinRvol
preBodyOk = not preUseBodyAtr or radarBodyAtr >= preMinBodyAtr
long : trendOk = not preUseTrend or upTrend     slopeOk = not preUseEmaSlope or radarSlope > 0
       pressureOk = closeLocation >= preCloseLocation          breakOk = not preUseMicroBreak or radarBreakLong
short: trendOk = not preUseTrend or downTrend   slopeOk = not preUseEmaSlope or radarSlope < 0
       pressureOk = closeLocation <= 1.0 - preCloseLocation    breakOk = not preUseMicroBreak or radarBreakShort
score = 25*volOk + 20*trendOk + 15*slopeOk + 10*rvolOk + 10*bodyOk + 10*pressureOk + 10*breakOk   (per side)
preLongArm  = usePreCandleArm and [all seven long conditions]  and preLongScore  >= preMinScore
preShortArm = usePreCandleArm and [all seven short conditions] and preShortScore >= preMinScore
armL = preLongArm  and preLongScore  >= preShortScore            (preLongEntryArm,  L1228)
armS = preShortArm and preShortScore >  preLongScore             (preShortEntryArm, L1229)
```

`barstate.isconfirmed` (L933-934) is true in the bar-close run on history. Write `1.0 - preCloseLocation`
exactly so. A zero-range candle has `closeLocation = 0.50`.

### 4.4 Clocks and gates (L961-986)

All clocks are read at the bar's OPEN (`time`). New York time = `America/New_York` with daylight saving
(`zoneinfo` / pandas `tz_convert`).

```
polyWindowStartMs = time - (time % 300000)                               -> win  (int64)
secondsFromPolyWindowStart = int((time - polyWindowStartMs) / 1000)
poly_window_time_ok = secondsFromPolyWindowStart <= maxSignalSecondsAfterWindowStart
timeframe_ok   = allowAnyChartTimeframe or chart_tf == requiredSignalTimeframe
weekday_ok     = allowWeekendEntries or (New York weekday of the open is not Saturday / Sunday)
entry_window_ok = not useSessionFilter or entry_session_active                         (G17)
flat_window_ok  = not useSessionFilter or flat_session_active            -> flatOk
balanced_weak_entry_bar = useSessionFilter and tradePreset == "Balanced" and ny_hhmm in (1245, 1345, 1400, 1500)
gate = timeframe_ok and poly_window_time_ok and entry_window_ok and weekday_ok and not balanced_weak_entry_bar
ny_day_key = year*10000 + month*100 + dayofmonth of the open in New York (L1176)  -> day (int64)
```

`entry_session_active` = the "Conservative AM" preset ? in `morning_entry_session` : in `entry_session`.
`gate` is the position-free part of `can_enter` (L1223); the rest of `can_enter` is in `simulate`.

What they mean on our bars (checked): on every chart of 5 minutes or more, both pairs, every bar opens on
a 5-minute boundary, so `secondsFromPolyWindowStart == 0` on all bars, each bar is its own window and
`oneSignalPerPolyWindow` can never bind (one order per run at most). On chart "1" the seconds are 0, 60,
120, 180, 240: with the default 90 only the bars opening at minute 0 and 1 of each 5-minute window pass
(BTC 416,072 of 1,039,430 window bars; XAU 197,559 of 493,819), and at most one order is placed per window.
The New York day changes at 04:00 or 05:00 UTC: on BTC "240" the first bar of a day is the 04:00 UTC bar
in summer and the 08:00 UTC bar in winter; on gold (session 18:00-17:00) the day changes in mid-session,
on "240" at the 02:00 bar. Window days: BTC 731, XAU 453.

### 4.5 What `P` holds

`pair`, `tf`, `start`, `end`, `mid = start + (end - start) // 2`, `w0`, `w1`, `n`, `rows` (file rows of
the window bars), window arrays `open high low close t_open t_close`, `armL armS sigL sigS` (bool),
`buyOk sellOk` (bool), `gate flatOk` (bool), `win day` (int64), `atr14` (= `atr_value`), an ATR cache per
`atrLen` (window slice; compute on demand from the file), the resolved `prepare` parameters, and the
position-free counts `arms_long`, `arms_short`, `sig_long`, `sig_short` (window bars with `armL`, `armS`,
`sigL`, `sigS`). Nothing in `P` may depend on a 3.2 input.

Cache inside the module, keyed by `(pair, tf)`: the bars, each ATR / EMA / RSI by length, the vol score
and `expansion_regime` by their lengths; keyed by `(pair, tf, start, end, the fgf parameters)`: the filter
permissions. A calibration cell calls `prepare` several hundred times with other thresholds: after the
first call a `prepare` must cost a few vector comparisons.

Reference counts, default inputs, full windows (probe, unverified):

| cell | window bars | `armL` / `armS` | `sigL` / `sigS` | `sigL` / `sigS` with `risingRule` 'mono' |
|---|---|---|---|---|
| BTC 1 | 1,039,430 | 33,909 / 36,634 (30,710 on `gate` bars) | 9,627 / 9,491 | 9,393 / 9,279 |
| BTC 5 | 210,155 | 5,203 / 5,830 | 2,080 / 2,008 | 2,040 / 1,964 |
| BTC 15 | 70,058 | 1,746 / 1,883 | 679 / 640 | 660 / 628 |
| BTC 30 | 35,032 | 918 / 961 | 301 / 335 | 293 / 323 |
| BTC 60 | 17,518 | 474 / 536 | 167 / 182 | 164 / 177 |
| BTC 120 | 8,760 | 254 / 297 | 82 / 74 | 79 / 71 |
| BTC 240 | 4,381 | 127 / 130 | 43 / 39 | 42 / 38 |
| XAU 1 | 493,819 | 13,440 / 13,331 (12,051 on `gate` bars) | 4,847 / 4,660 | 4,735 / 4,550 |
| XAU 5 | 98,787 | 2,537 / 2,495 | 941 / 937 | 923 / 913 |
| XAU 15 | 32,935 | 820 / 719 | 287 / 273 | 283 / 268 |
| XAU 30 | 16,471 | 429 / 392 | 151 / 120 | 149 / 118 |
| XAU 60 | 8,238 | 260 / 190 | 75 / 62 | 71 / 61 |
| XAU 120 | 4,493 | 161 / 102 | 48 / 33 | 45 / 31 |
| XAU 240 | 2,246 | 81 / 50 | 26 / 15 | 25 / 15 |

No default bar has both arms. The RSI filter removes 1 to 3 % of the EMA-cross signals and no arm (BTC 60:
172 -> 167 long, 187 -> 182 short).

---------------------------------------------------------------------------------------------------

## 5. How TradingView runs this script on history (G1)

Documented, used here: (a) history bars: the script runs once per bar at its close; `barstate.isconfirmed`
is true there. (b) `process_orders_on_close=false`: orders of that run are processed from the next bar on.
(c) `calc_on_order_fills=true`: the script runs again right after every order fill, on history too; on a
history bar such a run sees the bar's final open / high / low / close (the manual warns that this lets a
strategy act on a bar's close before it closed), starts from the variables as they were at the end of the
previous bar (the changes of an extra run are rolled back before the next run on the same bar), and an
order it places is processed at the next of the bar's four price points. tradingview.com cannot be
reached from this session: (c) is the documentation as remembered and cannot be tested.

What an extra run can do in THIS script:
- After an ENTRY fill the position is not flat: `can_enter` is false, the cancel block (L1284) is skipped,
  `barsInTrade` is 0, so no order, no cancel and no close can come out of it (with the defaults; with a
  daily $ lock, the session filter, or a time stop on a trade that inherited its bar count (C5), a
  `strategy.close` could). The bracket was sent with the entry and is not re-sent. Nothing changes.
- After an EXIT fill the position is flat. The run sees the final candle and the same equity the bar-close
  run will see, so it takes exactly the decision the bar-close run of that candle takes: the same arm or
  signal, the same gates (the daily count is recomputed inside the run), the same quantity and ticks. If
  that decision is an entry, TradingView would place it there and then; the cancel block would also act
  there and then.

**G1. One decision run per bar, at its close.** The replica runs the script once per chart bar, after the
bar's fills, and treats the extra runs as changing nothing: an order decided on bar j is placed at j's
close and can fill from bar j+1 on; a cancel takes effect at j's close. Consequences:
- **Same-bar exit: yes.** The bracket belongs to the entry order, so it is live from the fill: a market
  entry filled at the open of bar k, or a pending order filled inside bar k, can be stopped or reach its
  target later in bar k (probe: 20 to 25 % of the default trades up to the 60-minute chart, under 10 % on
  "240"; `zero_length`).
- **Same-bar re-entry: never.** After an exit inside (or at the open of) bar j the earliest new entry is
  decided at j's close and fills at the open of j+1 ("Market") or along bar j+1 ("Stop").
- Why this reading: it is what the Pine header states for its own calibration ("market entries at the
  next open"); it is how the script trades live (the arms need the confirmed close, the fill is the next
  tick, i.e. the next open); it is exact for the arms if TradingView reports `barstate.isconfirmed` false
  in the extra runs (then no arm can fire in them, only an EMA-cross signal could; the documentation does
  not settle this); and one entry model keeps 'mag' == 'tv' testable on chart "1". For "Stop" orders it
  changes nothing: the order price lies beyond the candle's range (`preStopAtrBuffer > 0`), so the order
  could not fill inside bar j anyway (with a buffer of exactly 0 it sits on the extreme and TradingView
  could fill it there: outside the grid).
- What TradingView most likely shows instead for a MARKET entry decided on an exit bar: a fill at the next
  of its four price points of bar j: the first extreme if the exit was at the open or on the first leg,
  the second extreme if on the second leg, the close if on the third. That is a fill at the candle's
  extreme in the direction of the move (a sell at the low of a candle that closes low), usually WORSE than
  the next open. This is frequent (probe: 15 to 25 % of the default trades are entered by an order decided
  on an exit bar, nearly all after an exit on the second leg), so it is counted and estimated, not
  modelled: trade column `reentry`, summary `reentry_same_bar`, `reentry_extreme`, `reentry_gap_r`
  (section 12). Report them next to every 'tv' result.
- "Stop" mode only: TradingView's run after an exit would execute the cancel block at once; the replica
  cancels at the close, so a pending order can still fill in the rest of that bar. Counted:
  `pend_fill_after_exit`.

---------------------------------------------------------------------------------------------------

## 6. The broker inside a bar (path 'tv')

### 6.1 Orders the script can place (all of them)

| call (lines) | type | replica |
|---|---|---|
| `strategy.entry(gvBuyId, ...)` in block 1 (1243 / 1246) and block 4 (1292) | 1243: stop (limit when inverted) at `preLongStopPrice`; 1246, 1292: market | order with `sig = +1` |
| `strategy.entry(gvSellId, ...)` in block 2 (1266 / 1269) and block 5 (1308) | 1266: stop (limit when inverted) at `preShortStopPrice`; 1269, 1308: market | order with `sig = -1` |
| `strategy.exit(gvBuyExit / gvSellExit, from_entry, loss, profit[, trail_points, trail_offset])` (1257/1259, 1280/1282, 1301/1303, 1317/1319) | bracket of that entry id, in ticks | the ticks stored with the order |
| `strategy.cancel("Long")`, `strategy.cancel("Short")` (1285-1286) | removes pending entry orders | empties both slots |
| `strategy.close("Long" / "Short")` (1333/1335, 1340/1342, 1346/1348, 1352/1354) | market close at the next open | `close_req` |

Ids: "Long" is always a real buy, "Short" a real sell (Update 1 keeps that). One order slot per id. An
order: `{slot = real side d, sig, type: market | price, P and trig for a price order, qty, slTicks,
tpTicks, trActTicks, trDstTicks, kind (1 pre-candle market, 2 pre-candle price, 3 EMA-cross signal), placed
bar, reentry code}`. A new order for a slot replaces what is in it (G7). The script places at most ONE
entry order per run, and only when flat. In "Market" and "Signal Only" modes every order is a market
order, filled at the next open: the slots are empty during a bar. In "Stop" mode a slot can hold a price
order for many bars.

Price orders: `sig = +1`: `P = high + atr_value * preStopAtrBuffer` of the placing candle, `trig = +1`
(fires when price >= P). `sig = -1`: `P = low - atr_value * preStopAtrBuffer`, `trig = -1` (fires when
price <= P). Normal: a buy stop / a sell stop. Inverted: a sell LIMIT at the same `P` / a buy LIMIT at the
same `P`. Trigger and fill price are identical for the stop and the limit (G6); only the real side differs.

A pending order is always on the side opposite to an open position or the position is flat (a slot is
filled only when flat, and a fill empties it). Assert it. So a pending order that fills while a position is
open is always a REVERSAL: the open trade is closed at the fill price (kind 'reverse') and the order's
quantity opens the new trade with the order's ticks.

### 6.2 A trade's levels, fixed at its fill at price `e`, real side `d` (ticks of the bar that PLACED the order)

```
mintick = 0.01
SL  = e - d * (slTicks * mintick)        exists if slTicks > 0
TP  = e + d * (tpTicks * mintick)        exists if tpTicks > 0
if useTrail:  A = e + d * (trActTicks * mintick) ;  off = trDstTicks * mintick
              armed = (trActTicks <= 0) ;  best = e
```
No rounding to the tick grid, no tolerance, inclusive comparisons (as `hrd._walk`). The stop in force for a
long is `S* = max(SL, best - off if armed)`; for a short `S* = min(SL, best + off if armed)`; a missing
level does not take part. A stop fill is kind 'trail' if the trailing stop is the level hit (for a long
`best - off >= SL`, or no `SL`), else 'sl'.

### 6.3 One bar `j`, steps A and B (step C, the script, is section 7)

`exleg = 0` at the start of every bar; it becomes 1 for an exit fill at the open or on leg 0, 2 on leg 1,
3 on leg 2 (the LAST exit fill of the bar counts).

**A. The open `o`.**
- A1. `close_req` set and a position open: close it at `o`, kind = `close_req`; `exleg = 1`. Clear `close_req`.
- A2. A market order in a slot: fill at `o` (the position is flat here; assert), subject to G14. Its
  levels from `e = o`.
- A3. A position that was open BEFORE this bar (not one opened in A2), in this order (long; a short with
  the inequalities turned and `min` for `max`): `o <= S*` -> exit at `o` ('sl' / 'trail'), `exleg = 1`;
  else `TP` exists and `o >= TP` -> exit at `o` ('tp'), `exleg = 1`; else, with `useTrail`: if `armed`,
  `best = max(best, o)`, else if `o >= A`: `armed = True`, `best = o`.
- A4. Price orders, the older placement first: `trig +1` and `o >= P`, or `trig -1` and `o <= P` -> fill at
  `o` (G14 applies): a reversal if a position is open (close it at `o`, kind 'reverse'), else a fresh
  trade. Its levels from `e = o`.

**B. The path.** `v1, v2` = `high, low` if `(high - open) < (open - low)` else `low, high` (a tie goes low
first); three legs `o -> v1`, `v1 -> v2`, `v2 -> close`. On a leg from `cur` to `b` (skip if equal), loop:

```
UP leg (b > cur), candidates:                                DOWN leg (b < cur), candidates:
  long open,  TP exists, b >= TP  -> at max(TP, cur), 'tp'     short open, TP exists, b <= TP -> at min(TP, cur), 'tp'
  short open, S* exists, b >= S*  -> at max(S*, cur), stop     long open,  S* exists, b <= S* -> at min(S*, cur), stop
  price order trig +1, b >= P     -> at max(P, cur)            price order trig -1, b <= P    -> at min(P, cur)
take the candidate reached FIRST (UP: the lowest price; DOWN: the highest). Tie: the exit before the order.
  exit   -> close the trade there; exleg = leg + 1
  order  -> fill there (G14): reversal if a position is open (kind 'reverse'; a reversal does not set exleg), else a
            fresh trade; levels from e = that price
  then cur = that price and loop again on the rest of the leg (the new trade is walked on it: 6.2 at once)
no candidate -> if the leg favours the open trade (UP for a long, DOWN for a short) and useTrail: if armed, best = the
            better of best and b (max for a long, min for a short); else if b has reached A (b >= A long, b <= A
            short): armed = True, best = b. Leg done.
```
`S*` is fixed along an adverse leg (the trail does not move on it). On a favourable leg the target is
tested before the trail arms, so a target at or inside the activation distance means the trail never acts.
In "Market" / "Signal Only" modes there is no price order and B is `hrd._walk` for the one open trade.

Worked checks (ticks 300 / 1500, i.e. stop distance 3.00, target distance 15.00, no trail):
- Market long filled at the open 100.00; bar O 100.00 H 100.80 L 96.50 C 97.00: path O-H-L-C; the fall to
  96.50 meets `SL` 97.00: exit 97.00, 'sl', same bar (`entry_bar == exit_bar`).
- "Stop", `sig +1`, `P` 101.03; next bar O 100.50 H 101.50 L 100.20 C 101.40: path O-L-H-C; the rise meets
  101.03: long at 101.03 (`SL` 98.03, `TP` 116.03); nothing else. Inverted: the same fill is a SHORT at
  101.03 (`SL` 104.03, `TP` 86.03).
- The same order, next bar opens at 101.20: fill at 101.20 (A4), levels from 101.20.
- Long from 101.03 (`SL` 98.03) and a pending `sig -1` order at `P` 99.47, quantity 2.5, ticks 280 / 1400;
  bar O 100.40 H 100.60 L 98.90 C 99.10: path O-H-L-C; on the fall 99.47 comes before 98.03: the long is
  closed at 99.47 ('reverse'), a short of 2.5 opens at 99.47 (`SL` 102.27, `TP` 85.47) and is held.
- Trail (ticks loss 300, profit 0, `trail_points` 100, `trail_offset` 75), long from 100.00, on the next
  bar O 100.20 H 101.60 L 99.90 C 100.50: path O-L-H-C; the rise to 101.60 arms it; the fall to 100.50
  meets 101.60 - 0.75 = 100.85: exit 100.85, 'trail'.

**Window.** Flat, empty slots, clean variables at the first window bar; its run is the first decision, so
the first possible fill is on the second window bar. On the last window bar A, B and C run; then an open
trade is closed at the last close (kind 'end', exit cost charged, `exit_time = t_close`); orders placed or
still pending there are dropped (`pend_open_end`).

**Path 'mag' (stage 3, not built now; keep A3, A4 and B in one function so that it can be swapped).** A1 and
A2 stay on the chart bar's open. Then every 1-minute sub-bar of the chart bar (rows of `<PAIR>_1` with
`t_open` in `[t_open[j], t_close[j])`), in time order: A3 and A4 at its own open (for the first sub-bar that
is the chart open), then B on its own open / high / low / close. Trailing state and slots carry over. C
stays on the chart bar's close. `exleg` in 'mag': 1 for an exit at the chart open, else 2. Chart "1":
'mag' == 'tv'.

---------------------------------------------------------------------------------------------------

## 7. The script run at the close of bar `j` (step C), in the Pine's order

State it reads: the position after A and B (`pos` in 0 / +1 / -1, `qty`, `e`), `cash` (initial capital +
the closed trades' P/L after costs - the entry cost of the open trade), `nclosed` (number of closed trades)
and `last_pnl` (P/L after costs of the most recently closed one), and its own `var`s: `activeDayKey`,
`dayStartEquity`, `dayLossCount`, `lastClosedTrades`, `dailyLocked`, `lastSignalPolyWindowStartMs`,
`lastPreStopOrderBar`, `entryBarIndex`, and `prevPos` (`strategy.position_size[1]`: the position at the
previous close). `bi` = `bar_index`. `equity = cash + pos * qty * (close - e)` (`strategy.equity`, G20).

**C1. Daily lock (L1178-1203).**
```
if na(activeDayKey) or day[j] != activeDayKey:
    activeDayKey = day[j]; dayStartEquity = equity; dayLossCount = 0; dailyLocked = False
if nclosed > lastClosedTrades:
    if last_pnl < 0: dayLossCount += 1          # ONLY the last closed trade is looked at, +1 at most per run
    lastClosedTrades = nclosed
dayPnL = equity - dayStartEquity
dailyLossHit      = useDailyLossLock and maxDailyLossCurrency > 0 and dayPnL <= -maxDailyLossCurrency
dailyLossCountHit = useDailyLossLock and dayLossCount >= maxDailyLosses
if (dailyLossHit or dailyLossCountHit) and not dailyLocked: dailyLocked = True
```
The day is the New York calendar date of the bar's OPEN. The reset comes first, so a trade closed inside
the first bar of a day counts for the new day; a trade closed inside the last bar of a day counts for the
old one. A profit of exactly 0 is not a loss. With cost 'ours' / 'stress' `last_pnl` is after those costs
(G19). Two trades closed inside one bar ("Stop" mode) add at most 1. The lock ends only at the next day.

**C2. Exit geometry (L1210-1221), from this bar.**
```
exitAtr    = ta.atr(atrLen)
slTicks    = slPoints        if Points else nz(slAtrMult   * exitAtr / mintick)
tpTicks    = tpPoints        if Points else slTicks * tpR
trActTicks = trailActPoints  if Points else nz(trailActAtr * exitAtr / mintick)
trDstTicks = max(trailPoints if Points else nz(trailDstAtr * exitAtr / mintick), 1.0)
stop_distance    = slTicks * mintick
entry_qty        = f_get_qty(stop_distance)                        (section 9: this equity, this close)
stop_distance_ok = not useMaxStopDistance or stop_distance <= maxStopDistancePoints
```
**C3. `can_enter` (L1223).**
```
one_signal_window_ok = not oneSignalPerPolyWindow or na(lastSignalPolyWindowStartMs) or win[j] != lastSignalPolyWindowStartMs
can_enter = pos == 0 and gate[j] and one_signal_window_ok and not dailyLocked and stop_distance_ok and entry_qty > 0
```
**C4. The order blocks (L1238-1319).** `preCanOrder = preCandleEntryMode != "Signal Only"`; `stopMode =
preCandleEntryMode == "Stop Next Candle"`; `preOrderThisBar = False`.
```
1. if preCanOrder and armL[j] and can_enter and buyOk[j]:                                  (L1238)
       place(sig=+1, kind = 2 if stopMode else 1)
       lastPreStopOrderBar = bi if stopMode else na
       lastSignalPolyWindowStartMs = win[j]; preOrderThisBar = True
2. if preCanOrder and armS[j] and can_enter and not preOrderThisBar and sellOk[j]:        (L1261)
       place(sig=-1, kind = 2 if stopMode else 1); the same three assignments
3. if stopMode and pos == 0 and not na(lastPreStopOrderBar) and bi - lastPreStopOrderBar > preCancelAfterBars:   (L1284)
       empty both slots; lastPreStopOrderBar = na
4. if sigL[j] and can_enter and not preOrderThisBar and buyOk[j]:                          (L1289)
       place(sig=+1, kind=3, market); lastSignalPolyWindowStartMs = win[j]
5. if sigS[j] and can_enter and not preOrderThisBar and sellOk[j]:                         (L1305)
       place(sig=-1, kind=3, market); lastSignalPolyWindowStartMs = win[j]
```
`place(sig, kind)`: real side `d = -sig if gvInv else sig`; the order goes into slot `d` with `qty =
entry_qty`, the four tick values of C2, `reentry = exleg`, and for kind 2 `P`, `trig = sig` (6.1).
To keep exactly:
- Blocks 4 / 5 do not set `preOrderThisBar` and do not touch `lastPreStopOrderBar`. `sigL` and `sigS` are
  never both true. A filter-blocked arm leaves `preOrderThisBar` false, so a signal of the other side can
  still trade on that bar.
- Block 3 sits between the arms and the signals: an order placed by block 1 / 2 on this bar is safe (the
  difference is 0); a market order of block 4 / 5 is placed after the cancel, so it stays.
- The timer is shared: a new pre-candle order renews it for an older pending order of the other id. A
  pending order therefore lives on bars `b+1 .. b+preCancelAfterBars+1` after the LAST pre-candle placement
  `b` (default: three bars) and is removed at the close of the last of them, if the position is flat then.
  While a position is open nothing is cancelled, whatever the timer says.
- In "Stop" mode a kind-3 market order replaces a pending order of the same id and leaves the other id's
  pending order alive.
- The filter gates the PLACEMENT only: a pending order stays live when the zone changes afterwards.

Funnel (replica definition, normal frame, per bar): `rawL = (preCanOrder and armL and can_enter) or (sigL
and can_enter and not preOrderThisBar)` with `preOrderThisBar` as it is when block 4 is reached;
`raw_long` counts bars with `rawL`, `blocked_long` those of them with `buyOk` false. Short alike with
`armS and not preOrderThisBar` in block 2's term.

**C5. Bars in trade and the closes (L1322-1354).**
```
if pos != 0 and prevPos == 0: entryBarIndex = bi
if pos == 0:                  entryBarIndex = na
barsInTrade    = bi - entryBarIndex  if pos != 0 and not na(entryBarIndex)  else na
maxBarsExitHit = useMaxBarsExit and pos != 0 and not na(barsInTrade) and barsInTrade >= maxBarsInTrade
timeStopHit    = maxBarsHeld > 0 and pos != 0 and not na(barsInTrade) and barsInTrade >= maxBarsHeld and not maxBarsExitHit
close_req = 'maxbars' if maxBarsExitHit else 'time' if timeStopHit
            else 'daily_lock' if dailyLocked and pos != 0 else 'eod' if (not flatOk[j]) and pos != 0 else none
prevPos = pos
```
- `entryBarIndex` is the bar whose CLOSE first shows the position, i.e. the fill bar. With `maxBarsHeld =
  N` a trade filled in bar k gets its close order at the close of bar k+N and leaves at the open of bar
  k+N+1. A trade that opens and closes inside one bar is never seen here.
- Quirk to keep: a trade opened in a bar whose previous close already had a position (a reversal, or an
  exit followed by a pending fill in the same bar) INHERITS the old `entryBarIndex`: its bar count starts
  at the previous trade's entry bar. Count it (`inherit_ebi`).
- A close order and an entry order never come out of the same run (one needs a position, the other a flat
  account). `strategy.close` does not cancel pending orders.

**C6.** Bar-close equity `cash + pos * qty * (close - e)` for the curve; exposure counts bars with `pos != 0`
after C.

---------------------------------------------------------------------------------------------------

## 8. Update 1 ("Inverted direction", `gvInv`), line by line

| Pine | effect | replica |
|---|---|---|
| L835 | the input, declared last | `gvInv` / `inv` |
| L1041-1046 `gvBuyId`, `gvBuyExit`, `gvBuySide`, `gvSellId`, `gvSellExit`, `gvSellSide` | the normal BUY branch uses entry "Short" / exit "Exit Short" when inverted, the normal SELL branch "Long" / "Exit Long" | slot = real side `d = -sig` |
| L1243, L1266 | `strategy.entry(id, gvInv ? short : long, limit = gvInv ? P : na, stop = gvInv ? na : P)`: the stop order becomes a LIMIT order at the same price on the other side | same `P`, same `trig`, real side flipped (G6) |
| L1246, L1269, L1292, L1308 | market orders stay market orders, other side | same fill (next open) |
| L1257-1259, 1280-1282, 1301-1303, 1317-1319 | the same `loss` / `profit` / trail ticks, attached to the id really placed | 6.2 with the real `d`: a sell has its stop above, its target below, its trail arming below |
| L1240-1241, 1263-1264, 1290-1291, 1306-1307, L1058, L1124, L1143, L1251, 1274, 1295, 1311 | alert / label / training values of the real order | ignored |
| L1369-1370, L1406 | plots, table text | ignored |
| unchanged: L1223 `can_enter`, the arms, the signals, `fgfBuyOk` for `sig +1`, `fgfSellOk` for `sig -1`, `preOrderThisBar`, the window rule, L1284-1287 cancel, L1322-1354 (they read the REAL position: flat / not flat, or its sign to pick the id) | every decision is in the normal frame; the filter's "Allow buys" removes the `sig +1` entries, which inverted are the sells | `raw_*` / `blocked_*` stay in the normal frame; `long` / `short` trade counts are real sides |

This script has NO older reverse option and no Long-only / Short-only input (L1036). `gvInv` is not a
mirrored trade list in general: the exits change sides (a 1 ATR stop / 5 R target long becomes a short with
the stop above), so the trades end elsewhere, the daily loss count differs and later entries differ.

Properties (stage 2 self-checks, stage 3 tests):
- P1, exact mirror. With a symmetric bracket and nothing that reads the sign of the P/L (`tpR = 1`,
  `useTrail` False, `QtyMode` "Fixed" with a small `fixedQty` such as 0.01, `capMargin` False,
  `useDailyLossLock` False, `tvMargin` 0, cost 'tv'; any `maxBarsHeld`, either pre-candle mode, filter on
  or off): `inv` True gives the trade list of `inv` False with `dir` negated, `pnl` negated, 'sl' <-> 'tp'
  swapped and every bar, price, quantity and other kind equal. (The long's stop is the short's target at
  the same price; triggers and gap rules are symmetric.)
- P2, single decisions: from the same state, the order placed with `inv` True is the order placed with
  `inv` False on the other side: same bar, same type slot-swapped, same `P` and `trig`, same quantity, same
  ticks; a filter-blocked decision is blocked in both.
- P3: the first trade of a run has the same entry bar and entry price with `inv` False and True, opposite
  `dir` (default inputs).
- P4: `fgfOn` False equals `fgfOn` True with all-True permissions injected; with `gvInv` False the result
  is independent of every Update 1 line.

---------------------------------------------------------------------------------------------------

## 9. Sizing, money, costs, margin

`f_get_qty(stop_distance)` (L1163-1171), in this order, float64:
```
q = fixedQty
if QtyMode == "Risk %":
    stopCash = stop_distance * pointValue                  # the script's pointValue input (1.0)
    q = equity * riskPct / 100.0 / stopCash  if stopCash > 0  else 0.0
q = min(q, maxQty)
if capMargin and marginPct > 0:
    q = min(q, equity / (close * pointValue * marginPct / 100.0))
return floor((q + 1e-9 * qtyStep) / qtyStep) * qtyStep     # qtyStep > 0 (else q unchanged)
```
`equity` and `close` of the placing bar; an order is placed only when flat, so `equity = cash`. The
quantity is fixed at placement (a pending order keeps it until it fills, is replaced or is cancelled).

What the defaults do (probe, unverified; 100,000 account, stop 1 x ATR(14)):
- Gold: risk sizing asks for 1,000 / ATR = about 4,200 oz on "1", 420 on "60", 210 on "240"; `maxQty = 50`
  caps it on 100 % of the arm candles of every chart. Every default gold trade is 50 oz (about 65,000 of
  notional): the money at risk is 50 x ATR, i.e. about 12 on "1", 120 on "60", 240 on "240" (0.01 to 0.24 %
  of the account, not 1 %), and results barely compound. 'ours' costs are 15 per round trip: 1.3 R on "1",
  0.5 R on "5", 0.13 R on "60", 0.06 R on "240".
- BTC: 1 % risk over 1 ATR is a notional of `0.01 x close / ATR` accounts: about 23 accounts on "1", 8 on
  "5", 1.8 on "60", 0.85 on "240". `maxQty = 50` (coins) binds on "1" (17 % of arm candles) and almost
  never above it (0.7 % on "5"); the script's own margin cap (`marginPct = 1`: 100 accounts of notional)
  does not bind at a 100,000 account, only after heavy losses.

Money model:
- `cash` starts at 100,000. Cost of a fill = `qty * (fixed + fraction * fill_px)`, charged when the fill
  happens (entry and exit; a reversal = the closing fill and the opening fill), with the `hrd.COSTS` pairs
  `(fixed, fraction)`: 'tv' `(0, 0)` both pairs; 'ours' XAU `(0.15, 0)`, BTC `(0.10, 0.0002)`; 'stress'
  XAU `(0.26, 0)`, BTC `(0.11, 0.00035)`. Fill prices never move (slippage 0; the stress tick is a cost).
- `pnl_gross = dir * qty * (exit_px - entry_px)`; `pnl = pnl_gross - entry cost - exit cost`.
- `eq_before` of a trade = `cash` just before its entry fill (after the closing leg of a reversal, before
  its own entry cost).
- R: `sl_dist` = `stop_distance` of the placing bar; `r_mult = pnl / (sl_dist * qty)` (NaN without a stop).

**G14, margin.** `strategy()` sets no `margin_long` / `margin_short`; the Pine v6 default is 100 %, under
which TradingView does not open an entry that needs more money than the account has. The script's own cap
uses `marginPct = 1.0` ("match Properties -> Margin"), i.e. it assumes the user set the Properties to 1 %;
the file does not do that. Replica: `tvMargin = 0.0` (default) = no TradingView margin rule at all (the
reading of every other replica here, SPEC_xpw23 T11; with the Properties at 1 % nothing would ever be
refused). `tvMargin = m > 0`: at an entry fill (A2, A4, B) the order is REFUSED (removed, no fill, the
open trade if any stays) when `qty * fill_px * m / 100.0 > cash` at that moment; count `margin_refused`.
Always count `margin_over` = entry fills with `qty * fill_px > eq_before` and report `max_notional_x` =
the largest `qty * fill_px / eq_before`. Margin calls are not modelled in either setting. Size of the
matter (probe, default inputs, filter off, `tvMargin` 100): BTC "5" 5 trades instead of about 2,700, "15"
14 / 2,100, "30" 41 / 1,275, "60" 89 / 740, "120" 143 / 360, "240" 130 / 155; gold unchanged (65,000 <
100,000). The refusal rule itself (refuse, not shrink; a reversal dropped whole) is the documentation as
remembered: `tvMargin = 100` results are indicative.

---------------------------------------------------------------------------------------------------

## 10. Assumptions (one each; both builders implement exactly these)

| id | assumption | why |
|---|---|---|
| G1 | One decision run per bar at its close; the extra runs of `calc_on_order_fills` change nothing. Same-bar exit yes, same-bar re-entry never; exposure counted (`reentry_*`, `pend_fill_after_exit`). | Section 5. |
| G2 | A market order fills at the next bar's open, raw price. | `process_orders_on_close=false`, slippage 0; SPEC_AH rule 1. |
| G3 | The bracket is live from the entry fill, on the fill bar for the rest of its path; levels = fill price -/+ the ticks of the PLACING bar; they never change afterwards (the script never re-sends an exit for an open trade). | `strategy.exit` is called with the entry order; `loss` / `profit` / `trail_points` are relative to the fill. SPEC_AH rule 3. |
| G4 | Intrabar path = SPEC_AH rule 4; the first level reached wins; a level already passed at the open fills at the open (stop, limit and entry orders alike); a limit fills on touch. | Documented broker emulator. |
| G5 | Trailing stop as SWEEP_AH_SPEC section 1: armed when price reaches fill + `trail_points` ticks (0 = at the fill), then stop = best price - `trail_offset` ticks, moving only in favour; with `loss`, the nearer stop is the one hit; the target is tested before arming. | The verified reading of apex / hrd / xpw. |
| G6 | A buy stop at `P` and a sell limit at `P` (above the market) have the same trigger (price >= `P`) and the same fill (`P`, or the open when a bar opens at or beyond it); mirror for the sell stop / buy limit below. | Slippage 0, "verify price for limit orders" 0 (the Pine says so at L1005-1011). |
| G7 | `strategy.entry` with the id of a pending order replaces it (type, price, quantity); the `strategy.exit` sent with it replaces the earlier one of that id. A cancelled entry leaves no bracket behind (every later entry of that id re-sends its own). | Documented order modification by id. |
| G8 | A pending order that fills against an open position closes it at the fill price (kind 'reverse') and opens the order's own quantity; the closed trade's bracket is gone. | `strategy.entry` reverses; `pyramiding = 0` only limits same-side entries. |
| G9 | `strategy.cancel` empties the slot at the close run; the order cannot fill from the next bar on. `strategy.close` fills at the next open and cancels nothing else. Several `strategy.close` of one run: the first in code order names the kind (same price). | Order of the calls; G1. |
| G10 | At one price point: A1, A2, then the exit of the trade already open, then pending orders (older first); on a leg a tie goes to the exit. Only the label 'sl' / 'tp' vs 'reverse' depends on it; prices and the resulting position do not. | TradingView's order is not documented; deterministic choice. |
| G11 | Two pending orders can coexist (one per id), and one stays live while the other's trade is open. | Section 7: the cancel block needs a flat position. |
| G12 | No rounding: tick distances stay fractional, levels and pending prices are not rounded to the tick, quantities only by `qtyStep`. | As apex / hrd / xpw23 (T12). At most half a tick per level. |
| G13 | `strategy.entry` with `qty <= 0` is never called (`can_enter` needs `entry_qty > 0`). A `strategy.exit` whose `loss`, `profit` and trail are all absent places nothing. | Code; only reachable in Points mode with zeros. |
| G14 | TradingView margin: not modelled by default; `tvMargin` switch; counters. | Section 9. |
| G15 | `ta.rising(x, 2)` = `x > x[1] and x > x[2]` (`risingRule` 'any'). 'mono' = `x > x[1] and x[1] > x[2]`, for the reconciler to measure. | The reference text ("greater than any previous value for length bars back"). It only feeds the EMA-cross signals: 'mono' removes about 2 % of them. |
| G16 | `request.security` of a LOWER timeframe (the radar), lookahead off: the last radar bar with `t_close <=` the chart bar's `t_close`. | SPEC.md rule. Default radar = the chart: no request is used. |
| G17 | `time(timeframe.period, session, "America/New_York")` is not na iff the bar's OPEN, in New York time, has HHMM in `[start, end)`, every day of the week. `dayofweek`, `hour`, `minute`, `year`, `month`, `dayofmonth` with that zone: of the bar's open. | Pine `time()`; the zone is explicit in the script, so the pair's exchange zone does not matter. Session filter off by default and outside the grid: unverifiable, flag any result that uses it. |
| G18 | The daily lock's day = New York calendar date of the bar's open (midnight New York, daylight saving included). | L1176. |
| G19 | `strategy.closedtrades.profit` = the trade's P/L net of its costs in the cost mode. | TradingView's trade profit is net of commission. |
| G20 | `strategy.equity` = `cash` + open P/L at the close; `strategy.position_size[1]` = the position at the previous bar's close. | SPEC_AH rule 6. |
| G21 | Trading starts flat with clean variables at the first window bar; orders of the last window bar do not fill; 'end' at the last close. | REPLICA_SPEC; SPEC_AH rule 5. |

Live-only, ignored: `calc_on_every_tick` (live, the time stop fires one bar early and a re-entry can come
mid-bar), `barstate.islast` tables, alerts, webhook delivery, the filter's live branches (inside `fgf.py`).

---------------------------------------------------------------------------------------------------

## 11. What cannot be reproduced, and what the replica does instead

- TradingView itself: nothing can be compiled or backtested here. G1, G10, G14 are readings of its engine.
  G1's exposure is counted on every run; G14 has a switch.
- TradingView's default Margin 100 % (G14): the default replica ignores it; `tvMargin = 100` approximates it.
- Seconds charts: the script's 5-minute-window logic ("Max Seconds After 5M Window Start", one signal per
  window) was written for seconds and 1-minute charts. No data below 1 minute: chart "1" is the finest.
- Volume: the vol score uses none. Only `preUseRvol` (off, outside the grid) reads volume: on BTC Bitstamp
  volume, on gold the Dukascopy TICK COUNT (TradingView's gold feeds are tick volume too, of another
  broker). With it on, gold results are relative tick activity of this feed, not traded volume.
- Bars of another broker: gold bars are 18:00-17:00 New York with 120 / 240-minute bars anchored at 18:00;
  BTC bars are on a UTC grid. Another session changes the bars, the New York day's first bar and what the
  session filter sees.
- Live behaviour: per-tick runs, the one-bar-early time stop, mid-bar re-entries, webhook / Polymarket
  routing, the paper stake, spreads.
- TradingView's rounding of prices to the tick and of quantities to the symbol's minimum, its margin calls,
  its cap of about 9,000 trades per report (v6 drops the oldest; a 1-minute chart, or loose settings on
  "5", can exceed it), the bars a plan can load (a 1-minute chart cannot hold two years).
- The unfused original's exits and sizing (section 1).
- Bar Magnifier inside TradingView: path 'mag' is OUR 1-minute walk of the bracket and of the pending
  orders, with decisions, market fills and `strategy.close` on the chart bars.

---------------------------------------------------------------------------------------------------

## 12. Interface, trade record, summary

    prepare(pair, chart_tf, params=None) -> P
    simulate(P, x=None) -> R
    trades(P, R) -> DataFrame
    summary(P, R) -> dict
    run(pair, chart_tf, params=None) -> (trades, summary)        # splits one dict into 3.1 / 3.2 keys

`DEFAULTS` = every Pine default of 3.1 and 3.2, so `fgfOn = False`, plus the replica controls (`path`
'tv', `cost` 'tv', `tvMargin` 0.0, `risingRule` 'any', `inv` False). One numba kernel for A, B, C over the
window bars (no Python object in the loop). Speed: one `simulate` on BTC "1" (1,039,430 bars) well under
1 s after compilation; first `prepare` under 2 minutes; under 3 GB.

**Trades**, one row per entry fill, in fill order:

| column | content |
|---|---|
| `dir` | REAL side, +1 / -1 |
| `sig` | normal-frame side of the decision (+1 PRE-L arm / long signal); `= dir` with `inv` off, `-dir` with it on |
| `entry_kind` | 1 pre-candle market, 2 pre-candle price order, 3 EMA-cross signal |
| `order_type` | 'market', 'stop', 'limit' (kind 2: 'stop' normal, 'limit' inverted) |
| `sig_bar`, `entry_bar`, `exit_bar` | file rows: where the order was placed, where it filled, where the trade closed |
| `entry_time`, `exit_time` | `t_open` of the fill bar / of the exit bar (chart bars, also in 'mag'); 'end': `t_close` |
| `entry_px`, `qty`, `exit_px` | fill price, units, exit fill price |
| `exit_kind` | 'sl', 'tp', 'trail' (bracket), 'reverse' ("Stop" mode only), 'time' (`maxBarsHeld`), 'maxbars' (`useMaxBarsExit`), 'daily_lock', 'eod' (session filter), 'end' |
| `pnl`, `pnl_gross`, `costs`, `eq_before` | section 9 |
| `sl_dist`, `sl_px`, `tp_px`, `r_mult` | stop distance of the placing bar, the levels at the fill (NaN if absent), `pnl / (sl_dist * qty)` |
| `reentry` | 0, or the `exleg` of the bar that placed the order: 1 (exit at the open or on leg 0), 2 (leg 1), 3 (leg 2) |
| `inherit_ebi` | True when the trade inherited `entryBarIndex` (C5) |
| `after_exit` | True when a pending order opened the trade (as a fresh trade) on a bar AFTER an exit fill of that same bar |

**Summary.** The common fields exactly as `hrd.summary_fast` + `hrd.extra_fields` compute them, with
`INITIAL_CAPITAL = 100000`: `start, end, bars, trades, net_pct, pf, win_pct, max_dd_pct, max_dd_init_pct,
long, short, raw_long, raw_short, blocked_long, blocked_short, half1_pct, half2_pct, exposure,
final_equity, exit_sl, exit_tp, exit_trail, exit_reverse, exit_time, exit_maxbars, exit_daily_lock,
exit_eod, exit_end, zero_length, h1r_pct, h2r_pct, h1_trades, h2_trades, avg_bars_held, costs`. Fair halves:
trades ENTERED in each half by `entry_time <= mid` / `> mid`, `100 * (prod(1 + pnl / eq_before) - 1)`, 0
for an empty half. `max_dd_pct` on the bar-close equity curve incl. open P/L, starting at 100,000.

Fields of this strategy:
- `net_r`, `h1_r`, `h2_r`: sum of `r_mult` over all trades / the trades entered in each half (the Pine
  header's unit; on gold the cap makes % tiny, R stays readable).
- `arms_long`, `arms_short`, `sig_long`, `sig_short` (from `P`); `orders_placed`; `pend_placed`,
  `pend_filled`, `pend_replaced`, `pend_cancelled`, `pend_open_end` (kind-2 orders; all 0 outside "Stop").
- `reentry_same_bar` (trades with `reentry > 0`), `reentry_extreme` (`reentry` 1 or 2 and a market order),
  `reentry_gap_r`: over the trades with `reentry > 0` entered by a MARKET order, the sum of `dir *
  (entry_px - tv_px) / sl_dist`, where `tv_px` is the path point of the placing bar that TradingView would
  most likely have used: `v1` for code 1, `v2` for code 2, the close for code 3 (path 'tv' only; 0 in
  'mag'). Positive = TradingView's fill would have been better for the trade by that many R, to first
  order (the bracket would move with the fill).
- `pend_fill_after_exit`: trades with `after_exit` (TradingView would probably have cancelled or kept that
  order in the run after the exit; G1). `orders_placed`: `place()` calls.
- `inherit_ebi` (count), `locked_bars` (window bars with `dailyLocked` after C1), `lock_days` (days on
  which it became true), `zero_qty` (runs where only `entry_qty > 0` was missing from `can_enter` while an
  arm or signal was present), `qty_capped_max` / `qty_capped_margin` (entry fills whose quantity was set by
  `maxQty` / by the script's margin cap), `margin_over`, `margin_refused`, `max_notional_x`.

Comparing A and B: bars, kinds, codes and counts exactly; prices, quantities, P/L and equity fields to a
relative 1e-9.

---------------------------------------------------------------------------------------------------

## 13. Builders: outputs, self-checks, sanity numbers

- Saved trade lists (cost 'tv', path 'tv', default inputs): `$W/out/gvl_<a|b>_<PAIR>_<TF>.parquet` for BTC
  60, BTC 5, XAU 60, XAU 15, one file per cell with a column `variant` in `off_normal`, `on_normal`,
  `off_inv`, `on_inv` (filter off / on, `inv` off / on), and the same four with `preCandleEntryMode =
  "Stop Next Candle"` (`off_normal_stop`, ...): the default mode never exercises the pending orders.
- Reference counts of section 4.5 (`arms_*`, `sig_*`), and on chart "1" the number of `gate` bars.
- Hand traces with the bars printed, at least 3 trades each: 'sl', 'tp', a same-bar entry and exit, 'trail'
  (`useTrail` with an activation inside the target, or `tpR = 0`), 'time' (`maxBarsHeld`), 'maxbars'
  (`useMaxBarsExit`), 'daily_lock' (a pending order filling on a locked day, or `maxDailyLossCurrency >
  0`), 'eod' (`useSessionFilter`), 'reverse', 'end'. Also trace: a day locked after the third loss and the
  first bar allowed again, across one New York midnight in winter and one in summer; a trade closed inside
  the first bar of a day; in "Stop" mode a gap fill at an open, a fill inside a bar followed by its stop in
  the same bar, a cancel after three bars, a replacement by the same id, two pending orders at once, an
  `inherit_ebi` trade, the inverted limit fill at the same price as the stop order; on chart "1" the window
  rule (which minutes can place, one order per window); sizing against a direct evaluation of `f_get_qty`
  (a gold trade capped at 50, a BTC trade not capped); `tvMargin = 100` refusing one BTC entry.
- P1-P4 of section 8. `risingRule` 'mono' changes only kind-3 entries.
- Sanity numbers (probe, plain single implementation, unverified, order of magnitude only; default inputs,
  "Market Next Candle", filter off, cost 'tv', path 'tv'): trades BTC "5" about 2,700, "15" 2,100, "30"
  1,275, "60" 740, "120" 360, "240" 155; XAU "5" about 1,480, "15" 990, "30" 600, "60" 330, "120" 190,
  "240" 83. Win rate 15 to 19 % (target 5 R: break-even 16.7 % before costs); every exit is 'sl' or 'tp';
  20 to 25 % of the trades open and close in one bar up to "60" (under 10 % on "240"); 15 to 25 % have
  `reentry > 0`, almost all code 2,
  none code 3 (with a fixed bracket a trade open since the bar's open cannot exit on the third leg);
  `locked_bars` about 68 % of the bars on "5", 19 to 27 % on "15", 6 to 8 % on "30", 1 to 2 % on "60".
  `margin_over`: every BTC "5" trade, about 90 % on BTC "60", 20 % on BTC "240", none on gold.

Additions for stage 3 (beyond REPLICA_SPEC):
- In `out/inv_gvl_<PAIR>_<TF>.json` keep `runs[...]` = the 16 keys with the defaults ("Market Next Candle",
  `tvMargin` 0) and add `runs_stop[...]` (the same 16 with "Stop Next Candle") and `runs_m100[...]` (the
  16 with `tvMargin = 100`: what the file most likely shows in TradingView with its untouched Properties).
  Print `reentry_same_bar`, `reentry_gap_r`, `margin_over` next to every 'tv' row.
- Tests: P1 (both modes, filter on and off, with and without a time stop), P2-P4; 'mag' on chart "1" ==
  'tv' in both modes; the daily lock against a slow recount from the trade list in "Market" mode (there
  every bar closes at most one trade, so losses per New York day of the exit bar's open are countable);
  the pending-order life: every kind-2 fill is (i) on a bar `<= b + preCancelAfterBars + 1`, `b` = the last
  pre-candle placement before it, or (ii) a reversal, or (iii) an `after_exit` fill.
- The random reconcile settings must draw both pre-candle modes, `useTrail` on, `maxBarsHeld > 0`, the
  daily lock on and off, and a few settings outside the grid: `useMaxBarsExit`, `maxDailyLossCurrency >
  0`, `QtyMode` "Fixed", `ExitMode` "Points", `radarTimeframeMode` "Auto" and "1", `preUseRvol`,
  `preUseBodyAtr`, `preUseMicroBreak`, `preUseEmaSlope`, `useSessionFilter` with each preset,
  `allowWeekendEntries` false, `oneSignalPerPolyWindow` false on chart "1".

---------------------------------------------------------------------------------------------------

## 14. Calibration grid proposal (for `$W/CALIB_SPEC.md`)

Scored as CALIB_SPEC says (path 'mag', cost 'ours'), `tvMargin` 0 (see the notes). **20,736 settings per
cell**, the same product in every cell: 288 `prepare` settings x 72 `simulate` settings.

| # | dimension (Pine names) | values | kind | side | default |
|---|---|---|---|---|---|
| 1 | `emaPair` = (`fastEmaLen`, `slowEmaLen`) | (5, 13), (8, 21) | ordinal | prepare | (8, 21) |
| 2 | `trendFilterLen` | 50, 100, 200 | ordinal | prepare | 100 |
| 3 | `preMinVolScore` | 0, 35 | ordinal | prepare | 35 |
| 4 | `preMinVolRise` | 0, 1 | ordinal | prepare | 1 |
| 5 | `preCloseLocation` | 0.55, 0.65, 0.75 | ordinal | prepare | 0.65 |
| 6 | `preUseTrend` | True, False | categorical | prepare | True |
| 7 | `fgfOn` | False, True (this script has no blocked-signal close) | categorical | prepare | False |
| 8 | `preCandleEntryMode` | "Market Next Candle", "Stop Next Candle" | categorical | simulate | "Market Next Candle" |
| 9 | `inv` (`gvInv`) | False, True | categorical (the direction control) | simulate | False |
| 10 | `slAtrMult` | 0.5, 1.0, 2.0 | ordinal | simulate | 1.0 |
| 11 | `exitStyle` = (`tpR`, `maxBarsHeld`, `useTrail`) | 'tp5' = (5.0, 0, False); 'time4' = (0.0, 4, False); 'trail' = (0.0, 0, True with the cell's pair below) | categorical | simulate | 'tp5' |
| 12 | `useDailyLossLock` | True (3 losing trades per New York day), False | categorical | simulate | True |

Count: 2 x 3 x 2 x 2 x 3 x 2 x 2 = 288; 2 x 2 x 3 x 3 x 2 = 72; 288 x 72 = **20,736**. The script default is
one grid point: (8, 21), 100, 35, 1, 0.65, trend on, filter off, Market, normal, 1.0, 'tp5', lock on.
Everything else at the script defaults (RSI filter on, radar Chart, `ExitMode` ATR, `atrLen` 14, Risk 1 %,
`maxQty` 50, `preStopAtrBuffer` 0.03, `preCancelAfterBars` 2, `maxDailyLosses` 3, no $ lock, the filter's
own inputs). No combination is a structural duplicate of another (with `preUseTrend` False the trend EMA
still gates the EMA-cross signals), so no dimension is ever None; `exitStyle` is one categorical dimension
on purpose (its three members are whole exit rules: a target, a time stop, a trail), with the Pine inputs
it sets written as extra columns that do not start with `p_`.

Trailing (`exitStyle` 'trail'): `trailActAtr = 2d`, `trailDstAtr = d`, with `d` the smallest of {1, 1.75,
2.5, 3.5, 5, 6.5} for which `d x ATR(14) / close` at the 10th percentile of the window is at least the
floor (0.1 % BTC, 0.05 % gold):

| cell | BTC 1 | BTC 5 | BTC 15 - 240 | XAU 1 | XAU 5 | XAU 15 - 240 |
|---|---|---|---|---|---|---|
| 10th percentile of ATR(14) / close, % (probe) | 0.0157 | 0.0574 | 0.125 / 0.198 / 0.318 / 0.512 / 0.826 | 0.0101 | 0.0290 | 0.060 / 0.094 / 0.145 / 0.203 / 0.311 |
| `d` | 6.5 | 1.75 | 1 | 5 | 1.75 | 1 |
| (`trailActAtr`, `trailDstAtr`) | (13, 6.5) | (3.5, 1.75) | (2, 1) | (10, 5) | (3.5, 1.75) | (2, 1) |

(Same table as SPEC_danny, same ATR. On the 1-minute charts the floor makes the trail nearly inert.)

Why these dimensions (evidence from the probes and from the per-timeframe README, which names the inputs
that moved its earlier calibration: EMA pair, trend EMA, RSI filter, pre-candle mode, min vol score, vol
rise, close location, trend direction, stop, target, trail, time stop):
- The arms give about three quarters of the entry candidates and are driven by dimensions 3-6 (BTC 60:
  1,010 arms at the defaults, 5,959 with 0 / 0 / 0.55 / trend off; XAU 240: 131 against 805).
- The EMA pair and the trend EMA drive the EMA-cross signals (BTC 60: 349 signals with 8 / 21, 509 with
  5 / 13); the trend EMA also the arms.
- **The RSI filter is left out although the README lists it**: it removes 1 to 3 % of the EMA-cross signals
  and touches no arm, so its two values would be near-duplicate rows.
- **The daily lock is added although the README kept it at 3**: at the defaults it is in force on about two
  thirds of the 5-minute bars and a fifth to a quarter of the 15-minute bars, so on the low timeframes it
  decides more than any signal input (expected consequence, not measured: the trades cluster in the hours
  after midnight New York, where each day's count restarts). On 60 minutes and above the two values will
  often give identical rows; rule C counts those once.
- 'tp5', 'time4' and 'trail' are the three exit rules the earlier per-timeframe picks used (5 R target five
  times, no target with a 4-bar time stop twice, no target with a trail once). A setting with no target, no
  time stop and no trail has no way to take a profit and is not in the grid.

Notes for the orchestrator:
- **Margin (G14).** With TradingView's untouched Properties (Margin 100 %) the BTC charts below 240 minutes
  would most likely take almost no trade, and the published BTC per-timeframe files (5m, 30m, 60m, 120m)
  have the same `strategy()` line. The grid uses `tvMargin` 0, i.e. it calibrates the script as its own
  sizing input assumes the Properties are set (Margin 1 %). A file published from a BTC pick should say so,
  or carry `margin_long = 1, margin_short = 1` in `strategy()`. Gold is not affected.
- **Sizing stays the script's**, so that the default is literally a grid point. On gold that means 50 oz on
  every trade (the cap), i.e. a risk of 0.01 to 0.24 % of the account: the halves in % are small but their
  signs and ranks are what rule C reads; `h1_r` / `h2_r` are in the rows for a readable scale. On BTC the
  1 % risk compounds and an account can be ruined (`zero_qty` then shows it and the setting drops out of
  the 30-trades-per-half pool). If scale-free halves are preferred on both pairs: fix `maxQty = 1e9` for
  every row and define the default row with it.
- **Chart "1"**: with the default 90 seconds only 2 of every 5 one-minute bars may place an order, one per
  window. Kept at the default (it is the script's design); `maxSignalSecondsAfterWindowStart = 299` with
  `oneSignalPerPolyWindow` False is the obvious extra control for that cell.
- **G1**: every 'tv' number carries the same-bar re-entry exposure; the calibration is scored on 'mag',
  where a re-entry at the next chart open is the realistic fill. Suggested with each pick: its
  `reentry_same_bar` share and, on the 'tv' view, `reentry_gap_r`.
- Left out to stay in budget, in order of expected weight: `tpR` 2.5 / 3 (the header says 3 was about half
  as good as 5), `maxBarsHeld` other than 4, a second trail (activation 4 ATR, the tightest distance the
  floor allows: the old XAU 240 pick), `maxDailyLosses` other than 3, `preStopAtrBuffer`,
  `preCancelAfterBars`, EMA (3, 8) (the old BTC 60 pick), `radarTimeframeMode` "Auto", "Signal Only",
  `riskPct`.
- Speed: 288 `prepare` calls per cell must be vector work on cached series (section 4.5); 20,736
  `simulate` calls on BTC "1" fit CALIB_SPEC's 45 minutes with 3 workers if one call takes under 0.35 s.
