# XPW v0.9.2 + FlashGold EA: input calibration (XAUUSD, BTCUSD), 2026-11-06

Presets in `presets/` are the input combinations that stayed profitable in-sample, out-of-sample and under doubled trading costs in a Python replica of the EA's decision logic. This is **not** an MT5 Strategy Tester result and **not** live-broker evidence; all live gates in the presets remain disabled (`EnableTrading=false`, `FenceAllowExecution=false`).

## Search summary

| Symbol | TF | Bars | Data window | Combos evaluated | Pass IS+OOS | Pass 2x-cost stress | Saved presets | Reference-preset net (USD/0.01 lot) |
|---|---|---:|---|---:|---:|---:|---:|---:|
| BTCUSD | H1 | 33599 | 2023-01..2026-10 | 2001 | 67 | 56 | 3 | -699.26 (1982 trades, PF 0.768) |
| BTCUSD | H4 | 8401 | 2023-01..2026-10 | 1846 | 223 | 80 | 3 | -1.37 (499 trades, PF 0.998) |
| BTCUSD | M1 | 2015920 | 2023-01..2026-10 | 680 | 0 | 0 | 0 | -3534.65 (15476 trades, PF 0.839) |
| BTCUSD | M15 | 134395 | 2023-01..2026-10 | 2009 | 51 | 45 | 3 | -757.8 (4130 trades, PF 0.871) |
| BTCUSD | M30 | 67198 | 2023-01..2026-10 | 2072 | 155 | 80 | 3 | -689.46 (2854 trades, PF 0.836) |
| BTCUSD | M5 | 403184 | 2023-01..2026-10 | 1331 | 52 | 48 | 3 | -1086.36 (7057 trades, PF 0.891) |
| XAUUSD | H1 | 22999 | 2023-01..2026-10 | 1793 | 75 | 75 | 3 | -1152.86 (920 trades, PF 0.859) |
| XAUUSD | H4 | 6000 | 2023-01..2026-10 | 2093 | 539 | 80 | 3 | 324.67 (268 trades, PF 1.158) |
| XAUUSD | M1 | 540900 | 2025-05..2026-10 (cent-precision gold proxy only) | 590 | 113 | 13 | 3 | 1047.82 (2929 trades, PF 1.052) |
| XAUUSD | M15 | 36060 | 2025-05..2026-10 (cent-precision gold proxy only) | 2047 | 104 | 80 | 3 | 179.14 (802 trades, PF 1.027) |
| XAUUSD | M30 | 45998 | 2023-01..2026-10 | 1745 | 55 | 53 | 3 | -0.84 (1304 trades, PF 1.0) |
| XAUUSD | M5 | 108180 | 2025-05..2026-10 (cent-precision gold proxy only) | 1390 | 133 | 80 | 3 | -230.97 (1320 trades, PF 0.979) |

## Accepted presets

Profit figures are USD per 0.01 lot (gold: 1 oz; BTC: 0.01 BTC) after modeled spread and commission. IS = in-sample selection window, OOS = out-of-sample validation window, 2x = full period with spread and commission doubled.

