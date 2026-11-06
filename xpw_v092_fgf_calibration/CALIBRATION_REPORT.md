# XPW v0.9.2 + FlashGold EA: input calibration (XAUUSD, BTCUSD), 2026-11-06

Presets in `presets/` are the input combinations that stayed profitable in-sample, out-of-sample and under doubled trading costs in a Python replica of the EA's decision logic. This is **not** an MT5 Strategy Tester result and **not** live-broker evidence; all live gates in the presets remain disabled (`EnableTrading=false`, `FenceAllowExecution=false`).

## Search summary

| Symbol | TF | Bars | Data window | Combos evaluated | Pass IS+OOS | Pass 2x-cost stress | Saved presets | Reference-preset net (USD/0.01 lot) |
|---|---|---:|---|---:|---:|---:|---:|---:|
| BTCUSD | H1 | 33599 | 2023-01..2026-10 | 1946 | 110 | 80 | 3 | -699.26 (1982 trades, PF 0.768) |
| BTCUSD | H4 | 8401 | 2023-01..2026-10 | 1845 | 270 | 80 | 3 | -1.37 (499 trades, PF 0.998) |
| BTCUSD | M1 | 2015920 | 2023-01..2026-10 | 677 | 0 | 0 | 0 | -3534.65 (15476 trades, PF 0.839) |
| BTCUSD | M15 | 134395 | 2023-01..2026-10 | 2122 | 58 | 50 | 3 | -757.8 (4130 trades, PF 0.871) |
| BTCUSD | M30 | 67198 | 2023-01..2026-10 | 2009 | 205 | 80 | 3 | -689.46 (2854 trades, PF 0.836) |
| BTCUSD | M5 | 403184 | 2023-01..2026-10 | 1348 | 12 | 11 | 3 | -1086.36 (7057 trades, PF 0.891) |
| XAUUSD | H1 | 22999 | 2023-01..2026-10 | 1768 | 59 | 59 | 3 | -1152.86 (920 trades, PF 0.859) |
| XAUUSD | H4 | 6000 | 2023-01..2026-10 | 1950 | 383 | 80 | 3 | 324.67 (268 trades, PF 1.158) |
| XAUUSD | M1 | 540900 | 2025-05..2026-10 (cent-precision gold proxy only) | 609 | 116 | 10 | 3 | 1047.82 (2929 trades, PF 1.052) |
| XAUUSD | M15 | 36060 | 2025-05..2026-10 (cent-precision gold proxy only) | 2040 | 151 | 78 | 3 | 179.14 (802 trades, PF 1.027) |
| XAUUSD | M30 | 45998 | 2023-01..2026-10 | 1736 | 40 | 40 | 3 | -0.84 (1304 trades, PF 1.0) |
| XAUUSD | M5 | 108180 | 2025-05..2026-10 (cent-precision gold proxy only) | 1294 | 98 | 80 | 3 | -230.97 (1320 trades, PF 0.979) |

## Accepted presets

Profit figures are USD per 0.01 lot (gold: 1 oz; BTC: 0.01 BTC) after modeled spread and commission. IS = in-sample selection window, OOS = out-of-sample validation window, 2x = full period with spread and commission doubled.

