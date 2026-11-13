# XPW v0.9.2 + FlashGold EA: calibration run 2 (XAUUSD, BTCUSD), 2026-11-13

Run 2 searches every way the EA can be played as its own problem: 7 entry styles x 3 trade directions, per symbol and timeframe, over a wider input grid than run 1 and with stricter acceptance. Results are replica backtests on Binance 1-minute data (PAX Gold as the XAUUSD proxy), **not** MT5 Strategy Tester or broker results. Live gates stay disabled in every preset.

## How run 1 did on data it never saw

Before recalibrating, the 33 run-1 presets were run on 2026-11-01 to 2026-11-12, published after run 1. Positions still open at the end are valued at the last price.

| Symbol | Presets | Made money | Lost money | Did not trade | Combined net (USD per 0.01 lot) |
|---|---:|---:|---:|---:|---:|
| XAUUSD | 18 | 9 | 9 | 0 | 720 |
| BTCUSD | 15 | 5 | 9 | 1 | -56 |

Twelve days is a short test. It is the only fully independent evidence available, and it is mixed: fewer than half the presets made money. Figures count only what was earned after 2026-11-01. Per-preset figures are in `data/run1_forward_test.csv`.

## Search summary

| Symbol | TF | Clock | Window | Combos tested | Pass in and out of sample | Leaders kept and re-scored | Pass cost, block and winner rules | Stability-checked | Stable | Saved | Reference preset net |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BTCUSD | M1 | Live | 2023-01 to 2026-10 | 1919 | 0 | 0 | 0 | 0 | 0 | 0 | -3536 (15481 trades) |
| BTCUSD | M5 | Live | 2023-01 to 2026-10 | 6653 | 55 | 54 | 29 | 29 | 23 | 3 | -1086 (7058 trades) |
| BTCUSD | M15 | Tester only | 2023-01 to 2026-10 | 23751 | 1021 | 880 | 727 | 118 | 112 | 3 | -756 (4130 trades) |
| BTCUSD | M30 | Tester only | 2023-01 to 2026-10 | 23666 | 1435 | 1004 | 721 | 112 | 104 | 3 | -690 (2855 trades) |
| BTCUSD | H1 | Tester only | 2023-01 to 2026-10 | 23578 | 1744 | 1096 | 872 | 118 | 113 | 3 | -701 (1984 trades) |
| BTCUSD | H4 | Tester only | 2023-01 to 2026-10 | 23482 | 2320 | 1178 | 889 | 120 | 120 | 3 | -1 (499 trades) |
| XAUUSD | M1 | Live | 2025-05-17 to 2026-10 | 3526 | 458 | 199 | 137 | 56 | 56 | 3 | 952 (2844 trades) |
| XAUUSD | M5 | Live | 2025-05-17 to 2026-10 | 7296 | 515 | 436 | 387 | 115 | 113 | 3 | -377 (1285 trades) |
| XAUUSD | M15 | Tester only | 2025-05-17 to 2026-10 | 23602 | 2314 | 1102 | 1059 | 130 | 127 | 3 | 248 (779 trades) |
| XAUUSD | M30 | Tester only | 2023-01 to 2026-10 | 23272 | 2025 | 1086 | 1013 | 106 | 106 | 3 | 9 (1309 trades) |
| XAUUSD | H1 | Tester only | 2023-01 to 2026-10 | 23317 | 3555 | 1163 | 1066 | 128 | 124 | 3 | -1153 (920 trades) |
| XAUUSD | H4 | Tester only | 2023-01 to 2026-10 | 23438 | 5230 | 1184 | 1013 | 109 | 109 | 3 | 325 (268 trades) |

Total combinations tested: **207,500**. Of the combinations that pass in and out of sample, the best 60 of each way of playing are kept and re-scored against the cost, block and winner rules.

## Which ways of playing survive

Count of timeframes (out of 6) where at least one stable preset exists for that entry style and direction.

**XAUUSD**

| Entry style | Both | Long only | Short only |
|---|---:|---:|---:|
| BOT/TOP square | 5 | 5 | 6 |
| Turn, predict stop | 6 | 6 | 5 |
| Turn, at cross | 6 | 6 | 6 |
| Turn, after hold | 5 | 5 | 6 |
| BOT/TOP tick | 5 | 5 | 5 |
| CONT, at close | 5 | 6 | 5 |
| CONT, stop entry | 6 | 6 | 6 |