| Preset | Clock | IS trades | IS net | IS PF | IS win | IS maxDD | OOS trades | OOS net | OOS PF | OOS win | OOS maxDD | 2x-cost net | 2x PF | Avg/trade | Note |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `BTCUSD_H1_rank1.set` | tester-only | 265 | 715 | 1.38 | 0.35 | 171 | 200 | 479 | 1.36 | 0.40 | 145 | 913 | 1.27 | 2.57 |  |
| `BTCUSD_H1_rank2.set` | tester-only | 284 | 700 | 1.37 | 0.50 | 231 | 153 | 396 | 1.32 | 0.50 | 141 | 1042 | 1.33 | 2.51 |  |
| `BTCUSD_H1_rank3.set` | tester-only | 470 | 729 | 1.30 | 0.32 | 185 | 271 | 371 | 1.20 | 0.37 | 237 | 669 | 1.15 | 1.49 |  |
| `BTCUSD_H4_rank1.set` | tester-only | 35 | 843 | 2.69 | 0.54 | 121 | 20 | 641 | 2.38 | 0.50 | 256 | 1472 | 2.52 | 26.98 |  |
| `BTCUSD_H4_rank2.set` | tester-only | 39 | 925 | 2.65 | 0.54 | 108 | 19 | 456 | 2.10 | 0.42 | 174 | 1368 | 2.40 | 23.80 |  |
| `BTCUSD_H4_rank3.set` | tester-only | 50 | 753 | 2.36 | 0.60 | 105 | 24 | 650 | 3.10 | 0.58 | 91 | 1385 | 2.60 | 18.96 |  |
| `BTCUSD_M15_rank1.set` | tester-only | 286 | 513 | 1.27 | 0.44 | 318 | 169 | 346 | 1.23 | 0.41 | 223 | 591 | 1.17 | 1.89 |  |
| `BTCUSD_M15_rank2.set` | tester-only | 322 | 424 | 1.25 | 0.42 | 210 | 190 | 257 | 1.21 | 0.45 | 206 | 424 | 1.13 | 1.33 |  |
| `BTCUSD_M15_rank3.set` | tester-only | 361 | 442 | 1.22 | 0.43 | 211 | 221 | 420 | 1.30 | 0.43 | 163 | 802 | 1.23 | 1.48 |  |
| `BTCUSD_M30_rank1.set` | tester-only | 112 | 779 | 1.57 | 0.34 | 304 | 58 | 706 | 1.92 | 0.31 | 192 | 1407 | 1.65 | 8.73 |  |
| `BTCUSD_M30_rank2.set` | tester-only | 196 | 671 | 1.94 | 0.37 | 79 | 101 | 348 | 1.73 | 0.32 | 44 | 939 | 1.76 | 3.43 |  |
| `BTCUSD_M30_rank3.set` | tester-only | 105 | 796 | 1.73 | 0.30 | 150 | 54 | 363 | 1.45 | 0.26 | 273 | 1128 | 1.59 | 7.29 |  |
| `BTCUSD_M5_rank1.set` | live | 407 | 879 | 1.27 | 0.20 | 232 | 251 | 827 | 1.42 | 0.22 | 256 | 1481 | 1.28 | 2.59 |  |
| `BTCUSD_M5_rank2.set` | live | 447 | 775 | 1.21 | 0.20 | 213 | 255 | 607 | 1.30 | 0.21 | 173 | 802 | 1.14 | 1.97 |  |
| `BTCUSD_M5_rank3.set` | live | 436 | 766 | 1.22 | 0.20 | 264 | 268 | 596 | 1.28 | 0.20 | 224 | 1061 | 1.18 | 1.93 |  |
| `XAUUSD_H1_rank1.set` | tester-only | 59 | 1246 | 1.80 | 0.47 | 202 | 101 | 844 | 1.27 | 0.39 | 513 | 2083 | 1.44 | 13.06 |  |
| `XAUUSD_H1_rank2.set` | tester-only | 166 | 1140 | 1.50 | 0.23 | 283 | 157 | 1585 | 1.33 | 0.21 | 864 | 2861 | 1.41 | 8.43 |  |
| `XAUUSD_H1_rank3.set` | tester-only | 319 | 936 | 1.46 | 0.49 | 233 | 133 | 1175 | 1.50 | 0.52 | 308 | 1953 | 1.44 | 4.67 |  |
| `XAUUSD_H4_rank1.set` | tester-only | 151 | 1889 | 2.60 | 0.45 | 179 | 103 | 4316 | 3.20 | 0.48 | 534 | 6143 | 2.93 | 24.43 |  |
| `XAUUSD_H4_rank2.set` | tester-only | 124 | 1883 | 2.77 | 0.43 | 171 | 86 | 3240 | 2.61 | 0.45 | 638 | 5076 | 2.64 | 24.40 |  |
| `XAUUSD_H4_rank3.set` | tester-only | 140 | 1851 | 2.51 | 0.48 | 180 | 101 | 4268 | 3.14 | 0.47 | 541 | 6045 | 2.85 | 25.39 |  |
| `XAUUSD_M1_rank1.set` | live | 7005 | 2632 | 1.20 | 0.60 | 275 | 5243 | 1759 | 1.24 | 0.60 | 112 | 929 | 1.04 | 0.36 | cost-fragile |
| `XAUUSD_M1_rank2.set` | live | 439 | 2752 | 1.67 | 0.08 | 876 | 202 | 1104 | 1.57 | 0.08 | 1165 | 3823 | 1.62 | 6.01 |  |
| `XAUUSD_M1_rank3.set` | live | 2363 | 2299 | 1.37 | 0.63 | 305 | 1545 | 1253 | 1.50 | 0.65 | 52 | 2623 | 1.27 | 0.91 |  |
| `XAUUSD_M15_rank1.set` | tester-only | 1272 | 1884 | 1.30 | 0.30 | 296 | 906 | 1186 | 1.25 | 0.26 | 345 | 2596 | 1.23 | 1.41 |  |
| `XAUUSD_M15_rank2.set` | tester-only | 129 | 1136 | 1.55 | 0.63 | 456 | 84 | 1004 | 1.77 | 0.73 | 261 | 2164 | 1.64 | 10.05 |  |
| `XAUUSD_M15_rank3.set` | tester-only | 535 | 1847 | 1.27 | 0.44 | 642 | 352 | 868 | 1.20 | 0.47 | 315 | 2267 | 1.20 | 3.06 |  |
| `XAUUSD_M30_rank1.set` | tester-only | 231 | 1615 | 1.80 | 0.24 | 178 | 185 | 1427 | 1.40 | 0.23 | 595 | 2805 | 1.50 | 7.31 |  |
| `XAUUSD_M30_rank2.set` | tester-only | 163 | 1134 | 1.87 | 0.24 | 190 | 104 | 1579 | 1.83 | 0.26 | 313 | 2441 | 1.75 | 10.16 |  |
| `XAUUSD_M30_rank3.set` | tester-only | 370 | 1854 | 1.77 | 0.44 | 159 | 253 | 872 | 1.22 | 0.40 | 346 | 2575 | 1.40 | 4.38 |  |
| `XAUUSD_M5_rank1.set` | live | 916 | 2611 | 1.29 | 0.28 | 505 | 559 | 1492 | 1.25 | 0.29 | 337 | 3504 | 1.23 | 2.78 |  |
| `XAUUSD_M5_rank2.set` | live | 1322 | 2589 | 1.26 | 0.50 | 355 | 860 | 1488 | 1.23 | 0.50 | 293 | 3087 | 1.18 | 1.87 |  |
| `XAUUSD_M5_rank3.set` | live | 1322 | 2530 | 1.25 | 0.50 | 346 | 860 | 1488 | 1.23 | 0.50 | 293 | 3028 | 1.17 | 1.84 |  |

