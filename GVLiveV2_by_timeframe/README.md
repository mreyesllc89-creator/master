# GVLiveV2 FGF: one file per pair and timeframe

**Update 1 (2026-11-23).** Every file here now has the option "Inverted direction: opposite side at the same entries" (the last setting, off by default) and a title ending in `[Update 1]`. Off is exactly the previous version, so every result below still holds; nothing here was tested with the option on. See [UPDATES.md](../UPDATES.md).

Same code as `GVLiveV2_Polymarket_PreCandle_Strategy_FGF.pine`; only the input defaults differ. Each file's header starts with a FRAGILITY block (what the result depends on), then the full record: data, costs, the rule, the hold-out in both directions, stressed costs, monthly spread and the sets it was compared with.

**Rule v3.1.** Per pair and timeframe, a setting is picked from the full input grid: among the settings positive in both halves of every dataset, the 40 best by worst half are scored by 0.5 x worst half + 0.5 x the mean worst half of their clone-free grid neighbours (at least 5 neighbours with a positive mean), and the best of them is the pick. It becomes the file's defaults only if choosing settings on one half and testing them on the other works in both directions: the 40 best beat 95% of random 40-setting draws from the same pool, also when counted as their distinct entry-overlap clusters; forward they are also at least 60% positive with a positive mean. The pick must also survive stressed costs. Otherwise a general set is used only if it passes its own robustness and plateau check, and the file says so in its title. Otherwise no file is published for that timeframe.

Costs: gold $0.30 spread per round trip; BTC 0.02% fee per side + $0.20 spread per round trip; no slippage. Stressed: gold $0.50 spread + 1 tick per side; BTC 0.035% per side + $0.20 + 1 tick per side. R = one stop distance. Results are in-sample; the hold-out columns are the out-of-sample guide.

**TradingView's own report** will differ: the strategy() properties have commission 0 and slippage 0, so TradingView shows the strategy with no costs at all.

## XAUUSD

