# SPEC_danny: Danny Phantom FX V10.21.1 LiveSafe + FGF (key `danny`), stage 1 brief

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Read first: `$W/REPLICA_SPEC.md` (stages, interface, data, windows, cost modes), `$W/SPEC_AH.md`
(Pine built-ins, the intrabar path = "rule 4"), `$W/SWEEP_AH_SPEC.md` section 2 (prepare / simulate,
'mag', 'stress', fair halves), `$W/hrd.py` (worked example of a numba broker with the same summary).

Ground truth: `/home/user/master/DannyPhantomFX_V10_21_1_LiveSafe_FGF.pine` at HEAD (1,560 lines;
line numbers `Lnnn` below are of this file). Unfused original:
`/home/user/master/DannyPhantomFX_V10_21_1_LiveSafe.pine` (872 lines). The fused file = the original
+ the filter block (L249-829, replicated by `$W/fgf.py`, do not reimplement) + the gate
`fgfBuyOk` / `fgfSellOk` in the two entry conditions + Update 1 (`dpInv`, L832, L1291-1296) + the
FGD plots. Where this brief and the Pine disagree, the Pine wins; say so in your notes.

This script is different from apex / hrd / xpw in four ways that shape everything below:
1. `process_orders_on_close = true` AND `calc_on_order_fills = true`: market orders fill at the
   close of the candle that placed them, and the script runs again after every fill. The exit
   bracket is only ever placed in such a re-run (section 5).
2. The stop / target / trailing / breakeven are computed by hand from `strategy.position_avg_price`
   and re-sent every candle with `strategy.exit(stop=, limit=)`. There is no `trail_points`.
3. `strategy()` charges 75 ticks of slippage per fill: with cost 'tv' the fill PRICE moves, so the
   average price, the bracket, the dead-trade test and the sizing all depend on the cost mode.
4. Presets: on a XAUUSD 5-minute chart "Preset Mode = Auto" switches to another rule set
   (section 2). On our data that is the cell XAU "5", and there the default script takes NO trade.

Section 9 lists every assumption with an id (E1-E3 are the important ones). An indicative,
unverified stage-1 probe exists in `.../scratchpad/danny_spec_probe/`; builders must NOT read it
(it would make the two builds share its mistakes). Its rough numbers are quoted in section 13 only
as an order of magnitude.

---------------------------------------------------------------------------------------------------

## 1. The `strategy()` call (L75), argument by argument

```
strategy("OF S/D Robust — Inverted FX Top 3 V10.21.1 LiveSafe [Update 1]", shorttitle="DPFX10.211 U1",
  overlay=true, pyramiding=0, initial_capital=2000, default_qty_type=strategy.fixed, default_qty_value=1,
  calc_on_every_tick=false, calc_on_order_fills=true, process_orders_on_close=true,
  commission_type=strategy.commission.percent, commission_value=0.001, slippage=75,
  margin_long=0.2, margin_short=0.2, max_lines_count=500, max_labels_count=500, max_bars_back=500)
```

| argument | meaning for the replica |
|---|---|
| `pyramiding=0` | at most one entry per side. The script never sends a same-side entry anyway (position test in the entry condition). An opposite `strategy.entry` reverses in ONE order. |
| `initial_capital=2000` | `INITIAL_CAPITAL = 2000.0` (not 1,000,000). Net % DOES depend on it: `maxQtyS3 = 50` and `qtyStepS3 = 0.001` are absolute. |
| `default_qty_type=fixed, default_qty_value=1` | unused: every `strategy.entry` passes `qty = f_qty(...)` (section 7). |
| `calc_on_every_tick=false` | live only (no per-tick runs). No effect on history. |
| `calc_on_order_fills=true` | the script runs again after every order fill, also on history. Section 5 (E1-E3). |
| `process_orders_on_close=true` | a market order placed in the bar-close run fills at THAT bar's close. Stop / limit exit orders are evaluated inside the following bars. |
| `commission_type=percent, commission_value=0.001` | 0.001 % of the fill value per fill = `1e-5 * fill_px * qty * pointvalue`, on every fill (entry, exit; a reversal = the closing fill + the opening fill). |
| `slippage=75` | 75 ticks = 75 x mintick = **0.75 price units** on a 0.01-tick symbol, added against the order on every MARKET fill and every STOP fill; LIMIT fills (the target) get none. Section 8. |
| `margin_long=0.2, margin_short=0.2` | 0.2 % margin (500x). Not modelled: the script's own cap (`capMarginS3`, 1 %) is 5 times stricter, so TradingView's margin check cannot bind at entry; a margin call needs a loss of about 80 % of equity inside one trade. The replica counts `margin_breach` (section 11), expected 0. |
| `overlay`, `max_*` | drawing / history buffers: ignored. |

Symbol constants: `syminfo.mintick = 0.01`, `syminfo.pointvalue = 1` for both pairs.
`syminfo.ticker`: pair `XAU` = "XAUUSD", pair `BTC` = "BTCUSD" (E11). `timeframe.isminutes` is true
on every chart here and `tfMin = int(chart_tf)`.

---------------------------------------------------------------------------------------------------

## 2. Presets and the "active settings" (L849-933)

`presetMode` (L83, default "Auto"). Replica support:

| `presetMode` | replica |
|---|---|
| "Auto" | `presetXAUUSD = (pair == 'XAU' and chart_tf == '5')` (L854, L862, L869). Every other cell: no preset. |
| "XAUUSD 5m" | `presetXAUUSD = True` on any pair / chart (forced). |
| "Manual" | no preset; additionally `zoneTrendFilter = manualZoneTrend` (L923: only with the literal value "Manual"). |
| "AUDJPY 2m", "EURGBP 3m", "USDCAD 5m", "XAGUSD 5m", "NAS100 5m" | other markets: `raise NotImplementedError`. (Not needed for BTC / XAU; NAS100 would need `strategy.opentrades.max_runup` for the adaptive dead exit, L1099-1115.) |

With that, `usingFxPreset = topThreePreset = presetXAUUSD`, `presetXAGUSD = presetNAS100 = false`,
`useProfile = usingFxPreset and (lockAutoProfile or v2Source == "Auto Optimized Profile")` (L874;
defaults true / "Auto Optimized Profile").

Active settings (left: with the XAUUSD 5m preset; right: without):

| Pine name (line) | preset XAUUSD 5m | no preset |
|---|---|---|
| `zoneLengthInput` (899) | 50 | `manualZoneLength` |
| `deltaThresholdInput` (900) | 1.5 | `manualDeltaThreshold` |
| `emaLength` (901) | 100 | `manualEmaLength` |
| `entryMode` (920) | "Normal Retest Touch" | `manualEntryMode` |
| `deadExitActive` (908) | `useProfile ? false : useDeadExit` (profDeadOn = not presetXAUUSD) | `useDeadExit` |
| `deadBars` (909) | `useProfile ? 15 : deadBarsIn` | `deadBarsIn` |
| `breakevenActive`, `beTrigger` (910-911) | `useProfile ? false, 1.0 : useBreakeven, beTriggerAtr` | `useBreakeven`, `beTriggerAtr` |
| `entryBufferActive`, `entryBufferMin` (912-913) | `useProfile ? true, 60 : useEntryBuffer, entryBufferIn` | `useEntryBuffer`, `entryBufferIn` |
| `sundayBlockActive` (914) | `useProfile ? true : useSundayBlock` | `useSundayBlock` |
| `entryWindowActive`, `entryWindow` (915-916) | `useProfile ? false, "0800-1200" : useEntryWindow, entryWindowIn` | `useEntryWindow`, `entryWindowIn` |
| `onePerZoneActive` (917) | `useProfile ? true : useOnePerZone` | `useOnePerZone` |
| `cooldownActive`, `cooldownBars` (918-919) | `useProfile ? true, 10 : useCooldown, cooldownIn` | `useCooldown`, `cooldownIn` |
| `lossClusterTrigger`, `lossClusterPauseBars` (932-933) | 5, 12 | `manualLossClusterCount`, `manualLossClusterPauseBars` (5, 12) |
| `robustHourBlock` (947) | `useRobustHourFilter and hourNY in {3, 14, 18}` | false |
| `longDirectionalBlock` (953) | `useDirectionalMicroFilter and hourNY == 4 and minuteNY < 15` | false |
| `shortDirectionalBlock` (959) | `useDirectionalMicroFilter and hourNY == 9 and minuteNY < 15` | false |
| `v105LongBlock` (965) | `useV105DirectionalFilter and ((hourNY == 10 and 15 <= minuteNY < 30) or (hourNY == 11 and minuteNY >= 30))` | false |
| `v105ShortBlock` (971) | false (NAS100 / XAGUSD only) | false |
| `v1010LongBlock` (976) | `useV1010PfFilter and ((hourNY == 1 and 15 <= minuteNY < 30) or (hourNY == 4 and 15 <= minuteNY < 30))` | false |
| `v1010ShortBlock` (982) | `useV1010PfFilter and hourNY == 4 and minuteNY >= 45` | false |
| `topThreeCostProfile` (1089) -> cost filter (1097) | active if `useV1013VolCostFilter` | never |