### What each preset does

- **BTCUSD_H1_rank1.set**: Turn / predict stop; opp reverse; SL 3.0xATR / TP 5.0R, no trail; no loss-rev; RSI 14 fast 3 slow 21, turnMax 24 hold 3, allOn=True; FGF off
- **BTCUSD_H1_rank2.set**: BOT/TOP square; opp ignore; SL 250000 / TP 1000000 pts, no trail, time stop 48 bars; loss-rev x3; RSI 9 fast 1 slow 13, turnMax 12 hold 2, allOn=True; FGF on: filter H1, parent H1, zones H1/120min/H4, band 0.25xATR, burst 1.0xATR, minAligned 2, against=True, window=next signal
- **BTCUSD_H1_rank3.set**: Turn / predict stop; opp reverse; SL 3.0xATR / TP 5.0R, no trail; loss-rev x1; RSI 14 fast 3 slow 21, turnMax 24 hold 3, allOn=True; FGF off
- **BTCUSD_H4_rank1.set**: BOT/TOP square; opp reverse; SL 6.0xATR / TP 5.0R, no trail; no loss-rev; RSI 14 fast 2 slow 9, turnMax 12 hold 2, allOn=False; FGF off
- **BTCUSD_H4_rank2.set**: BOT/TOP square; opp reverse; SL 6.0xATR / TP 5.0R, no trail; no loss-rev; RSI 14 fast 1 slow 9, turnMax 12 hold 2, allOn=False; FGF off
- **BTCUSD_H4_rank3.set**: Turn / after hold; opp close only; SL 6.0xATR / TP 5.0R, no trail; no loss-rev; RSI 9 fast 2 slow 9, turnMax 24 hold 2, allOn=False; FGF off
- **BTCUSD_M15_rank1.set**: CONT / at close; opp close only; SL 350000 / TP 1000000 pts, no trail; loss-rev x3; RSI 9 fast 1 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter M30, parent H1, zones H1/120min/H4, band 0.0xATR, burst 1.0xATR, minAligned 2, against=True, window=minutes
- **BTCUSD_M15_rank2.set**: CONT / stop past candle; opp close only; SL 350000 / TP 1000000 pts, no trail; loss-rev x3; RSI 9 fast 1 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter M30, parent H1, zones H1/120min/H4, band 0.0xATR, burst 0.25xATR, minAligned 2, against=True, window=minutes
- **BTCUSD_M15_rank3.set**: CONT / stop past candle; opp close only; SL 350000 / TP 1000000 pts, no trail; loss-rev x3; RSI 9 fast 1 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter M15, parent H1, zones H1/120min/H4, band 0.0xATR, burst 1.0xATR, minAligned 2, against=True, window=minutes
- **BTCUSD_M30_rank1.set**: CONT / at close; opp ignore; SL 6.0xATR / TP 5.0R, no trail; no loss-rev; RSI 9 fast 3 slow 13, turnMax 12 hold 2, allOn=True; FGF off
- **BTCUSD_M30_rank2.set**: Turn / at cross; opp reverse; SL 75000 / TP 500000 pts, no trail; no loss-rev; RSI 9 fast 3 slow 21, turnMax 24 hold 1, allOn=False; FGF on: filter M30, parent H1, zones M15/M30/H1, band 0.25xATR, burst 0.5xATR, minAligned 2, against=True, window=next signal
- **BTCUSD_M30_rank3.set**: BOT/TOP tick; opp ignore; SL 6.0xATR / TP 5.0R, no trail; no loss-rev; RSI 9 fast 3 slow 13, turnMax 12 hold 2, allOn=True; FGF on: filter 120min, parent 120min, zones H1/120min/H4, band 0.25xATR, burst 0.25xATR, minAligned 1, against=True, window=minutes
- **BTCUSD_M5_rank1.set**: Turn / after hold; opp ignore; SL 100000 / TP 500000 pts, no trail; loss-rev x1; RSI 14 fast 1 slow 7, turnMax 12 hold 2, allOn=True; FGF on: filter H4, parent H4, zones H1/120min/H4, band 0.1xATR, burst 1.0xATR, minAligned 1, against=True, window=next signal
- **BTCUSD_M5_rank2.set**: Turn / after hold; opp ignore; SL 100000 / TP 500000 pts, no trail; loss-rev x1; RSI 14 fast 1 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter H4, parent H4, zones H1/120min/H4, band 0.1xATR, burst 1.0xATR, minAligned 1, against=True, window=next signal
- **BTCUSD_M5_rank3.set**: Turn / after hold; opp ignore; SL 100000 / TP 500000 pts, no trail; loss-rev x1; RSI 21 fast 1 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter H4, parent H4, zones H1/120min/H4, band 0.1xATR, burst 1.0xATR, minAligned 1, against=True, window=next signal
- **XAUUSD_H1_rank1.set**: BOT/TOP square; opp ignore; SL 5000 / TP 10000 pts, no trail; loss-rev x2; RSI 7 fast 3 slow 9, turnMax 12 hold 2, allOn=False; FGF off
- **XAUUSD_H1_rank2.set**: CONT / at close; opp ignore; SL 2.0xATR / TP 5.0R, no trail; loss-rev x2; RSI 14 fast 3 slow 13, turnMax 12 hold 2, allOn=True; FGF on: filter 120min, parent H1, zones H1/120min/H4, band 0.1xATR, burst 0.5xATR, minAligned 2, against=True, window=next signal
- **XAUUSD_H1_rank3.set**: BOT/TOP tick; opp close only; SL 4.0xATR / TP 1.5R, no trail, time stop 96 bars; no loss-rev; RSI 7 fast 3 slow 7, turnMax 12 hold 2, allOn=True; FGF on: filter H4, parent 480min, zones H4/480min/1440min, band 0.0xATR, burst 0.5xATR, minAligned 1, against=False, window=next signal
- **XAUUSD_H4_rank1.set**: Turn / predict stop; opp reverse; SL 6.0xATR / TP 1.5R, trail act 4.0xATR dist 2.0xATR; loss-rev x3; RSI 9 fast 3 slow 9, turnMax 24 hold 1, allOn=True; FGF on: filter H4, parent H1, zones H1/120min/H4, band 0.25xATR, burst 1.0xATR, minAligned 2, against=True, window=next signal
- **XAUUSD_H4_rank2.set**: Turn / predict stop; opp reverse; SL 6.0xATR / TP 1.5R, trail act 4.0xATR dist 2.0xATR; loss-rev x3; RSI 9 fast 3 slow 9, turnMax 24 hold 1, allOn=True; FGF on: filter H4, parent H1, zones H1/120min/H4, band 0.25xATR, burst 1.0xATR, minAligned 2, against=True, window=next signal
- **XAUUSD_H4_rank3.set**: Turn / predict stop; opp reverse; SL 6.0xATR / TP 1.5R, trail act 4.0xATR dist 2.0xATR; loss-rev x3; RSI 9 fast 3 slow 9, turnMax 24 hold 1, allOn=True; FGF on: filter H4, parent H1, zones H1/120min/H4, band 0.25xATR, burst 1.0xATR, minAligned 2, against=True, window=next signal
- **XAUUSD_M1_rank1.set**: Turn / predict stop; opp reverse; SL 2.0xATR / TP 5.0R, trail act 1.0xATR dist 0.2xATR; loss-rev x3; RSI 21 fast 3 slow 5, turnMax 12 hold 2, allOn=False; FGF on: filter 120min, parent 480min, zones H4/480min/1440min, band 0.5xATR, burst 0.25xATR, minAligned 2, against=True, window=next signal
- **XAUUSD_M1_rank2.set**: BOT/TOP tick; opp ignore; SL 1000 / TP 20000 pts, no trail; no loss-rev; RSI 9 fast 2 slow 13, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M1_rank3.set**: Turn / predict stop; opp reverse; SL 2.0xATR / TP 5.0R, trail act 1.0xATR dist 0.2xATR; loss-rev x3; RSI 21 fast 1 slow 9, turnMax 12 hold 2, allOn=False; FGF on: filter 120min, parent 480min, zones H4/480min/1440min, band 0.5xATR, burst 0.25xATR, minAligned 2, against=True, window=next signal
- **XAUUSD_M15_rank1.set**: BOT/TOP square; opp reverse; SL 700 / TP 10000 pts, no trail; loss-rev x3; RSI 14 fast 2 slow 21, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M15_rank2.set**: CONT / at close; opp ignore; SL 6.0xATR / TP 0.0R, trail act 4.0xATR dist 2.0xATR; no loss-rev; RSI 14 fast 3 slow 7, turnMax 12 hold 2, allOn=True; FGF on: filter 120min, parent H1, zones H1/120min/H4, band 0.1xATR, burst 0.25xATR, minAligned 2, against=False, window=next signal
- **XAUUSD_M15_rank3.set**: CONT / at close; opp reverse; SL 3000 / TP 10000 pts, no trail; loss-rev x3; RSI 14 fast 2 slow 21, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M30_rank1.set**: BOT/TOP square; opp ignore; SL 2.0xATR / TP 5.0R, no trail; loss-rev x1; RSI 9 fast 2 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter 120min, parent H1, zones H1/120min/H4, band 0.0xATR, burst 0.25xATR, minAligned 2, against=False, window=next signal
- **XAUUSD_M30_rank2.set**: BOT/TOP square; opp ignore; SL 2.0xATR / TP 5.0R, no trail; loss-rev x1; RSI 9 fast 2 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter H4, parent H1, zones H1/120min/H4, band 0.0xATR, burst 0.25xATR, minAligned 2, against=False, window=candles
- **XAUUSD_M30_rank3.set**: BOT/TOP square; opp ignore; SL 2.0xATR / TP 5.0R, trail act 4.0xATR dist 0.2xATR; loss-rev x1; RSI 9 fast 2 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter H4, parent H1, zones H1/120min/H4, band 0.0xATR, burst 0.25xATR, minAligned 2, against=False, window=candles
- **XAUUSD_M5_rank1.set**: BOT/TOP tick; opp ignore; SL 3.0xATR / TP 3.0R, no trail; loss-rev x3; RSI 21 fast 2 slow 7, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M5_rank2.set**: CONT / stop past candle; opp reverse; SL 4.0xATR / TP 0.0R, trail act 4.0xATR dist 2.0xATR; loss-rev x1; RSI 21 fast 2 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter H4, parent H4, zones H1/120min/H4, band 0.0xATR, burst 0.5xATR, minAligned 3, against=True, window=next signal
- **XAUUSD_M5_rank3.set**: CONT / stop past candle; opp reverse; SL 4.0xATR / TP 5.0R, trail act 4.0xATR dist 2.0xATR; loss-rev x1; RSI 21 fast 2 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter H4, parent H4, zones H1/120min/H4, band 0.0xATR, burst 0.5xATR, minAligned 3, against=True, window=next signal

