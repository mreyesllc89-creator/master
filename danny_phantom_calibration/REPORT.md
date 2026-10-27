# Danny Phantom V10.21.1 — calibration on XAUUSD and BTCUSD, every timeframe

Date: 2026-10-27. Input: `Danny_Phantom_V10211_USD_Tester_70230f19.zip` (the MT5 port of the
frozen 84-input TradingView strategy, build 70230f19). Data: your own M1 bid/ask history in this
repository (`calibration/data/*.npz` on branch `claude/sharp-brown-qqghvg`): XAUUSD 2011-05 →
2018-06 plus the 2026-07/08 Octa export (≈28 trading days), BTCUSD 2015-01 → 2019-12 plus the
2026-07/08 export (≈58 days).

Neither MetaTrader nor TradingView runs in this environment, so the strategy was ported line by
line from `DPFXCore.mqh` / `DPFXRules.mqh` / `DPFXProtection.mqh` into a numba backtester
(`tools/engine.py`) that uses TradingView's execution model (decide on bar close, fill at next
bar open, stop/limit resolved on the OHLC path) and real bid/ask prices. 290 000 backtests were
run: 16 000 random input combinations per timeframe (6 000 on M1-M3) over every numeric and
boolean strategy input, then one-input-at-a-time hill climbing of the six most robust survivors,
then a cost stress of the winners. Everything is reproducible with the commands at the end.

## 1. Short version

1. **The shipped preset (XAUUSD 5m profile, inverted signals, 0.5 ATR stop / 10 R target) loses
   on every gold timeframe once a spread is paid** — about −0.3 R per trade on M5, ruin at 1 %
   risk. The same preset is profitable only on TradingView-style mid prices with no spread
   (+417 % on M5 2011-2018, PF 1.11). The stop is so tight (≈ $0.5-1 on M5) that a $0.12 spread
   plus the V10.13 cost filter's own 75-tick slippage assumption consumes the edge. The TradingView
   result you are comparing against is the no-spread number.
2. **Gold has a real but modest edge, and it is on the higher timeframes with the *original*
   (un-inverted) signal direction and wider stops.** Every XAUUSD timeframe from M5 to H4 has a
   calibrated set that is positive in-sample (2011-2015), positive out-of-sample (2016-2018),
   profitable in 6-8 of 8 years, with profit factor 1.2-1.8 and 7-17 % max drawdown at 1 % risk.
   M60 and M30 are the most trustworthy (most trades, best OOS t-stat); M15 has the best
   quality per trade. Returns are 125-275 % over eight years at 1 % risk — a steady strategy,
   not a rocket.
3. **M1-M3 on gold and everything below H1 on bitcoin should not be traded.** The gold M1-M3
   winners halve with 5 cents of extra slippage per fill and are flat or negative on the 2026
   export. The bitcoin M1-M30 "winners" (five-digit returns, t-stats above 10) are an artefact:
   they vanish with 0.5 bp of slippage, and on the real 2026 Octa feed they lose −0.2 to −0.4 R
   per trade over 1 000-4 400 trades. They only work on no-spread mid prices — which is exactly
   what TradingView shows. Do not trust a TradingView bitcoin backtest of this strategy below H1.
4. **Bitcoin H4 is the only BTC configuration that survives every test** (PF 1.6, +585 % over
   2015-2019 at 8 % drawdown, profitable every year, positive on the 2026 export, insensitive to
   slippage). H1 is close but slightly negative on the short 2026 sample.
5. Inputs that mattered everywhere: `tradeOriginalDirection = true` (7 of 9 gold timeframes and
   all bitcoin timeframes prefer the un-inverted signal), `slAtrMultS2` 1.0-3.0 instead of 0.5,
   a trailing stop (`useTrailS2 = true`) on most timeframes, and dropping the gold-specific NY
   hour filters when the preset is run in `Manual` mode. The money-management inputs
   (riskPct, lot caps) do not change the ranking and were left at the shipped values.

## 2. What was simulated, and how faithfully

* Signals and state machine: `DPFEngine.Push` (volume-delta supply/demand zones, retest touch
  or close-beyond entry, EMA filter, ATR, cost filter, robust-hour / directional / V10.5 /
  V10.10 windows, weekend and daily blackout with entry buffer, Sunday block, cooldown, loss
  cluster pause, one-per-zone consumption, dead / time / blackout forced exits) and
  `DPFProtectionEvaluate` (fixed stop, R-multiple target, trailing stop, breakeven) were ported
  literally. The XAUUSD 5m auto profile and the Manual profile resolve exactly as in
  `DPFResolve`. Quantity follows `DPFS3Quantity` (Risk % of equity, 0.001 step, margin cap).
* Execution: bar-close evaluation, market fills at the next bar's open (TradingView broker
  emulator on history), protective orders live from the fill bar and resolved on the bar path
  open → nearer extreme → farther extreme → close; a gap through a stop fills at the open.
  Longs buy the ask and sell the bid, shorts the reverse, so the spread is the trading cost.