Always manual, with or without a preset: `useEmaFilter = manualUseEmaFilter` (922),
`invalidateZones = manualInvalidate`, `minRetestBars = manualMinRetestBars`,
`maxZoneAge = manualMaxZoneAge` (924-926), `atrLength = atrLenS2` (927), `maxBarsInTrade =
timeStopBars`, `useTrailing = useTrailS2` (906-907), the loss-cluster switch
`lossClusterProfileActive = useV1011LossClusterPause` (931), the blackout inputs.
`zoneTrendFilter` (923) is `manualZoneTrend` ONLY when `presetMode == "Manual"`, else false.

**Fact (checked on the data): on XAU "5" with the defaults the script takes no trade.** The cost
filter needs `slDistNow / (2 x 75 x 0.01 + close x 0.00002) >= 4`, i.e. a stop distance of about
$6.10; 1.2 x ATR(14) of 5-minute gold is $0.71 at the median and never above $3.3 in the window
(max ratio 2.15, 0 of 98,787 bars pass). The preset was written for a finer tick. Implement it as
written; report it; the calibration uses `presetMode = "Manual"` on that cell (section 14).

---------------------------------------------------------------------------------------------------

## 3. Inputs

### 3.1 SIGNAL inputs -> `prepare(pair, chart_tf, params)` (per-bar arrays, no position needed)

| Pine name | default | used for |
|---|---|---|
| `presetMode`, `v2Source`, `lockAutoProfile` | "Auto", "Auto Optimized Profile", true | section 2 |
| `manualZoneLength` | 50 | `ta.sma(|volumeDelta|, n)` |
| `manualDeltaThreshold` | 1.5 | spike threshold |
| `manualUseEmaFilter`, `manualEmaLength` | true, 100 | `trendAllowsLong / Short`; also `zoneTrendFilter` |
| `manualZoneTrend` | false | only with `presetMode == "Manual"` |
| `manualMinRetestBars`, `manualMaxZoneAge`, `manualInvalidate`, `manualEntryMode` | 1, 200, true, "Normal Retest Touch" | the zone machine (it RUNS in `simulate`, section 6, but these are fixed at `prepare` and stored in P as scalars) |
| `useEntryBuffer`, `entryBufferIn` | true, 60 | `nearBlackout` |
| `useSundayBlock` | true | `sundayBlock` |
| `useEntryWindow`, `entryWindowIn` | false, "0800-1200" | `inEntryWindow` (E12) |
| `useSessionFilter`, `nySession` | false, "0930-1600" | `inSession` (E12) |
| `useRobustHourFilter`, `useDirectionalMicroFilter`, `useV105DirectionalFilter`, `useV1010PfFilter` | all true | preset XAUUSD 5m only |
| `useWeekendBlackout`, `useDailyBlackout`, `closeLeadMin` | true, true, 10 | blackout gates and the blackout close |
| `fgfOn` and every `fgf*` input | as `fgf.DEFAULTS` (filter on, "60", ...) | `fgf.fgf_permissions(pair, chart_tf, start, end, params)` -> `buyOk`, `sellOk`; with `fgfOn` False use all-True arrays without calling it |
| `start`, `end` (replica) | the pair's window | window override by `t_close`, as `hrd.py` |

### 3.2 ORDER / EXIT inputs -> `simulate(P, x)` (also accepted by `prepare` / `run` as defaults)

| Pine name | default | used for |
|---|---|---|
| `signalDirection` | "Inverted (V10 design)" | the OLDER reverse option: maps zone signals to BUY / SELL before the windows and the filter (section 6 step B9). The other value: "Original (un-inverted)". |
| `dpInv` (alias `inv`) | false | Update 1: flips the ORDER after the gate (section 6 step B11) |
| `ExitMode` | "ATR" | "Points" or "ATR" |
| `atrLenS2` | 14 | `atrValue = ta.atr(atrLenS2)` (prepare keeps what is needed to serve any length: cache per length) |
| `slAtrMultS2`, `tpRS2` | 1.2, 4.1667 | stop = mult x ATR; target = stop distance x R (0 = no target) |
| `slPointsIn`, `tpPointsIn` | 5000, 50000 | Points mode: x mintick (0 = none) |
| `useTrailS2`, `trailActAtr`, `trailDstAtr`, `trailActPts`, `trailPts` | false, 4.0, 0.2, 1000, 100 | trailing by hand |
| `timeStopBars` | 50 | time stop (0 = off) |
| `useDeadExit`, `deadBarsIn` | true, 15 | dead-trade exit (ignored when `useProfile`) |
| `useBreakeven`, `beTriggerAtr` | false, 1.0 | breakeven (ignored when `useProfile`) |
| `useOnePerZone` | true | one entry per zone (ignored when `useProfile`; see E2) |
| `useCooldown`, `cooldownIn` | true, 10 | cooldown after a dead / time exit (ignored when `useProfile`; see E2) |
| `useV1011LossClusterPause`, `manualLossClusterCount`, `manualLossClusterPauseBars` | true, 5, 12 | loss-cluster pause |
| `useV1013VolCostFilter`, `minStopToCostRatio`, `modeledSlippageTicksOverride` | true, 4.0, 0 | cost filter (preset only). It depends on the stop distance, so it is computed in `simulate`. |
| `QtyMode`, `fixedQtyS3`, `riskPctS3`, `maxQtyS3`, `qtyStepS3`, `capMarginS3`, `marginPctS3` | "Risk %", 10, 1.0, 50, 0.001, true, 1.0 | `f_qty` (section 7) |
| replica: `path` | 'tv' | 'tv' (stage 2), 'mag' (stage 3) |
| replica: `cost` | 'tv' | 'tv', 'ours', 'stress' (section 8) |
| replica: `varRollback` | True | E2 |

`simulate` raises if `x` tries to change a 3.1 key (as `hrd.simulate`).

### 3.3 Accepted, no effect in the replica (say so in the notes)

- `limitOneDecisionPerBar`, `limitOneFlatExitPerBar` (L103-105): the `varip` locks (L1231-1246).
  Under E1/E3 there is one decision per bar on history, so they never bind.
- `useV106GrowthSlTp` (L91): declared, never read.
- `useV1021NasAdaptiveDead`, `nasAdaptiveRunupAtr`: NAS100 preset only.
- With `varRollback` True (default): `useOnePerZone`, `useCooldown`, `cooldownIn` (E2).

### 3.4 Drawing / alerts only: listed once, ignored

`manualShowZones`, `appendLiveSafeId`, `appendExitReason`, `webhookPointSizeInput`, `useLotInAlert`,
`mt4Balance`, `mt4RiskPct`, `lotStep`, `minLot`, `maxLot`, `contractOverride`, `quoteUsd`, the six
colours, `showOriginalSignals`, `showRawActiveSignals`; the filter's `fgfShowBg`, `fgfShowLv`,
`fgfSigMark`, `fgfShowTbl`, `fgfTblPos`, `fgsShow`, `fgsWin`, `fgsH`. Also ignored: the alert
strings (L1207-1225), `contractSize`, the MT4 lot, all plots and both tables.

---------------------------------------------------------------------------------------------------

## 4. Series and gates computed in `prepare` (every series from the START of the data file)

Bars: `$W/data/<PAIR>_<TF>.parquet` + `<PAIR>_<TF>_vol.parquet` (same rows). `time` = `t_open`,
`bar_index` = the row number in the file. `x[1]` = the previous row (na on row 0).