| Preset | Clock | IS trades | IS net | IS PF | IS win | IS maxDD | OOS trades | OOS net | OOS PF | OOS win | OOS maxDD | 2x-cost net | 2x PF | Avg/trade | Note |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `BTCUSD_H1_rank1.set` | tester-only | 317 | 805 | 1.37 | 0.40 | 291 | 199 | 407 | 1.25 | 0.43 | 192 | 1105 | 1.29 | 2.35 |  |
| `BTCUSD_H1_rank2.set` | tester-only | 88 | 442 | 1.96 | 0.59 | 89 | 35 | 309 | 2.28 | 0.60 | 74 | 789 | 2.09 | 6.11 |  |
| `BTCUSD_H1_rank3.set` | tester-only | 158 | 645 | 1.78 | 0.54 | 123 | 77 | 295 | 1.51 | 0.53 | 188 | 858 | 1.60 | 4.00 |  |
| `BTCUSD_H4_rank1.set` | tester-only | 25 | 1076 | 5.44 | 0.64 | 102 | 16 | 617 | 3.07 | 0.56 | 105 | 1684 | 4.11 | 41.29 |  |
| `BTCUSD_H4_rank2.set` | tester-only | 28 | 1118 | 4.50 | 0.68 | 81 | 18 | 633 | 2.79 | 0.61 | 125 | 1741 | 3.58 | 38.06 |  |
| `BTCUSD_H4_rank3.set` | tester-only | 28 | 1118 | 4.50 | 0.68 | 81 | 17 | 625 | 2.78 | 0.59 | 125 | 1734 | 3.58 | 38.73 |  |
| `BTCUSD_M15_rank1.set` | tester-only | 341 | 457 | 1.24 | 0.43 | 192 | 208 | 524 | 1.44 | 0.43 | 128 | 864 | 1.27 | 1.79 |  |
| `BTCUSD_M15_rank2.set` | tester-only | 324 | 444 | 1.27 | 0.43 | 210 | 190 | 257 | 1.21 | 0.45 | 206 | 444 | 1.14 | 1.36 |  |
| `BTCUSD_M15_rank3.set` | tester-only | 186 | 593 | 2.06 | 0.61 | 73 | 99 | 203 | 1.42 | 0.53 | 90 | 745 | 1.70 | 2.79 |  |
| `BTCUSD_M30_rank1.set` | tester-only | 236 | 709 | 1.65 | 0.34 | 129 | 116 | 345 | 1.55 | 0.28 | 76 | 962 | 1.55 | 2.99 |  |
| `BTCUSD_M30_rank2.set` | tester-only | 165 | 548 | 1.67 | 0.32 | 129 | 86 | 340 | 1.72 | 0.27 | 54 | 782 | 1.59 | 3.54 |  |
| `BTCUSD_M30_rank3.set` | tester-only | 217 | 823 | 1.83 | 0.35 | 122 | 104 | 311 | 1.55 | 0.27 | 68 | 1040 | 1.65 | 3.53 |  |
| `BTCUSD_M5_rank1.set` | live | 446 | 725 | 1.20 | 0.20 | 243 | 252 | 697 | 1.35 | 0.21 | 235 | 486 | 1.08 | 2.04 |  |
| `BTCUSD_M5_rank2.set` | live | 443 | 696 | 1.19 | 0.19 | 243 | 261 | 546 | 1.26 | 0.20 | 196 | 518 | 1.08 | 1.76 |  |
| `BTCUSD_M5_rank3.set` | live | 451 | 675 | 1.18 | 0.19 | 294 | 252 | 517 | 1.25 | 0.20 | 246 | 376 | 1.06 | 1.70 |  |
| `XAUUSD_H1_rank1.set` | tester-only | 179 | 787 | 1.67 | 0.48 | 119 | 63 | 958 | 1.55 | 0.43 | 391 | 1651 | 1.56 | 7.21 |  |
| `XAUUSD_H1_rank2.set` | tester-only | 64 | 769 | 1.40 | 0.41 | 500 | 115 | 1050 | 1.30 | 0.39 | 301 | 2062 | 1.38 | 10.16 |  |
| `XAUUSD_H1_rank3.set` | tester-only | 153 | 693 | 1.37 | 0.52 | 381 | 66 | 1526 | 1.82 | 0.56 | 306 | 2201 | 1.59 | 10.13 |  |
| `XAUUSD_H4_rank1.set` | tester-only | 28 | 1665 | 7.21 | 0.89 | 115 | 21 | 1582 | 3.00 | 0.76 | 292 | 3236 | 4.05 | 66.28 |  |
| `XAUUSD_H4_rank2.set` | tester-only | 26 | 1607 | 9.21 | 0.89 | 79 | 16 | 1687 | 4.88 | 0.88 | 328 | 3286 | 6.21 | 78.45 |  |
| `XAUUSD_H4_rank3.set` | tester-only | 36 | 1576 | 4.00 | 0.83 | 142 | 18 | 1437 | 3.38 | 0.78 | 199 | 3001 | 3.65 | 55.80 |  |
| `XAUUSD_M1_rank1.set` | live | 9876 | 3050 | 1.30 | 0.70 | 263 | 7125 | 2088 | 1.29 | 0.70 | 66 | 632 | 1.03 | 0.30 | cost-fragile |
| `XAUUSD_M1_rank2.set` | live | 11493 | 2621 | 1.27 | 0.49 | 122 | 8443 | 1963 | 1.32 | 0.49 | 72 | 231 | 1.01 | 0.23 | cost-fragile |
| `XAUUSD_M1_rank3.set` | live | 9289 | 2429 | 1.27 | 0.45 | 182 | 6910 | 1853 | 1.34 | 0.44 | 63 | 742 | 1.04 | 0.26 | cost-fragile |
| `XAUUSD_M15_rank1.set` | tester-only | 106 | 1989 | 1.94 | 0.23 | 555 | 62 | 1362 | 1.97 | 0.31 | 311 | 3397 | 1.97 | 19.95 |  |
| `XAUUSD_M15_rank2.set` | tester-only | 152 | 1719 | 1.78 | 0.65 | 380 | 106 | 1120 | 1.75 | 0.72 | 229 | 2754 | 1.73 | 11.00 |  |
| `XAUUSD_M15_rank3.set` | tester-only | 384 | 2930 | 1.76 | 0.50 | 389 | 238 | 1019 | 1.36 | 0.49 | 355 | 3710 | 1.54 | 6.35 |  |
| `XAUUSD_M30_rank1.set` | tester-only | 685 | 1180 | 1.50 | 0.81 | 170 | 321 | 569 | 1.24 | 0.84 | 529 | 1529 | 1.32 | 1.74 |  |
| `XAUUSD_M30_rank2.set` | tester-only | 230 | 932 | 1.43 | 0.54 | 166 | 142 | 803 | 1.29 | 0.53 | 353 | 1609 | 1.32 | 4.66 |  |
| `XAUUSD_M30_rank3.set` | tester-only | 88 | 622 | 1.75 | 0.66 | 254 | 49 | 830 | 2.11 | 0.63 | 154 | 1464 | 1.94 | 10.59 |  |
| `XAUUSD_M5_rank1.set` | live | 782 | 2653 | 1.35 | 0.20 | 834 | 398 | 1560 | 1.38 | 0.21 | 225 | 3580 | 1.30 | 3.57 |  |
| `XAUUSD_M5_rank2.set` | live | 788 | 2580 | 1.34 | 0.20 | 834 | 398 | 1560 | 1.38 | 0.21 | 225 | 3535 | 1.29 | 3.49 |  |
| `XAUUSD_M5_rank3.set` | live | 174 | 1737 | 1.75 | 0.12 | 582 | 103 | 1038 | 1.76 | 0.12 | 256 | 2706 | 1.72 | 10.02 |  |

