# Danny Phantom FX V10.21.1 LiveSafe FGF: one file per pair and timeframe

**Update 1 (2026-11-23).** Every file here now has the option "Inverted direction: opposite side at the same entries" (the last setting, off by default) and a title ending in `[Update 1]`. Off is exactly the previous version, so every result below still holds; nothing here was tested with the option on. It is a different thing from "Signal direction", which stays as each file set it. See [UPDATES.md](../UPDATES.md).

Same code as `DannyPhantomFX_V10_21_1_LiveSafe_FGF.pine`; only the input defaults differ. Each file's header starts with a FRAGILITY block (what the result depends on), then the full record: data, costs, the rule, the hold-out in both directions, stressed costs, monthly spread and the sets it was compared with.

**Rule v3.1.** Per pair and timeframe, a setting is picked from the full input grid: among the settings positive in both halves of every dataset, the 40 best by worst half are scored by 0.5 x worst half + 0.5 x the mean worst half of their clone-free grid neighbours (at least 5 neighbours with a positive mean), and the best of them is the pick. It becomes the file's defaults only if choosing settings on one half and testing them on the other works in both directions: the 40 best beat 95% of random 40-setting draws from the same pool, also when counted as their distinct entry-overlap clusters; forward they are also at least 60% positive with a positive mean. The pick must also survive stressed costs. Otherwise a general set is used only if it passes its own robustness and plateau check, and the file says so in its title. Otherwise no file is published for that timeframe.

Costs: gold $0.30 spread per round trip; BTC 0.02% fee per side + $0.20 spread per round trip; no slippage. Stressed: gold $0.50 spread + 1 tick per side; BTC 0.035% per side + $0.20 + 1 tick per side. R = one stop distance. Results are in-sample; the hold-out columns are the out-of-sample guide.

**TradingView's own report** will differ: the strategy() properties add 75 ticks of slippage per fill and 0.001% commission. On a 0.01-tick gold symbol that is $0.75 per fill, which turns several files negative; set Properties > Slippage to match your broker. Each header gives the result at several tick sizes.

**S2 and S3.** Each file carries ATR-mode defaults (the calibrated mode) and Points-mode distances for the same signal inputs: calibrated where the Points exit rule passed its own hold-out (see the Points column), otherwise the ATR distances converted at the median ATR. The trail switch and time stop are shared by both units. The Risk % default is sized so that the 95th-percentile drawdown of reordered trades at stressed costs stays within 20%; these sizing figures exclude the 75-tick slippage property, whose effect each header states.

## XAUUSD

| TF | File | Defaults | Result on the data | Without the 10 biggest trades | Stressed costs | Forward hold-out | Reverse hold-out | Points mode | Risk % |
|---|---|---|---|---|---|---|---|---|---|
| 10m | **no file** | no defensible setting (see below) | | | | 85% positive, +5.4R vs +0.8R; 4 clusters +13.3R vs +11.2R: pass | -16.3R vs -1.8R; 6 clusters -14.2R vs +9.8R: FAIL | | |
| 15m | **no file** | no defensible setting (see below) | | | | 0% positive, -116.1R vs -7.4R; 1 cluster -109.3R vs +44.8R: FAIL | -20.5R vs -4.4R; 2 clusters +3.7R vs +16.6R: FAIL | | |
| 30m | [DannyPhantomFX_FGF_XAUUSD_30m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/DannyPhantomFX_by_timeframe/DannyPhantomFX_FGF_XAUUSD_30m.pine) | **calibrated for this timeframe**: preset Auto (manual path on this chart), direction ORIGINAL (not inverted), S2 ATR mode: SL 0.8 x ATR(14), no target, no trail, time stop 50 bars, dead exit on, 15 bars, EMA filter on, length 100, delta threshold 1, zone length 50, cooldown off, one entry per zone off, direction filter off | VANTAGE XAUUSD +288.1R, 1287 trades, PF 1.27, DD 42.8R | +56.8R | +247.8R | 90% positive, +31.0R vs +13.0R; 5 clusters +29.0R vs +24.4R: pass | +120.9R vs +24.4R; 9 clusters +114.6R vs +40.7R: pass | calibrated: +204.1R | 0.15% |
| 45m | [DannyPhantomFX_FGF_XAUUSD_45m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/DannyPhantomFX_by_timeframe/DannyPhantomFX_FGF_XAUUSD_45m.pine) | **calibrated for this timeframe**: preset Auto (manual path on this chart), direction ORIGINAL (not inverted), S2 ATR mode: SL 0.8 x ATR(14), no target, no trail, time stop 50 bars, dead exit on, 30 bars, EMA filter on, length 200, delta threshold 1, zone length 100, cooldown off, one entry per zone off, direction filter off | VANTAGE XAUUSD +260.9R, 1235 trades, PF 1.24, DD 64.6R | +88.1R | +213.9R | 95% positive, +72.0R vs +27.4R; 10 clusters +76.3R vs +37.2R: pass | +40.8R vs -2.2R; 7 clusters +41.4R vs +7.8R: pass | converted: +352.0R | 0.15% |
| 60m | **no file** | no defensible setting (see below) | | | | 100% positive, +64.1R vs +17.2R; 10 clusters +81.9R vs +23.1R: pass | -42.1R vs -1.3R; 3 clusters -15.7R vs +35.6R: FAIL | | |
| 120m | **no file** | no defensible setting (see below) | | | | 85% positive, +11.5R vs +7.4R; 1 cluster +16.7R vs +23.2R: FAIL | +63.5R vs +35.6R; 2 clusters +57.1R vs +67.2R: FAIL | | |
| 240m | **no file** | no defensible setting (see below) | | | | 100% positive, +66.1R vs +34.5R; 1 cluster +48.0R vs +63.6R: FAIL | +38.6R vs +21.3R; 1 cluster +30.1R vs +40.6R: FAIL | | |