* Timeframes: M1 M2 M3 M5 M10 M15 M30 M60 built from UTC-aligned M1 bars; H4 bars aligned to
  the 17:00 New York session boundary. New York clock with DST as in `DPFNewYork`.
* Three spread models (`tools/data.py`): **modern** = the spread of your 2026 Octa export
  ($0.12 on gold, 2.2 bp on bitcoin) applied around the historical mid; **recorded** = the
  bid/ask that was actually in the 2011-2019 files ($0.25-0.40 on gold, i.e. three times
  today's); **mid** = no spread, what TradingView uses by default. Results are ranked on
  *modern*; the other two are stress tests.
* Not simulated: tick-level evaluation inside the bar (the EA evaluates every tick but, as the
  README notes, decisions are still per committed bar), commission, swap, broker stop/freeze
  levels, requotes. Trade-for-trade parity with TradingView is not claimed — the upstream
  README says the same for the MT5 build itself.

## 3. Method

* **Search space** (`tools/space.py`): both preset modes (`XAUUSD 5m` auto profile and
  `Manual`), both signal directions, ATR length 7-50, stop 0.3-3 ATR, target off / 1-15 R,
  trailing on/off with activation 0.5-4 ATR and distance 0.2-2 ATR, time stop 0-200 bars,
  every quality filter toggle, loss-cluster count / pause, cost-filter ratio 2-10, session
  filter and four sessions, weekend / daily blackout toggles, zone invalidation, min retest
  bars 1-5, zone age 25-400; in Manual mode additionally zone length 20-150, delta multiplier
  1-4, EMA filter and length 20-200, zone-trend filter, entry mode, dead exit 5-30 bars,
  breakeven 0.5-2 ATR, entry buffer, Sunday block, one-per-zone, cooldown 3-20, five entry
  windows. Points-mode exits were not swept (an ATR stop is the same thing with adaptive size).
* **Scoring**: in-sample years only (gold 2011-2015, bitcoin 2015-2017). Objective = t-statistic
  of the per-trade R multiple (mean R / sd R × √n), which is sizing-independent and penalises
  configurations with few trades. Candidates had to have ≥ 30 trades per in-sample year, and
  for the refinement stage a positive out-of-sample mean R with ≥ 50 OOS trades. Refinement
  climbed the in-sample t-stat only; OOS, per-year and 2026 figures were recorded, never
  optimised. The final pick per timeframe is the refined candidate with the best OOS t-stat
  among those with IS t > 2.
* **Stress**: three spread models; extra slippage of $0.05 / $0.10 per fill on gold and 0.5 /
  1.0 bp per fill on bitcoin; per-year profit; the 2026 export as a second, untouched sample.

## 4. Results

### Best configuration per timeframe (modern spread, 1 % risk, $10k start)

| Config | trades | IS t-stat | OOS t-stat | OOS avg R | PF all | win % | return | max DD | 2026 trades | 2026 avg R |
|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSD_M1 | 137312 | 27.5 | 14.2 | +0.094 | 1.28 | 45 | 105,608 % | 10.8 % | 4404 | -0.236 |
| BTCUSD_M2 | 113787 | 20.8 | 22.4 | +0.171 | 1.27 | 45 | 70,956 % | 7.7 % | 4086 | -0.183 |
| BTCUSD_M3 | 96599 | 17.7 | 17.5 | +0.187 | 1.19 | 29 | 43,146 % | 17.5 % | 2682 | -0.380 |
| BTCUSD_M5 | 96478 | 16.3 | 13.5 | +0.174 | 1.20 | 33 | 45,643 % | 8.0 % | 2468 | -0.412 |
| BTCUSD_M10 | 48369 | 12.5 | 8.0 | +0.112 | 1.30 | 28 | 33,415 % | 5.6 % | 1767 | -0.327 |
| BTCUSD_M15 | 52734 | 10.7 | 9.0 | +0.124 | 1.19 | 31 | 27,634 % | 12.5 % | 1793 | -0.234 |
| BTCUSD_M30 | 28390 | 9.3 | 3.6 | +0.063 | 1.16 | 27 | 17,309 % | 13.7 % | 1040 | -0.182 |
| BTCUSD_M60 | 1167 | 5.0 | 2.9 | +0.218 | 1.43 | 43 | 1,754 % | 16.9 % | 37 | -0.167 |
| BTCUSD_M240 | 1104 | 5.2 | 2.8 | +0.107 | 1.61 | 39 | 585 % | 8.1 % | 36 | +0.223 |
| XAUUSD_M1 | 2307 | 3.7 | 2.6 | +0.407 | 1.27 | 25 | 332 % | 13.2 % | 1036 | +0.105 |
| XAUUSD_M2 | 1232 | 3.9 | 1.4 | +0.382 | 1.44 | 27 | 266 % | 10.8 % | 1045 | -0.020 |
| XAUUSD_M3 | 5310 | 2.8 | 1.0 | +0.076 | 1.09 | 32 | 399 % | 37.2 % | 632 | -0.082 |
| XAUUSD_M5 | 563 | 3.6 | 1.8 | +0.368 | 1.55 | 34 | 220 % | 10.1 % | 0 | +0.000 |
| XAUUSD_M10 | 688 | 3.5 | 1.1 | +0.388 | 1.46 | 29 | 206 % | 16.8 % | 0 | +0.000 |
| XAUUSD_M15 | 561 | 3.8 | 2.3 | +0.173 | 1.54 | 61 | 157 % | 8.0 % | 0 | +0.000 |
| XAUUSD_M30 | 1940 | 3.2 | 2.3 | +0.091 | 1.22 | 59 | 229 % | 15.3 % | 24 | -0.035 |
| XAUUSD_M60 | 1084 | 4.2 | 1.9 | +0.142 | 1.32 | 44 | 275 % | 12.2 % | 26 | +0.031 |
| XAUUSD_M240 | 257 | 4.3 | 1.4 | +0.160 | 1.76 | 51 | 125 % | 7.2 % | 2 | -0.595 |

### Same configurations under the three spread models (return over the long history / 2026 export)

| Config | modern | recorded broker spread | TradingView mid (no spread) |
|---|---|---|---|
| BTCUSD_M1 | 105,608 % / -100 % | 87,071 % / -100 % | 190,232 % / 20,367 % |
| BTCUSD_M2 | 70,956 % / -100 % | 56,299 % / -100 % | 129,272 % / 5,243 % |
| BTCUSD_M3 | 43,146 % / -100 % | 32,207 % / -100 % | 89,929 % / 6,748 % |
| BTCUSD_M5 | 45,643 % / -100 % | 33,357 % / -100 % | 96,069 % / 821 % |
| BTCUSD_M10 | 33,415 % / -100 % | 28,319 % / -100 % | 55,037 % / 586 % |
| BTCUSD_M15 | 27,634 % / -99 % | 22,900 % / -100 % | 48,716 % / 1,261 % |
| BTCUSD_M30 | 17,309 % / -88 % | 14,659 % / -94 % | 28,769 % / 61 % |
| BTCUSD_M60 | 1,754 % / -6 % | 1,709 % / -6 % | 1,909 % / -5 % |
| BTCUSD_M240 | 585 % / 8 % | 594 % / 8 % | 641 % / 8 % |
| XAUUSD_M1 | 332 % / 134 % | -97 % / 118 % | 476 % / 175 % |
| XAUUSD_M2 | 266 % / -18 % | 31 % / -14 % | 354 % / 82 % |
| XAUUSD_M3 | 399 % / -45 % | -94 % / -47 % | 740 % / -37 % |
| XAUUSD_M5 | 220 % / 0 % | 110 % / 0 % | 255 % / 0 % |
| XAUUSD_M10 | 206 % / 0 % | 90 % / 0 % | 237 % / 0 % |
| XAUUSD_M15 | 157 % / 0 % | 81 % / 0 % | 185 % / 0 % |
| XAUUSD_M30 | 229 % / -1 % | 47 % / -1 % | 349 % / -1 % |
| XAUUSD_M60 | 275 % / 1 % | 138 % / 1 % | 308 % / 1 % |
| XAUUSD_M240 | 125 % / -1 % | 63 % / -1 % | 126 % / -1 % |

### Year-by-year net profit (modern spread, USD on a $10k start, compounding)

| Config | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | profitable years |
|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSD_M1 |  |  |  | -30 | 63,778 | 51,137 | 6,251,660 | 2,251,649 | 1,942,577 | 5/6 |
| BTCUSD_M2 |  |  |  |  | 62,163 | 28,943 | 3,044,738 | 2,141,105 | 1,818,668 | 5/5 |
| BTCUSD_M3 |  |  |  | -19 | 43,413 | 32,814 | 2,019,581 | 1,076,544 | 1,142,268 | 5/6 |
| BTCUSD_M5 |  |  |  |  | 51,613 | 48,418 | 2,157,012 | 1,072,341 | 1,234,902 | 5/5 |
| BTCUSD_M10 |  |  |  |  | 35,319 | 35,003 | 1,714,735 | 1,061,918 | 494,538 | 5/5 |
| BTCUSD_M15 |  |  |  |  | 38,483 | 34,339 | 1,162,708 | 1,125,378 | 402,484 | 5/5 |
| BTCUSD_M30 |  |  |  |  | 25,925 | 18,764 | 1,058,426 | 496,352 | 131,425 | 5/5 |
| BTCUSD_M60 |  |  |  |  | 4,536 | 11,302 | 46,272 | 75,723 | 37,598 | 5/5 |
| BTCUSD_M240 |  |  |  |  | 2,573 | 7,903 | 20,647 | 14,890 | 12,501 | 5/5 |
| XAUUSD_M1 | 14,565 | 3,340 | 8,921 | -708 | 1,179 | 5,642 | -3 | 226 |  | 6/8 |
| XAUUSD_M2 | 18,778 | 1,852 | 3,291 | -122 | 264 | 2,570 |  |  |  | 5/6 |
| XAUUSD_M3 | 12,801 | -621 | 12,217 | 9,440 | -2,351 | 7,528 | -1,127 | 2,012 |  | 5/8 |
| XAUUSD_M5 | 1,081 | 6,782 | 6,609 | -348 | 5,654 | 547 | 471 | 1,220 |  | 7/8 |
| XAUUSD_M10 | -559 | 7,090 | 6,893 | 3,067 | 2,714 | 157 | 1,435 | -160 |  | 6/8 |
| XAUUSD_M15 | -439 | 2,835 | 4,206 | 1,541 | 3,329 | 3,608 | 1,054 | -409 |  | 6/8 |
| XAUUSD_M30 | 1,907 | 3,090 | 2,672 | 3,701 | 3,774 | 4,991 | 1,095 | 1,720 |  | 8/8 |
| XAUUSD_M60 | 3,841 | 3,856 | 1,126 | 7,435 | 4,423 | 3,703 | 3,375 | -293 |  | 7/8 |
| XAUUSD_M240 | 1,113 | 2,822 | 2,853 | 675 | 1,764 | -97 | 2,626 | 748 |  | 7/8 |

### Inputs of every calibrated preset (only values that differ from the shipped Tester preset are listed)

**BTCUSD_M1** (`presets/DPFX_BTCUSD_M1_calibrated.set`)

```
atrLenS2 = 50
beTriggerAtr = 0.5
cooldownIn = 20
deadBarsIn = 30
entryWindowIn = 0200-1000
manualDeltaThreshold = 1.25
manualEmaLength = 20
manualEntryMode = Close Beyond Key Zone
manualLossClusterPauseBars = 6
manualMaxZoneAge = 400
manualZoneLength = 20
nySession = 0200-1700
presetMode = Manual
slAtrMultS2 = 2.0
timeStopBars = 100
tpRS2 = 0
tradeOriginalDirection = True
trailActAtr = 0.5
trailDstAtr = 1.0
useDailyBlackout = False
useDeadExit = False
useDirectionalMicroFilter = False
useEntryBuffer = False
useSundayBlock = False
useTrailS2 = True
useV1011LossClusterPause = False
useV1013VolCostFilter = False
useV105DirectionalFilter = False
useWeekendBlackout = False
```

**BTCUSD_M2** (`presets/DPFX_BTCUSD_M2_calibrated.set`)

```
atrLenS2 = 50
beTriggerAtr = 2.0
deadBarsIn = 10
entryWindowIn = 0300-1200
manualDeltaThreshold = 1.0
manualEmaLength = 20
manualEntryMode = Close Beyond Key Zone
manualLossClusterPauseBars = 24
manualMaxZoneAge = 400
manualZoneLength = 150
minStopToCostRatio = 6.0
nySession = 0200-1700
presetMode = Manual
slAtrMultS2 = 1.0
timeStopBars = 0
tradeOriginalDirection = True
trailActAtr = 0.5
trailDstAtr = 0.5
useDailyBlackout = False
useDirectionalMicroFilter = False
useEntryBuffer = False
useRobustHourFilter = False
useTrailS2 = True
useV1011LossClusterPause = False
useV105DirectionalFilter = False
```

**BTCUSD_M3** (`presets/DPFX_BTCUSD_M3_calibrated.set`)

```
atrLenS2 = 50
beTriggerAtr = 0.5
deadBarsIn = 5
manualDeltaThreshold = 1.0
manualEmaLength = 20
manualEntryMode = Close Beyond Key Zone
manualInvalidate = False
manualLossClusterPauseBars = 6
manualMaxZoneAge = 400
manualUseEmaFilter = True
manualZoneLength = 30
minStopToCostRatio = 6.0
nySession = 0300-1200
presetMode = Manual
slAtrMultS2 = 0.75
timeStopBars = 0
tpRS2 = 15.0
tradeOriginalDirection = True
trailActAtr = 1.0
trailDstAtr = 0.5
useBreakeven = True
useCooldown = False
useDailyBlackout = False
useDirectionalMicroFilter = False
useSundayBlock = False
useTrailS2 = True
useV1013VolCostFilter = False
useWeekendBlackout = False
```

**BTCUSD_M5** (`presets/DPFX_BTCUSD_M5_calibrated.set`)

```
atrLenS2 = 30
beTriggerAtr = 0.5
cooldownIn = 5
deadBarsIn = 10
entryWindowIn = 1800-0200
manualDeltaThreshold = 1.0
manualEmaLength = 20
manualLossClusterCount = 3
manualLossClusterPauseBars = 6
manualZoneLength = 150
minStopToCostRatio = 6.0
nySession = 0200-1700
presetMode = Manual
tpRS2 = 0
tradeOriginalDirection = True
trailActAtr = 0.5
trailDstAtr = 0.2
useBreakeven = True
useCooldown = False
useDirectionalMicroFilter = False
useOnePerZone = False
useRobustHourFilter = False
useSundayBlock = False
useTrailS2 = True
useV105DirectionalFilter = False
useWeekendBlackout = False
```

**BTCUSD_M10** (`presets/DPFX_BTCUSD_M10_calibrated.set`)

```
atrLenS2 = 30
beTriggerAtr = 1.5
cooldownIn = 5
entryWindowIn = 1800-0200
manualDeltaThreshold = 1.0
manualEmaLength = 20
manualLossClusterPauseBars = 24
manualUseEmaFilter = True
manualZoneLength = 100
manualZoneTrend = True
minStopToCostRatio = 10.0
nySession = 0200-1700
presetMode = Manual
slAtrMultS2 = 0.3
tpRS2 = 6.0
trailActAtr = 0.5
trailDstAtr = 0.2
useDirectionalMicroFilter = False
useOnePerZone = False
useTrailS2 = True
useV1010PfFilter = False
useV1011LossClusterPause = False
useV105DirectionalFilter = False
useWeekendBlackout = False
```

**BTCUSD_M15** (`presets/DPFX_BTCUSD_M15_calibrated.set`)

```
atrLenS2 = 50
beTriggerAtr = 0.5
manualDeltaThreshold = 1.25
manualEmaLength = 50
manualLossClusterCount = 8
manualLossClusterPauseBars = 6
manualMaxZoneAge = 25
manualZoneLength = 100
minStopToCostRatio = 6.0
nySession = 0200-1700
presetMode = Manual
slAtrMultS2 = 0.3
timeStopBars = 200
tpRS2 = 15.0
trailActAtr = 0.5
trailDstAtr = 0.2
useCooldown = False
useDeadExit = False
useOnePerZone = False
useRobustHourFilter = False
useSundayBlock = False
useTrailS2 = True
useV1010PfFilter = False
useV1011LossClusterPause = False
useV1013VolCostFilter = False
useV105DirectionalFilter = False
useWeekendBlackout = False
```

**BTCUSD_M30** (`presets/DPFX_BTCUSD_M30_calibrated.set`)

```
atrLenS2 = 50
beTriggerAtr = 0.5
deadBarsIn = 30
entryWindowIn = 0800-1700
manualDeltaThreshold = 1.25
manualEmaLength = 20
manualLossClusterCount = 8
manualLossClusterPauseBars = 24
manualMaxZoneAge = 400
manualZoneLength = 30
minStopToCostRatio = 2.0
presetMode = Manual
slAtrMultS2 = 0.3
timeStopBars = 10
tpRS2 = 6.0
trailActAtr = 2.0
trailDstAtr = 1.0
useBreakeven = True
useDailyBlackout = False
useDeadExit = False
useEntryBuffer = False
useOnePerZone = False
useSundayBlock = False
useV1011LossClusterPause = False
useWeekendBlackout = False
```

**BTCUSD_M60** (`presets/DPFX_BTCUSD_M60_calibrated.set`)

```
atrLenS2 = 7
manualLossClusterCount = 3
manualLossClusterPauseBars = 24
manualMaxZoneAge = 50
manualUseEmaFilter = True
minStopToCostRatio = 10.0
nySession = 0200-1700
slAtrMultS2 = 2.0
timeStopBars = 20
tpRS2 = 6.0
tradeOriginalDirection = True
trailActAtr = 2.0
trailDstAtr = 0.2
useDailyBlackout = False
useRobustHourFilter = False
useSessionFilter = True
useV1010PfFilter = False
useV1013VolCostFilter = False
useV105DirectionalFilter = False
useWeekendBlackout = False
```

**BTCUSD_M240** (`presets/DPFX_BTCUSD_M240_calibrated.set`)

```
atrLenS2 = 7
cooldownIn = 3
deadBarsIn = 20
entryWindowIn = 1800-0200
manualDeltaThreshold = 1.0
manualEmaLength = 20
manualEntryMode = Close Beyond Key Zone
manualInvalidate = False
manualLossClusterCount = 3
manualZoneLength = 30
minStopToCostRatio = 2.0
nySession = 0300-1200
presetMode = Manual
slAtrMultS2 = 2.0
timeStopBars = 20
tpRS2 = 2.0
tradeOriginalDirection = True
trailActAtr = 0.5
trailDstAtr = 2.0
useBreakeven = True
useCooldown = False
useDailyBlackout = False
useDeadExit = False
useDirectionalMicroFilter = False
useSundayBlock = False
useTrailS2 = True
useV1011LossClusterPause = False
```

**XAUUSD_M1** (`presets/DPFX_XAUUSD_M1_calibrated.set`)

```
atrLenS2 = 30
manualInvalidate = False
manualLossClusterCount = 8
manualLossClusterPauseBars = 6
manualMaxZoneAge = 100
manualMinRetestBars = 5
manualUseEmaFilter = True
minStopToCostRatio = 6.0
nySession = 0300-1200
slAtrMultS2 = 1.0
timeStopBars = 0
tpRS2 = 15.0
tradeOriginalDirection = True
trailActAtr = 3.0
trailDstAtr = 0.5
useDailyBlackout = False
useDirectionalMicroFilter = False
useRobustHourFilter = False
useTrailS2 = True
useV1010PfFilter = False
useV105DirectionalFilter = False
```

**XAUUSD_M2** (`presets/DPFX_XAUUSD_M2_calibrated.set`)

```
atrLenS2 = 30
manualLossClusterCount = 3
manualLossClusterPauseBars = 6
minStopToCostRatio = 6.0
nySession = 0300-1200
timeStopBars = 0
trailActAtr = 4.0
trailDstAtr = 0.2
useDirectionalMicroFilter = False
useRobustHourFilter = False
useV1010PfFilter = False
useV1011LossClusterPause = False
useV105DirectionalFilter = False
useWeekendBlackout = False
```

**XAUUSD_M3** (`presets/DPFX_XAUUSD_M3_calibrated.set`)

```
atrLenS2 = 7
manualLossClusterCount = 3
manualMaxZoneAge = 25
manualUseEmaFilter = True
minStopToCostRatio = 10.0
nySession = 0800-1200
slAtrMultS2 = 1.25
timeStopBars = 0
tpRS2 = 15.0
trailActAtr = 2.0
trailDstAtr = 2.0
useDirectionalMicroFilter = False
useV1011LossClusterPause = False
useV105DirectionalFilter = False
```

**XAUUSD_M5** (`presets/DPFX_XAUUSD_M5_calibrated.set`)

```
beTriggerAtr = 0.5
cooldownIn = 5
deadBarsIn = 30
entryWindowIn = 0800-1700
manualDeltaThreshold = 4.0
manualInvalidate = False
manualMaxZoneAge = 25
manualZoneLength = 30
manualZoneTrend = True
nySession = 0200-1700
presetMode = Manual
slAtrMultS2 = 1.5
timeStopBars = 200
tpRS2 = 8.0
tradeOriginalDirection = True
trailActAtr = 4.0
trailDstAtr = 2.0
useDailyBlackout = False
useDeadExit = False
useEntryWindow = True
useOnePerZone = False
useRobustHourFilter = False
useTrailS2 = True
useWeekendBlackout = False
```

**XAUUSD_M10** (`presets/DPFX_XAUUSD_M10_calibrated.set`)

```
atrLenS2 = 7
cooldownIn = 20
deadBarsIn = 30
manualDeltaThreshold = 4.0
manualEmaLength = 20
manualEntryMode = Close Beyond Key Zone
manualInvalidate = False
manualLossClusterCount = 8
manualLossClusterPauseBars = 24
manualMaxZoneAge = 50
manualUseEmaFilter = True
manualZoneLength = 150
minStopToCostRatio = 6.0
nySession = 0200-1700
presetMode = Manual
slAtrMultS2 = 0.75
timeStopBars = 20
tpRS2 = 0
tradeOriginalDirection = True
trailActAtr = 4.0
trailDstAtr = 2.0
useCooldown = False
useDailyBlackout = False
useDeadExit = False
useEntryBuffer = False
useEntryWindow = True
useSundayBlock = False
useTrailS2 = True
useV1010PfFilter = False
useV1011LossClusterPause = False
useV1013VolCostFilter = False
useWeekendBlackout = False
```

**XAUUSD_M15** (`presets/DPFX_XAUUSD_M15_calibrated.set`)

```
beTriggerAtr = 2.0
cooldownIn = 5
deadBarsIn = 10
entryWindowIn = 0300-1200
manualDeltaThreshold = 4.0
manualEmaLength = 20
manualEntryMode = Close Beyond Key Zone
manualLossClusterCount = 8
manualLossClusterPauseBars = 6
manualMaxZoneAge = 400
manualZoneLength = 100
manualZoneTrend = True
minStopToCostRatio = 2.0
nySession = 0200-1700
presetMode = Manual
slAtrMultS2 = 3.0
timeStopBars = 100
tpRS2 = 8.0
tradeOriginalDirection = True
trailActAtr = 2.0
trailDstAtr = 0.2
useBreakeven = True
useCooldown = False
useDailyBlackout = False
useDeadExit = False
useEntryBuffer = False
useRobustHourFilter = False
useSundayBlock = False
useTrailS2 = True
useV1010PfFilter = False
useV1011LossClusterPause = False
useV105DirectionalFilter = False
```

**XAUUSD_M30** (`presets/DPFX_XAUUSD_M30_calibrated.set`)

```
beTriggerAtr = 0.5
cooldownIn = 5
deadBarsIn = 20
entryWindowIn = 0200-1000
manualEmaLength = 200
manualEntryMode = Close Beyond Key Zone
manualLossClusterPauseBars = 6
manualMaxZoneAge = 50
manualMinRetestBars = 2
manualZoneLength = 30
manualZoneTrend = True
minStopToCostRatio = 2.0
nySession = 0200-1700
presetMode = Manual
slAtrMultS2 = 1.5
timeStopBars = 100
tradeOriginalDirection = True
trailActAtr = 0.5
trailDstAtr = 0.2
useBreakeven = True
useCooldown = False
useDailyBlackout = False
useDeadExit = False
useEntryWindow = True
useOnePerZone = False
useRobustHourFilter = False
useSundayBlock = False
useTrailS2 = True
useV1010PfFilter = False
useV1013VolCostFilter = False
useWeekendBlackout = False
```

**XAUUSD_M60** (`presets/DPFX_XAUUSD_M60_calibrated.set`)

```
atrLenS2 = 10
beTriggerAtr = 1.5
cooldownIn = 3
deadBarsIn = 10
entryWindowIn = 1800-0200
manualDeltaThreshold = 1.25
manualEmaLength = 50
manualEntryMode = Close Beyond Key Zone
manualInvalidate = False
manualLossClusterPauseBars = 6
manualMaxZoneAge = 400
manualUseEmaFilter = True
manualZoneLength = 75
minStopToCostRatio = 2.0
presetMode = Manual
slAtrMultS2 = 1.0
tpRS2 = 4.1667
tradeOriginalDirection = True
trailActAtr = 1.0
trailDstAtr = 0.5
useCooldown = False
useDailyBlackout = False
useEntryBuffer = False
useEntryWindow = True
useOnePerZone = False
useRobustHourFilter = False
useSundayBlock = False
useTrailS2 = True
useV1011LossClusterPause = False
useV1013VolCostFilter = False
useV105DirectionalFilter = False
useWeekendBlackout = False
```

**XAUUSD_M240** (`presets/DPFX_XAUUSD_M240_calibrated.set`)

```
atrLenS2 = 10
manualInvalidate = False
manualLossClusterPauseBars = 24
manualMaxZoneAge = 50
manualMinRetestBars = 2
manualUseEmaFilter = True
minStopToCostRatio = 10.0
slAtrMultS2 = 1.25
timeStopBars = 0
tpRS2 = 2.0
tradeOriginalDirection = True
trailActAtr = 0.5
trailDstAtr = 1.0
useDailyBlackout = False
useDirectionalMicroFilter = False
useSessionFilter = True
useTrailS2 = True
useV1010PfFilter = False
useV1011LossClusterPause = False
useWeekendBlackout = False
```

### Slippage stress (modern spread plus extra slippage per fill; R per trade, PF)

| Config | +0 | gold +$0.05 / BTC +0.5 bp | gold +$0.10 / BTC +1 bp | 2026 export (+0) |
|---|---|---|---|---|
| XAUUSD_M5 | +0.42 R, PF 1.55 | +0.34 R, PF 1.44 | +0.27 R, PF 1.34 | no trades (28-day sample) |
| XAUUSD_M10 | +0.44 R, PF 1.46 | +0.37 R, PF 1.37 | +0.30 R, PF 1.28 | no trades |
| XAUUSD_M15 | +0.18 R, PF 1.54 | +0.16 R, PF 1.47 | +0.14 R, PF 1.40 | no trades |
| XAUUSD_M30 | +0.10 R, PF 1.22 | +0.07 R, PF 1.14 | +0.03 R, PF 1.05 | 24 trades, −0.04 R |
| XAUUSD_M60 | +0.21 R, PF 1.32 | +0.19 R, PF 1.28 | +0.15 R, PF 1.22 | 26 trades, +0.03 R |
| XAUUSD_M240 | +0.32 R, PF 1.76 | +0.32 R, PF 1.73 | +0.30 R, PF 1.68 | 2 trades |
| XAUUSD_M1 | +0.20 R, PF 1.27 | +0.12 R, PF 1.15 | +0.03 R, PF 1.04 | 1036 trades, +0.11 R |
| XAUUSD_M2 | +0.32 R, PF 1.44 | +0.22 R, PF 1.30 | +0.15 R, PF 1.20 | 1045 trades, −0.02 R |
| XAUUSD_M3 | +0.08 R, PF 1.09 | +0.04 R, PF 1.04 | −0.00 R, PF 0.98 | 632 trades, −0.08 R |
| BTCUSD_M240 | +0.18 R, PF 1.61 | +0.18 R, PF 1.60 | +0.18 R, PF 1.59 | 36 trades, +0.22 R |
| BTCUSD_M60 | +0.28 R, PF 1.43 | +0.27 R, PF 1.42 | +0.26 R, PF 1.41 | 37 trades, −0.17 R |
| BTCUSD_M30 | +0.12 R, PF 1.16 | +0.04 R, PF 1.10 | −0.04 R, PF 1.04 | 1040 trades, −0.18 R |
| BTCUSD_M15 | +0.13 R, PF 1.19 | −0.00 R, PF 1.11 | −0.11 R, PF 0.96 | 1793 trades, −0.23 R |
| BTCUSD_M5 | +0.18 R, PF 1.20 | −0.04 R, PF 1.09 | −0.22 R, PF 0.95 | 2468 trades, −0.41 R |
| BTCUSD_M1 | +0.12 R, PF 1.28 | −0.01 R, PF 1.16 | −0.13 R, PF 1.04 | 4404 trades, −0.24 R |

Reading: the gold M5-H4 and bitcoin H1/H4 sets lose 10-25 % of their edge under double
slippage and stay clearly positive; the bitcoin sub-H1 sets and gold M1-M3 go to zero or
negative, and the 2026 feed confirms it with thousands of trades.

## 5. Recommended sets

Ranked by how much evidence supports them. All use `ExitMode = ATR`, `QtyMode = Risk %`,
`riskPctS3 = 1.0` as shipped; the `.set` files in `presets/` carry every other input at the
shipped value. Each needs a fresh `RecoverySession` per independent tester run (README rule).

| Rank | Set | Why |
|---|---|---|
| 1 | `XAUUSD_M60` | OOS t 1.9, 1 084 trades, 7/8 years, PF 1.32, 12 % DD, slippage-robust, flat-positive on 2026 |
| 2 | `XAUUSD_M30` | OOS t 2.3, 1 940 trades, 8/8 years, PF 1.22, 15 % DD; thinnest per-trade margin, watch costs |
| 3 | `XAUUSD_M15` | OOS t 2.3, PF 1.54, 8 % DD, 61 % win; only 70 trades/yr |
| 4 | `BTCUSD_M240` | PF 1.61, 5/5 years, +8 % on the 2026 sample, cost-insensitive |
| 5 | `XAUUSD_M5` / `XAUUSD_M10` / `XAUUSD_M240` | strong per-trade R (0.3-0.4) but 30-90 trades/yr, OOS t only 1.1-1.8 |
| — | `BTCUSD_M60` | good history, slightly negative on 37 trades in 2026 — paper-trade first |
| ✗ | gold M1-M3, bitcoin M1-M30 | spread-dependent; do not trade, do not trust the TradingView number |

To reproduce a set on TradingView: the Pine inputs have the same names as the MT5 inputs
(the MT5 file is generated from the Pine source); set `Preset Mode` to Manual or XAUUSD 5m as
listed, then the values in section 4. Because TradingView charges no spread by default, set
*Properties → Commission* or *Slippage* to approximate the $0.12 / 2.2 bp spread, otherwise
TradingView will overstate every result here, dramatically so on the short timeframes.

## 6. Caveats

* The MT5 port processes every tick, so real fills happen on the first tick after the bar close,
  not at the next bar's open; the difference is one tick of price on each fill, which the
  slippage stress covers.
* The 2026 samples are short (28 trading days of gold, 58 of bitcoin). They are decisive where
  thousands of trades happen (sub-H1) and uninformative where 0-40 trades happen.
* The bitcoin 2015-2017 history is sparse (28-37 % of minutes have a single tick); intrabar
  stop/target resolution on it is optimistic. This is another reason the sub-H1 bitcoin numbers
  are not believable, and it mildly flatters the H1/H4 numbers too.
* Gold history ends mid-2018; 2019-2025 (including the 2020 and 2024-25 regimes) is not in the
  data you have in the repo. Add Octa tick exports for those years (`convert_mt5_ticks.py` from
  the RegimeTrend toolkit writes the same npz layout) and rerun — the pipeline is ~40 minutes.
* No profitability guarantee is implied; 1 % risk with 10-15 % historical drawdown means 25-30 %
  drawdowns are plausible live.

## 7. Reproduction

```
cd danny_phantom_calibration/tools
export DP_DATA=/path/to/npz DP_CACHE=/tmp/dp_cache
python -I baseline.py                      # shipped preset, every timeframe, three spread models
python -I sweep.py XAUUSD 60 16000         # stage 1 (one symbol / timeframe)
python -I refine.py XAUUSD 60              # stage 2
python -I final_eval.py                    # tables, equity charts, .set presets
```

Files: `results/final_table.csv` (every metric, every spread model), `results/final_configs.json`,
`results/refined_*.csv` (six finalists per timeframe), `results/equity_*.png`, `presets/*.set`,
`baseline.txt`. The raw 16 000-row stage-1 sweeps are git-ignored (90 MB) and live in the
session scratchpad.