| TF | File | Defaults | Result on the data | Without the 10 biggest trades | Stressed costs | Forward hold-out | Reverse hold-out |
|---|---|---|---|---|---|---|---|
| 10m | **no file** | no defensible setting (see below) | | | | 55% positive, +2.6R vs -3.5R; 27 clusters +1.2R vs -2.9R: FAIL | -5.2R vs -5.7R; 20 clusters -7.9R vs -3.8R: FAIL |
| 15m | **no file** | no defensible setting (see below) | | | | 12% positive, -30.6R vs -6.1R; 11 clusters -12.4R vs -2.3R: FAIL | +13.1R vs +4.0R; 8 clusters +15.5R vs +9.8R: pass |
| 30m | [GVLiveV2_FGF_XAUUSD_30m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/GVLiveV2_by_timeframe/GVLiveV2_FGF_XAUUSD_30m.pine) | fallback: all-timeframe profile: EMA 5 / 13, trend EMA 200, RSI filter on, pre-candle Stop Next Candle, radar Chart, min vol score 0, vol rise 1, close location 0.65, trend direction on, SL 1.5 x ATR(14), TP 5R, no trail, no time stop, no $ daily lock, max 3 losing trades per day (Pine default, kept), direction filter off | VANTAGE XAUUSD +99.2R, 590 trades, PF 1.2, DD 36.0R | +49.1R | +89.6R | 88% positive, +23.5R vs -0.5R; 11 clusters +19.9R vs +4.1R: pass | -3.2R vs +9.1R; 8 clusters -20.7R vs +16.3R: FAIL |
| 45m | **no file** | no defensible setting (see below) | | | | 78% positive, +30.4R vs +18.0R; 17 clusters +38.8R vs +21.6R: pass | -23.1R vs -15.0R; 8 clusters -47.8R vs -7.9R: FAIL |
| 60m | [GVLiveV2_FGF_XAUUSD_60m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/GVLiveV2_by_timeframe/GVLiveV2_FGF_XAUUSD_60m.pine) | **calibrated for this timeframe**: EMA 5 / 13, trend EMA 200, RSI filter off, pre-candle Market Next Candle, radar Chart, min vol score 35, vol rise 1, close location 0.75, trend direction off, SL 1 x ATR(14), TP 5R, no trail, no time stop, no $ daily lock, max 3 losing trades per day (Pine default, kept), direction filter off | OANDA XAUUSD +75.9R, 194 trades, PF 1.5, DD 16.5R; VANTAGE XAUUSD +132.3R, 490 trades, PF 1.33, DD 17.7R | +22.2R; +82.3R | +74.1R; +124.4R | 93% positive, +52.8R vs +0.7R; 16 clusters +40.3R vs +4.2R: pass | +11.8R vs +3.6R; 9 clusters +29.7R vs +11.2R: pass |
| 120m | [GVLiveV2_FGF_XAUUSD_120m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/GVLiveV2_by_timeframe/GVLiveV2_FGF_XAUUSD_120m.pine) | fallback: master-file hourly defaults: EMA 8 / 21, trend EMA 100, RSI filter on, pre-candle Market Next Candle, radar Chart, min vol score 35, vol rise 1, close location 0.65, trend direction on, SL 1 x ATR(14), TP 5R, no trail, no time stop, no $ daily lock, max 3 losing trades per day (Pine default, kept), direction filter off | OANDA XAUUSD +36.8R, 82 trades, PF 1.57, DD 17.0R; VANTAGE XAUUSD +45.6R, 209 trades, PF 1.27, DD 21.7R | -14.2R; -4.3R | +36.2R; +43.2R | 55% positive, +1.1R vs +6.7R; 9 clusters +22.4R vs +11.3R: FAIL | +54.9R vs +5.4R; 10 clusters +43.9R vs +9.6R: pass |
| 240m | [GVLiveV2_FGF_XAUUSD_240m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/GVLiveV2_by_timeframe/GVLiveV2_FGF_XAUUSD_240m.pine) | **calibrated for this timeframe**: EMA 5 / 13, trend EMA 100, RSI filter on, pre-candle Market Next Candle, radar Chart, min vol score 0, vol rise 0, close location 0.75, trend direction off, SL 0.5 x ATR(14), no target, trail: activate at 4 ATR of profit, distance 0.2 ATR, no time stop, no $ daily lock, max 3 losing trades per day (Pine default, kept), direction filter off | OANDA XAUUSD +86.2R, 219 trades, PF 1.46, DD 20.9R; VANTAGE XAUUSD +109.7R, 340 trades, PF 1.37, DD 30.2R | +10.3R; +33.8R | +83.3R; +104.2R | 65% positive, +18.7R vs +8.9R; 7 clusters +34.4R vs +14.6R: pass | +40.1R vs +10.9R; 5 clusters +44.7R vs +19.8R: pass |

## BTCUSD

