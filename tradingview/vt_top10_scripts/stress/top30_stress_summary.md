# Top-10 per strategy: in-engine re-run with commission and slippage (VT XAUUSD-ECNc, July 2026 ticks, 0.10 cent lot)

Base = VT actual costs: commission 0.30 USD per lot per side (0.60 round trip), real bid/ask fills, no extra slippage.
Stress levels add slippage of 2 / 5 / 10 ticks per side on every fill (10 ticks = 0.10 USD/oz on top of the real 13-tick spread) and double the commission to 0.60 per side (1.20 round trip).
All 30 base re-runs reproduce the screen table exactly (same trades, same net).

## FlashGold v5

| # | TF | settings | trades | net base | net s2 | net s5 | net s10 | net c0.60 | net c0.60+s5 | net c0.60+s10 | PF base | PF worst | PF>=1.35 at worst | trades changed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | H1 | ATR SL 1.0 TP 3.0R Fixed, burst 0.7, filter off | 21 | 18.96 | 18.92 | 18.84 | 20.71 | 17.70 | 17.57 | 19.51 | 1.84 | 1.75 | yes | yes |
| 2 | H1 | ATR SL 1.0 TP 3.0R Fixed, burst 0.5, filter off | 29 | 15.84 | 15.79 | 15.95 | 17.75 | 14.10 | 14.21 | 16.07 | 1.51 | 1.44 | yes | yes |
| 3 | H1 | ATR SL 0.5 TP 5.0R Fixed+trail, burst 0.3, filter off | 58 | 13.10 | 12.89 | 12.74 | 12.34 | 9.62 | 9.26 | 8.86 | 1.47 | 1.29 | no | no |
| 4 | H1 | ATR SL 0.5 TP 5.0R Fixed, burst 0.3, filter off | 45 | 11.28 | 11.11 | 11.03 | 10.80 | 8.57 | 8.32 | 8.10 | 1.41 | 1.27 | no | no |
| 5 | H1 | ATR SL 0.5 TP 2.0R Fixed+trail, burst 0.3, filter off | 58 | 11.04 | 10.92 | 10.79 | 10.46 | 7.56 | 7.31 | 6.98 | 1.40 | 1.23 | no | no |
| 6 | H1 | ATR SL 0.5 TP 2.0R Fixed, burst 0.3, filter off | 58 | 11.04 | 10.92 | 10.79 | 10.46 | 7.56 | 7.31 | 6.98 | 1.40 | 1.23 | no | no |
| 7 | H1 | ATR SL 1.0 TP 5.0R Fixed, burst 0.7, filter off | 17 | 10.98 | 10.94 | 10.86 | 10.70 | 9.96 | 9.84 | 9.68 | 1.51 | 1.43 | yes | no |
| 8 | H1 | ATR SL 0.5 TP 3.0R Fixed+trail, burst 0.3, filter off | 58 | 10.95 | 10.78 | 10.62 | 10.28 | 7.47 | 7.14 | 6.80 | 1.39 | 1.23 | no | no |
| 9 | M15 | ATR SL 2.0 TP 5.0R Fixed, burst 0.7, filter off | 58 | 10.28 | 10.08 | 9.79 | 9.26 | 6.80 | 6.32 | 5.78 | 1.22 | 1.12 | no | no |
| 10 | H1 | ATR SL 0.5 TP 3.0R Fixed, burst 0.3, filter off | 51 | 10.25 | 10.12 | 10.02 | 10.05 | 7.19 | 6.96 | 6.99 | 1.35 | 1.22 | no | no |

## ShapeMap v0.9.2