**BTCUSD**

| Entry style | Both | Long only | Short only |
|---|---:|---:|---:|
| BOT/TOP square | 4 | 4 | 4 |
| Turn, predict stop | 4 | 4 | 5 |
| Turn, at cross | 4 | 5 | 4 |
| Turn, after hold | 4 | 4 | 5 |
| BOT/TOP tick | 5 | 3 | 5 |
| CONT, at close | 4 | 5 | 4 |
| CONT, stop entry | 5 | 4 | 4 |

Per-timeframe detail is in `data/strata_summary.csv`.

## Saved presets

USD per 0.01 lot (gold: 1 oz; BTC: 0.01 BTC) after modeled spread and commission. Fwd = profit earned on the unseen days 2026-11-01 to 2026-11-12, never used to pick or accept a preset. A position carried in from October counts only its change after 2026-11-01, and a position still open at the end is valued at the last price.

| Preset | Clock | Way of playing | IS trades | IS net | IS PF | OOS trades | OOS net | OOS PF | OOS maxDD | 2x-cost net | Blocks | Stability | Fwd trades | Fwd net | Note |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `BTCUSD_M5_run2_rank1.set` | Live | CONT, stop entry, Both | 382 | 670 | 1.26 | 62 | 134 | 1.31 | 166 | 567 | 3/4 | 67% | 0 | 0 |  |
| `BTCUSD_M5_run2_rank2.set` | Live | CONT, stop entry, Long only | 476 | 422 | 1.37 | 305 | 141 | 1.19 | 120 | 313 | 4/4 | 67% | 7 | -19 | Cost-fragile, Long only |
| `BTCUSD_M5_run2_rank3.set` | Live | BOT/TOP tick, Both | 180 | 174 | 1.54 | 90 | 103 | 1.54 | 58 | 141 | 3/4 | 75% | 4 | -10 |  |
| `BTCUSD_M15_run2_rank1.set` | Tester only | CONT, stop entry, Both | 202 | 1180 | 1.76 | 145 | 684 | 1.47 | 287 | 1726 | 4/4 | 71% | 7 | 44 |  |
| `BTCUSD_M15_run2_rank2.set` | Tester only | Turn, predict stop, Both | 165 | 980 | 1.41 | 97 | 526 | 1.37 | 319 | 1309 | 4/4 | 88% | 3 | -71 |  |
| `BTCUSD_M15_run2_rank3.set` | Tester only | Turn, predict stop, Long only | 156 | 694 | 2.06 | 99 | 376 | 1.89 | 116 | 1050 | 4/4 | 88% | 1 | -5 | Long only |
| `BTCUSD_M30_run2_rank1.set` | Tester only | BOT/TOP square, Both | 242 | 1120 | 1.61 | 141 | 617 | 1.46 | 229 | 1651 | 3/4 | 79% | 2 | -6 |  |
| `BTCUSD_M30_run2_rank2.set` | Tester only | Turn, at cross, Both | 85 | 597 | 2.46 | 39 | 333 | 2.22 | 91 | 901 | 4/4 | 83% | 0 | 0 |  |
| `BTCUSD_M30_run2_rank3.set` | Tester only | CONT, at close, Both | 83 | 561 | 2.03 | 57 | 337 | 1.80 | 122 | 883 | 4/4 | 83% | 1 | 48 |  |
| `BTCUSD_H1_run2_rank1.set` | Tester only | BOT/TOP square, Both | 53 | 1352 | 4.36 | 31 | 443 | 1.95 | 306 | 1789 | 4/4 | 67% | 1 | 62 |  |
| `BTCUSD_H1_run2_rank2.set` | Tester only | Turn, at cross, Both | 274 | 1036 | 1.65 | 178 | 563 | 1.42 | 224 | 1386 | 4/4 | 83% | 2 | -27 |  |
| `BTCUSD_H1_run2_rank3.set` | Tester only | Turn, after hold, Both | 703 | 911 | 1.28 | 386 | 548 | 1.23 | 366 | 1236 | 4/4 | 88% | 7 | -11 |  |
| `BTCUSD_H4_run2_rank1.set` | Tester only | BOT/TOP square, Both | 89 | 1106 | 2.31 | 48 | 612 | 2.29 | 250 | 1717 | 4/4 | 62% | 1 | 62 |  |
| `BTCUSD_H4_run2_rank2.set` | Tester only | Turn, predict stop, Both | 85 | 1193 | 2.16 | 43 | 606 | 1.83 | 216 | 1776 | 4/4 | 75% | 2 | -9 |  |
| `BTCUSD_H4_run2_rank3.set` | Tester only | CONT, at close, Both | 33 | 916 | 3.50 | 22 | 458 | 2.12 | 196 | 1365 | 4/4 | 92% | 1 | 62 |  |
| `XAUUSD_M1_run2_rank1.set` | Live | Turn, predict stop, Both | 45610 | 25899 | 1.57 | 34360 | 18320 | 1.60 | 159 | 24314 | 3/3 | 100% | 2041 | 954 | Cost-fragile |
| `XAUUSD_M1_run2_rank2.set` | Live | CONT, stop entry, Both | 31653 | 16721 | 1.47 | 21669 | 9526 | 1.39 | 169 | 11545 | 3/3 | 100% | 1221 | 622 | Cost-fragile |
| `XAUUSD_M1_run2_rank3.set` | Live | Turn, predict stop, Long only | 24390 | 12563 | 1.58 | 17932 | 7450 | 1.62 | 98 | 10912 | 3/3 | 100% | 1048 | 282 | Cost-fragile, Long only |
| `XAUUSD_M5_run2_rank1.set` | Live | CONT, stop entry, Both | 2511 | 2580 | 1.42 | 1801 | 1496 | 1.33 | 277 | 2935 | 3/3 | 100% | 108 | 366 |  |
| `XAUUSD_M5_run2_rank2.set` | Live | Turn, predict stop, Short only | 6064 | 2827 | 1.23 | 4579 | 1556 | 1.19 | 189 | 1258 | 2/3 | 92% | 264 | -109 | Cost-fragile, Short only |
| `XAUUSD_M5_run2_rank3.set` | Live | Turn, predict stop, Long only | 5689 | 2898 | 1.36 | 4123 | 1304 | 1.21 | 139 | 1622 | 3/3 | 83% | 265 | 3 | Cost-fragile, Long only |
| `XAUUSD_M15_run2_rank1.set` | Tester only | Turn, predict stop, Both | 9053 | 4439 | 1.25 | 6311 | 3195 | 1.26 | 175 | 3381 | 3/3 | 96% | 399 | 293 | Cost-fragile |
| `XAUUSD_M15_run2_rank2.set` | Tester only | CONT, stop entry, Both | 143 | 2397 | 1.87 | 90 | 1584 | 2.02 | 284 | 3805 | 3/3 | 92% | 5 | 89 |  |
| `XAUUSD_M15_run2_rank3.set` | Tester only | Turn, predict stop, Long only | 5221 | 3878 | 1.46 | 4218 | 1966 | 1.27 | 179 | 3406 | 3/3 | 92% | 267 | 54 | Long only |
| `XAUUSD_M30_run2_rank1.set` | Tester only | Turn, at cross, Long only | 198 | 1940 | 2.17 | 96 | 1358 | 2.15 | 482 | 3231 | 4/4 | 79% | 0 | 0 | Long only |
| `XAUUSD_M30_run2_rank2.set` | Tester only | BOT/TOP tick, Both | 60 | 1483 | 2.43 | 47 | 2570 | 2.48 | 565 | 4047 | 4/4 | 88% | 0 | 0 |  |
| `XAUUSD_M30_run2_rank3.set` | Tester only | CONT, at close, Both | 223 | 2443 | 2.21 | 184 | 2121 | 1.44 | 862 | 4596 | 4/4 | 83% | 9 | -250 |  |
| `XAUUSD_H1_run2_rank1.set` | Tester only | Turn, predict stop, Both | 65 | 2217 | 2.82 | 57 | 3723 | 2.86 | 724 | 5921 | 4/4 | 96% | 2 | -280 |  |
| `XAUUSD_H1_run2_rank2.set` | Tester only | Turn, at cross, Long only | 92 | 2250 | 2.64 | 58 | 1925 | 1.70 | 756 | 4136 | 4/4 | 96% | 3 | -183 | Long only |
| `XAUUSD_H1_run2_rank3.set` | Tester only | Turn, after hold, Both | 357 | 2047 | 1.81 | 211 | 3391 | 1.88 | 554 | 5184 | 4/4 | 96% | 9 | -98 |  |
| `XAUUSD_H4_run2_rank1.set` | Tester only | CONT, at close, Long only | 39 | 2220 | 11.68 | 20 | 1600 | 3.19 | 1162 | 3802 | 4/4 | 88% | 1 | 116 | Long only |
| `XAUUSD_H4_run2_rank2.set` | Tester only | Turn, after hold, Both | 37 | 1971 | 9.34 | 21 | 1828 | 3.17 | 693 | 3788 | 4/4 | 96% | 0 | 0 |  |
| `XAUUSD_H4_run2_rank3.set` | Tester only | Turn, predict stop, Both | 63 | 1872 | 3.77 | 25 | 1654 | 2.92 | 1162 | 3429 | 4/4 | 71% | 2 | -35 |  |