```
priceRange  = high - low
upFraction  = (close - low) / priceRange            if priceRange != 0
            = 1.0 if close > nz(close[1], close)    else 0.0 if close < nz(close[1], close) else 0.5
safeVolume  = nz(volume, 1.0)                       (no NaN / zero volume in our files)
volumeDelta = safeVolume*upFraction - safeVolume*(1 - upFraction)
avgDelta    = ta.sma(abs(volumeDelta), zoneLengthInput)      (includes the current bar; na for the first n-1 rows)
emaValue    = ta.ema(close, emaLength)                       (seeded with the first close, SPEC_AH)
atrValue    = ta.atr(atrLenS2) = RMA(true range, n), TR[0] = high-low, seeded with the SMA of the first n TRs
              (the same formula as fgf._atr, which matched TradingView for the filter)
rawDemandSpike = not na(avgDelta) and volumeDelta >  avgDelta*deltaThresholdInput and close > open
rawSupplySpike = not na(avgDelta) and volumeDelta < -avgDelta*deltaThresholdInput and close < open
isDemandSpike  = zoneTrendFilter ? rawDemandSpike and close > emaValue : rawDemandSpike
isSupplySpike  = zoneTrendFilter ? rawSupplySpike and close < emaValue : rawSupplySpike
trendAllowsLong  = not useEmaFilter or close > emaValue
trendAllowsShort = not useEmaFilter or close < emaValue
```

New York clock of the bar OPEN (L942-945), with daylight saving (zoneinfo / pandas
`tz_convert('America/New_York')`): `dowNY` in Pine numbering (Sunday = 1 ... Saturday = 7),
`hourNY`, `minuteNY`, `minutesNY = hourNY*60 + minuteNY`. `dailyStartMin = 1015` (16:55),
`dailyEndMin = 1080` (18:00).

```
weekendBlackout  = useWeekendBlackout and ((dowNY == 6 and minutesNY >= 1015) or dowNY == 7 or (dowNY == 1 and minutesNY < 1080))
dailyBlackout    = useDailyBlackout and 2 <= dowNY <= 5 and 1015 <= minutesNY < 1080
blackoutActive   = weekendBlackout or dailyBlackout
preBlackoutClose = (useWeekendBlackout and dowNY == 6 and 1015 - closeLeadMin <= minutesNY < 1015)
                or (useDailyBlackout and 2 <= dowNY <= 5 and 1015 - closeLeadMin <= minutesNY < 1015)
nearBlackout     = entryBufferActive and 2 <= dowNY <= 6 and 1015 - entryBufferMin <= minutesNY < 1080
sundayBlock      = sundayBlockActive and dowNY == 1
inSession, inEntryWindow: E12 (both true with the defaults)
robustHourBlock, the six directional blocks: section 2
```

Arrays handed to the kernel (window rows `w0..w1-1`, `t_close` in the window):
`o h l c`, `pc` (= `close[1]`, from the file, so row `w0` has it), `t_open`, `t_close`,
`dSpike`, `sSpike`, `trendL`, `trendS`,
`gate = inSession and inEntryWindow and not blackoutActive and not nearBlackout and not sundayBlock and not robustHourBlock`
(the position-free part of `tradingAllowed`, L1120),
`bclose = blackoutActive or preBlackoutClose` (time part of `blackoutExitIntent`, L1117),
`pre = preBlackoutClose` (step C3),
`lblock = longDirectionalBlock or v105LongBlock or v1010LongBlock`, `sblock` = the three short ones,
`buyOk`, `sellOk`, ATR (per `atrLenS2`).

Zone seed: the state of the ten zone variables after row `w0-1`, obtained by running ONLY the
invalidation (L1145-1157) and the new-zone assignment (L1178-1190) over the rows before the
window (no trades exist before the window, so nothing else can touch the zones). Starting that
warm-up at the first row or at `w0 - maxZoneAge - 2` gives the same trades (an older zone can
never be valid again); say which you did.

What the gates mean on our bars (for sanity, not to hard-code): BTC "60": weekend blackout 5,117
bars, daily blackout 417 (the 17:00 NY bar, Mon-Thu), `nearBlackout` 1,042 (16:00 and 17:00), no
`preBlackoutClose` bar. XAU "60": no blackout bar at all (the session ends 17:00), 366
`nearBlackout` bars (16:00), 369 Sunday bars. XAU "5": 73 weekend, 293 daily (the 16:55 bar),
732 `preBlackoutClose` bars. XAU "240": bars open 18:00, 22:00, 02:00, 06:00, 10:00, 14:00 NY, so
no blackout, no buffer, positions are held over the weekend.

---------------------------------------------------------------------------------------------------

## 5. How TradingView runs this script on history (E1-E3: read carefully)

Documented behaviour used here:
(a) `process_orders_on_close`: market orders placed in the bar-close run fill at that close;
(b) `calc_on_order_fills`: the script runs again right after every fill, on history too, and on a
    history bar every run sees the bar's FINAL open / high / low / close (a TradingView help
    article, "Strategy produces unrealistically good results by peeking into the future", lists
    `calc_on_order_fills` among the causes: seen only as a web-search summary);
(c) before each further run on the same bar, variables are rolled back to their values at the end
    of the previous bar, except `varip` ones (Pine reference, `varip`: "the values of such
    variables are preserved across successive iterations of the script on the same bar" in
    "strategies that may execute more than once per historical chart bar").
tradingview.com cannot be reached from this session, so (b) and (c) are the documentation as
remembered; they cannot be re-read or tested here. That is why E2 has a switch and E3 has counters.

**E1. One candle = three phases.**
- Phase A, inside the candle: the open trade's exit bracket (stop and / or limit, the levels sent
  at the previous candle's close) is evaluated along the candle's path (5.3). If it fills,
  TradingView runs the script; the replica does nothing at that moment except book the trade.
- Phase B, the bar-close run: the whole logic of section 6 on the position left by phase A. It
  can place ONE market order (an entry / reversal, or a forced close); it fills at this close.
- Phase C, the run after that fill: bookkeeping that the Pine does in the post-fill run
  (closed-trade accounting on THIS bar index; for a new trade: `longAtrAtEntry`, `slDistAtEntry`,
  `tpDistAtEntry` and the first `strategy.exit`). A bracket placed or re-sent at candle i is
  active from the OPEN of candle i+1 (never inside candle i, never "at the close" of candle i).

  Why: the script only calls `strategy.exit` when `strategy.position_size != 0 and not
  na(longAtrAtEntry)` (L1414, L1433), which is first true in the run after the entry fill; that
  run happens on the entry candle (same `atrValue`, `slDistNow`, `tpDistNow`, which is why the
  `pending*` variables never change a number on history: L1372-1374 fall back to the current
  values, and they are equal). Same convention as the verified XPW replica (SPEC.md rule 3).

**E2. Rollback: `varRollback` (replica control of `simulate`, default True).**
The bar-close run of an order candle is followed by the post-fill run of the same candle, and that
run starts from the variable values at the END OF THE PREVIOUS CANDLE. So every `var` assignment
made in the bar-close run is LOST whenever an order placed in that run fills (it always fills, at
that close, if its quantity is > 0), and the post-fill run sees the previous candle's state. This
has exactly three consequences in this script (the `varip` locks stop the post-fill run from
executing the entry and forced-flat blocks again):
- (i) the one-entry-per-zone reset inside the entry blocks (L1314-1326, L1339-1351) is lost;
- (ii) `cooldownUntilBar := bar_index + cooldownBars` in the forced-flat block (L1465, 1471, 1477,
  1483) is lost;
- (iii) INHERITED ENTRY STATE: when the bracket closes a long inside candle j and a new LONG is
  entered at the close of candle j (same side, same candle), the post-fill run starts with the old
  long's `longAtrAtEntry` (not na), so `strategy.position_size > 0 and na(longAtrAtEntry)` (L1371)
  is false and the new trade is NOT initialised: it keeps the closed trade's `longAtrAtEntry`,
  `slDistAtEntry`, `tpDistAtEntry`, `trailArmedLong`, `beArmedLong` and `trailStopLong`, as they
  were at the end of candle j-1 (shorts alike). Its quantity is still sized with the current
  `slDistNow`. This chains over consecutive same-side same-candle re-entries. An opposite-side
  re-entry, a reversal, and any entry on a later candle initialise normally (the other side's
  variable is na; a flat candle resets everything, L1395-1405).