| TF | File | Defaults | Result on the data | Without the 10 biggest trades | Stressed costs | Forward hold-out | Reverse hold-out |
|---|---|---|---|---|---|---|---|
| 1m | **no file** | no defensible setting (see below) | | | | 68% positive, +29.5R vs +40.5R; 14 clusters +23.3R vs +53.9R: FAIL | +63.1R vs +30.2R; 18 clusters +52.3R vs +39.1R: pass |
| 5m | [GVLiveV2_FGF_BTCUSD_5m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/GVLiveV2_by_timeframe/GVLiveV2_FGF_BTCUSD_5m.pine) | **calibrated for this timeframe**: EMA 5 / 13, trend EMA 100, RSI filter on, pre-candle Stop Next Candle, radar Chart, min vol score 35, vol rise 0, close location 0.75, trend direction off, SL 2 x ATR(14), TP 5R, no trail, no time stop, no $ daily lock, max 3 losing trades per day (Pine default, kept), direction filter off | Bitfinex BTCUSD +509.6R, 2255 trades, PF 1.25, DD 68.6R | +459.8R | +190.8R | 97% positive, +186.1R vs +62.4R; 18 clusters +159.9R vs +71.7R: pass | +86.6R vs +22.9R; 7 clusters +99.1R vs +39.1R: pass |
| 15m | **no file** | no defensible setting (see below) | | | | 57% positive, +36.1R vs +6.7R; 6 clusters +43.6R vs +21.9R: FAIL | -8.9R vs +14.9R; 10 clusters -44.9R vs +23.4R: FAIL |
| 30m | [GVLiveV2_FGF_BTCUSD_30m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/GVLiveV2_by_timeframe/GVLiveV2_FGF_BTCUSD_30m.pine) | **calibrated for this timeframe**: EMA 8 / 21, trend EMA 50, RSI filter on, pre-candle Market Next Candle, radar Chart, min vol score 40, vol rise 0, close location 0.65, trend direction on, SL 1 x ATR(14), TP 5R, no trail, no time stop, no $ daily lock, max 3 losing trades per day (Pine default, kept), direction filter off | Bitfinex BTCUSD +316.8R, 1134 trades, PF 1.33, DD 36.3R | +267.0R | +231.3R | 95% positive, +91.7R vs +17.0R; 9 clusters +75.9R vs +25.4R: pass | +39.8R vs +16.6R; 4 clusters +56.1R vs +28.9R: pass |
| 60m | [GVLiveV2_FGF_BTCUSD_60m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/GVLiveV2_by_timeframe/GVLiveV2_FGF_BTCUSD_60m.pine) | **calibrated for this timeframe**: EMA 3 / 8, trend EMA 100, RSI filter on, pre-candle Market Next Candle, radar Chart, min vol score 35, vol rise 0, close location 0.65, trend direction on, SL 1 x ATR(14), no target, no trail, time stop 4 bars, no $ daily lock, max 3 losing trades per day (Pine default, kept), direction filter off | Bitfinex BTCUSD +250.0R, 1067 trades, PF 1.48, DD 20.7R | +63.0R | +190.7R | 100% positive, +64.1R vs +16.3R; 2 clusters +43.4R vs +35.3R: pass | +21.9R vs +8.3R; 7 clusters +21.8R vs +15.3R: pass |
| 120m | [GVLiveV2_FGF_BTCUSD_120m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/GVLiveV2_by_timeframe/GVLiveV2_FGF_BTCUSD_120m.pine) | fallback: master-file hourly defaults: EMA 8 / 21, trend EMA 100, RSI filter on, pre-candle Market Next Candle, radar Chart, min vol score 35, vol rise 1, close location 0.65, trend direction on, SL 1 x ATR(14), TP 5R, no trail, no time stop, no $ daily lock, max 3 losing trades per day (Pine default, kept), direction filter off | Bitfinex BTCUSD +124.7R, 279 trades, PF 1.57, DD 29.1R | +74.9R | +116.8R | 95% positive, +65.6R vs +13.2R; 11 clusters +56.3R vs +16.7R: pass | -0.5R vs +6.9R; 5 clusters +8.2R vs +12.3R: FAIL |
| 240m | [GVLiveV2_FGF_BTCUSD_240m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/GVLiveV2_by_timeframe/GVLiveV2_FGF_BTCUSD_240m.pine) | **calibrated for this timeframe**: EMA 8 / 21, trend EMA 50, RSI filter off, pre-candle Market Next Candle, radar Chart, min vol score 0, vol rise 1, close location 0.75, trend direction off, SL 0.5 x ATR(14), no target, no trail, time stop 4 bars, no $ daily lock, max 3 losing trades per day (Pine default, kept), direction filter off | Bitfinex BTCUSD +224.9R, 423 trades, PF 1.8, DD 15.3R | +54.1R | +207.9R | 100% positive, +125.6R vs +8.4R; 3 clusters +113.5R vs +17.9R: pass | +88.9R vs +8.8R; 3 clusters +83.3R vs +16.2R: pass |

## Timeframes without a file