### What each preset does

- **BTCUSD_M5_run2_rank1.set**: Both; CONT / stop past candle; opp ignore; SL 6.0xATR / TP 8.0R, no trail; loss-rev x3; RSI 9 fast 5 slow 9, turnMax 12 hold 2, allOn=True; FGF on: filter H1, parent H1, zones H1/120min/H4, band 1.0xATR, burst 2.0xATR, minAligned 2, against=False, window=next signal
- **BTCUSD_M5_run2_rank2.set**: Long only; CONT / stop past candle; opp reverse; SL 25000 / TP 500000 pts, no trail; no loss-rev; RSI 28 fast 2 slow 9, turnMax 12 hold 2, allOn=True; FGF on: filter M15, parent H1, zones H1/120min/H4, band 0.25xATR, burst 0.75xATR, minAligned 2, against=True, window=next signal
- **BTCUSD_M5_run2_rank3.set**: Both; BOT/TOP tick; opp reverse; SL 2.0xATR / TP 0.0R, no trail, time stop 192 bars; no loss-rev; RSI 14 fast 2 slow 7, turnMax 12 hold 2, allOn=True; FGF on: filter 120min, parent 1440min, zones H1/120min/H4, band 0.75xATR, burst 1.5xATR, minAligned 2, against=False, window=candles
- **BTCUSD_M15_run2_rank1.set**: Both; CONT / stop past candle; opp reverse; SL 250000 / TP 2500000 pts, no trail; loss-rev unlimited; RSI 7 fast 5 slow 9, turnMax 12 hold 2, allOn=True; FGF off
- **BTCUSD_M15_run2_rank2.set**: Both; Turn / predict stop; opp ignore; SL 250000 / TP 500000 pts, no trail; no loss-rev; RSI 21 fast 5 slow 7, turnMax 12 hold 2, allOn=True; FGF on: filter H1, parent H1, zones H1/120min/H4, band 0.25xATR, burst 0.5xATR, minAligned 2, against=True, window=next signal
- **BTCUSD_M15_run2_rank3.set**: Long only; Turn / predict stop; opp reverse; SL 50000 / TP 500000 pts, no trail; no loss-rev; RSI 5 fast 5 slow 7, turnMax 24 hold 3, allOn=False; FGF on: filter M30, parent 120min, zones M30/H1/H4, band 1.5xATR, burst 1.0xATR, minAligned 2, against=True, window=next signal
- **BTCUSD_M30_run2_rank1.set**: Both; BOT/TOP square; opp ignore; SL 8.0xATR / TP 8.0R, trail act 6.0xATR dist 3.0xATR; no loss-rev; RSI 5 fast 5 slow 7, turnMax 12 hold 2, allOn=False; FGF on: filter H4, parent 480min, zones M30/H1/H4, band 0.25xATR, burst 1.0xATR, minAligned 3, against=True, window=next signal
- **BTCUSD_M30_run2_rank2.set**: Both; Turn / at cross; opp reverse; SL 8.0xATR / TP 2.0R, no trail, time stop 192 bars; no loss-rev; RSI 7 fast 3 slow 13, turnMax 12 hold 1, allOn=True; FGF on: filter 120min, parent 1440min, zones M30/H1/H4, band 0.0xATR, burst 1.0xATR, minAligned 2, against=True, window=next signal
- **BTCUSD_M30_run2_rank3.set**: Both; CONT / at close; opp reverse; SL 100000 / TP 1000000 pts, no trail; no loss-rev; RSI 9 fast 2 slow 7, turnMax 12 hold 2, allOn=True; FGF off
- **BTCUSD_H1_run2_rank1.set**: Both; BOT/TOP square; opp close only; SL 350000 / TP 2500000 pts, no trail; loss-rev x3; RSI 21 fast 5 slow 21, turnMax 12 hold 2, allOn=True; FGF off
- **BTCUSD_H1_run2_rank2.set**: Both; Turn / at cross; opp reverse; SL 250000 / TP 1000000 pts, no trail; loss-rev x1; RSI 9 fast 3 slow 21, turnMax 24 hold 1, allOn=True; FGF off
- **BTCUSD_H1_run2_rank3.set**: Both; Turn / after hold; opp reverse; SL 3.0xATR / TP 0.0R, no trail; loss-rev unlimited; RSI 7 fast 3 slow 13, turnMax 12 hold 2, allOn=False; FGF off
- **BTCUSD_H4_run2_rank1.set**: Both; BOT/TOP square; opp reverse; SL 1.5xATR / TP 0.0R, no trail; loss-rev unlimited; RSI 9 fast 5 slow 21, turnMax 12 hold 2, allOn=True; FGF off
- **BTCUSD_H4_run2_rank2.set**: Both; Turn / predict stop; opp reverse; SL 6.0xATR / TP 8.0R, trail act 6.0xATR dist 2.0xATR, time stop 192 bars; loss-rev unlimited; RSI 7 fast 5 slow 9, turnMax 12 hold 2, allOn=True; FGF on: filter 480min, parent 1440min, zones H1/120min/H4, band 0.25xATR, burst 1.0xATR, minAligned 1, against=True, window=next signal
- **BTCUSD_H4_run2_rank3.set**: Both; CONT / at close; opp ignore; SL 4.0xATR / TP 8.0R, no trail, time stop 192 bars; loss-rev x1; RSI 14 fast 2 slow 13, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M1_run2_rank1.set**: Both; Turn / predict stop; opp reverse; SL 7000 / TP 50000 pts, no trail, time stop 12 bars; no loss-rev; RSI 21 fast 1 slow 5, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M1_run2_rank2.set**: Both; CONT / stop past candle; opp reverse; SL 200 / TP 3000 pts, trail act 4000 dist 500, time stop 192 bars; loss-rev unlimited; RSI 14 fast 2 slow 9, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M1_run2_rank3.set**: Long only; Turn / predict stop; opp close only; SL 0.75xATR / TP 8.0R, trail act 6.0xATR dist 0.2xATR, time stop 48 bars; no loss-rev; RSI 7 fast 1 slow 3, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M5_run2_rank1.set**: Both; CONT / stop past candle; opp reverse; SL 300 / TP 20000 pts, no trail; loss-rev x1; RSI 9 fast 2 slow 7, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M5_run2_rank2.set**: Short only; Turn / predict stop; opp reverse; SL 1000 / TP 0 pts, trail act 500 dist 100, time stop 6 bars; no loss-rev; RSI 14 fast 1 slow 3, turnMax 12 hold 4, allOn=True; FGF off
- **XAUUSD_M5_run2_rank3.set**: Long only; Turn / predict stop; opp close only; SL 200 / TP 10000 pts, trail act 4000 dist 100; no loss-rev; RSI 5 fast 3 slow 7, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M15_run2_rank1.set**: Both; Turn / predict stop; opp reverse; SL 0.75xATR / TP 0.0R, trail act 6.0xATR dist 0.2xATR, time stop 6 bars; loss-rev x2; RSI 5 fast 1 slow 5, turnMax 12 hold 4, allOn=True; FGF off
- **XAUUSD_M15_run2_rank2.set**: Both; CONT / stop past candle; opp ignore; SL 6.0xATR / TP 3.0R, trail act 6.0xATR dist 2.0xATR; loss-rev x1; RSI 21 fast 1 slow 9, turnMax 12 hold 2, allOn=True; FGF on: filter 120min, parent H1, zones H1/120min/H4, band 0.5xATR, burst 0.5xATR, minAligned 2, against=True, window=candles
- **XAUUSD_M15_run2_rank3.set**: Long only; Turn / predict stop; opp reverse; SL 200 / TP 10000 pts, trail act 1000 dist 100, time stop 96 bars; no loss-rev; RSI 5 fast 1 slow 3, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M30_run2_rank1.set**: Long only; Turn / at cross; opp ignore; SL 8.0xATR / TP 1.5R, trail act 6.0xATR dist 3.0xATR; no loss-rev; RSI 7 fast 2 slow 5, turnMax 12 hold 2, allOn=False; FGF on: filter 480min, parent 480min, zones H1/H4/1440min, band 0.1xATR, burst 1.5xATR, minAligned 2, against=False, window=next signal
- **XAUUSD_M30_run2_rank2.set**: Both; BOT/TOP tick; opp ignore; SL 8.0xATR / TP 1.5R, no trail; loss-rev x5; RSI 14 fast 2 slow 7, turnMax 12 hold 2, allOn=True; FGF on: filter H4, parent H4, zones H1/120min/H4, band 1.0xATR, burst 0.5xATR, minAligned 3, against=True, window=next signal
- **XAUUSD_M30_run2_rank3.set**: Both; CONT / at close; opp ignore; SL 8.0xATR / TP 8.0R, trail act 4.0xATR dist 0.5xATR; loss-rev x1; RSI 14 fast 1 slow 21, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_H1_run2_rank1.set**: Both; Turn / predict stop; opp reverse; SL 8.0xATR / TP 1.5R, no trail; loss-rev unlimited; RSI 5 fast 3 slow 7, turnMax 48 hold 2, allOn=True; FGF on: filter H1, parent 480min, zones H1/120min/H4, band 0.25xATR, burst 2.0xATR, minAligned 2, against=True, window=next signal
- **XAUUSD_H1_run2_rank2.set**: Long only; Turn / at cross; opp ignore; SL 8.0xATR / TP 1.0R, trail act 6.0xATR dist 0.2xATR; no loss-rev; RSI 7 fast 1 slow 21, turnMax 12 hold 2, allOn=True; FGF on: filter H1, parent H1, zones H1/120min/H4, band 0.25xATR, burst 0.5xATR, minAligned 2, against=True, window=next signal
- **XAUUSD_H1_run2_rank3.set**: Both; Turn / after hold; opp reverse; SL 6.0xATR / TP 8.0R, trail act 4.0xATR dist 0.2xATR; loss-rev x1; RSI 7 fast 1 slow 21, turnMax 48 hold 2, allOn=True; FGF off
- **XAUUSD_H4_run2_rank1.set**: Long only; CONT / at close; opp ignore; SL 8.0xATR / TP 5.0R, trail act 4.0xATR dist 0.2xATR; no loss-rev; RSI 9 fast 3 slow 9, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_H4_run2_rank2.set**: Both; Turn / after hold; opp close only; SL 8.0xATR / TP 1.0R, no trail, time stop 192 bars; loss-rev x5; RSI 5 fast 1 slow 5, turnMax 6 hold 2, allOn=False; FGF on: filter H1, parent H1, zones H1/120min/H4, band 0.25xATR, burst 0.5xATR, minAligned 2, against=True, window=next signal
- **XAUUSD_H4_run2_rank3.set**: Both; Turn / predict stop; opp reverse; SL 8.0xATR / TP 1.5R, trail act 6.0xATR dist 3.0xATR; no loss-rev; RSI 5 fast 1 slow 3, turnMax 12 hold 1, allOn=True; FGF on: filter 480min, parent H1, zones H1/120min/H4, band 0.5xATR, burst 0.5xATR, minAligned 2, against=True, window=next signal