## BTCUSD

| TF | File | Defaults | Result on the data | Without the 10 biggest trades | Stressed costs | Forward hold-out | Reverse hold-out | Points mode | Risk % |
|---|---|---|---|---|---|---|---|---|---|
| 1m | **no file** | no defensible setting (see below) | | | | 100% positive, +4145.5R vs +1343.8R; 1 cluster +4675.3R vs +3391.9R: pass | +6423.8R vs +2664.7R; 4 clusters +4439.9R vs +3727.4R: pass | | |
| 5m | **no file** | no defensible setting (see below) | | | | 47% positive, +121.3R vs +121.3R; 5 clusters +186.8R vs +212.8R: FAIL | +239.2R vs +179.7R; 2 clusters +268.8R vs +324.0R: FAIL | | |
| 15m | [DannyPhantomFX_FGF_BTCUSD_15m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/DannyPhantomFX_by_timeframe/DannyPhantomFX_FGF_BTCUSD_15m.pine) | **calibrated for this timeframe**: preset Auto (manual path on this chart), direction ORIGINAL (not inverted), S2 ATR mode: SL 0.8 x ATR(14), no target, no trail, time stop 100 bars, dead exit on, 15 bars, EMA filter on, length 200, delta threshold 1, zone length 100, cooldown on, 10 bars, one entry per zone off, direction filter off | Bitfinex BTCUSD +797.0R, 2180 trades, PF 1.38, DD 92.4R | +157.4R | +472.8R | 100% positive, +230.5R vs +27.1R; 5 clusters +188.9R vs +63.0R: pass | +294.1R vs +112.8R; 6 clusters +318.3R vs +155.5R: pass | converted: +253.8R (loses under stressed costs, -55.9R: keep ATR) | 0.1% (FLAGGED: exceeds the drawdown limit even at 0.1%) |
| 30m | [DannyPhantomFX_FGF_BTCUSD_30m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/DannyPhantomFX_by_timeframe/DannyPhantomFX_FGF_BTCUSD_30m.pine) | **calibrated for this timeframe**: preset Auto (manual path on this chart), direction ORIGINAL (not inverted), S2 ATR mode: SL 0.8 x ATR(14), no target, trail: arm at 4 ATR, distance 0.2 ATR, time stop 50 bars, dead exit on, 30 bars, EMA filter on, length 100, delta threshold 1, zone length 100, cooldown off, one entry per zone off, direction filter off | Bitfinex BTCUSD +370.8R, 1663 trades, PF 1.27, DD 52.7R | +45.5R | +215.6R | 100% positive, +128.0R vs +28.1R; 4 clusters +111.4R vs +59.9R: pass | +93.8R vs +43.8R; 5 clusters +111.2R vs +68.3R: pass | converted: -80.2R (loses, keep ATR) | 0.15% |
| 60m | [DannyPhantomFX_FGF_BTCUSD_60m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/DannyPhantomFX_by_timeframe/DannyPhantomFX_FGF_BTCUSD_60m.pine) | **calibrated for this timeframe**: preset Auto (manual path on this chart), direction ORIGINAL (not inverted), S2 ATR mode: SL 0.8 x ATR(14), no target, no trail, time stop 25 bars, dead exit on, 15 bars, EMA filter on, length 100, delta threshold 2, zone length 100, cooldown on, 10 bars, one entry per zone on, direction filter off | Bitfinex BTCUSD +229.4R, 568 trades, PF 1.56, DD 27.8R | +6.2R | +199.8R | 100% positive, +62.2R vs +21.4R; 4 clusters +60.6R vs +39.7R: pass | +76.7R vs +50.5R; 3 clusters +85.6R vs +78.5R: pass | converted: +40.3R | 0.25% |
| 120m | [DannyPhantomFX_FGF_BTCUSD_120m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/DannyPhantomFX_by_timeframe/DannyPhantomFX_FGF_BTCUSD_120m.pine) | **calibrated for this timeframe**: preset Auto (manual path on this chart), direction ORIGINAL (not inverted), S2 ATR mode: SL 0.8 x ATR(14), no target, no trail, time stop 100 bars, dead exit on, 30 bars, EMA filter on, length 100, delta threshold 1, zone length 100, cooldown on, 10 bars, one entry per zone off, direction filter off | Bitfinex BTCUSD +195.3R, 456 trades, PF 1.64, DD 33.3R | -13.8R | +159.8R | 93% positive, +24.7R vs +19.4R; 2 clusters +50.3R vs +48.9R: pass | +34.0R vs +8.2R; 7 clusters +34.9R vs +15.5R: pass | converted: +42.5R | 0.25% |
| 240m | [DannyPhantomFX_FGF_BTCUSD_240m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/DannyPhantomFX_by_timeframe/DannyPhantomFX_FGF_BTCUSD_240m.pine) | **calibrated for this timeframe**: preset Auto (manual path on this chart), direction ORIGINAL (not inverted), S2 ATR mode: SL 0.8 x ATR(14), no target, no trail, time stop 25 bars, dead exit on, 15 bars, EMA filter on, length 100, delta threshold 2, zone length 100, cooldown on, 10 bars, one entry per zone off, direction filter off | Bitfinex BTCUSD +115.8R, 174 trades, PF 1.95, DD 18.7R | -17.6R | +107.0R | 100% positive, +54.8R vs +19.2R; 4 clusters +54.1R vs +30.8R: pass | +12.4R vs +7.5R; 4 clusters +14.9R vs +13.3R: pass | converted: +15.8R | 0.75% |