- **XAUUSD 10m**: forward hold-out failed: only 55% positive (60% needed); reverse hold-out failed: cluster representatives -7.9R not above -3.8R (20 clusters); the general set (all-timeframe profile) failed its check: VANTAGE XAUUSD PF 1.09 (1.10 needed); not on a plateau (12 clone-free neighbours, mean worst half -5.8R).
- **XAUUSD 15m**: forward hold-out failed: only 12% positive (60% needed), mean not positive, mean -30.6R not above the random 95th percentile -6.1R, cluster representatives -12.4R not above -2.3R (11 clusters); the general set (all-timeframe profile) failed its check: VANTAGE XAUUSD PF 1.06 (1.10 needed).
- **XAUUSD 45m**: reverse hold-out failed: mean -23.1R not above -15.0R, cluster representatives -47.8R not above -7.9R (8 clusters); the general set (all-timeframe profile) failed its check: not on a plateau (12 clone-free neighbours, mean worst half -1.9R).
- **BTCUSD 1m**: forward hold-out failed: mean +29.5R not above the random 95th percentile +40.5R, cluster representatives +23.3R not above +53.9R (14 clusters); the general set (all-timeframe profile) failed its check: Bitfinex BTCUSD halves -499.2 / -709.5; Bitfinex BTCUSD PF 0.75 (1.10 needed); Bitfinex BTCUSD stressed -4280.5R; not in this timeframe's grid, so its plateau cannot be checked.
- **BTCUSD 15m**: forward hold-out failed: only 57% positive (60% needed); reverse hold-out failed: mean -8.9R not above +14.9R, cluster representatives -44.9R not above +23.4R (10 clusters); the general set (all-timeframe profile) failed its check: Bitfinex BTCUSD PF 1.05 (1.10 needed); Bitfinex BTCUSD stressed -71.1R.

## Revision history

- v1 (commit 18f2f62): 14 files, one per pair and timeframe, per-timeframe picks with a single first-half hold-out.
- v3 (commit 19384f7), after the first adversarial review: the replica booked trail exits beyond the target when the trail activation lay at or beyond it (the Pine fills the target first); the engine was fixed and those settings dropped (they had inflated the v1 XAUUSD 10m/15m/30m and BTCUSD 30m files by 34-73%). Random baselines became fair permutation tests, the hold-out had to pass both ways and the pick had to survive stressed costs. XAUUSD 10m/15m and BTCUSD 1m/15m were withdrawn; XAUUSD 30m/45m/120m and BTCUSD 120m became fallback files (10 files).
- v3.1 (this version), after the second review: the permutation test also counts the top 40 as distinct entry-overlap clusters, plateaus ignore clones, fallback sets must sit on a plateau (XAUUSD 45m withdrawn, 9 files), headers open with the fragility facts, the OANDA/VANTAGE overlap dates in the gold 60m/120m/240m files were corrected, and the live one-bar-early time stop and TradingView's zero-cost report are stated.

## Inverted direction (Update 1): results by timeframe on new data

This section is separate from everything above. The files and tables above were calibrated in October on TradingView exports (OANDA / VANTAGE gold, Bitfinex BTC 2018-2019) that are no longer available here. Below, the **master file** [`GVLiveV2_Polymarket_PreCandle_Strategy_FGF.pine`](../GVLiveV2_Polymarket_PreCandle_Strategy_FGF.pine) is run at its own defaults on the data used for the other strategies, with the new option off ("normal") and on ("inverted").

- **Data.** BTCUSD: Bitstamp, 2024-11-17 to 2026-11-17. XAUUSD: Dukascopy, 2017-01-02 to 2018-06-19.
- **Defaults.** EMA 8 / 21, trend EMA 100, pre-candle arm on with "Market Next Candle", stop 1 x ATR, target 5R, no trailing, at most 3 losing trades per New York day. In this file the direction filter is off by default; both states are shown.
- **Sizing** is the file's own: risk 1% of equity on a 100,000 account, at most 50 units. On gold every trade hits the 50-ounce cap, so the real risk is 0.01% to 0.24% of the account and the percentages are small. On BTC the 1% risk compounds, and -100% means the account could no longer size a trade.
- **"As TradingView shows"** has no costs at all: the file's Properties are commission 0 and slippage 0. **"1-minute fills with our costs"** is the realistic figure: stop and target checked on 1-minute candles, gold $0.30 per ounce per round trip, BTC 0.02% per side + $0.20.
- **How it was tested.** A new Python replica: two builds written independently agree on all 2.0 million trades of 1,440 test cases, and an auditor's own reference written from the Pine alone agrees on another 1.35 million trades and on every figure below. No defect was found.