## Method

1. **Logic port.** The EA's pure decision code was ported line by line to Python/numba (`tools/xpw_engine.py`): RSI/SMA/ATR and square detection (`ShapeMapV7Core`), crosses, turns, wick ticks and the inverse-Wilder prediction (`ShapeMapV8Core`), the CONT state machine (`ShapeMapV92Core`), the ordered command planner incl. loss/tiny reversal (`ShapeMapV92Execution`), exit distances and trailing (`ShapeMapV8Execution`), and the FlashGold direction filter with TDI zones, burst signal and permission gate (`FlashGold/DirectionFilterCore` + the Filter indicator's bar mapping). Chart period = signal period for every run.
2. **Data.** Binance Vision 1-minute klines: `BTCUSDT` for BTCUSD and `PAXGUSDT` (PAX Gold, a tokenised ounce) as the XAUUSD proxy, 2023-01 to 2026-10. Gold bars outside a typical XAUUSD quote session (weekends, 00:00-00:59 server time) were removed; timestamps shifted to UTC+2 so H1/H4 bars align like an EET MT5 server. PAXG traded in whole dollars before 2025-05, so gold M1/M5/M15 use 2025-05..2026-10 only; gold M30/H1/H4 and all BTC runs use the full span.
3. **Fills.** Signals are evaluated on closed bars (`EnterTick=false` in every preset, matching the backtest). Market orders fill at the next bar open, virtual stop entries at max(stop, open) inside the 1-minute sub-bar that reaches them, SL/TP/trailing are resolved on 1-minute sub-bars with the stop loss assumed first when both are reachable and the pessimistic high-then-low order for trailing. One position at a time, fixed 0.01 lot (the cent gate rejects any other volume).
4. **Costs.** XAUUSD: 25-point spread + 3-point commission per trade (0.28 USD per oz round trip). BTCUSD: 0.03 % spread + 0.01 % commission of price. Acceptance additionally requires profit with both doubled.
5. **Search.** Per symbol and timeframe: the reference preset, then random sampling over the input grid in `tools/xpw_search.py` (signal mode, turn/CONT entry style, opposite-signal mode, exits in points or ATR, trailing, time stop, loss reversal, RSI/MA lengths, square geometry, wick and CONT thresholds, FlashGold filter on/off and its timeframes, band, burst, zones), followed by 3-5 rounds of mutating the best in-sample candidates.
6. **Acceptance.** In-sample net > 0 and PF >= 1.15 with a minimum trade count, out-of-sample net > 0 and PF >= 1.15, net > 0 in both windows with 2x costs, and at least 15 (IS) / 8 (OOS) winning trades so a handful of outliers cannot carry a preset. Ranked by the weaker of the annualised IS and OOS profits, weighted by the weaker profit factor and the recovery factor. Up to 3 distinct presets per symbol/timeframe are saved. "cost-fragile" marks presets whose average profit per trade is below twice the modeled round-trip cost.