| # | TF | settings | trades | net base | net s2 | net s5 | net s10 | net c0.60 | net c0.60+s5 | net c0.60+s10 | PF base | PF worst | PF>=1.35 at worst | trades changed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | M30 | Turn_AfterHold, ATR_default_2.0_2R_4.0_0.2, lossrev any+tiny, filter off | 27 | 40.42 | 40.32 | 40.23 | 40.03 | 38.80 | 38.62 | 38.41 | 2.89 | 2.74 | yes | no |
| 2 | M30 | Square, ATR_1.0_3R_notrail, lossrev any+tiny, filter off | 54 | 26.16 | 25.99 | 25.76 | 25.43 | 22.92 | 22.52 | 22.19 | 1.95 | 1.76 | yes | no |
| 3 | M15 | Turn_AfterHold, Points_default, lossrev any_notiny, filter off | 64 | 26.09 | 25.84 | 24.90 | 24.26 | 22.25 | 21.06 | 20.42 | 2.00 | 1.73 | yes | no |
| 4 | M30 | Turn_AtCross, ATR_default_2.0_2R_4.0_0.2, lossrev any_notiny, filter off | 42 | 25.53 | 25.41 | 25.31 | 25.00 | 23.01 | 22.79 | 22.48 | 1.75 | 1.63 | yes | no |
| 5 | H1 | CONT_Stop, ATR_default_2.0_2R_4.0_0.2, lossrev SLtrail+tiny, filter off | 15 | 24.79 | 24.73 | 24.65 | 24.56 | 23.89 | 23.75 | 23.66 | 2.65 | 2.53 | yes | no |
| 6 | M15 | Turn_AfterHold, ATR_1.5_2R_1.0_0.5, lossrev any_notiny, filter off | 82 | 23.65 | 21.23 | 21.35 | 19.53 | 18.73 | 16.31 | 14.43 | 1.90 | 1.45 | yes | yes |
| 7 | H1 | CONT_Close, ATR_default_2.0_2R_4.0_0.2, lossrev any+tiny, filter off | 16 | 23.36 | 23.31 | 23.28 | 23.26 | 22.41 | 22.32 | 22.30 | 2.25 | 2.16 | yes | no |
| 8 | M15 | Turn_AfterHold, ATR_2.5_2R_1.0_0.5, lossrev any_notiny, filter off | 74 | 22.36 | 22.51 | 22.12 | 19.59 | 17.92 | 17.68 | 15.09 | 1.90 | 1.54 | yes | yes |
| 9 | M15 | Turn_AfterHold, ATR_default_2.0_2R_4.0_0.2, lossrev any_notiny, filter off | 74 | 21.97 | 21.74 | 21.68 | 21.11 | 17.53 | 17.24 | 16.67 | 1.44 | 1.32 | no | no |
| 10 | M15 | Square, ATR_default_2.0_2R_4.0_0.2, lossrev any_notiny, filter off | 110 | 20.08 | 19.92 | 19.42 | 18.47 | 13.48 | 12.82 | 11.87 | 1.33 | 1.19 | no | no |

## Orientation v2.8 (partial ladder)

| # | TF | settings | trades | net base | net s2 | net s5 | net s10 | net c0.60 | net c0.60+s5 | net c0.60+s10 | PF base | PF worst | PF>=1.35 at worst | trades changed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | H1 | chart+READ, info enter, reverse off, ATR_2.0_2R_notrail, maxOpen 20, filter off | 84 | 137.54 | 137.27 | 136.91 | 136.33 | 132.50 | 131.87 | 131.29 | 2.67 | 2.54 | yes | no |
| 2 | H1 | chart only, info enter, reverse off, Points_default, maxOpen 20, filter off | 37 | 122.55 | 122.40 | 122.18 | 121.81 | 120.33 | 119.96 | 119.59 | 8.81 | 8.29 | yes | no |
| 3 | H1 | every rung, info enter, reverse off, Points_default, maxOpen 20, filter off | 275 | 111.42 | 110.32 | 108.67 | 105.92 | 94.92 | 92.17 | 89.42 | 1.73 | 1.55 | yes | no |
| 4 | M30 | chart+READ, info enter, reverse off, Points_default, maxOpen 20, filter off | 138 | 107.92 | 107.37 | 106.54 | 105.16 | 99.64 | 98.26 | 96.88 | 2.12 | 1.96 | yes | no |
| 5 | M15 | chart+READ, info off, reverse off, Points_default, maxOpen 20, filter off | 188 | 106.77 | 106.02 | 104.89 | 103.01 | 95.49 | 93.61 | 91.73 | 2.07 | 1.86 | yes | no |
| 6 | M15 | chart+READ, info enter, reverse off, Points_default, maxOpen 20, filter off | 242 | 101.21 | 100.24 | 98.79 | 96.37 | 86.69 | 84.27 | 81.85 | 1.78 | 1.59 | yes | no |
| 7 | H1 | every rung, info enter, reverse off, ATR_2.0_2R_notrail, maxOpen 20, filter off | 275 | 100.64 | 99.56 | 97.97 | 95.45 | 84.14 | 81.47 | 78.95 | 1.63 | 1.47 | yes | no |
| 8 | H1 | chart only, info enter, reverse off, ATR_2.0_2R_notrail, maxOpen 20, filter off | 37 | 88.56 | 88.41 | 88.25 | 87.92 | 86.34 | 86.03 | 85.69 | 4.48 | 4.25 | yes | no |
| 9 | M30 | chart+READ, info enter, reverse off, ATR_2.0_2R_notrail, maxOpen 20, filter off | 138 | 76.74 | 76.24 | 75.57 | 74.35 | 68.46 | 67.29 | 66.07 | 1.84 | 1.68 | yes | no |
| 10 | H1 | chart+READ, info enter, reverse off, ATR_1.0_3R_notrail, maxOpen 20, filter off | 84 | 72.96 | 72.73 | 72.29 | 71.62 | 67.92 | 67.25 | 66.58 | 2.07 | 1.93 | yes | no |