## Timeframes without a file

- **XAUUSD 10m**: reverse hold-out failed: mean -16.3R not above -1.8R, cluster representatives -14.2R not above +9.8R (6 clusters); no pair-wide general set exists (no setting positive in every half of every timeframe of the pair sits on a plateau); a full sweep in S2 Points mode (124,416 settings with fixed dollar distances) also gave no file: forward hold-out failed: only 50% positive (60% needed), mean not positive, mean -2.2R not above the random 95th percentile +2.9R, cluster representatives +7.9R not above +10.2R (3 clusters); reverse hold-out failed: mean -58.7R not above -9.1R, cluster representatives -53.8R not above +8.0R (4 clusters).
- **XAUUSD 15m**: forward hold-out failed: only 0% positive (60% needed), mean not positive, mean -116.1R not above the random 95th percentile -7.4R, cluster representatives -109.3R not above +44.8R (1 cluster); reverse hold-out failed: mean -20.5R not above -4.4R, cluster representatives +3.7R not above +16.6R (2 clusters); no pair-wide general set exists (no setting positive in every half of every timeframe of the pair sits on a plateau); a full sweep in S2 Points mode (124,416 settings with fixed dollar distances) also gave no file: forward hold-out failed: only 0% positive (60% needed), mean not positive, mean -94.1R not above the random 95th percentile -7.7R, cluster representatives -129.7R not above +21.1R (1 cluster); reverse hold-out failed: mean -32.0R not above -12.7R, cluster representatives -44.7R not above +10.3R (2 clusters).
- **XAUUSD 60m**: reverse hold-out failed: mean -42.1R not above -1.3R, cluster representatives -15.7R not above +35.6R (3 clusters); no pair-wide general set exists (no setting positive in every half of every timeframe of the pair sits on a plateau); a full sweep in S2 Points mode (124,416 settings with fixed dollar distances) also gave no file: reverse hold-out failed: mean -36.7R not above +2.3R, cluster representatives -39.4R not above +42.4R (2 clusters).
- **XAUUSD 120m**: forward hold-out failed: cluster representatives +16.7R not above +23.2R (1 cluster); reverse hold-out failed: cluster representatives +57.1R not above +67.2R (2 clusters); no pair-wide general set exists (no setting positive in every half of every timeframe of the pair sits on a plateau); a full sweep in S2 Points mode (124,416 settings with fixed dollar distances) also gave no file: forward hold-out failed: mean +10.2R not above the random 95th percentile +11.2R, cluster representatives -1.2R not above +26.4R (2 clusters); reverse hold-out failed: cluster representatives +20.8R not above +55.0R (2 clusters).
- **XAUUSD 240m**: forward hold-out failed: cluster representatives +48.0R not above +63.6R (1 cluster); reverse hold-out failed: cluster representatives +30.1R not above +40.6R (1 cluster); no pair-wide general set exists (no setting positive in every half of every timeframe of the pair sits on a plateau); a full sweep in S2 Points mode (124,416 settings with fixed dollar distances) also gave no file: reverse hold-out failed: cluster representatives +24.4R not above +27.2R (2 clusters).
- **BTCUSD 1m**: none of the 40 best settings sits on a plateau (fewer than 5 clone-free neighbours, or their mean worst half is not positive), so there is no pick; no pair-wide general set exists (no setting positive in every half of every timeframe of the pair sits on a plateau); a full sweep in S2 Points mode (124,416 settings with fixed dollar distances) also gave no file: the pick loses under stressed costs (Bitfinex BTCUSD -14246.5R).
- **BTCUSD 5m**: forward hold-out failed: only 47% positive (60% needed), mean +121.3R not above the random 95th percentile +121.3R, cluster representatives +186.8R not above +212.8R (5 clusters); reverse hold-out failed: cluster representatives +268.8R not above +324.0R (2 clusters); the pick loses under stressed costs (Bitfinex BTCUSD -674.1R); no pair-wide general set exists (no setting positive in every half of every timeframe of the pair sits on a plateau); a full sweep in S2 Points mode (124,416 settings with fixed dollar distances) also gave no file: none of the 40 best settings sits on a plateau (fewer than 5 clone-free neighbours, or their mean worst half is not positive), so there is no pick; forward hold-out failed: cluster representatives -217.3R not above +23.5R (2 clusters); reverse hold-out failed: cluster representatives +34.5R not above +319.0R (3 clusters).

