# AMVI Full MTF Strategy: results by pair and timeframe

Two versions were backtested and swept: the original (`AMVI_Full_MTF_Strategy.pine`, direction from EMA / candle / Donchian) and the direction filter version (`AMVI_Full_MTF_Strategy_FGF.pine`, direction from the FlashGold Direction Filter, with Trade direction Follow the filter or Inverted).

Python replica of both files (reviewed twice; no lookahead). Costs: gold $0.30 spread per round trip, BTC 0.02% per side + $0.20; the files' own properties (0.04% per side + 1 tick) are shown as 'file costs'. R = the stop distance. Seconds timeframes (1s-45s) were off in every run (no seconds data). Gold 45m uses the 45m chart from 2025-01-01, where 30m data exists. BTC is Bitfinex 2018-2019 only.

Rule v3.1 with nested hold-outs: a setting becomes a file only if the settings chosen on one half beat random settings on the other half, in both directions, on searches that never saw the scored half, and the pick survives stressed costs.

**Result: one file. XAUUSD 15m, direction filter version, Trade direction = Inverted.** Every other timeframe has no file in either version.

## XAUUSD

| TF | Defaults: original | Defaults: filter Follow / Inverted | Original calibrated | Filter version calibrated | File |
|---|---|---|---|---|---|
| 10m | XAUV10 -3.5R (22 tr) | XAUV10 -0.2R / -2.4R | in-sample XAUV10 +51.4R; fwd -2.3 vs +0.9; rev -2.6 vs +1.3: **no file** (forward fail; reverse fail) | in-sample XAUV10 +104.3R; fwd -20.3 vs +0.7; rev +20.1 vs +4.5: **no file** (forward fail) | none |
| 15m | XAUV15 +12.1R (48 tr) | XAUV15 +6.6R / -4.1R | in-sample XAUV15 +109.9R; fwd -8.9 vs +2.8; rev +2.4 vs +6.0: **no file** (forward fail; reverse fail) | in-sample XAUV15 +226.9R; fwd +39.3 vs +7.3; rev +34.7 vs +13.0: **file** (pick passes forward, reverse and stress; sceptic's few-days refutation not confirmed (forward edge survives week resampling and a pool-chose) | [AMVI_FGF_XAUUSD_15m.pine](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/AMVI_by_timeframe/AMVI_FGF_XAUUSD_15m.pine) |
| 30m | XAUV30 +2.6R (36 tr) | XAUV30 +2.7R / +5.4R | in-sample XAUV30 +202.9R; fwd -3.3 vs +6.8; rev +34.6 vs +13.0: **no file** (forward fail) | in-sample XAUV30 +180.3R; fwd +0.4 vs +1.4; rev +47.7 vs +12.3: **no file** (forward fail) | none |
| 45m | XAUV45T +12.4R (33 tr) | XAUV45T +3.8R / +6.5R | in-sample XAUV45T +216.4R; fwd -0.4 vs +11.6; rev +72.4 vs +19.5: **no file** (forward fail) | in-sample XAUV45T +190.7R; fwd +5.0 vs +2.5; rev +37.5 vs +16.2: **no file** (forward fail) | none |
| 60m | XAU60 +0.0R (0 tr); XAUV60 +14.1R (32 tr) | XAU60 +0.0R / +0.0R; XAUV60 +3.9R / +4.7R | in-sample XAU60 +56.4R; XAUV60 +82.1R; fwd +52.9 vs +28.8; rev +16.0 vs +14.0: **no file** (sweep 'file' overturned: the stored hold-out passes rest on calendar overlap (XAU60 lies inside XAUV60's second half); the rule's reverse te) | in-sample no pick; fwd +26.9 vs +14.7; rev +9.7 vs +11.2: **no file** (no pick (no plateau among the top 40 (clone-free neighbour mean <= 0 or < 5 neighbours): no pick); reverse fail) | none |
| 120m | XAU120 +0.0R (0 tr); XAUV120 +3.8R (27 tr) | XAU120 +0.0R / +0.0R; XAUV120 -0.4R / -4.1R | in-sample XAU120 +35.8R; XAUV120 +41.1R; fwd -6.0 vs +14.7; rev +34.4 vs +17.5: **no file** (forward fail) | in-sample XAU120 +21.1R; XAUV120 +30.4R; fwd -1.1 vs +6.5; rev +2.3 vs +9.2: **no file** (forward fail; reverse fail) | none |
| 240m | XAU240 +0.0R (0 tr); XAUV240 +9.8R (23 tr) | XAU240 +0.0R / +0.0R; XAUV240 +7.4R / +5.8R | in-sample XAU240 +32.8R; XAUV240 +43.6R; fwd +13.1 vs +8.8; rev +17.2 vs +18.3: **no file** (reverse fail) | in-sample XAU240 +25.1R; XAUV240 +17.3R; fwd +3.3 vs +2.7; rev +9.2 vs +6.2: **no file** (forward fail) | none |

## BTCUSD

| TF | Defaults: original | Defaults: filter Follow / Inverted | Original calibrated | Filter version calibrated | File |
|---|---|---|---|---|---|
| 1m | BTC1 -129.1R (805 tr) | BTC1 -116.2R / -65.2R | in-sample BTC1 +4917.5R; fwd +294.9 vs +252.1; rev +521.5 vs +157.2: **no file** (forward fail) | in-sample BTC1 +3417.6R; fwd +0.0 vs +89.1; rev -454.6 vs -63.4: **no file** (forward fail; reverse fail) | none |
| 5m | BTC5 +19.9R (605 tr) | BTC5 -39.6R / -83.1R | in-sample no pick; fwd +508.6 vs +230.2; rev +778.0 vs +102.5: **no file** (no pick (no plateau among the top 40 (clone-free neighbour mean <= 0 or < 5 neighbours): no pick); forward fail) | in-sample BTC5 +1555.0R; fwd +40.4 vs +102.6; rev -287.6 vs -13.2: **no file** (forward fail; reverse fail) | none |
| 15m | BTC15 +75.6R (411 tr) | BTC15 -16.0R / -22.0R | in-sample no pick; fwd +509.0 vs +121.3; rev -107.5 vs +66.1: **no file** (no pick (no plateau among the top 40 (clone-free neighbour mean <= 0 or < 5 neighbours): no pick); reverse fail) | in-sample BTC15 +1171.5R; fwd +501.8 vs +92.6; rev -135.3 vs +17.4: **no file** (reverse fail) | none |
| 30m | BTC30 +55.4R (273 tr) | BTC30 -51.4R / +54.1R | in-sample no pick; fwd +349.9 vs +98.3; rev +170.7 vs +60.7: **no file** (no pick (no plateau among the top 40 (clone-free neighbour mean <= 0 or < 5 neighbours): no pick)) | in-sample BTC30 +474.6R; fwd +74.7 vs +37.8; rev -80.7 vs +10.8: **no file** (reverse fail) | none |
| 60m | BTC60 +18.9R (187 tr) | BTC60 -0.4R / -4.8R | in-sample no pick; fwd +246.6 vs +78.0; rev +124.1 vs +42.6: **no file** (no pick (no plateau among the top 40 (clone-free neighbour mean <= 0 or < 5 neighbours): no pick)) | in-sample BTC60 +397.1R; fwd -13.7 vs +15.9; rev -24.6 vs +3.4: **no file** (forward fail; reverse fail) | none |
| 120m | BTC120 +10.8R (122 tr) | BTC120 -16.4R / +3.7R | in-sample no pick; fwd +90.9 vs +42.1; rev +68.5 vs +29.7: **no file** (no pick (no plateau among the top 40 (clone-free neighbour mean <= 0 or < 5 neighbours): no pick)) | in-sample BTC120 +273.8R; fwd +51.2 vs +20.9; rev -7.7 vs +10.1: **no file** (reverse fail) | none |
| 240m | BTC240 +9.3R (76 tr) | BTC240 -9.4R / +3.9R | in-sample no pick; fwd +64.9 vs +21.9; rev +56.1 vs +13.1: **no file** (no pick (no plateau among the top 40 (clone-free neighbour mean <= 0 or < 5 neighbours): no pick)) | in-sample BTC240 +149.6R; fwd +9.4 vs +3.5; rev -17.6 vs +7.8: **no file** (forward fail; reverse fail) | none |

## Results by timeframe on new data, normal vs inverted

This section is separate from everything above, which was calibrated earlier on TradingView exports (VANTAGE gold, Bitfinex BTC 2018-2019) that are no longer available here. Below, the **master file** [`AMVI_Full_MTF_Strategy_FGF.pine`](../AMVI_Full_MTF_Strategy_FGF.pine) is run at its own defaults on the data used for the other strategies, and the published gold 15m file is checked on that data too.

- **Data.** BTCUSD: Bitstamp, 2024-11-17 to 2026-11-17. XAUUSD: Dukascopy, 2017-01-02 to 2018-06-19.
- **"Direction from".** "filter" is the master file (direction from the FlashGold Direction Filter). "original (EMA)" is your unfused file, which takes its direction from the 50-period EMA. In the master file, turning the filter off means no trades at all, so the unfused original is the meaningful comparison.
- **Normal / inverted** is the file's own input "Trade direction: Follow the filter / Inverted", which it had before Update 1.
- **Sizing** is the file's own: 10% of equity per trade on a 10,000 account, so the percentages are small.
- **"As TradingView shows"** uses the file's own Properties: 0.04% commission per side and 1 tick of slippage. **"1-minute fills with our costs"**: stop, target and trailing checked on 1-minute candles, gold $0.30 per ounce per round trip, BTC 0.02% per side + $0.20.
- **Seconds timeframes** (1s to 45s) cannot be reproduced here (no data below 1 minute); these results equal the file with them switched off.
- **How it was tested.** A new Python replica: two builds written independently agree on all 513,859 trades of 952 test cases, and an audit against the Pine found no defect.

### BTCUSD

| TF | Direction from | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Inverted, both halves (1-minute fills, our costs) | PF inverted (same) |
|---|---|---|---|---|---|---|
| 1m | original (EMA) | 1,332 / 1,353 | -8.18% / -11.20% | -3.19% / **-6.29%** | -2.90% / -3.49% | 0.75 |
| 1m | filter | 1,124 / 1,117 | -7.49% / -9.00% | -3.27% / **-4.87%** | -2.20% / -2.73% | 0.77 |
| 5m | original (EMA) | 959 / 1,000 | -3.82% / -7.61% | -0.10% / **-3.86%** | -2.28% / -1.61% | 0.89 |
| 5m | filter | 850 / 883 | -4.35% / -4.49% | -1.07% / **-1.08%** | +2.49% / -3.48% | 0.96 |
| 15m | original (EMA) | 666 / 709 | -6.06% / -7.07% | -3.55% / **-4.41%** | -3.51% / -0.94% | 0.87 |
| 15m | filter | 638 / 654 | -6.58% / -5.78% | -4.18% / **-3.30%** | -1.71% / -1.62% | 0.89 |
| 30m | original (EMA) | 437 / 466 | -4.02% / -3.38% | -2.34% / **-1.58%** | -0.56% / -1.02% | 0.94 |
| 30m | filter | 434 / 425 | -6.13% / +1.36% | -4.49% / **+3.36%** | +4.59% / -1.18% | 1.14 |
| 1h | original (EMA) | 313 / 342 | -4.35% / -1.51% | -3.15% / **-0.15%** | -0.17% / +0.01% | 0.99 |
| 1h | filter | 303 / 288 | -5.90% / +2.46% | -4.76% / **+3.64%** | +1.81% / +1.80% | 1.20 |
| 2h | original (EMA) | 208 / 223 | -3.04% / +1.69% | -2.23% / **+2.60%** | +3.42% / -0.79% | 1.16 |
| 2h | filter | 206 / 200 | +2.51% / -2.86% | +3.35% / **-2.08%** | -2.30% / +0.22% | 0.87 |
| 4h | original (EMA) | 136 / 149 | +1.02% / +1.16% | +1.56% / **+1.76%** | +1.66% / +0.10% | 1.13 |
| 4h | filter | 132 / 125 | +0.73% / +0.52% | +1.26% / **+1.02%** | +0.49% / +0.53% | 1.10 |

### XAUUSD

| TF | Direction from | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Inverted, both halves (1-minute fills, our costs) | PF inverted (same) |
|---|---|---|---|---|---|---|
| 1m | original (EMA) | 377 / 377 | -3.04% / -2.52% | -0.92% / **-0.39%** | -0.26% / -0.13% | 0.84 |
| 1m | filter | 323 / 327 | -2.51% / -2.30% | -0.69% / **-0.44%** | -0.32% / -0.12% | 0.79 |
| 5m | original (EMA) | 279 / 284 | -2.03% / -2.38% | -0.43% / **-0.78%** | -0.57% / -0.21% | 0.76 |
| 5m | filter | 265 / 266 | -1.86% / -2.03% | -0.35% / **-0.50%** | -0.42% / -0.08% | 0.83 |
| 15m | original (EMA) | 210 / 212 | -1.45% / -1.38% | -0.25% / **-0.21%** | -0.57% / +0.36% | 0.92 |
| 15m | filter | 214 / 216 | -1.43% / -1.54% | -0.21% / **-0.30%** | -0.43% / +0.13% | 0.89 |
| 30m | original (EMA) | 144 / 144 | -1.25% / -1.33% | -0.42% / **-0.42%** | -0.52% / +0.09% | 0.80 |
| 30m | filter | 127 / 128 | -1.08% / -1.17% | -0.35% / **-0.35%** | -0.01% / -0.34% | 0.82 |
| 1h | original (EMA) | 105 / 109 | -1.57% / -0.78% | -0.97% / **-0.16%** | -0.35% / +0.20% | 0.91 |
| 1h | filter | 91 / 90 | -0.99% / -1.04% | -0.47% / **-0.52%** | -0.27% / -0.25% | 0.69 |
| 2h | original (EMA) | 73 / 74 | -0.79% / -0.62% | -0.37% / **-0.19%** | -0.38% / +0.19% | 0.87 |
| 2h | filter | 61 / 61 | -0.39% / -0.79% | -0.04% / **-0.43%** | -0.08% / -0.36% | 0.69 |
| 4h | original (EMA) | 55 / 51 | -1.10% / +0.03% | -0.78% / **+0.33%** | +0.12% / +0.21% | 1.28 |
| 4h | filter | 49 / 51 | -0.31% / -0.74% | -0.03% / **-0.44%** | -0.32% / -0.12% | 0.67 |

### The published gold 15m file on the new data

[`AMVI_FGF_XAUUSD_15m.pine`](AMVI_FGF_XAUUSD_15m.pine) (Inverted, calibrated on VANTAGE gold) run with its own inputs on Dukascopy gold 2017-01 to 2018-06:

| | Trades | 1-minute fills, our costs | Halves | As TradingView shows | Stressed costs |
|---|---|---|---|---|---|
| As published (Inverted) | 206 | **-0.72%** | -0.62% / -0.10% | -1.89% | -1.07% |
| Same inputs, Follow the filter | 178 | +0.33% | +0.73% / -0.40% | -0.83% | +0.02% |

**It loses on this data, in both halves.** This is a different feed and an older period than the one it was calibrated on, so it is a genuine out-of-sample test, and the file did not pass it. The same inputs in the normal direction are positive overall but lose in the second half. Treat the published file's record with caution until it is checked on recent gold data. The file's header now carries a warning saying so (comment lines only; no code, input or default changed).

### What it shows

- **Five rows are profitable in both halves with realistic costs.** On BTC: 1h inverted with the filter (+3.6%, 288 trades), 2h normal with the filter (+3.4%, 206 trades), 4h inverted with the filter (+1.0%, 125 trades) and 4h inverted from the EMA (+1.8%, 149 trades, second half +0.1%). On gold: 4h inverted from the EMA (+0.3%, 51 trades). All are single default runs, small and not hold-out tested.
- **The three filter rows depend on how TradingView reads lower timeframes on history** (see Limits). Under the other reading, BTC 1h inverted becomes -0.1%, 2h normal -0.9% and 4h inverted -3.8%. The EMA rows were not run under the other reading.
- **1m to 30m lose on both pairs in both directions**, apart from BTC 30m inverted with the filter (+3.4%, but one losing half).
- **Normal vs inverted has no consistent sign** across timeframes or pairs.

### Limits

- **Lower-timeframe requests on history.** With "Non-Repainting" on, the file reads every timeframe one bar back with lookahead. For timeframes below the chart's, the replica takes the last lower-timeframe bar closed before the chart bar opens, which is how the Pine manual describes it; the other reading moves up to a third of the triggers. Both were run for the filter rows; the BTC 1h, 2h and 4h results above change sign between them.
- **TradingView keeps only limited lower-timeframe history** on long charts, so its own report can differ further on old data.
- **No lot rounding:** 10% of 10,000 is about 0.78 ounce of gold, which a symbol with a 1-unit minimum would not trade.
- Short windows and old gold data. Nothing here was compiled or run in TradingView.

## Calibration by timeframe on the new data, with the direction as an input

The inputs were searched per pair and timeframe on the new data (Bitstamp BTC 2024-2026, Dukascopy gold 2017-2018), with "Trade direction: Inverted" as one of them: 266,112 backtests.

### What was searched

24,192 settings on the 5m, 15m, 30m and 1h charts and 12,096 on 1m, 2h and 4h, the full product of:

| | Values |
|---|---|
| Trigger | "High Vol Threshold" 50, 60, 70, 80; "Min TFs Above High Vol" 1, 2, 3; timeframes: all seven, or only those at or above the chart's (5m to 1h charts only) |
| Direction source | your unfused file's direction ("Trend (EMA)", "Candle" or "Breakout (Donchian)"), or the FlashGold Direction Filter with filter timeframe 15, 60 or 240, no-trade band 0, 0.25 or 0.75 x ATR and level at the entry price or the signal close |
| Direction | normal ("Follow the filter") or inverted |
| Exits | stop 1, 1.5, 2.5 x ATR; exit: 3 x ATR target, 1.5 x ATR target, no target, or the ATR trailing stop; "Vol Collapse" exit on or off |

- **Scoring.** 1-minute fills with costs (gold $0.30 per ounce per round trip, BTC 0.02% per side + $0.20), 10% of equity per trade as in the file, on the two halves of the window separately.
- **Seconds timeframes** are off throughout (no data below 1 minute).

### The rule

The same rule as for ApexForge and HRD ([how it works and what its audit found](../ApexForge_HRD_by_timeframe/README.md#the-rule-rule-c)), plus the step added after that audit: the selection is repeated on one half only, and the setting it picks must be profitable on the other half and beat its direction-flipped twin there, both ways. A pick must also stay profitable in both halves under the other reading of lower-timeframe requests (see Limits above). A pass is a reason to review a setting, never a reason to trade it.

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
| 1m | 9,397 | 53 / 81 | -11.18% / -12.53% | +9.56% (+4.26% / +5.09%, 2686 trades) | +6.22% (+2.41% / +3.72%, 2184 trades) | -0.33% vs -5.83%, 48% positive: FAIL | -0.81% vs -6.52%, 30% positive: FAIL | -0.14% / -2.27% | no setting: none of the 40 best candidates sits on a plateau |
| 5m | 20,068 | 297 / 374 | -4.38% / -5.00% | +8.30% (+3.92% / +4.21%, 1566 trades) | +8.17% (+4.21% / +3.80%, 1242 trades) | -1.83% vs -2.23%, 20% positive: FAIL | -1.10% vs -2.78%, 35% positive: FAIL | -1.16% / -2.08% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 15m | 21,696 | 696 / 493 | -1.95% / -3.11% | +8.17% (+4.20% / +3.81%, 197 trades) | +11.95% (+7.23% / +4.39%, 136 trades) | +0.15% vs -1.19%, 65% positive: pass | -2.56% vs -1.41%, 12% positive: FAIL | +1.13% / -3.96% | no setting: reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 30m | 21,735 | 451 / 1,216 | -2.91% / -1.34% | +7.68% (+3.99% / +3.55%, 201 trades) | +9.13% (+4.64% / +4.29%, 65 trades) | -2.00% vs -0.91%, 18% positive: FAIL | -1.76% vs -0.75%, 20% positive: FAIL | -3.01% / -2.06% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 1h | 21,246 | 489 / 1,373 | -3.00% / -1.01% | +9.09% (+3.64% / +5.26%, 622 trades) | +12.99% (+5.42% / +7.18%, 1039 trades) | -1.15% vs -0.67%, 30% positive: FAIL | -0.41% vs -0.61%, 52% positive: FAIL | -1.05% / +2.27% | no setting: with the other lower-timeframe reading; forward hold-out failed; reverse hold-out failed; nested forward pick failed |
| 2h | 12,090 | 948 / 1,210 | -1.57% / -0.83% | +12.29% (+5.24% / +6.70%, 627 trades) | +14.16% (+7.54% / +6.16%, 749 trades) | -2.44% vs -0.10%, 2% positive: FAIL | -0.15% vs +0.06%, 48% positive: FAIL | -0.48% / -0.75% | no setting: with the other lower-timeframe reading; forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 4h | 12,076 | 482 / 856 | -1.56% / -0.81% | +12.97% (+7.23% / +5.35%, 300 trades) | +11.42% (+5.65% / +5.46%, 787 trades) | -2.74% vs -0.03%, 22% positive: FAIL | -3.97% vs +0.13%, 12% positive: FAIL | -3.45% / -1.87% | no setting: with the other lower-timeframe reading; forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |

#### XAUUSD

| TF | Different results | Positive in both halves: normal / inverted | Typical result: normal / inverted | Best normal (halves, trades) | Best inverted (halves, trades) | Forward hold-out | Reverse hold-out | Chosen on one half, result on the other: first to second / second to first | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1m | 10,138 | 50 / 5 | -3.41% / -3.09% | +1.38% (+0.93% / +0.44%, 256 trades) | +0.34% (+0.14% / +0.21%, 66 trades) | -0.56% vs -1.79%, 18% positive: FAIL | -0.60% vs -1.78%, 2% positive: FAIL | -1.36% / -0.64% | no setting: none of the 40 best candidates sits on a plateau |
| 5m | 21,641 | 260 / 70 | -1.29% / -1.42% | +1.66% (+0.93% / +0.72%, 118 trades) | +1.33% (+0.68% / +0.65%, 86 trades) | -0.71% vs -0.76%, 5% positive: FAIL | -0.75% vs -0.79%, 5% positive: FAIL | -0.46% / -1.24% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 15m | 22,333 | 345 / 106 | -0.64% / -1.09% | +2.18% (+1.03% / +1.14%, 101 trades) | +1.00% (+0.51% / +0.49%, 76 trades) | -0.75% vs -0.49%, 10% positive: FAIL | -0.36% vs -0.46%, 42% positive: FAIL | -0.53% / +0.72% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed |
| 30m | 22,188 | 223 / 198 | -0.67% / -0.99% | +2.88% (+1.70% / +1.16%, 108 trades) | +2.25% (+1.02% / +1.22%, 88 trades) | -0.36% vs -0.43%, 25% positive: FAIL | +0.04% vs -0.40%, 48% positive: FAIL | -0.18% / +0.42% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed |
| 1h | 19,156 | 313 / 255 | -0.66% / -0.88% | +2.99% (+1.41% / +1.56%, 163 trades) | +1.98% (+1.12% / +0.85%, 87 trades) | -0.62% vs -0.32%, 12% positive: FAIL | +0.02% vs -0.31%, 60% positive: pass | -0.76% / +0.55% | no setting: forward hold-out failed; nested forward pick failed |
| 2h | 11,940 | 165 / 292 | -0.65% / -0.48% | +2.00% (+1.13% / +0.86%, 132 trades) | +3.21% (+2.00% / +1.19%, 154 trades) | -0.63% vs -0.24%, 12% positive: FAIL | -0.90% vs -0.19%, 8% positive: FAIL | -0.36% / -0.93% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 4h | 11,882 | 276 / 242 | -0.54% / -0.53% | +2.60% (+1.22% / +1.36%, 99 trades) | +1.88% (+1.04% / +0.84%, 251 trades) | -0.83% vs -0.12%, 22% positive: FAIL | -1.13% vs -0.17%, 5% positive: FAIL | -0.90% / -1.24% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |

### What it shows

- **No setting passes on any timeframe of either pair, in either direction.**
- **The typical setting loses on every timeframe, in both directions.** Results are small because the file puts 10% of equity in each trade: the best in-sample settings make +7% to +14% over two years on BTC and +1% to +3% over 18 months on gold.
- **Settings chosen on one half do not carry over:** of the 28 single settings chosen on one half, 5 were profitable on the other.
- **Closest: BTC 15m and gold 1h, each passing one of the two hold-outs.** On BTC 15m the 40 best of the first half are 65% profitable on the second, but only 13% the other way round. On gold 1h it is the reverse (60% from the second half to the first, 13% from the first to the second).
- **Direction.** On BTC from 30m to 4h, inverted has more profitable settings (BTC 1h: 1,373 against 489). On gold, normal has more from 1m to 1h, inverted on 2h. Neither carries from one half to the other.
- **Gold 15m, where the published file sits:** 345 normal against 106 inverted profitable settings, and none passes. That agrees with the check of the published file above, which loses on this data.

### Data

Every setting of every timeframe, with its inputs, trades, net result, profit factor, drawdown and both halves: [`calibration_amvi_newdata.csv.gz`](calibration_amvi_newdata.csv.gz) (266,112 rows; `floor_ok` false marks trailing settings under the 1-minute noise floor, which were not counted).

### Limits

- The same limits as the by-timeframe section above: the reading of lower-timeframe requests, TradingView's limited intrabar history, no lot rounding, the short windows and the old gold data.
- Nothing here was compiled or run in TradingView.