## Caveats (read before using)

- **Proxy data.** PAXG is not the broker's XAUUSD-ECNc feed (different spreads, no session gaps, coarse ticks before 2025-05); BTCUSDT spot is not BTCUSD.c. Expect lower performance on the broker feed; re-test every preset in the MT5 Strategy Tester with real tick data before any consideration of live use.
- **Replica, not the EA.** The port follows the MQL5 sources but was not cross-checked against native tester output in this environment (no MetaTrader here). Timing differences remain: the EA re-plans on every tick, the replica once per closed bar; loss-reversal entries fill at the next bar open instead of the next tick.
- **Overfitting risk.** Thousands of combinations were tried per symbol/timeframe; even with an out-of-sample window and cost stress, the accepted presets are the survivors of a search and will degrade. Treat the OOS and 2x-cost columns as the realistic expectation, not the IS column.
- **Clocks.** The EA admits only M1/M5 charts with SigTF 1 or 5 (and M10/M15 with 10) outside the Strategy Tester (`XpwV92ClockPairAdmitted`). M15/M30/H1/H4 presets here are tester-only and were produced because the calibration brief covered six timeframes.
- **Sizing fix.** The reference presets carried `QtyFixed=0.01` (gold, oz) and `0.0001` (BTC), which the EA floors to 0 lots, and the cent gate requires exactly 0.01 lots. All calibrated presets use `QtyFixed=1.0` (gold, 100 oz contract) and `0.01` (BTC, 1 BTC contract) so the source quantity maps to 0.01 lots; verify the broker contract sizes.
- **Port review.** The port was reviewed against the MQL5 sources by seven independent reviewers with adversarial verification; confirmed discrepancies (SMA floating-point drift, pending-stop clearing on market fills, stop-fill reversal pricing, `enteredThisBar` on market fills, the 499-bar ATR re-anchor, loss-reversal command precedence) were fixed before the final search. Two low-impact deviations remain by design: bar ends are nominal `open + period` (the indicator clips them to the broker quote session, which only matters when a session ends inside a bar), and ATR exit distances use the confirmed entry-bar ATR rather than the forming first-tick value.
- **Risk gates untouched.** `EnableTrading`, `FenceAllowExecution`, the fence capital and the cent-gate limits are exactly as in the handoff package. Nothing here is approval to trade.

## Reproduce

```bash
pip install numpy numba
python3 tools/xpw_data.py        # expects Binance Vision monthly 1m zips under ../data/<SYMBOL>/
python3 tools/xpw_search.py      # writes results/*.json (about 30-60 min on 4 cores)
python3 tools/xpw_report.py out  # presets + CSV + this report
```