## Direction filter (FlashGold Direction Filter v1.2)

The filter was rebuilt in Python and checked against TradingView: at the Pine defaults it reproduces TradingView's own filter output (buy, sell, level, signal) on 100% of the covered bars of the three OANDA gold exports (60m 4,560 bars, 120m 2,379, 240m 1,192). Its inputs were then swept on every timeframe: filter timeframe (the chart, 2x, 4x, 8x), parent timeframe, child zone timeframe sets with minimum aligned, no-trade band, level mode, permission lifetime, burst gate and trading against the signal (about 900 to 3,700 settings per timeframe, then a finer pass). The filter is switched on only if it improves the weakest half, survives a hold-out of the whole selection in both directions and beats filter-off under stressed costs; on a timeframe without a file it had to create a setting that passes the same tests.

**Result: the filter stays off on every timeframe and creates no new file.** The best in-sample filters often looked much better, but most used a parent or zone timeframe above the filter timeframe, which reads a still-forming bar live (it repaints), and none survived the hold-outs once evaluated as it would trade live.

| Pair | TF | Decision | Why |
|---|---|---|---|
| XAUUSD | 10m | still no file | Changed from new_file. Confirmed (probe_fgfdecide_check.py): the pick repaints (parent 20 above F10, zones 60/120/240 with htfClosed off); live it makes 79.08R vs 78.86R for the same Danny with the filter off. The unchanged rule on a non-repainting grid returns no_file (reverse hold-out -8.99R vs pool median 8.79R). |
| XAUUSD | 15m | still no file | Sweep decision kept. Both hold-outs fail: forward 5.41R vs 57.52R for its own Danny unfiltered, reverse -22.73R vs 50.13R. |
| XAUUSD | 30m | filter off (file unchanged) | Sweep decision kept (no sceptic refuted it). The forward hold-out fails: the filter chosen on the first half made 47.88R on the second half vs 142.56R with the filter off. |
| XAUUSD | 45m | filter off (file unchanged) | Sweep decision kept. The forward hold-out fails: 104.97R on the second half vs 155.94R with the filter off. |
| XAUUSD | 60m | still no file | Changed from new_file. Confirmed: the hold-out picks lose to the same Danny with the filter off (forward XAU60 34.24R vs 34.84R, XAUV60 105.91R vs 146.64R); the pick repaints (parent 240 above F120); and the unchanged rule on a non-repainting grid returns no_file (reverse XAUV60 22.46R vs median 27.96R). |
| XAUUSD | 120m | still no file | Sweep decision kept. Both hold-outs fail on XAUV120: forward 5.5R vs 16.49R and reverse 2.67R vs 26.32R for the same Danny unfiltered. |
| XAUUSD | 240m | still no file | Changed from new_file. Confirmed: both hold-out picks lose to the same Danny with the filter off on XAU240 (22.1R vs 27.02R, 14.17R vs 20.25R); XAUV240.csv is on a UTC grid, and on TradingView-style VANTAGE 240 bars the unchanged rule returns no_file (forward 20.41R vs median 20.65R). |
| BTCUSD | 1m | still no file | Sweep decision kept. Stress fails: the pick makes -19,369.89R at stressed costs (about 31,500 trades). |
| BTCUSD | 5m | still no file | Changed from new_file. Confirmed: both hold-out picks lose to the same Danny with the filter off (299.11R vs 603.75R, 537.41R vs 767.06R) and are negative at stressed costs; the unchanged rule on a non-repainting grid returns no_file (forward 233.24R vs median 260.76R). |
| BTCUSD | 15m | filter off (file unchanged) | Sweep decision kept. No full-data pick on a plateau; the reverse hold-out makes 65.32R vs 444.38R with the filter off. |
| BTCUSD | 30m | filter off (file unchanged) | Sweep decision kept. No full-data pick on a plateau; the reverse hold-out makes 19.63R vs 185.08R with the filter off. |
| BTCUSD | 60m | filter off (file unchanged) | Sweep decision kept. No full-data pick; both hold-outs fail (forward -17.62R vs 125.33R, reverse 33.03R vs 104.06R). |
| BTCUSD | 120m | filter off (file unchanged) | Sweep decision kept. No full-data pick; the reverse hold-out makes 68.88R vs 99.85R with the filter off. |
| BTCUSD | 240m | filter off (file unchanged) | Changed from filter_on. Confirmed (probe_fgfdecide_rules.py liveA/safeA): the reverse hold-out was won by a repainting setting (parent 480 above F240); re-running the unchanged rule with live semantics, or without repainting settings, the reverse pick makes 20.89R vs 50.75R with the filter off, so the rule returns filter_off. |