### Forward window, run-2 presets together

| Symbol | Presets | Made money | Lost money | Did not trade | Combined net |
|---|---:|---:|---:|---:|---:|
| XAUUSD | 18 | 9 | 6 | 3 | 1824 |
| BTCUSD | 15 | 5 | 8 | 2 | 121 |

## What changed from run 1

- **Every way of playing gets its own search.** 7 entry styles (BOT/TOP square; Turn with predict stop, at cross, after hold; BOT/TOP tick; CONT at close, CONT stop entry) x 3 directions (both, long only, short only) = 21 searches per symbol and timeframe, half of each starting with the FlashGold filter on.
- **Wider grid.** New or widened inputs: TradeDir, InvertFill, AtrLen, ExAtrLen, MaxChase, ContStopBars, BotMinW/TopMinW, BotNeedLow/TopNeedHigh, FlashGold hold bars, drift bars, TDI lengths, D1 filter/parent/zone timeframes, and more values for stops, targets, trailing, time stop, RSI/MA lengths, squares, wicks and CONT thresholds.
- **Stricter acceptance.** On top of run 1's rules (in-sample and out-of-sample net > 0 with PF >= 1.15, minimum trades and winners, profitable at 2x costs): at most one losing calendar block (yearly blocks, or half-year blocks for the short gold window), and neighbour stability of at least 50 %.
- **Neighbour stability.** For each leading candidate, up to 24 variants are built by changing a single input to another value from its search grid (any value, not only the adjacent one). Only variants whose trades inside the scored windows differ from the candidate and from each other count, and at least 12 such variants are required. The share that stays profitable overall and out of sample is the stability score. The overall top 30 and the top 5 of every way of playing are checked, so no way of playing is skipped.
- **Drawdown is mark-to-market.** Maximum drawdown includes the paper loss of open positions at each bar close, not only closed trades. Run 1 used closed trades only, so run-2 drawdowns read higher for the same behaviour.
- **Warm-up.** Indicators and the FlashGold filter get 120 days of history before the in-sample window; no trade may open in the warm-up. Run 1 started cold.
- **Window accounting.** A position that is open across a window edge is split at the last bar close before the edge, so each window's profit is what was earned inside it and the windows add up exactly. In particular a loss already on the books at the end of the out-of-sample window counts against it.
- **Gold short window.** PAX Gold is quoted in cents only from 2025-05-16, so gold M1/M5/M15 now start on 2025-05-17 (run 1 started on 2025-05-01 and included two weeks of whole-dollar prices).
- **Unseen days.** 2026-11-01 to 2026-11-12 is reported for every preset and used for nothing else.
- **Diverse picks.** Up to 3 presets per symbol and timeframe, preferring different entry style / direction combinations.