### BTCUSD

| TF | Filter | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Inverted, both halves (1-minute fills, our costs) | PF inverted (same) |
|---|---|---|---|---|---|---|
| 1m | off | 915 / 1,000 | +740.7% / +810.3% | -100.0% / **-100.0%** | -100.0% / -41.6% | 0.51 |
| 1m | on | 939 / 1,023 | +665.2% / +1,010.4% | -100.0% / **-100.0%** | -100.0% / -43.2% | 0.60 |
| 5m | off | 2,688 / 2,530 | +872.6% / +235.6% | -100.0% / **-100.0%** | -99.4% / -99.2% | 0.71 |
| 5m | on | 2,612 / 2,621 | +676.4% / +496.5% | -100.0% / **-100.0%** | -98.5% / -98.4% | 0.69 |
| 15m | off | 2,107 / 1,985 | +298.3% / +220.8% | -91.1% / **-90.1%** | -90.5% / +4.0% | 0.84 |
| 15m | on | 1,654 / 1,599 | +332.4% / +150.8% | -71.4% / **-82.9%** | -82.4% / -2.7% | 0.89 |
| 30m | off | 1,275 / 1,228 | +82.5% / +16.6% | -55.4% / **-67.7%** | -69.6% / +6.1% | 0.90 |
| 30m | on | 896 / 883 | +328.8% / +61.7% | +66.5% / **-35.4%** | -69.9% / +114.5% | 0.93 |
| 1h | off | 741 / 663 | -52.2% / +6.3% | -71.9% / **-32.3%** | +16.3% / -41.8% | 0.95 |
| 1h | on | 279 / 249 | -32.4% / -3.1% | -45.0% / **-19.2%** | -7.0% / -13.2% | 0.91 |
| 2h | off | 359 / 373 | +48.1% / +11.2% | +25.2% / **-6.6%** | +17.6% / -20.6% | 0.98 |
| 2h | on | 129 / 121 | -5.9% / +8.1% | -11.5% / **+2.1%** | +9.1% / -6.4% | 1.02 |
| 4h | off | 155 / 170 | +42.0% / -24.7% | +35.2% / **-28.5%** | +1.1% / -29.3% | 0.80 |
| 4h | on | 52 / 52 | +43.3% / -10.5% | +41.0% / **-11.9%** | -5.3% / -7.0% | 0.73 |

### XAUUSD

| TF | Filter | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Inverted, both halves (1-minute fills, our costs) | PF inverted (same) |
|---|---|---|---|---|---|---|
| 1m | off | 1,649 / 1,642 | +1.6% / +1.0% | -23.2% / **-23.6%** | -11.8% / -13.3% | 0.31 |
| 1m | on | 1,579 / 1,566 | -0.2% / +0.8% | -23.9% / **-22.7%** | -10.7% / -13.5% | 0.35 |
| 5m | off | 1,482 / 1,471 | +0.3% / +0.7% | -22.0% / **-20.9%** | -9.1% / -13.0% | 0.61 |
| 5m | on | 1,343 / 1,364 | +0.2% / -1.1% | -19.9% / **-21.6%** | -11.0% / -11.8% | 0.61 |
| 15m | off | 993 / 1,000 | +4.4% / +5.2% | -9.5% / **-9.9%** | -7.9% / -2.1% | 0.85 |
| 15m | on | 756 / 773 | +1.0% / +3.3% | -9.3% / **-8.3%** | -7.2% / -1.2% | 0.84 |
| 30m | off | 603 / 584 | +2.5% / +10.0% | -6.6% / **+1.3%** | -1.9% / +3.2% | 1.02 |
| 30m | on | 404 / 416 | +8.0% / +5.4% | +1.9% / **-0.8%** | -5.6% / +5.1% | 0.98 |
| 1h | off | 329 / 325 | -0.1% / -1.1% | -5.1% / **-5.9%** | -0.2% / -5.7% | 0.86 |
| 1h | on | 122 / 126 | +8.0% / +1.1% | +6.2% / **-0.8%** | -0.7% / -0.1% | 0.95 |
| 2h | off | 193 / 188 | +3.7% / -9.6% | +0.8% / **-12.5%** | -7.7% / -5.1% | 0.63 |
| 2h | on | 72 / 73 | +0.7% / +2.4% | -0.4% / **+1.3%** | +1.5% / -0.2% | 1.11 |
| 4h | off | 84 / 88 | +6.5% / -8.4% | +5.3% / **-9.8%** | -5.9% / -4.1% | 0.56 |
| 4h | on | 35 / 32 | +1.0% / +4.2% | +0.5% / **+3.7%** | +0.8% / +2.9% | 1.55 |