### What each preset does

- **BTCUSD_H1_rank1.set**: Turn / predict stop; opp reverse; SL 3.0xATR / TP 3.0R, no trail; no loss-rev; RSI 9 fast 3 slow 5, turnMax 6 hold 1, allOn=True; FGF on: filter H4, parent H1, zones H1/120min/H4, band 0.1xATR, burst 0.75xATR, minAligned 2, against=True, window=next signal
- **BTCUSD_H1_rank2.set**: BOT/TOP square; opp ignore; SL 250000 / TP 2500000 pts, no trail, time stop 48 bars; loss-rev x3; RSI 14 fast 1 slow 13, turnMax 12 hold 2, allOn=True; FGF on: filter H1, parent H1, zones H1/120min/H4, band 0.5xATR, burst 0.75xATR, minAligned 2, against=True, window=next signal
- **BTCUSD_H1_rank3.set**: BOT/TOP square; opp ignore; SL 250000 / TP 2500000 pts, no trail, time stop 48 bars; loss-rev x3; RSI 14 fast 1 slow 13, turnMax 12 hold 2, allOn=True; FGF on: filter H1, parent H1, zones H1/120min/H4, band 0.5xATR, burst 1.0xATR, minAligned 2, against=True, window=next signal
- **BTCUSD_H4_rank1.set**: Turn / after hold; opp close only; SL 6.0xATR / TP 5.0R, no trail; no loss-rev; RSI 14 fast 2 slow 9, turnMax 24 hold 1, allOn=False; FGF off
- **BTCUSD_H4_rank2.set**: Turn / at cross; opp close only; SL 6.0xATR / TP 5.0R, no trail; no loss-rev; RSI 14 fast 2 slow 9, turnMax 12 hold 3, allOn=False; FGF off
- **BTCUSD_H4_rank3.set**: Turn / at cross; opp close only; SL 6.0xATR / TP 5.0R, no trail; no loss-rev; RSI 14 fast 2 slow 9, turnMax 12 hold 3, allOn=False; FGF off
- **BTCUSD_M15_rank1.set**: CONT / stop past candle; opp close only; SL 350000 / TP 1000000 pts, no trail; loss-rev x1; RSI 9 fast 1 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter M30, parent H1, zones H1/120min/H4, band 0.0xATR, burst 1.0xATR, minAligned 2, against=True, window=minutes
- **BTCUSD_M15_rank2.set**: CONT / stop past candle; opp close only; SL 350000 / TP 1000000 pts, no trail; loss-rev x3; RSI 9 fast 1 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter M30, parent H1, zones H1/120min/H4, band 0.0xATR, burst 1.0xATR, minAligned 2, against=True, window=minutes
- **BTCUSD_M15_rank3.set**: Turn / at cross; opp close only; SL 6.0xATR / TP 1.5R, no trail; loss-rev x1; RSI 14 fast 1 slow 5, turnMax 12 hold 2, allOn=False; FGF on: filter H1, parent H1, zones H1/120min/H4, band 0.25xATR, burst 0.25xATR, minAligned 2, against=False, window=minutes
- **BTCUSD_M30_rank1.set**: Turn / after hold; opp reverse; SL 75000 / TP 500000 pts, no trail; no loss-rev; RSI 9 fast 3 slow 21, turnMax 24 hold 1, allOn=False; FGF on: filter M30, parent H1, zones H1/120min/H4, band 0.25xATR, burst 0.5xATR, minAligned 2, against=True, window=next signal
- **BTCUSD_M30_rank2.set**: Turn / at cross; opp reverse; SL 75000 / TP 500000 pts, no trail; no loss-rev; RSI 9 fast 3 slow 21, turnMax 6 hold 2, allOn=False; FGF on: filter M30, parent H1, zones H1/120min/H4, band 0.25xATR, burst 0.5xATR, minAligned 2, against=True, window=next signal
- **BTCUSD_M30_rank3.set**: Turn / after hold; opp reverse; SL 75000 / TP 500000 pts, no trail; no loss-rev; RSI 9 fast 3 slow 21, turnMax 24 hold 1, allOn=False; FGF on: filter M30, parent H1, zones H1/120min/H4, band 0.25xATR, burst 0.5xATR, minAligned 2, against=True, window=next signal
- **BTCUSD_M5_rank1.set**: Turn / after hold; opp ignore; SL 100000 / TP 500000 pts, no trail; loss-rev x1; RSI 14 fast 1 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter H4, parent H4, zones H1/120min/H4, band 0.1xATR, burst 1.0xATR, minAligned 1, against=True, window=next signal
- **BTCUSD_M5_rank2.set**: Turn / after hold; opp ignore; SL 100000 / TP 500000 pts, no trail; loss-rev x1; RSI 14 fast 1 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter H4, parent H4, zones H1/120min/H4, band 0.1xATR, burst 1.0xATR, minAligned 1, against=True, window=next signal
- **BTCUSD_M5_rank3.set**: Turn / after hold; opp ignore; SL 100000 / TP 500000 pts, no trail; loss-rev x1; RSI 14 fast 1 slow 5, turnMax 12 hold 2, allOn=True; FGF on: filter H4, parent H1, zones H1/120min/H4, band 0.1xATR, burst 1.0xATR, minAligned 2, against=True, window=next signal
- **XAUUSD_H1_rank1.set**: BOT/TOP tick; opp reverse; SL 4.0xATR / TP 3.0R, no trail; no loss-rev; RSI 9 fast 3 slow 13, turnMax 12 hold 2, allOn=True; FGF on: filter H4, parent H4, zones H1/120min/H4, band 0.5xATR, burst 1.0xATR, minAligned 3, against=True, window=next signal
- **XAUUSD_H1_rank2.set**: BOT/TOP square; opp ignore; SL 5000 / TP 10000 pts, no trail; loss-rev x2; RSI 7 fast 2 slow 7, turnMax 12 hold 2, allOn=False; FGF off
- **XAUUSD_H1_rank3.set**: Turn / after hold; opp reverse; SL 4.0xATR / TP 1.5R, no trail; loss-rev x1; RSI 14 fast 2 slow 21, turnMax 12 hold 2, allOn=False; FGF off
- **XAUUSD_H4_rank1.set**: BOT/TOP square; opp ignore; SL 6.0xATR / TP 0.0R, trail act 4.0xATR dist 2.0xATR; loss-rev x1; RSI 7 fast 2 slow 5, turnMax 12 hold 2, allOn=False; FGF off
- **XAUUSD_H4_rank2.set**: BOT/TOP square; opp ignore; SL 6.0xATR / TP 1.5R, trail act 4.0xATR dist 2.0xATR; loss-rev x1; RSI 7 fast 2 slow 5, turnMax 12 hold 2, allOn=False; FGF off
- **XAUUSD_H4_rank3.set**: BOT/TOP square; opp ignore; SL 6.0xATR / TP 0.0R, trail act 4.0xATR dist 2.0xATR; loss-rev x1; RSI 7 fast 2 slow 5, turnMax 12 hold 2, allOn=False; FGF off
- **XAUUSD_M1_rank1.set**: CONT / stop past candle; opp reverse; SL 3.0xATR / TP 3.0R, trail act 1.0xATR dist 0.5xATR; no loss-rev; RSI 14 fast 1 slow 5, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M1_rank2.set**: CONT / stop past candle; opp close only; SL 1.0xATR / TP 1.5R, no trail, time stop 96 bars; no loss-rev; RSI 14 fast 1 slow 9, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M1_rank3.set**: CONT / stop past candle; opp close only; SL 1.0xATR / TP 2.0R, no trail, time stop 96 bars; no loss-rev; RSI 9 fast 1 slow 9, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M15_rank1.set**: Turn / predict stop; opp ignore; SL 4.0xATR / TP 5.0R, no trail; no loss-rev; RSI 14 fast 1 slow 9, turnMax 12 hold 2, allOn=True; FGF on: filter H1, parent 480min, zones H1/120min/H4, band 0.5xATR, burst 0.75xATR, minAligned 2, against=True, window=next signal
- **XAUUSD_M15_rank2.set**: CONT / at close; opp ignore; SL 6.0xATR / TP 0.0R, trail act 4.0xATR dist 2.0xATR; no loss-rev; RSI 14 fast 3 slow 7, turnMax 12 hold 2, allOn=True; FGF on: filter 120min, parent H1, zones H1/120min/H4, band 0.1xATR, burst 0.5xATR, minAligned 2, against=False, window=next signal
- **XAUUSD_M15_rank3.set**: Turn / predict stop; opp ignore; SL 6.0xATR / TP 0.0R, trail act 4.0xATR dist 2.0xATR; no loss-rev; RSI 14 fast 3 slow 7, turnMax 24 hold 2, allOn=True; FGF on: filter 120min, parent H1, zones H1/120min/H4, band 0.1xATR, burst 0.25xATR, minAligned 2, against=False, window=next signal
- **XAUUSD_M30_rank1.set**: BOT/TOP tick; opp close only; SL 6.0xATR / TP 1.0R, trail act 1.0xATR dist 0.2xATR; loss-rev x1; RSI 7 fast 3 slow 7, turnMax 12 hold 2, allOn=True; FGF on: filter M30, parent H1, zones H4/480min/1440min, band 0.5xATR, burst 1.0xATR, minAligned 3, against=True, window=next signal
- **XAUUSD_M30_rank2.set**: BOT/TOP square; opp ignore; SL 4.0xATR / TP 3.0R, trail act 4.0xATR dist 0.2xATR; loss-rev x3; RSI 7 fast 2 slow 13, turnMax 12 hold 2, allOn=True; FGF on: filter H1, parent 480min, zones H1/120min/H4, band 1.0xATR, burst 1.0xATR, minAligned 3, against=True, window=next signal
- **XAUUSD_M30_rank3.set**: BOT/TOP square; opp ignore; SL 4.0xATR / TP 1.0R, no trail; loss-rev x1; RSI 7 fast 1 slow 9, turnMax 12 hold 2, allOn=True; FGF on: filter 120min, parent H4, zones H4/480min/1440min, band 0.0xATR, burst 0.25xATR, minAligned 3, against=False, window=next signal
- **XAUUSD_M5_rank1.set**: BOT/TOP tick; opp ignore; SL 3.0xATR / TP 5.0R, no trail; loss-rev x3; RSI 21 fast 2 slow 21, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M5_rank2.set**: BOT/TOP tick; opp ignore; SL 3.0xATR / TP 5.0R, no trail; loss-rev x3; RSI 21 fast 2 slow 7, turnMax 12 hold 2, allOn=True; FGF off
- **XAUUSD_M5_rank3.set**: BOT/TOP square; opp ignore; SL 1500 / TP 20000 pts, no trail; loss-rev x1; RSI 14 fast 2 slow 21, turnMax 12 hold 2, allOn=True; FGF on: filter H1, parent H1, zones H1/120min/H4, band 0.25xATR, burst 0.5xATR, minAligned 2, against=True, window=next signal

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
- **Port review.** The port was reviewed against the MQL5 sources by seven independent reviewers, each claim checked by three adversarial verifiers (37 agents). All confirmed discrepancies were fixed before the final search: SMA floating-point drift, same-side-only clearing of pending virtual stops on market fills, frozen stop transaction units (a stop placed while flat only flattens an opposite position and triggers regardless of OppMode), stop-fill reversal pricing, `enteredThisBar` on any fill, the 499-bar ATR re-anchor, loss-reversal command precedence over a same-plan catch-up entry, and the exit-ATR anchor at the EA's effective first-tick value. One low-impact deviation remains by design: bar ends are nominal `open + period`, whereas the indicator clips them to the broker quote session, which only matters when a session ends inside a bar.
- **Risk gates untouched.** `EnableTrading`, `FenceAllowExecution`, the fence capital and the cent-gate limits are exactly as in the handoff package. Nothing here is approval to trade.

## Reproduce

```bash
pip install numpy numba
python3 tools/xpw_data.py        # expects Binance Vision monthly 1m zips under ../data/<SYMBOL>/
python3 tools/xpw_search.py      # writes results/*.json (about 30-60 min on 4 cores)
python3 tools/xpw_report.py out  # presets + CSV + this report
```