## Checks on the tooling

- **No look-ahead.** 168 configurations across all styles and directions produce identical trades with and without later data (`tools/causality_test.py`).
- **Search-space bookkeeping is sound.** Inputs that cannot matter for a given way of playing are reset to defaults so duplicates are not re-tested; 1,890 cases confirm that resetting them never changes a single trade (`tools/canon_test.py`).
- **Windows add up.** In-sample + out-of-sample + unseen-days profit equals the total, and in-sample + out-of-sample profit equals the equity at the out-of-sample end, in every test run; no trade can open in the warm-up (`tools/warmup_test.py`).
- **Independent review, twice.** The run-2 search code was reviewed by three reviewers with adversarial verification of each finding, and the fixes were then checked again the same way. All confirmed findings were fixed before the results below were produced, including an inflated stability score, stability checks limited to the overall leaders, closed-trade-only drawdown, positions open at a window end not being counted, and BTC point inputs re-entering the search at gold scale. BTC M1, M5 and part of M15 were searched before the window-accounting fix; all of their saved candidates were re-scored with the corrected accounting.

## Caveats

- **Search size cuts both ways.** Testing this many combinations finds more candidates and also more lucky ones. The block, stability and unseen-days columns are there to tell them apart; no rule removes the risk.
- **One-direction presets ride the trend.** Gold rose strongly over 2023-2026, so a long-only gold preset profits partly from that rise, and would lose it in a falling market. They are marked in the Note column.
- **Proxy data, replica engine, clocks, sizing.** As in run 1: PAXG is not the broker's XAUUSD feed, the Python port is not the MT5 tester, only M1/M5 presets run on a live chart, and `QtyFixed` assumes 100 oz (gold) and 1 BTC contracts. See `../CALIBRATION_REPORT.md`.
- **BTC points.** Stops and targets in points assume a 0.01 tick on BTCUSD.c; scale `SlPts`, `TpPts` and the other point inputs if your broker's tick differs.

## Reproduce

```bash
python3 tools/xpw_search2.py          # writes results2/strata/*.json, then results2/*.json (resumable)
python3 tools/xpw_search2.py merge    # re-run acceptance and stability from the saved strata
python3 tools/xpw_report2.py out2     # presets, CSV and this report
python3 tools/causality_test.py       # look-ahead check
python3 tools/canon_test.py 30        # inert-input check
python3 tools/warmup_test.py          # warm-up and drawdown check
python3 tools/fwd_run1.py             # run-1 presets on the unseen days
```