### What it shows

- **Normal is positive in both halves on four cells:** BTC 30m with the filter on (+66.5%, halves +53.3% / +8.6%, 896 trades), BTC 4h with the filter off (+35.2%, 155 trades) and on (+41.0%, 52 trades), and gold 1h with the filter on (+6.2%, 122 trades).
- **Inverted is positive in both halves on one cell only:** gold 4h with the filter on (+3.7%, 32 trades). On BTC from 30m up, inverted is mostly worse than normal.
- **These are single default runs,** several of them on few trades, and none has been through a hold-out test. The calibration with the direction as an input is a separate run.
- **1m and 5m lose in both directions.** On BTC the costs wipe the account; on gold they cost 20% to 24%.
- **BTC 1m to 15m "as TradingView shows" are not results.** Both directions show several hundred percent there with no costs, which no signal can explain: on those charts the stop is about the size of one candle and the backtest books it exactly at its level.

### Limits

- **Margin.** The file sets no margin, so TradingView's default of 100% applies, and on BTC most default positions below the 4h chart are larger than the account and would be refused. These results assume Properties > Margin is set low (about 1%), as the file's own sizing input assumes. Gold is not affected.
- **One TradingView behaviour could not be checked here, and it moves its own report.** After a stop or target, the file can enter again on the same candle. The replica fills that entry at the next candle's open, which is what happens live. TradingView's backtest may fill it inside the exit candle at an extreme price, and would then show more profit than the figures above, most of all for inverted.
- **The daily limit shapes the fast charts.** "3 losing trades per day" counts New York calendar days and is in force on about two thirds of the 5-minute candles, so the 1m and 5m results are mostly the hours after New York midnight.
- Short windows and old gold data, as for the other strategies. Nothing here was compiled or run in TradingView.

## Calibration by timeframe on the new data, with the direction as an input

The master file's inputs were searched per pair and timeframe on the new data (Bitstamp BTC 2024-2026, Dukascopy gold 2017-2018), with the Update 1 option "Inverted direction" as one of them: 290,304 backtests.

### What was searched

20,736 settings on every timeframe from 1m to 4h of BTCUSD and XAUUSD, the full product of:

| | Values |
|---|---|
| Signals | EMA pair 5 / 13 or 8 / 21; trend EMA 50, 100, 200; min vol score 0 or 35; min vol rise 0 or 1; close location 0.55, 0.65, 0.75; trend direction on or off |
| Filter and direction | filter off or on; normal or inverted |
| Entry and exits | pre-candle mode "Market Next Candle" or "Stop Next Candle"; stop 0.5, 1, 2 x ATR; exit: 5R target, a 4-candle time stop with no target, or an ATR trailing stop with no target; "3 losing trades per day" lock on or off |

- **Scoring.** 1-minute fills with costs (gold $0.30 per ounce per round trip, BTC 0.02% per side + $0.20), on the two halves of the window separately.
- **Sizing.** Risk 1% of equity per trade as in the file, but without the file's 50-unit cap, so that gold is not stuck at 50 ounces and the cap does not decide which setting looks best. A setting chosen this way is re-run with the file's own sizing before it counts. Margin is assumed low (about 1%), as the file's own sizing input assumes.

### The rule