## Revision history

- v3 (commits 19384f7 and 4ed9157): first release, 9 files (XAUUSD 30m/45m/120m/240m, BTCUSD 15m/30m/60m/120m/240m).
- v3.1 (this version), after the adversarial review: the permutation test also counts the top 40 as distinct entry-overlap clusters and plateaus ignore clones, which withdrew XAUUSD 120m and 240m (their top 40 were one or two clusters) and revised the BTCUSD picks (7 files); headers open with the fragility facts (the result without the 10 biggest trades, fee break-even, TradingView's 75-tick slippage report, weekend holds, exits); Points-mode distances were added to every file (calibrated where the Points exit rule passed, converted elsewhere) and the Risk % size was set by the reordered-drawdown rule. The Points timeframes without a file were also swept in Points mode; none passed.
- Direction filter test (this version): the filter was rebuilt in Python, validated against TradingView and swept on all 14 timeframes; it stays off everywhere (see the section above).

## Inverted direction (Update 1): results by timeframe on new data

This section is separate from everything above. The files and tables above were calibrated in October on TradingView exports (OANDA / VANTAGE gold, Bitfinex BTC 2018-2019) that are no longer available here. Below, the **master file** [`DannyPhantomFX_V10_21_1_LiveSafe_FGF.pine`](../DannyPhantomFX_V10_21_1_LiveSafe_FGF.pine) is run at its own defaults on the data used for the other strategies, with the new option off ("normal") and on ("inverted").

- **Data.** BTCUSD: Bitstamp, 2024-11-17 to 2026-11-17. XAUUSD: Dukascopy, 2017-01-02 to 2018-06-19.
- **Normal** is the file as it ships, which already has "Signal direction" at "Inverted (V10 design)". **Inverted** adds the Update 1 option on top. With the filter off, inverted gives the same trades as "Signal direction: Original".
- **Sizing** is the file's own: risk 1% of equity per trade on a 2,000 account. A result of -100% means the account could no longer size a trade.
- **"As TradingView shows"** uses the file's own Properties: 75 ticks of slippage per fill and 0.001% commission, on a 0.01-tick symbol. **"1-minute fills with our costs"** is the realistic figure: stop and target checked on 1-minute candles, gold $0.30 per ounce per round trip, BTC 0.02% per side + $0.20.
- **How it was tested.** A new Python replica: two builds written independently agree on all 1.8 million trades of 1,016 test cases, and an audit against the Pine found one defect, on a switch that is not at its default, with no effect on any number here.

### BTCUSD

| TF | Filter | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Inverted, both halves (1-minute fills, our costs) | PF inverted (same) |
|---|---|---|---|---|---|---|
| 1m | off | 1,435 / 1,578 | +195,422% / +167,030% | -100.0% / **-100.0%** | -99.9% / -40.5% | 0.68 |
| 1m | on | 1,208 / 1,233 | +227.1% / +1,245% | -100.0% / **-100.0%** | -99.9% / -33.1% | 0.59 |
| 5m | off | 3,509 / 2,990 | +631.2% / +369.6% | -99.8% / **-99.8%** | -99.4% / -62.4% | 0.82 |
| 5m | on | 2,495 / 2,598 | +25.4% / +489.5% | -99.2% / **-97.8%** | -87.1% / -82.9% | 0.84 |
| 15m | off | 3,379 / 2,616 | -62.3% / +547.8% | -98.5% / **-61.8%** | -38.8% / -37.5% | 0.95 |
| 15m | on | 1,389 / 1,334 | -72.8% / +81.1% | -93.1% / **-55.6%** | -23.8% / -41.7% | 0.92 |
| 30m | off | 1,959 / 1,505 | +0.8% / -1.4% | -75.1% / **-64.2%** | -30.9% / -48.2% | 0.90 |
| 30m | on | 1,030 / 904 | -3.7% / -5.0% | -54.3% / **-48.8%** | -33.8% / -22.6% | 0.88 |
| 1h | off | 1,198 / 927 | -10.4% / +41.8% | -50.5% / **-10.8%** | -29.0% / +25.7% | 0.97 |
| 1h | on | 779 / 631 | -42.4% / +47.7% | -60.6% / **+5.3%** | -3.8% / +9.4% | 1.02 |
| 2h | off | 633 / 481 | +23.8% / -10.0% | -1.0% / **-28.1%** | +5.3% / -31.8% | 0.89 |
| 2h | on | 425 / 345 | +51.5% / +11.9% | +30.2% / **-0.9%** | +17.3% / -15.5% | 1.00 |
| 4h | off | 328 / 248 | +12.6% / +3.8% | +3.8% / **-1.6%** | -7.7% / +6.6% | 0.99 |
| 4h | on | 216 / 176 | +15.2% / +14.8% | +9.3% / **+9.8%** | -2.2% / +12.3% | 1.09 |

### XAUUSD

| TF | Filter | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Inverted, both halves (1-minute fills, our costs) | PF inverted (same) |
|---|---|---|---|---|---|---|
| 1m | off | 1,517 / 1,605 | -100.0% / -100.0% | -100.0% / **-100.0%** | -100.0% / +0.0% | 0.46 |
| 1m | on | 1,299 / 1,347 | -100.0% / -100.0% | -100.0% / **-100.0%** | -100.0% / +0.0% | 0.44 |
| 5m | off | 0 / 0 | no trades | no trades | | |
| 5m | on | 0 / 0 | no trades | no trades | | |
| 15m | off | 2,492 / 1,900 | -100.0% / -100.0% | -99.6% / **-97.9%** | -90.2% / -78.9% | 0.71 |
| 15m | on | 1,013 / 987 | -100.0% / -100.0% | -87.9% / **-85.0%** | -69.8% / -50.5% | 0.75 |
| 30m | off | 1,208 / 872 | -100.0% / -99.9% | -88.8% / **-63.4%** | -29.4% / -48.2% | 0.87 |
| 30m | on | 633 / 551 | -99.5% / -99.3% | -40.8% / **-67.2%** | -49.2% / -35.5% | 0.75 |
| 1h | off | 615 / 453 | -95.2% / -88.6% | -24.8% / **-31.3%** | -5.9% / -27.1% | 0.91 |
| 1h | on | 416 / 317 | -84.5% / -77.5% | -17.2% / **-6.5%** | +15.0% / -18.7% | 0.97 |
| 2h | off | 357 / 273 | -81.0% / -56.8% | -36.7% / **-13.7%** | +24.8% / -30.8% | 0.94 |
| 2h | on | 235 / 191 | -74.7% / -39.5% | -45.2% / **+13.2%** | +44.1% / -21.5% | 1.07 |
| 4h | off | 178 / 132 | -55.2% / -25.5% | -30.9% / **+0.7%** | +15.2% / -12.6% | 1.01 |
| 4h | on | 125 / 99 | -34.9% / -17.6% | -14.6% / **-4.0%** | +9.0% / -11.9% | 0.95 |

Gold 5m takes no trade at the defaults: on that chart the file switches to its XAUUSD 5m preset, whose cost filter never passes on a 0.01-tick symbol.

### What it shows

- **Inverted is not positive in both halves on any timeframe.** Its positive totals (BTC 1h and 4h and gold 2h with the filter on, gold 4h with the filter off) each have one losing half.
- **Two default cells are positive in both halves, both normal, both BTC with the filter on:** 2h (+30.2%, halves +10.0% / +18.4%, 425 trades) and 4h (+9.3%, halves +7.8% / +1.4%, 216 trades). These are single default runs, not tested by any hold-out.
- **1m to 30m lose in both directions on both pairs.** With 1% risk per trade the costs wipe the account on the fastest charts.
- **Inverted loses less than normal on most BTC charts up to 1h and on gold from 2h**, but it is not a consistent winner: on BTC 2h normal is far ahead.
- **BTC 1m and 5m "as TradingView shows" are not results.** Both directions show large profits there, which no signal can explain. With this script's exits, random entries on a random side also profit on those charts when costs are near zero, and the file's 75 ticks are only $0.75 on a 0.01-tick BTC symbol.
- **Gold "as TradingView shows" is negative everywhere** because $0.75 of slippage per fill is a large part of the stop distance on gold.

### Limits

- **Two TradingView behaviours could not be checked here, and they move the numbers.**
  - The file runs again after every fill. The replica assumes TradingView then restores the script's variables to the previous candle, as its documentation describes. Under that reading "One entry per zone" and the cooldown have no effect. The other reading changes BTC 1h with the filter on from 779 trades / -42.4% to 648 / -39.2% in the TradingView view.
  - About 15% of trades are re-entries on the candle where the stop or target closed the previous trade. The replica fills them at that candle's close. If TradingView fills them earlier in the candle, the normal direction gains a lot in its view (BTC 1h, filter off: -10.4% becomes about +160%) and the inverted one does not.
- **The TradingView view depends on the symbol's tick.** 75 ticks is $0.75 on a 0.01 tick, $75 on a whole-dollar BTC symbol and $0.075 on a 0.001-tick gold symbol. Set Properties > Slippage to match your broker.
- **Short windows and old gold data**, as for the other strategies. Gold volume is tick count.
- These are the defaults only. The calibration of this file on the new data, with the direction as an input, is a separate run.
- Nothing here was compiled or run in TradingView.
