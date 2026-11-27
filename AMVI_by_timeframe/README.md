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

**It loses on this data, in both halves.** This is a different feed and an older period than the one it was calibrated on, so it is a genuine out-of-sample test, and the file did not pass it. The same inputs in the normal direction are positive overall but lose in the second half. Treat the published file's record with caution until it is checked on recent gold data.

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