`varRollback = True` (default; the documented TradingView reading): (i), (ii), (iii) apply, so
`useOnePerZone`, `useCooldown`, `cooldownIn` are inert. Exception kept for exactness: an entry
decision whose quantity is <= 0 places no order, no fill follows, the run is not repeated, so the
zone reset of that decision DOES persist.
`varRollback = False` ("as written, once per candle": the model of the earlier per-timeframe
calibration): none of the three; the reset and the cooldown act as the code reads top to bottom,
and every new trade is initialised from its own entry candle.
Nothing else differs between the two: every other `var` written in the bar-close run is either
recomputed identically by the post-fill run (loss cluster, zone invalidation and creation, the
flat reset) or belongs to a trade that the fill closed; the `pending*` variables never matter
(E1). Why True is the default: it is what the reference manual says about successive runs on one
bar, and the author's own `varip` locks exist for that reason. Why the switch exists: it cannot be
checked here, it changes the default trade count by about 20 %, and with trailing on (iii) can
hand a new trade a trailing stop that is already above the market (section 13).

**E3. A new entry on the candle where the bracket just closed the old trade: at the CLOSE.**
After a phase-A exit the position is flat, so the bar-close run may enter again on the same
candle (same or opposite side). The replica decides and fills that entry in phase B, at the
close, like any other entry. TradingView most likely places it in the run that follows the
intrabar fill (the decision is the same: that run already sees the final candle) and fills it at
"the next tick" of its 4-point path: the close when the exit happened on the second or third leg,
an extreme of the candle when it happened at the open (the first extreme) or on the first leg (the
second extreme); a reading in which it fills at the end of the leg being walked (an extreme in
most cases) cannot be excluded. The Pine header
states the intent ("market order at the close"), a fill at an extreme with knowledge of the
close is not obtainable, and one entry model for 'tv' and 'mag' keeps `mag == tv` on chart "1"
testable. (The `varip` entry lock allows one entry decision per candle in every reading.) The
exposure is COUNTED instead of modelled: trades column `reentry` and summary
fields `reentry_same_bar`, `reentry_leg1` (section 11). This is frequent (section 13), so the
reconciler and the auditor must report those counts next to every 'tv' result.

### 5.3 The bracket inside a candle (path 'tv' = SPEC_AH rule 4)

Levels `S` (stop) and `T` (limit); either may be na (then it does not exist; both na = no
bracket). Long (short mirrored: stop above, limit below):
1. At the open: `if S set and open <= S` -> stop fill, raw price = open. `elif T set and open >=
   T` -> limit fill at the open.
2. Else walk `open -> high -> low -> close` if `(high - open) < (open - low)`, else `open -> low
   -> high -> close`; legs are numbered 0, 1, 2. On a rising leg ending at `b`: `if T set and b >=
   T` -> limit fill at `T`. On a falling leg ending at `b`: `if S set and b <= S` -> stop fill, raw
   price = `S`. The first fill along the path wins. Comparisons are inclusive, no tolerance, no
   rounding of `S`, `T` to the tick (as apex / hrd).
3. Fill price: stop fill = raw price minus `slip` for a long (plus for a short); limit fill = raw
   price, no slippage. `slip` = 0.75 with cost 'tv', 0 otherwise (section 8).
Record for step B12: whether phase A filled, and where (at the open / leg 0 / leg 1 / leg 2).
Not evaluated on the entry candle (the bracket did not exist yet). Path 'mag' (stage 3): the same
procedure on each 1-minute sub-bar of the chart candle in time order, the levels being constant
during the chart candle; the open test runs at every sub-bar open.

---------------------------------------------------------------------------------------------------

## 6. The logic of one candle, in execution order (the kernel)

State: `pos` (0, +1, -1), `qty`, `avg` (= `strategy.position_avg_price` = the entry fill price),
`entry_bar`, bracket `S`, `T`, `stop_kind`, `atrE` (`longAtrAtEntry` / `shortAtrAtEntry`), `slE`,
`tpE` (`slDistAtEntry`, `tpDistAtEntry`), `trailArmed`, `trailStop`, `beArmed`, the two zones
(top, bottom, keyTop, keyBottom, bar), `cons` (`consecutiveClosedLosses`), `pauseUntil`,
`cooldownUntil`, `cash` (initial capital + closed P/L after all costs paid, incl. the open
trade's entry cost). Everything starts clean at the window start (flat, counters 0, `pauseUntil`
= `cooldownUntil` = na) except the zone seed (section 4). `bi` = `bar_index` of the candle.

Orders the script can place (all nine calls; no `strategy.order`, no `strategy.cancel*`, no
pending entry order, no daily limit, and no `request.security` outside the filter block):

| call (line) | type | replica |
|---|---|---|
| `strategy.entry("Inverted Long", strategy.long, qty)` (1308) | market BUY at this close; reverses a short | B12 |
| `strategy.entry("Inverted Short", strategy.short, qty)` (1333) | market SELL at this close; reverses a long | B12 |
| `strategy.exit("Inverted Long Exit", "Inverted Long", stop, limit)` (1429) | bracket of the real long, re-sent every run while long | `protect()`, phase A |
| `strategy.exit("Inverted Short Exit", "Inverted Short", stop, limit)` (1448) | bracket of the real short | `protect()`, phase A |
| `strategy.close_all(comment="Blackout Close")` (1459) | market close at this close | B14 'blackout', C3 |
| `strategy.close("Inverted Long" / "Inverted Short", comment="Dead Trade")` (1464, 1470) | market close | B14 'dead' |
| `strategy.close("Inverted Long" / "Inverted Short", comment="Time Exit")` (1476, 1482) | market close | B14 'time' |

("Inverted" in the ids is the V10 name; "Inverted Long" is always a real long.)

**A. Bracket of the open trade** (5.3), only if `pos != 0 and bi > entry_bar` and a level exists.
A fill closes the trade with kind = `stop_kind` ('sl', 'trail' or 'be') or 'tp'. Keep, for this
candle only, the closed trade's side and its `atrE, slE, tpE, trailArmed, beArmed, trailStop` as
they were at the end of the previous candle (step C2 may hand them on, E2 (iii)); otherwise the
per-trade state is reset (the Pine does it at L1395-1405 and L1431 / L1450 when flat).

**B. Bar-close run.**

B1. Loss cluster (L1020-1032): for each trade closed since the last accounting (here: the phase-A
exit), in order: `if profit < 0: cons += 1 else: cons = 0`; then `if lossClusterProfileActive and
cons >= lossClusterTrigger: pauseUntil = bi + lossClusterPauseBars; cons = 0`. `profit` = the
trade's net P/L after the costs of the cost mode (E9); exactly 0 is not a loss.

B2. `inLossClusterPause = lossClusterProfileActive and not na(pauseUntil) and bi < pauseUntil`;
then `if lossClusterProfileActive and not na(pauseUntil) and bi >= pauseUntil: pauseUntil = na`
(L1034-1036; the flag is computed BEFORE the clear).

B3. `inCooldown = cooldownActive and not na(cooldownUntil) and bi < cooldownUntil` (L1039; never
cleared, only overwritten).

B4. `barsInTrade = bi - entry_bar if pos != 0 else na` (L1058-1059).