The same rule as for ApexForge and HRD ([how it works and what its audit found](../ApexForge_HRD_by_timeframe/README.md#the-rule-rule-c)), plus the step added after that audit: the selection is repeated on one half only, and the setting it picks must be profitable on the other half and beat its direction-flipped twin there, both ways. A pick must also stay profitable in both halves with the file's own sizing. A pass is a reason to review a setting, never a reason to trade it.

### Results

How to read the table:

- **Different results**: settings with the same trades count once.
- **Positive in both halves**: how many of those are profitable in both halves with 30+ trades in each, per direction.
- **Typical result**: the median over settings with 30+ trades per half.
- **Best normal / inverted**: the setting with the best worst half, as net result (first half / second half, trades). In-sample: the best of thousands always looks good.
- **Hold-outs**: what the 40 best of one half made on the other half, against the 95th percentile of random draws.
- **Chosen on one half**: what the single setting picked on one half made on the other.

#### BTCUSD

| TF | Different results | Positive in both halves: normal / inverted | Typical result: normal / inverted | Best normal (halves, trades) | Best inverted (halves, trades) | Forward hold-out | Reverse hold-out | Chosen on one half, result on the other: first to second / second to first | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1m | 20,723 | 0 / 0 | -100.00% / -100.00% | -99.89% (-97.38% / -95.90%, 2699 trades) | -100.00% (-99.53% / -99.52%, 2598 trades) | -98.09% vs -84.71%, 0% positive: FAIL | -100.00% vs -99.88%, 0% positive: FAIL | none / none | no setting: no setting is positive in both halves with 30+ trades in each |
| 5m | 20,736 | 0 / 0 | -100.00% / -100.00% | +8.12% (-2.96% / +11.42%, 2257 trades) | -60.57% (-38.72% / -35.65%, 2753 trades) | -53.50% vs -84.70%, 5% positive: FAIL | -81.40% vs -93.13%, 0% positive: FAIL | none / none | no setting: no setting is positive in both halves with 30+ trades in each |
| 15m | 20,733 | 218 / 118 | -94.19% / -99.58% | +383.19% (+169.08% / +79.57%, 2128 trades) | +204.46% (+61.43% / +88.60%, 805 trades) | +1.60% vs -60.21%, 55% positive: FAIL | -27.16% vs -65.79%, 22% positive: FAIL | +61.73% / +27.19% | no setting: stressed costs; forward hold-out failed; reverse hold-out failed |
| 30m | 20,718 | 778 / 186 | -54.36% / -80.25% | +216.97% (+61.26% / +96.56%, 1694 trades) | +149.02% (+58.34% / +57.27%, 402 trades) | -17.05% vs -35.04%, 25% positive: FAIL | -51.30% vs -26.52%, 2% positive: FAIL | +19.62% / -46.69% | no setting: stressed costs; forward hold-out failed; reverse hold-out failed; nested reverse pick failed |
| 1h | 19,185 | 1,892 / 165 | -18.96% / -45.66% | +269.22% (+91.26% / +93.05%, 472 trades) | +107.38% (+46.64% / +41.42%, 923 trades) | -13.24% vs -9.78%, 30% positive: FAIL | -26.73% vs -9.86%, 25% positive: FAIL | -53.53% / -61.22% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 2h | 15,388 | 1,308 / 328 | -8.95% / -32.15% | +147.54% (+57.15% / +57.52%, 502 trades) | +82.79% (+20.11% / +52.19%, 428 trades) | -9.54% vs -9.57%, 35% positive: FAIL | -2.06% vs -2.31%, 55% positive: FAIL | -6.37% / +45.05% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed |
| 4h | 12,580 | 1,159 / 349 | -7.43% / -16.44% | +166.31% (+51.69% / +75.57%, 203 trades) | +29.66% (+13.76% / +13.98%, 111 trades) | +6.03% vs -3.33%, 45% positive: FAIL | +28.07% vs -4.44%, 92% positive: pass | -34.80% / +51.66% | no setting: forward hold-out failed; nested forward pick failed |

#### XAUUSD

| TF | Different results | Positive in both halves: normal / inverted | Typical result: normal / inverted | Best normal (halves, trades) | Best inverted (halves, trades) | Forward hold-out | Reverse hold-out | Chosen on one half, result on the other: first to second / second to first | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1m | 15,027 | 0 / 0 | -100.00% / -100.00% | -99.99% (-98.86% / -98.89%, 1550 trades) | -99.99% (-98.70% / -99.16%, 1613 trades) | -99.73% vs -96.44%, 0% positive: FAIL | -100.00% vs -99.85%, 0% positive: FAIL | none / none | no setting: no setting is positive in both halves with 30+ trades in each |
| 5m | 20,171 | 0 / 0 | -100.00% / -100.00% | -52.17% (-34.80% / -26.64%, 1038 trades) | -76.23% (-51.84% / -50.64%, 1149 trades) | -71.47% vs -88.95%, 0% positive: FAIL | -78.22% vs -91.50%, 0% positive: FAIL | none / none | no setting: no setting is positive in both halves with 30+ trades in each |
| 15m | 20,723 | 107 / 0 | -96.75% / -97.90% | +145.94% (+41.23% / +74.15%, 397 trades) | +14.34% (+18.56% / -3.56%, 541 trades) | -5.14% vs -65.57%, 40% positive: FAIL | -28.78% vs -68.20%, 15% positive: FAIL | -3.13% / -29.24% | no setting: none of the 40 best candidates sits on a plateau |
| 30m | 20,454 | 259 / 54 | -64.92% / -81.24% | +150.55% (+70.43% / +47.01%, 267 trades) | +86.78% (+23.50% / +51.24%, 253 trades) | +2.30% vs -39.94%, 55% positive: FAIL | -29.31% vs -41.89%, 12% positive: FAIL | -17.78% / -36.23% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 1h | 17,564 | 638 / 82 | -27.86% / -44.10% | +88.09% (+36.39% / +37.91%, 178 trades) | +42.12% (+21.75% / +16.73%, 210 trades) | -19.23% vs -17.92%, 0% positive: FAIL | -16.49% vs -15.21%, 25% positive: FAIL | -11.67% / -3.51% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 2h | 13,855 | 412 / 178 | -16.08% / -29.16% | +81.78% (+35.99% / +33.67%, 428 trades) | +42.77% (+20.89% / +18.10%, 167 trades) | -2.95% vs -13.10%, 45% positive: FAIL | -10.74% vs -4.16%, 18% positive: FAIL | -9.07% / -2.98% | no setting: stressed costs; forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 4h | 10,749 | 557 / 136 | -3.93% / -16.51% | +69.27% (+32.20% / +28.04%, 222 trades) | +41.91% (+14.83% / +23.58%, 246 trades) | -28.78% vs -8.16%, 0% positive: FAIL | +1.48% vs +6.28%, 52% positive: FAIL | -27.04% / +12.69% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed |

### What it shows

- **No setting passes on any timeframe of either pair, in either direction.**
- **1m and 5m: not one setting with 30+ trades per half is profitable in both halves,** on either pair. The typical setting there loses the whole account.
- **The best settings look very large only in-sample** (BTC 15m normal +383%, BTC 1h normal +269%, at 1% risk per trade compounding). Settings chosen on one half mostly do not carry over: of the 20 single settings chosen on one half, 6 were profitable on the other.
- **Closest: BTC 4h, normal.** From the second half to the first the 40 best average +28% and 93% of them are profitable. From the first half to the second they average +6.0%, but only 45% are profitable (60% needed), and the setting chosen on the first half alone lost 35% on the second.
- **BTC 15m:** the settings chosen on one half were profitable on the other in both directions (+62% and +27%), but both hold-outs fail and the setting the rule would pick loses with stressed costs.
- **Normal is clearly ahead of inverted** from 15m up on both pairs (BTC 1h: 1,892 normal against 165 inverted profitable settings; gold 15m: 107 against 0). It still does not carry from one half to the other.

### Data

Every setting of every timeframe, with its inputs, trades, net result, profit factor, drawdown and both halves: [`calibration_gvl_newdata.csv.gz`](calibration_gvl_newdata.csv.gz) (290,304 rows).

### Limits

- The same limits as the by-timeframe section above: margin, the same-candle re-entry TradingView may fill differently, the daily limit on New York days, the short windows and the old gold data.
- This search does not replace the October files above. Those were calibrated on other data and were not re-tested here.
- Nothing here was compiled or run in TradingView.
