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