B5. Distances (L1084-1087), price units:
```
slDistNow   = ExitMode == "Points" ? slPointsIn*mintick : atrValue*slAtrMultS2
tpDistNow   = ExitMode == "Points" ? (tpPointsIn > 0 ? tpPointsIn*mintick : na) : (tpRS2 > 0 ? slDistNow*tpRS2 : na)
trailActNow = ExitMode == "Points" ? trailActPts*mintick : atrValue*trailActAtr
trailDstNow = ExitMode == "Points" ? trailPts*mintick   : max(atrValue*trailDstAtr, mintick)
```
B6. Cost filter (L1089-1097): `ticks = modeledSlippageTicksOverride > 0 ? override : 75`;
`cost = 2.0*ticks*mintick + close*0.00002`; `ratio = slDistNow / cost`;
`volatilityCostBlock = useV1013VolCostFilter and presetXAUUSD and not na(ratio) and ratio < minStopToCostRatio`.
(The script's own constants, the same in every replica cost mode.)

B7. Forced exits (L1105-1118), on the position after phase A:
```
positionLongNotProfitable  = pos > 0 and close <= avg
positionShortNotProfitable = pos < 0 and close >= avg
deadLong   = deadExitActive and positionLongNotProfitable  and barsInTrade >= deadBars
deadShort  = deadExitActive and positionShortNotProfitable and barsInTrade >= deadBars
timeExit   = maxBarsInTrade > 0 and pos != 0 and barsInTrade >= maxBarsInTrade
blackoutExitIntent = bclose and pos != 0
forcedExitThisBar  = deadLong or deadShort or timeExit or blackoutExitIntent
```
(So from `deadBars` candles on, the dead exit closes at the first close that is not beyond the
entry price; with cost 'tv' `avg` contains the entry slippage.)

B8. `tradingAllowed = gate and not inCooldown and not inLossClusterPause and not forcedExitThisBar` (L1120).

B9. Zones and signals (L1145-1175), in this order:
```
if invalidateZones:  if demand set and close < demandBottom: clear demand
                     if supply set and close > supplyTop:    clear supply
demandAge = bi - demandBar ; demandZoneValid = demand set and minRetestBars <= demandAge <= maxZoneAge   (supply alike)
normalDemandRetest = demandZoneValid and low  <= demandKeyTop    and close >= demandKeyBottom
normalSupplyRetest = supplyZoneValid and high >= supplyKeyBottom and close <= supplyKeyTop
inDemandKey = entryMode == "Close Beyond Key Zone" ? normalDemandRetest and close > demandKeyTop    : normalDemandRetest
inSupplyKey = entryMode == "Close Beyond Key Zone" ? normalSupplyRetest and close < supplyKeyBottom : normalSupplyRetest
originalBuySignal  = inDemandKey and close > open and close > close[1] and trendAllowsLong  and tradingAllowed and not volatilityCostBlock
originalSellSignal = inSupplyKey and close < open and close < close[1] and trendAllowsShort and tradingAllowed and not volatilityCostBlock
tradeOriginalDirection = signalDirection == "Original (un-inverted)"                                (L247)
activeBuySignalBase  = tradeOriginalDirection ? originalBuySignal  : originalSellSignal
activeSellSignalBase = tradeOriginalDirection ? originalSellSignal : originalBuySignal
invertedBuySignal  = activeBuySignalBase  and not lblock        ("normal BUY";  "inverted" is the V10 name)
invertedSellSignal = activeSellSignalBase and not sblock        ("normal SELL")
```
A zone older than `maxZoneAge` is not cleared, only invalid. The two original signals cannot both
be true (close > open vs close < open).

B10. New zones, AFTER the signals (L1178-1190): `if isDemandSpike: demandTop = high, demandBottom
= low, demandKeyTop = close, demandKeyBottom = open, demandBar = bi`; `if isSupplySpike: supplyTop
= high, supplyBottom = low, supplyKeyTop = open, supplyKeyBottom = close, supplyBar = bi`.

B11. Update 1 decisions (L1291-1296) and the funnel (L1354-1357). `canSubmitEntryThisBar` is true
in this run (E3: no earlier decision on this candle).
```
dpPosN   = dpInv ? -pos : pos
dpBuyGo  = invertedBuySignal  and dpPosN <= 0 and buyOk
dpSellGo = not dpBuyGo and invertedSellSignal and dpPosN >= 0 and sellOk
dpPlaceLong  = dpInv ? dpSellGo : dpBuyGo          # a real BUY
dpPlaceShort = dpInv ? dpBuyGo  : dpSellGo         # a real SELL
dpLongFromDemand = dpInv ? (not tradeOriginalDirection) : tradeOriginalDirection
fgdRawLong  = invertedBuySignal  and dpPosN <= 0 ; fgdBlockedLong  = fgdRawLong  and not buyOk     (counted per candle)
fgdRawShort = invertedSellSignal and dpPosN >= 0 ; fgdBlockedShort = fgdRawShort and not sellOk
```
B12. Entry / atomic reversal (L1302-1351), only if `dpPlaceLong or dpPlaceShort` (never both);
`nd = +1` for `dpPlaceLong`, `-1` for `dpPlaceShort`:
```
q = f_qty(slDistNow)                                  (section 7; equity and close of THIS run)
if q > 0:   px = close + nd*slip
            if pos == -nd: close the open trade at px, kind 'reverse'    (same order, same price)
            open the new trade: pos = nd, qty = q, avg = px, entry_bar = bi, eq_before = cash, then pay the entry cost
            reentry code of the new trade: 0 if phase A did not fill on this candle, else 1 (open or leg 0), 2 (leg 1), 3 (leg 2)
else:       zero_qty += 1 ; no order, nothing else changes                                   (E7)
if onePerZoneActive and (not varRollback or q <= 0):                                         (E2)
            clear the DEMAND zone if (dpPlaceLong == dpLongFromDemand) else clear the SUPPLY zone
```
(The Pine: the long block clears demand when `dpLongFromDemand`, else supply; the short block the
other way round. It is the zone that produced the signal. The clear runs after B10, so a zone
created on this very candle on that side is wiped too.)

B13. Bracket refresh (L1411-1450) for a trade that was open at the start of B and is still open
after it (no reversal in B12, no forced close in B14): run `protect()` below with this candle's
close; the result is the bracket for the next candle. (Calling `strategy.exit` again with the same
id replaces the prices; E5.)

B14. Forced flat (L1457-1486), only if a trade is open and no entry was placed (B12 and B14
exclude each other through `tradingAllowed`), first match wins:
```
blackoutExitIntent           -> strategy.close_all        kind 'blackout'   (no cooldown)
deadLong or deadShort        -> strategy.close(its id)    kind 'dead'  ; if not varRollback: cooldownUntil = bi + cooldownBars
timeExit                     -> strategy.close(its id)    kind 'time'  ; if not varRollback: cooldownUntil = bi + cooldownBars
```
fill at `close - pos*slip`. (`cooldownUntil` is assigned whether or not `cooldownActive`; only
`inCooldown` reads the switch.) No entry can happen on a forced-flat candle: the flat-exit lock
(L1243, `not sameFlatExitDecisionChartBar`, a `varip`) blocks the post-fill run.

**C. After the fills at this close.**

C1. Trades closed in B12 / B14: the accounting of B1 with THIS `bi` (so a pause triggered by a
close at candle j runs to `j + lossClusterPauseBars`; it blocks entries from candle j+1 on).

C2. A trade opened in B12 (L1371-1393, then the protective block):
- normally: `atrE = atrValue`, `slE = slDistNow`, `tpE = tpDistNow` of THIS candle, `trailArmed =
  beArmed = False`, `trailStop = na`;
- if `varRollback` and phase A closed a trade on this candle and that trade was on the SAME side
  as the new one (E2 (iii)): no initialisation; `atrE, slE, tpE, trailArmed, beArmed, trailStop`
  are the closed trade's (trades column `inherit` = True);
then `protect()` with this candle's close and the new `avg` -> the first bracket, active from the
next candle.

C3. Edge, unreachable with the defaults: if the trade opened in B12 started from flat and
`pre` (preBlackoutClose) is true on this candle (possible only with `useEntryBuffer` off or
`entryBufferIn < closeLeadMin`), the post-fill run sends `strategy.close_all`: close it at this
same close (`close - pos*slip`), kind 'blackout', `exit_bar == entry_bar`, then C1 for it (E8).

**`protect()`** (long; short mirrored: `avg + slE`, `avg - tpE`, `avg - close >= trailActNow`,
`close + trailDstNow`, `min`, `close <= avg - atrE*beTrigger`):
```
stop = slE > 0 ? avg - slE : na ; stop_kind = 'sl'          (slE na -> na)
T    = na(tpE) ? na : avg + tpE
if useTrailS2:
    if close - avg >= trailActNow: trailArmed = True                  (latched; trailActNow of THIS candle)
    if trailArmed:
        newTrail  = close - trailDstNow
        trailStop = na(trailStop) ? newTrail : max(trailStop, newTrail)
        if na(stop) or trailStop > stop: stop_kind = 'trail'
        stop = na(stop) ? trailStop : max(stop, trailStop)
if breakevenActive:
    if close >= avg + atrE*beTrigger: beArmed = True                  (latched)
    if beArmed:
        if not na(stop) and avg > stop: stop_kind = 'be'
        stop = max(stop, avg)                                         (na stays na: E6)
S = stop
```
The trailing stop follows the CLOSE once per candle; it is a plain stop level during the next
candle. In C2 the check runs with the entry candle's close: `close - avg` is `-slip` for a long,
so the trail can arm at entry only if `trailActNow == 0` and `slip == 0`.

**D.** Bar-close equity = `cash + pos*qty*(close - avg)`; exposure counts candles with `pos != 0`
after the close fills.

**Window end:** orders of the last candle are processed normally (they fill at its close). A trade
still open after that is closed at the last close as a market fill of the cost mode (`close -
pos*slip`, exit cost charged), kind 'end', `exit_time = t_close` (E10).

---------------------------------------------------------------------------------------------------

## 7. Sizing (`f_qty`, L1196-1205) and the money model

```
q = fixedQtyS3
if QtyMode == "Risk %":  stopCash = stopDistance*pointValue ; q = stopCash > 0 ? equity*riskPctS3/100.0/stopCash : 0.0
q = min(q, maxQtyS3)
if capMarginS3 and marginPctS3 > 0:  q = min(q, equity / (close*pointValue*marginPctS3/100.0))
return floor(q/qtyStepS3 + 1e-9)*qtyStepS3
```
Same operation order in float64. `stopDistance = slDistNow` (na or 0 -> 0 in Risk mode).
`equity = strategy.equity` in the bar-close run = `cash` + the open trade's unrealised P/L at this
close (`pos*qty*(close - avg)`, no exit cost): on a reversal the equity still contains the trade
about to be closed (E9). Defaults: 1 % of equity at risk over the stop distance, at most 50 units,
at most `equity / (1 % of price)` units, rounded DOWN to 0.001. With 2,000 of capital: gold "1"
would want about 70 oz and is capped at 50; BTC "240" gets about 0.015 BTC (the 0.001 step is a 5 %
grain). Count `qty_capped` (the max or the margin cap reduced q) and `zero_qty`.

R of a trade = `sl_dist x qty x pointvalue` with `sl_dist = slDistAtEntry` (the money lost at the
stop before costs and slippage); `r_mult = pnl / R` (NaN without a stop); summary `net_r` = sum.

---------------------------------------------------------------------------------------------------

## 8. Cost modes; what 75 ticks mean in price

| | fill prices | cost charged per fill (reduces `cash`) |
|---|---|---|
| 'tv' | market buy = close + 0.75, market sell = close - 0.75 (entries, reversals, dead / time / blackout / end closes); stop fill = stop price (or the open on a gap) - 0.75 for a long, + 0.75 for a short; limit fill = its price (or the open on a gap), no slippage | `1e-5 x fill_px x qty` |
| 'ours' | unshifted (`slip = 0`) | XAU `0.15 x qty`; BTC `0.0002 x fill_px x qty + 0.10 x qty` |
| 'stress' | unshifted (the tick is charged as a cost, as in apex / hrd) | XAU `(0.25 + 0.01) x qty`; BTC `0.00035 x fill_px x qty + (0.10 + 0.01) x qty` |

`pnl = dir x qty x (exit_px - entry_px) - entry cost - exit cost`. With 'tv' the slippage is inside
the prices: `avg` = the slipped fill, so the stop, the target, the breakeven level and the dead
test move with it. Report `slippage_paid` = sum of `0.75 x qty` over slipped fills.

What it means on a 0.01-tick symbol (window medians: gold $1,280, BTC $88,161; ATR(14) medians of
the window; default stop 1.2 ATR):

| chart | 1 | 5 | 15 | 30 | 60 | 120 | 240 |
|---|---|---|---|---|---|---|---|
| gold: stop distance, $ | 0.28 | 0.71 | 1.32 | 1.97 | 2.86 | 3.91 | 5.70 |
| gold: 'tv' round trip $1.53 (2 x 0.75 + commission 0.026), in R | 5.4 | 2.1 | 1.15 | 0.78 | 0.53 | 0.39 | 0.27 |
| gold: 'ours' round trip $0.30, in R | 1.06 | 0.42 | 0.23 | 0.15 | 0.10 | 0.08 | 0.05 |
| BTC: stop distance, $ | 46 | 136 | 271 | 404 | 595 | 869 | 1,265 |
| BTC: 'tv' round trip $3.3 (2 x 0.75 + commission 1.76), in R | 0.07 | 0.02 | 0.01 | 0.008 | 0.006 | 0.004 | 0.003 |
| BTC: 'ours' round trip about $35.5, in R | 0.77 | 0.26 | 0.13 | 0.09 | 0.06 | 0.04 | 0.03 |

So: ONE fill at $0.75 per ounce costs 2.5 times our whole gold round trip, a round trip 5 times.
On gold "1" and "5" the slippage of one fill is larger than the stop distance itself, so the stop
of a long sits ABOVE the close right after the fill and the trade is stopped at the next open (5.3
rule 1) for about -1.5 $/oz every time: the 'tv' gold results on low timeframes are destroyed by
the Property, not by the signals. On BTC the
same Property is $0.75 per coin, 0.0009 % of the price: TradingView's report is close to
cost-free there and far more optimistic than 'ours' (about 11 times cheaper).

---------------------------------------------------------------------------------------------------

## 9. Assumptions (one each; both builders implement exactly these)

| id | assumption | why |
|---|---|---|
| E1 | Three phases per candle; a bracket placed or re-sent at candle i is active from the open of i+1; entry state = values of the entry candle (except E2 (iii)). | Section 5. `strategy.exit` is first reachable in the post-fill run; same rule as the verified XPW replica. Even if TradingView tried the new stop at the close itself, the fill would be at about the same price one candle earlier. |
| E2 | `varRollback = True`: (i) the zone reset and (ii) the cooldown are lost, (iii) a same-side same-candle re-entry keeps the closed trade's entry state; `False` = none of the three. | Section 5. Documented rollback between runs on one bar; not testable here, hence the switch. |
| E3 | A same-candle re-entry after a bracket exit is decided and filled at the close; counted. | Section 5. |
| E4 | Stop and limit touched in one candle: the first along the rule-4 path ('tv'); gaps fill at the open (stop with slippage, limit without). | SPEC_AH rule 4. |
| E5 | `strategy.exit` re-sent with the same id replaces the levels from the next candle on; there is no hidden trailing state (no `trail_points`). A bracket whose trade closed is gone. | Pine order replacement. |
| E6 | `math.max(na, x)` / `math.min(na, x)` = na; `strategy.exit` with stop na and limit na places nothing. | Only reachable in Points mode with `slPointsIn = 0`. |
| E7 | `strategy.entry` with `qty <= 0` places no order. The Pine would still write its `pending*` variables there; with no fill they would persist and could feed a later entry: NOT replicated (ruin corner). Count `zero_qty`; flag any result where it is > 0. | Degenerate (equity near 0, or risk too small for the 0.001 step). |
| E8 | A market order placed in a post-fill run at the close fills at that same close (C3). | `process_orders_on_close` makes a further attempt after each calculation at the close. |
| E9 | `strategy.equity` = cash after every cost paid + open P/L at the close; `strategy.closedtrades.profit` = the trade's P/L net of its costs. In 'ours' / 'stress' both use those costs. | SPEC_AH rule 6; TradingView's trade profit is net of commission. |
| E10 | Window end: section 6. | As the XPW engine (orders of the last candle fill at its close). |
| E11 | `syminfo.ticker` = "XAUUSD" / "BTCUSD"; mintick 0.01; pointvalue 1. | REPLICA_SPEC. |
| E12 | `time(timeframe.period, sess)` is not na iff the bar's OPEN, in the exchange time zone (XAU: America/New_York; BTC: UTC), has `HHMM` in `[start, end)` (wrapping over midnight if start > end), every day of the week. Used by `useSessionFilter` and `useEntryWindow`, both off by default and outside the grid. | Pine `time()` uses `syminfo.timezone`; it depends on the broker symbol. |
| E13 | No rounding of prices or quantities beyond the script's own `qtyStepS3`; no TradingView margin logic; no order-count trimming. | As apex / hrd. |
| E14 | Trading starts flat at the first window candle with clean counters; only the zones carry over (seed). | REPLICA_SPEC windows. |

Live-only code, ignored on history: the `varip` locks and `lastLiveSafeAction` (L1231-1246; they
never bind under E1/E3), `calc_on_every_tick`, every alert string, `barstate.islast` tables, the
filter's live branches (inside `fgf.py`).

---------------------------------------------------------------------------------------------------

## 10. Update 1 ("Inverted direction", `dpInv`) and the older "Signal direction"

Line by line: L832 the input (declared last). L1291 `dpPosN`: the position as the decisions see it
(mirror when on). L1292-1293 `dpBuyGo` / `dpSellGo`: the two entry conditions of the previous
version with `dpPosN` instead of `strategy.position_size`, gate `fgfBuyOk` for the normal BUY and
`fgfSellOk` for the normal SELL, BUY tried first. L1294-1295: which real-side block runs
(`dpPlaceLong = dpInv ? dpSellGo : dpBuyGo`). L1296 `dpLongFromDemand`: which zone the reset
clears. L1302 / L1327: `if dpPlaceLong` / `else if dpPlaceShort`. L1315 / L1340: the reset tests
`dpLongFromDemand`. L1354-1355: the FGD raw lines read `dpPosN`. Nothing else changed: no
`strategy.*` call, no exit code. Everything after the entry (C2, `protect()`, B7, B14, B1, sizing)
reads the REAL position, so an inverted trade has its stop on the other side at the same distance
from its own fill. Market orders stay market orders (there is no stop / limit entry to swap), the
price is the same close; with cost 'tv' the slippage is on the other side of it.

Signal -> order, all four combinations:

| zone signal | `signalDirection` | normal side (windows + filter judge this) | `dpInv` off: order | `dpInv` on: order |
|---|---|---|---|---|
| demand retest, bullish candle (`originalBuySignal`) | Inverted (V10 design) | SELL: `sblock`, `sellOk` | SELL | BUY |
| | Original (un-inverted) | BUY: `lblock`, `buyOk` | BUY | SELL |
| supply retest, bearish candle (`originalSellSignal`) | Inverted (V10 design) | BUY: `lblock`, `buyOk` | BUY | SELL |
| | Original (un-inverted) | SELL: `sblock`, `sellOk` | SELL | BUY |

Position tests: a normal BUY is taken when `dpPosN <= 0`, i.e. with the option on when the REAL
position is flat or long (it then sells, reversing a long). `raw_*` / `blocked_*` stay in the
normal frame (a normal BUY the filter refuses is `blocked_long` even though it would have been a
SELL order). `dpInv` is NOT a mirrored trade list: exits change sides, so later entries differ.

Properties to test (stage 2 self-checks, stage 3 tests):
- P1 (header): with `fgfOn` False and no directional window in force (every cell except XAU "5"
  with the Auto preset), `(dpInv True, signalDirection X)` gives exactly the trades of `(dpInv
  False, the other signalDirection)`, every column; `raw_long` <-> `raw_short` swap. With the
  filter on, or on the preset cell, it does not (show an example of each).
- P2: on single decisions, the order placed with the option on from real position p is the
  opposite side of the order placed with it off from position -p, same candle, same quantity
  rule, the zone cleared is the signal's.
- P3: `fgfOn` False and `dpInv` False = the unfused original (its conditions are L1292-1293
  without the `fgf*Ok` operand and with `strategy.position_size`).
- P4: with `varRollback` True the result does not depend on `useOnePerZone`, `useCooldown`,
  `cooldownIn` (when `zero_qty == 0`). On any run where no trade has `inherit` True (cut a window
  that has none), `varRollback` True == `varRollback` False with `useOnePerZone` and `useCooldown`
  off, every column: the three consequences of E2 are the only differences.

---------------------------------------------------------------------------------------------------

## 11. Trade record and summary

`trades(P, R)`: one row per trade, in exit order.

| column | content |
|---|---|
| `dir` | REAL side, +1 / -1 |
| `entry_time`, `entry_bar` | `t_close` of the entry candle (the fill is at its close); its row number in the data file |
| `entry_px`, `qty` | fill price (slipped with 'tv'), units |
| `exit_time`, `exit_bar` | bracket exits: `t_open` of the exit candle ('mag': of the sub-bar); exits at a close ('reverse', 'dead', 'time', 'blackout', 'end'): `t_close` |
| `exit_px` | fill price |
| `exit_kind` | 'sl', 'tp', 'trail', 'be' (bracket: which stop level was in force / the target), 'reverse', 'dead', 'time', 'blackout', 'end' |
| `pnl` | after costs; `pnl_gross`, `costs` separately |
| `eq_before` | `cash` just before the entry fill (after the closing leg of a reversal, before the new entry's cost) |
| `sig` | +1 normal BUY decision, -1 normal SELL decision (= `dir` with `dpInv` off, `-dir` with it on) |
| `zone` | 'D' / 'S': the zone whose retest gave the signal |
| `sl_dist`, `sl_px`, `tp_px`, `r_mult` | `slDistAtEntry`, the first bracket, `pnl / (sl_dist x qty)` |
| `reentry` | 0, or 1 / 2 / 3 as in B12 (path 'mag': 2 for any same-candle re-entry) |
| `inherit` | True when the trade kept the closed trade's entry state (C2, only with `varRollback`) |

`summary(P, R)` (the common fields exactly as `hrd.summary_fast` computes them, initial capital
2,000): `start, end, bars, trades, net_pct, pf, win_pct, max_dd_pct, max_dd_init_pct, long, short,
raw_long, raw_short, blocked_long, blocked_short, half1_pct, half2_pct, exposure, final_equity,
exit_sl, exit_tp, exit_trail, exit_be, exit_reverse, exit_dead, exit_time, exit_blackout,
exit_end, zero_length, h1r_pct, h2r_pct, h1_trades, h2_trades, avg_bars_held, costs`, plus
`slippage_paid, net_r, reentry_same_bar` (trades with `reentry > 0`), `reentry_leg1` (`reentry ==
1`), `inherited` (trades with `inherit`), `zero_qty, qty_capped, margin_breach` (candles where the
bar-close equity < `qty x close x 0.002`). Fair halves: trades ENTERED in each half by `entry_time <= mid` / `> mid`, `mid = start +
(end - start)//2`, `prod(1 + pnl/eq_before) - 1` in %. `max_dd_pct` on the bar-close equity curve
incl. open P/L. A ruined account (equity so small that every quantity floors to 0) simply stops
trading: `zero_qty` shows it.

---------------------------------------------------------------------------------------------------

## 12. What cannot be reproduced, and what the replica does instead

- TradingView itself: E1-E3 and E8 are readings of its engine. E2 changes the default results
  (switch provided). E3: the fill price of same-candle re-entries in TradingView's report is not
  known (close, or an extreme of the candle); counted. Report both with every 'tv' number.
- Live behaviour: live, the post-fill run of an intrabar exit sees the FORMING candle, so a
  re-entry can happen mid-candle on a partial candle; the locks, alerts and webhook delivery only
  exist live. Not modelled: the replica is the history model.
- Volume: the signal is built on volume. Gold = Dukascopy tick count (TradingView-style tick
  volume of another feed), BTC = Bitstamp volume; another broker's volume gives other spikes.
- Sessions: gold bars are 18:00-17:00 New York with 120 / 240-minute bars anchored at 18:00;
  a broker with another session or time zone changes the bars, the Sunday bars and which candles
  fall in the blackout windows. BTC bars are on a UTC grid.
- Presets of other markets (section 2): not implemented. The XAUUSD 5m preset is implemented but
  takes no trade on a 0.01-tick gold symbol (cost filter).
- `useSessionFilter` / `useEntryWindow`: implemented under E12, unverifiable.
- TradingView's margin calls, quantity / price rounding to the symbol's steps, the 9,000-order
  limit of the tester, the bars a plan can load (a 1-minute chart cannot hold two years).
- Data Window "FGD raw ..." values: on a candle where an entry fills, TradingView shows the value
  of the LAST run (after the fill: 0). The replica counts the decision run (the funnel as meant).
- Seconds timeframes: none used with the default filter inputs (fgf.py returns na for them).
- Bar Magnifier inside TradingView: path 'mag' is OUR 1-minute walk of the exit bracket, with
  entries and forced closes at the chart close.

---------------------------------------------------------------------------------------------------

## 13. Builders: interface notes, self-checks, sanity numbers

- `prepare` -> P: the section 4 arrays (window), the zone seed, the resolved settings (section 2),
  `w0, w1, mid`, an ATR cache per length. `simulate(P, x)` resolves the active settings
  (`deadExitActive = useProfile ? False : useDeadExit` ...) and runs ONE numba kernel over the
  window candles: section 6 has no data-dependent Python. BTC "1": 1,039,430 window candles.
- Hand traces (REPLICA_SPEC): 3 trades of EACH kind: 'sl', 'tp', 'reverse', 'dead', 'time',
  'blackout', 'end' with default-like inputs; 'trail' (needs `useTrailS2`), 'be' (needs
  `useBreakeven`); print the candles, `avg`, `S`, `T`, the loss-cluster counter where it matters.
  Also trace: one loss-cluster pause (start and first candle allowed again), one cooldown with
  `varRollback` False, one same-candle re-entry, one 'tv'-cost gold trade whose stop is beyond
  the close at entry, one reversal's sizing (equity with the open P/L), P1-P4 of section 10.
- XAU "5", default inputs: 0 trades; print how many candles the cost filter lets through (0).
- Save the trade lists REPLICA_SPEC asks for (BTC 60, BTC 5, XAU 60, XAU 15; default inputs, cost
  'tv'; filter on / off; inv off / on), each also with `varRollback` False:
  `$W/out/danny_<a|b>_<PAIR>_<TF>[_foff][_inv][_aw].parquet` (`_foff` = filter off, `_inv` = `dpInv`
  on, `_aw` = `varRollback` False; no suffix = the defaults).
- Sanity numbers from the stage-1 probe (plain Python, unverified, order of magnitude only;
  default inputs, filter off, cost 'ours'): BTC 60 about 1,200 trades with `varRollback` True and
  about 970 with False; XAU 60 about 615 / 510; BTC 240 about 330 / 280; exits are mostly 'sl',
  then 'blackout' (BTC) or 'reverse'; with `varRollback` True about a quarter of the entries are
  same-candle re-entries (about 9 % with False), nearly all after an exit on leg 1 and a handful
  on leg 0, and about 95 % of them inherit the entry state; the header's property P1 held in the
  probe; with 'ours' costs BTC 5 and XAU 15 lose almost everything at the defaults (then
  `zero_qty` is in the thousands: the account is too small to size a trade).
- Why (iii) matters with trailing on: a long whose trailing stop is hit, re-entered on the same
  candle, inherits `trailArmed` and the old `trailStop`; `protect()` then sets the new stop to
  `max(old trailStop, close - trailDstNow)`, usually above the close, and the trade is stopped at
  the next open. Trace one such trade (`useTrailS2` True, `varRollback` True).

Additions for stage 3 (same files as REPLICA_SPEC asks, plus): in `out/inv_danny_<PAIR>_<TF>.json`
keep `runs[...]` = the defaults (`varRollback` True) and add `runs_aw[...]` = the same 16 keys with
`varRollback` False; for XAU "5" add `runs_manual[...]` with `presetMode = "Manual"` (the default
cell has no trade). Tests: P1-P4; `mag == tv` on chart "1" holds as is (one entry model).

---------------------------------------------------------------------------------------------------

## 14. Calibration grid proposal (for `$W/CALIB_SPEC.md`)

Scored as CALIB_SPEC says (path 'mag', cost 'ours'), with `varRollback` True (E2): under it
`useOnePerZone` / `useCooldown` are inert, so they are NOT dimensions (they stay at the script
defaults). 17,496 settings per cell (XAU "5": 17,497).

| # | dimension (Pine name) | values | kind | side | default |
|---|---|---|---|---|---|
| 1 | `presetMode` | "Auto"; on XAU "5" only: "Manual" for the grid + ONE row "Auto" | categorical | signal | "Auto" |
| 2 | `manualZoneLength` | 50, 100, 200 | ordinal | signal | 50 |
| 3 | `manualDeltaThreshold` | 1.0, 1.5, 2.0 | ordinal | signal | 1.5 |
| 4 | `manualUseEmaFilter` | True, False | categorical | signal | True |
| 5 | `manualEmaLength` | 100, 200 (None when 4 is False) | ordinal | signal | 100 |
| 6 | `fgfOn` | False, True (this script has no blocked-signal close) | categorical | signal | True |
| 7 | `signalDirection` | "Inverted (V10 design)", "Original (un-inverted)"; None with `fgfOn` False (the default value is used: there `inv` True IS the Original direction, property P1, so the pair would only repeat rows) | categorical | exit | "Inverted (V10 design)" |
| 8 | `inv` (`dpInv`) | False, True | categorical (the direction control) | exit | False |
| 9 | `slAtrMultS2` | 0.8, 1.2, 2.0 | ordinal | exit | 1.2 |
| 10 | `tpRS2` | 4.1667, 0.0 (= no target) | categorical | exit | 4.1667 |
| 11 | `timeStopBars` | 25, 50, 100 | ordinal | exit | 50 |
| 12 | `useDeadExit` | True, False | categorical | exit | True |
| 13 | `deadBarsIn` | 15, 30 (None when 12 is False) | ordinal | exit | 15 |
| 14 | `useTrailS2` | False, True (True = the cell's pair below) | categorical | exit | False |

Count: signals 3 x 3 x 3 (EMA: on/100, on/200, off) = 27; filter x direction = 2 (off: `inv` F / T)
+ 4 (on: `signalDirection` x `inv`) = 6; exits 3 x 2 x 3 x 3 (dead: on/15, on/30, off) x 2 = 108;
27 x 6 x 108 = **17,496**. The default setting is one grid point (50, 1.5, EMA on 100, filter on,
V10, normal, 1.2, 4.1667, 50, dead on 15, no trail). Everything else at the script defaults
(ExitMode ATR, ATR 14, Risk 1 %, loss-cluster pause on, blackouts on, breakeven off, the filter's
own inputs).

XAU "5": the 17,496 rows run with `presetMode = "Manual"` (what a user gets by choosing Manual;
no directional windows, so P1 holds); the extra row is the script default there (Auto = the
XAUUSD 5m preset, every other dimension at its default or None): it takes no trade and only
records that fact. On the other 13 cells "Auto" and "Manual" cannot differ (no preset matches;
`manualZoneTrend` is false), so "Auto" is listed once.

Trailing (`useTrailS2` True): ExitMode ATR, `trailActAtr = 2d`, `trailDstAtr = d`, with `d` the
smallest of {1, 1.75, 2.5, 3.5, 5, 6.5} for which `d x ATR(14)/close` at the 10th percentile of
the window is at least the floor (0.1 % BTC, 0.05 % gold):

| cell | BTC 1 | BTC 5 | BTC 15-240 | XAU 1 | XAU 5 | XAU 15-240 |
|---|---|---|---|---|---|---|
| 10th percentile of ATR(14)/close, % | 0.0157 | 0.0574 | 0.125 / 0.198 / 0.318 / 0.512 / 0.826 | 0.0101 | 0.0290 | 0.060 / 0.094 / 0.145 / 0.203 / 0.311 |
| `d` (distance, ATR) | 6.5 | 1.75 | 1.0 | 5.0 | 1.75 | 1.0 |
| (`trailActAtr`, `trailDstAtr`) | (13, 6.5) | (3.5, 1.75) | (2, 1) | (10, 5) | (3.5, 1.75) | (2, 1) |

(On the 1-minute charts the floor makes the trail almost inert within a 25-100 candle hold. The
stop trails the close once per candle and is a fixed level inside the candle, so this script has
no intrabar-trailing artefact; the floor is kept because the brief asks for it.)

Notes for the orchestrator:
- Every row rests on E2, and the trailing rows carry its consequence (iii) (section 13).
  Suggested extra control, cheap through `--one`: re-run a pick with
  `varRollback` False (and `useOnePerZone` / `useCooldown` as the published file would set them)
  and require it to stay positive in both halves, as for the stressed costs; and report its
  `reentry_same_bar` share (E3).
- Variant W, only if the "as written" reading is preferred over E2: same size, `varRollback`
  False, with `useOnePerZone` {True, False} x `useCooldown` {True, False} in place of dimensions
  10 and 14 (target fixed at 4.1667, trail off): 27 x 6 x (3 x 3 x 3 x 2 x 2) = 17,496. Any pick
  with one of the two ON then depends on a TradingView behaviour that cannot be checked here.
- Sizing stays the script's (Risk 1 %, max 50, step 0.001, capital 2,000) so that the default is
  literally a grid point. Its absolute numbers bite: gold "1" is capped at 50 oz from the first
  trade, the 0.001 step is a 5-15 % grain on BTC "120" / "240", and an account that has lost
  almost everything stops trading (`zero_qty`), which removes it from the pool of settings with
  30 trades per half. If the orchestrator prefers scale-free halves: fix `qtyStepS3 = 0.000001`
  and `maxQtyS3 = 1e9` for every row (both are inputs) and define the default row with them.
- Candidates left out to stay in budget: `manualMaxZoneAge` (200; it limits how long a zone keeps
  giving entries, which matters more once the reset is inert), `useDailyBlackout` /
  `useWeekendBlackout` on BTC (a 24/7 market closed every day at 18:00 New York by default: about
  30 % of the default BTC 60 exits), `useBreakeven`, `useV1011LossClusterPause`, `tpRS2` 2.0.
- Rule C step 5 flips `inv`; with the filter off that is the other "Signal direction".
- Speed: 54 prepared inputs per cell (27 x filter), one kernel call per exit setting.
