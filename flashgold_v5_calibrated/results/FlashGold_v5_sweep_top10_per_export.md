# FlashGold v5 exit sweep: top results per export

Source: calibration/results/fg/sweep_*.csv on branch claude/confident-einstein-uzfabw (sweep run 2026-09-26). 5,120 cells per file.
Ranking as in the original thread: at least 30 trades, same-bar fraction <= 0.5, score = min(PF, PF first half, PF second half), tie-break win rate.
Net is per 1 oz (gold), 1 contract at $1/point (SPX), 1 BTC, after VT Markets costs (SPX costs placeholder). Trail = activate 1.0 ATR, distance 0.75 ATR.

## XAUUSD 5m  (positive cells 17%, best PF 1.26)

| # | zones | signal | dist ATR | hold | SL ATR | TP R | trail | close opp | trades | win | net | PF | PF h1 | PF h2 | max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | chart+2x+4x (2 aligned) | burst 1.0 ATR | 0.25 | 0 | 3.0 | 1.5 | on | off | 37 | 76% | 22 | 1.23 | 1.17 | 1.37 | 27 |
| 2 | chart+2x+4x (2 aligned) | burst 1.0 ATR | 0.25 | 0 | 3.0 | 2.0 | on | off | 37 | 76% | 22 | 1.23 | 1.17 | 1.37 | 27 |
| 3 | chart+2x+4x (2 aligned) | burst 1.0 ATR | 0.25 | 0 | 3.0 | 3.0 | on | off | 37 | 76% | 22 | 1.23 | 1.17 | 1.37 | 27 |
| 4 | chart+2x+4x (2 aligned) | burst 1.0 ATR | 0.1 | 0 | 3.0 | 1.5 | on | off | 39 | 72% | 27 | 1.25 | 1.16 | 1.51 | 29 |
| 5 | chart+2x+4x (2 aligned) | burst 1.0 ATR | 0.1 | 0 | 3.0 | 2.0 | on | off | 39 | 72% | 27 | 1.25 | 1.16 | 1.51 | 29 |
| 6 | chart+2x+4x (2 aligned) | burst 1.0 ATR | 0.1 | 0 | 3.0 | 3.0 | on | off | 39 | 72% | 27 | 1.25 | 1.16 | 1.51 | 29 |
| 7 | chart+2x+4x+8x (3 aligned) | burst 0.25 ATR | 0.1 | 0 | 1.5 | 2.0 | off | on | 61 | 41% | 14 | 1.06 | 1.06 | 1.06 | 55 |
| 8 | 2x+4x+8x (2 aligned) | burst 0.25 ATR | 0.1 | 0 | 1.5 | 2.0 | off | on | 61 | 41% | 14 | 1.06 | 1.06 | 1.06 | 55 |
| 9 | chart only | any combo | 0.1 | 0 | 1.5 | 2.0 | on | off | 241 | 46% | 80 | 1.19 | 1.29 | 1.05 | 54 |
| 10 | chart only | any combo | 0.1 | 0 | 3.0 | 1.0 | on | off | 238 | 47% | 79 | 1.18 | 1.29 | 1.05 | 54 |

## XAUUSD 10m  (positive cells 29%, best PF 1.66)

| # | zones | signal | dist ATR | hold | SL ATR | TP R | trail | close opp | trades | win | net | PF | PF h1 | PF h2 | max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | chart only | burst 0.25 ATR | 0.25 | 3 | 1.0 | 3.0 | off | on | 70 | 36% | 95 | 1.29 | 1.32 | 1.25 | 84 |
| 2 | chart only | burst 0.25 ATR | 0.25 | 3 | 2.0 | 3.0 | off | off | 58 | 38% | 130 | 1.27 | 1.30 | 1.25 | 116 |
| 3 | chart only | burst 0.25 ATR | 0.25 | 3 | 3.0 | 3.0 | off | on | 57 | 40% | 154 | 1.31 | 1.23 | 1.42 | 153 |
| 4 | chart only | burst 0.25 ATR | 0.25 | 3 | 1.0 | 3.0 | off | off | 70 | 34% | 103 | 1.31 | 1.38 | 1.22 | 86 |
| 5 | chart+2x+4x+8x (3 aligned) | burst 0.25 ATR | 0.25 | 3 | 1.5 | 0.5 | off | off | 43 | 77% | 44 | 1.37 | 1.57 | 1.21 | 39 |
| 6 | chart+2x+4x+8x (3 aligned) | burst 0.25 ATR | 0.25 | 3 | 1.5 | 0.5 | off | on | 43 | 77% | 44 | 1.37 | 1.57 | 1.21 | 39 |
| 7 | chart+2x+4x+8x (3 aligned) | burst 0.25 ATR | 0.25 | 3 | 1.5 | 0.5 | on | off | 43 | 77% | 44 | 1.37 | 1.57 | 1.21 | 39 |
| 8 | chart+2x+4x+8x (3 aligned) | burst 0.25 ATR | 0.25 | 3 | 1.5 | 0.5 | on | on | 43 | 77% | 44 | 1.37 | 1.57 | 1.21 | 39 |
| 9 | 2x+4x+8x (2 aligned) | burst 0.25 ATR | 0.25 | 3 | 1.5 | 0.5 | off | off | 43 | 77% | 44 | 1.37 | 1.57 | 1.21 | 39 |
| 10 | 2x+4x+8x (2 aligned) | burst 0.25 ATR | 0.25 | 3 | 1.5 | 0.5 | off | on | 43 | 77% | 44 | 1.37 | 1.57 | 1.21 | 39 |

## XAUUSD 15m  (positive cells 40%, best PF 2.15)

| # | zones | signal | dist ATR | hold | SL ATR | TP R | trail | close opp | trades | win | net | PF | PF h1 | PF h2 | max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | chart+2x+4x+8x (3 aligned) | burst 1.0 ATR | 0.25 | 0 | 3.0 | 1.0 | off | off | 43 | 67% | 377 | 2.15 | 1.95 | 2.46 | 60 |
| 2 | 2x+4x+8x (2 aligned) | burst 1.0 ATR | 0.25 | 0 | 3.0 | 1.0 | off | off | 43 | 67% | 377 | 2.15 | 1.95 | 2.46 | 60 |
| 3 | chart only | burst 0.5 ATR | 0.1 | 3 | 2.0 | 1.5 | off | on | 30 | 53% | 171 | 1.72 | 1.73 | 1.69 | 62 |
| 4 | chart+2x+4x (2 aligned) | any combo | 0.1 | 3 | 2.0 | 3.0 | off | on | 53 | 36% | 321 | 1.74 | 1.79 | 1.68 | 130 |
| 5 | chart only | burst 0.5 ATR | 0.1 | 3 | 2.0 | 1.5 | off | off | 30 | 53% | 167 | 1.68 | 1.69 | 1.68 | 64 |
| 6 | chart+2x+4x (2 aligned) | any combo | 0.1 | 3 | 2.0 | 3.0 | off | off | 53 | 36% | 327 | 1.74 | 1.83 | 1.63 | 133 |
| 7 | chart+2x+4x (2 aligned) | any combo | 0.1 | 3 | 1.5 | 3.0 | off | off | 57 | 35% | 270 | 1.69 | 1.60 | 1.82 | 106 |
| 8 | chart+2x+4x (2 aligned) | any combo | 0.25 | 3 | 2.0 | 3.0 | off | on | 50 | 38% | 296 | 1.71 | 1.80 | 1.60 | 135 |
| 9 | chart+2x+4x+8x (3 aligned) | burst 1.0 ATR | 0.25 | 0 | 3.0 | 1.0 | off | on | 45 | 62% | 287 | 1.82 | 2.03 | 1.56 | 66 |
| 10 | 2x+4x+8x (2 aligned) | burst 1.0 ATR | 0.25 | 0 | 3.0 | 1.0 | off | on | 45 | 62% | 287 | 1.82 | 2.03 | 1.56 | 66 |

## XAUUSD 30m  (positive cells 60%, best PF 2.69)

| # | zones | signal | dist ATR | hold | SL ATR | TP R | trail | close opp | trades | win | net | PF | PF h1 | PF h2 | max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | chart only | any combo | 0.25 | 3 | 2.0 | 3.0 | off | on | 31 | 55% | 444 | 2.61 | 2.86 | 2.43 | 69 |
| 2 | chart only | any combo | 0.1 | 3 | 2.0 | 3.0 | off | off | 32 | 50% | 520 | 2.69 | 2.36 | 3.20 | 77 |
| 3 | chart only | any combo | 0.1 | 3 | 3.0 | 2.0 | off | off | 31 | 52% | 484 | 2.38 | 2.19 | 2.65 | 99 |
| 4 | chart only | any combo | 0.25 | 3 | 3.0 | 2.0 | off | on | 31 | 55% | 389 | 2.18 | 2.21 | 2.15 | 97 |
| 5 | chart only | any combo | 0.25 | 3 | 2.0 | 2.0 | off | off | 32 | 50% | 415 | 2.26 | 2.42 | 2.12 | 55 |
| 6 | chart only | any combo | 0.1 | 3 | 2.0 | 3.0 | off | on | 34 | 50% | 455 | 2.45 | 2.11 | 2.90 | 71 |
| 7 | chart only | any combo | 0.25 | 3 | 1.5 | 3.0 | off | off | 32 | 47% | 456 | 2.58 | 3.29 | 2.11 | 57 |
| 8 | chart only | any combo | 0.25 | 3 | 2.0 | 2.0 | off | on | 33 | 55% | 367 | 2.22 | 2.07 | 2.35 | 51 |
| 9 | chart only | any combo | 0.25 | 3 | 3.0 | 3.0 | on | off | 44 | 77% | 310 | 2.13 | 2.17 | 2.06 | 62 |
| 10 | chart only | any combo | 0.25 | 3 | 3.0 | 2.0 | on | off | 44 | 77% | 289 | 2.05 | 2.04 | 2.06 | 62 |

## XAUUSD 60m  (positive cells 56%, best PF 2.59)

| # | zones | signal | dist ATR | hold | SL ATR | TP R | trail | close opp | trades | win | net | PF | PF h1 | PF h2 | max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | chart+2x+4x (2 aligned) | burst 0.5 ATR | 0.25 | 0 | 2.0 | 3.0 | on | on | 88 | 72% | 556 | 1.95 | 2.00 | 1.92 | 120 |
| 2 | chart+2x+4x (2 aligned) | burst 0.5 ATR | 0.1 | 0 | 3.0 | 3.0 | off | off | 52 | 46% | 668 | 2.03 | 1.91 | 2.19 | 270 |
| 3 | chart+2x+4x (2 aligned) | burst 0.5 ATR | 0.25 | 0 | 2.0 | 2.0 | on | on | 88 | 72% | 546 | 1.94 | 2.00 | 1.89 | 120 |
| 4 | chart+2x+4x (2 aligned) | burst 0.5 ATR | 0.25 | 0 | 2.0 | 3.0 | on | off | 87 | 76% | 552 | 1.95 | 2.09 | 1.85 | 107 |
| 5 | chart+2x+4x (2 aligned) | burst 0.5 ATR | 0.25 | 0 | 3.0 | 1.5 | off | off | 54 | 48% | 636 | 1.86 | 1.89 | 1.83 | 220 |
| 6 | chart+2x+4x (2 aligned) | burst 0.5 ATR | 0.25 | 0 | 2.0 | 2.0 | on | off | 87 | 76% | 541 | 1.93 | 2.09 | 1.82 | 107 |
| 7 | chart+2x+4x (2 aligned) | burst 0.5 ATR | 0.25 | 0 | 2.0 | 1.5 | on | off | 88 | 75% | 520 | 1.83 | 1.81 | 1.86 | 107 |
| 8 | chart only | any combo | 0.1 | 3 | 2.0 | 1.5 | off | off | 39 | 54% | 512 | 2.01 | 1.80 | 2.26 | 109 |
| 9 | chart only | any combo | 0.25 | 3 | 1.5 | 3.0 | off | on | 32 | 41% | 333 | 1.79 | 1.77 | 1.83 | 132 |
| 10 | chart+2x+4x (2 aligned) | burst 0.5 ATR | 0.25 | 0 | 2.0 | 1.0 | on | on | 90 | 71% | 571 | 1.95 | 2.21 | 1.75 | 79 |

## BTCUSDT 5m (MEXC)  (positive cells 25%, best PF 1.79)

| # | zones | signal | dist ATR | hold | SL ATR | TP R | trail | close opp | trades | win | net | PF | PF h1 | PF h2 | max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | chart only | burst 0.5 ATR | 0.25 | 3 | 1.5 | 3.0 | on | off | 40 | 65% | 1,865 | 1.77 | 1.89 | 1.63 | 713 |
| 2 | chart only | burst 0.5 ATR | 0.25 | 3 | 1.5 | 3.0 | on | on | 40 | 65% | 1,865 | 1.77 | 1.89 | 1.63 | 713 |
| 3 | chart only | burst 0.25 ATR | 0.25 | 3 | 3.0 | 3.0 | on | on | 59 | 76% | 2,871 | 1.76 | 1.62 | 1.89 | 1,679 |
| 4 | chart only | burst 0.5 ATR | 0.1 | 3 | 1.5 | 3.0 | on | off | 44 | 64% | 1,790 | 1.69 | 1.60 | 1.86 | 687 |
| 5 | chart only | burst 0.5 ATR | 0.1 | 3 | 1.5 | 3.0 | on | on | 44 | 64% | 1,790 | 1.69 | 1.60 | 1.86 | 687 |
| 6 | chart only | burst 0.25 ATR | 0.25 | 3 | 3.0 | 3.0 | on | off | 59 | 78% | 2,968 | 1.79 | 1.59 | 2.01 | 1,722 |
| 7 | chart only | burst 0.25 ATR | 0.25 | 3 | 3.0 | 2.0 | on | on | 59 | 76% | 2,754 | 1.73 | 1.57 | 1.88 | 1,679 |
| 8 | chart only | burst 0.25 ATR | 0.25 | 3 | 3.0 | 2.0 | on | off | 59 | 78% | 2,852 | 1.76 | 1.54 | 2.00 | 1,722 |
| 9 | chart only | burst 0.5 ATR | 0.25 | 3 | 1.5 | 2.0 | on | off | 40 | 65% | 1,228 | 1.51 | 1.49 | 1.53 | 713 |
| 10 | chart only | burst 0.5 ATR | 0.25 | 3 | 1.5 | 2.0 | on | on | 40 | 65% | 1,228 | 1.51 | 1.49 | 1.53 | 713 |

## BTCUSD 15m  (positive cells 59%, best PF 2.65)

| # | zones | signal | dist ATR | hold | SL ATR | TP R | trail | close opp | trades | win | net | PF | PF h1 | PF h2 | max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | chart+2x+4x+8x (3 aligned) | burst 1.0 ATR | 0.1 | 0 | 3.0 | 3.0 | on | on | 30 | 80% | 4,216 | 2.24 | 2.64 | 1.98 | 1,225 |
| 2 | 2x+4x+8x (2 aligned) | burst 1.0 ATR | 0.1 | 0 | 3.0 | 3.0 | on | on | 30 | 80% | 4,216 | 2.24 | 2.64 | 1.98 | 1,225 |
| 3 | chart+2x+4x+8x (3 aligned) | burst 1.0 ATR | 0.1 | 0 | 3.0 | 3.0 | on | off | 30 | 80% | 4,155 | 2.20 | 2.58 | 1.95 | 1,258 |
| 4 | 2x+4x+8x (2 aligned) | burst 1.0 ATR | 0.1 | 0 | 3.0 | 3.0 | on | off | 30 | 80% | 4,155 | 2.20 | 2.58 | 1.95 | 1,258 |
| 5 | chart+2x+4x (2 aligned) | burst 1.0 ATR | 0.1 | 0 | 1.5 | 1.5 | off | off | 43 | 60% | 6,821 | 2.32 | 1.91 | 2.77 | 877 |
| 6 | chart+2x+4x (2 aligned) | burst 1.0 ATR | 0.1 | 0 | 2.0 | 2.0 | off | on | 35 | 49% | 6,514 | 2.08 | 2.34 | 1.90 | 1,548 |
| 7 | chart+2x+4x+8x (3 aligned) | burst 1.0 ATR | 0.1 | 0 | 3.0 | 2.0 | on | on | 30 | 80% | 3,463 | 2.02 | 2.22 | 1.88 | 1,225 |
| 8 | 2x+4x+8x (2 aligned) | burst 1.0 ATR | 0.1 | 0 | 3.0 | 2.0 | on | on | 30 | 80% | 3,463 | 2.02 | 2.22 | 1.88 | 1,225 |
| 9 | chart+2x+4x (2 aligned) | burst 1.0 ATR | 0.1 | 0 | 2.0 | 2.0 | off | off | 34 | 44% | 5,629 | 1.89 | 1.90 | 1.88 | 2,111 |
| 10 | chart+2x+4x (2 aligned) | burst 1.0 ATR | 0.25 | 0 | 3.0 | 1.5 | on | off | 37 | 78% | 4,566 | 2.20 | 1.86 | 2.64 | 1,400 |

## BTCUSD 30m  (positive cells 61%, best PF 2.57)

| # | zones | signal | dist ATR | hold | SL ATR | TP R | trail | close opp | trades | win | net | PF | PF h1 | PF h2 | max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | chart only | burst 1.0 ATR | 0.1 | 0 | 2.0 | 2.0 | on | off | 37 | 73% | 7,079 | 2.30 | 2.14 | 2.44 | 942 |
| 2 | chart only | burst 1.0 ATR | 0.1 | 0 | 2.0 | 1.5 | on | off | 39 | 74% | 6,998 | 2.29 | 2.14 | 2.42 | 942 |
| 3 | chart only | burst 1.0 ATR | 0.1 | 0 | 2.0 | 3.0 | on | off | 36 | 69% | 7,062 | 2.27 | 1.88 | 2.67 | 942 |
| 4 | chart only | burst 1.0 ATR | 0.25 | 0 | 2.0 | 1.5 | on | off | 37 | 73% | 6,205 | 2.11 | 1.87 | 2.34 | 1,746 |
| 5 | chart only | burst 1.0 ATR | 0.1 | 0 | 2.0 | 1.0 | on | off | 40 | 75% | 4,988 | 1.92 | 1.81 | 2.01 | 942 |
| 6 | chart only | burst 1.0 ATR | 0.1 | 0 | 3.0 | 1.0 | off | off | 35 | 54% | 6,269 | 1.82 | 1.80 | 1.84 | 1,745 |
| 7 | chart only | burst 1.0 ATR | 0.1 | 0 | 3.0 | 1.0 | on | off | 39 | 77% | 6,864 | 2.21 | 1.78 | 2.70 | 1,291 |
| 8 | chart only | any combo | 0.1 | 3 | 2.0 | 0.5 | off | on | 30 | 70% | 2,544 | 1.78 | 1.82 | 1.75 | 780 |
| 9 | chart only | any combo | 0.1 | 3 | 2.0 | 0.5 | on | on | 30 | 70% | 2,544 | 1.78 | 1.82 | 1.75 | 780 |
| 10 | chart only | burst 1.0 ATR | 0.25 | 0 | 1.5 | 2.0 | on | off | 37 | 68% | 5,015 | 1.89 | 1.74 | 2.04 | 1,599 |

## BTCUSD 60m  (positive cells 71%, best PF 2.63)

| # | zones | signal | dist ATR | hold | SL ATR | TP R | trail | close opp | trades | win | net | PF | PF h1 | PF h2 | max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | chart+2x+4x+8x (3 aligned) | burst 0.25 ATR | 0.1 | 0 | 3.0 | 2.0 | off | off | 31 | 52% | 15,374 | 2.57 | 2.76 | 2.44 | 3,237 |
| 2 | 2x+4x+8x (2 aligned) | burst 0.25 ATR | 0.1 | 0 | 3.0 | 2.0 | off | off | 31 | 52% | 15,374 | 2.57 | 2.76 | 2.44 | 3,237 |
| 3 | chart+2x+4x+8x (3 aligned) | burst 0.25 ATR | 0.1 | 0 | 3.0 | 2.0 | off | on | 33 | 48% | 14,217 | 2.37 | 2.09 | 2.60 | 3,297 |
| 4 | 2x+4x+8x (2 aligned) | burst 0.25 ATR | 0.1 | 0 | 3.0 | 2.0 | off | on | 33 | 48% | 14,217 | 2.37 | 2.09 | 2.60 | 3,297 |
| 5 | chart+2x+4x (2 aligned) | burst 0.25 ATR | 0.1 | 0 | 3.0 | 3.0 | off | off | 43 | 42% | 14,575 | 2.46 | 1.99 | 2.95 | 4,872 |
| 6 | chart+2x+4x (2 aligned) | burst 0.25 ATR | 0.1 | 0 | 3.0 | 2.0 | off | on | 51 | 41% | 13,960 | 1.99 | 2.12 | 1.91 | 5,358 |
| 7 | chart+2x+4x+8x (3 aligned) | burst 0.25 ATR | 0.25 | 0 | 1.5 | 3.0 | on | on | 60 | 67% | 10,822 | 2.05 | 1.87 | 2.20 | 1,772 |
| 8 | 2x+4x+8x (2 aligned) | burst 0.25 ATR | 0.25 | 0 | 1.5 | 3.0 | on | on | 60 | 67% | 10,822 | 2.05 | 1.87 | 2.20 | 1,772 |
| 9 | chart+2x+4x+8x (3 aligned) | burst 0.5 ATR | 0.1 | 0 | 3.0 | 1.0 | off | off | 39 | 56% | 11,709 | 1.96 | 1.86 | 2.04 | 4,929 |
| 10 | 2x+4x+8x (2 aligned) | burst 0.5 ATR | 0.1 | 0 | 3.0 | 1.0 | off | off | 39 | 56% | 11,709 | 1.96 | 1.86 | 2.04 | 4,929 |

## SPX 1m  (positive cells 27%, best PF 2.32)

| # | zones | signal | dist ATR | hold | SL ATR | TP R | trail | close opp | trades | win | net | PF | PF h1 | PF h2 | max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | chart+2x+4x+8x (3 aligned) | burst 1.0 ATR | 0.1 | 3 | 1.0 | 3.0 | on | off | 42 | 62% | 46 | 2.23 | 2.15 | 2.36 | 11 |
| 2 | chart+2x+4x+8x (3 aligned) | burst 1.0 ATR | 0.1 | 3 | 1.0 | 3.0 | on | on | 42 | 62% | 46 | 2.23 | 2.15 | 2.36 | 11 |
| 3 | 2x+4x+8x (2 aligned) | burst 1.0 ATR | 0.1 | 3 | 1.0 | 3.0 | on | off | 42 | 62% | 46 | 2.23 | 2.15 | 2.36 | 11 |
| 4 | 2x+4x+8x (2 aligned) | burst 1.0 ATR | 0.1 | 3 | 1.0 | 3.0 | on | on | 42 | 62% | 46 | 2.23 | 2.15 | 2.36 | 11 |
| 5 | chart+2x+4x+8x (3 aligned) | burst 1.0 ATR | 0.1 | 3 | 1.0 | 1.5 | off | off | 42 | 62% | 55 | 2.31 | 2.47 | 2.11 | 14 |
| 6 | chart+2x+4x+8x (3 aligned) | burst 1.0 ATR | 0.1 | 3 | 1.0 | 1.5 | off | on | 42 | 62% | 55 | 2.31 | 2.47 | 2.11 | 14 |
| 7 | 2x+4x+8x (2 aligned) | burst 1.0 ATR | 0.1 | 3 | 1.0 | 1.5 | off | off | 42 | 62% | 55 | 2.31 | 2.47 | 2.11 | 14 |
| 8 | 2x+4x+8x (2 aligned) | burst 1.0 ATR | 0.1 | 3 | 1.0 | 1.5 | off | on | 42 | 62% | 55 | 2.31 | 2.47 | 2.11 | 14 |
| 9 | chart+2x+4x+8x (3 aligned) | burst 1.0 ATR | 0.1 | 3 | 1.0 | 2.0 | on | off | 42 | 62% | 40 | 2.06 | 2.03 | 2.11 | 13 |
| 10 | chart+2x+4x+8x (3 aligned) | burst 1.0 ATR | 0.1 | 3 | 1.0 | 2.0 | on | on | 42 | 62% | 40 | 2.06 | 2.03 | 2.11 | 13 |

## SPX 15m  (positive cells 40%, best PF 2.06)

| # | zones | signal | dist ATR | hold | SL ATR | TP R | trail | close opp | trades | win | net | PF | PF h1 | PF h2 | max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | chart only | burst 0.5 ATR | 0.25 | 3 | 3.0 | 1.5 | on | off | 46 | 83% | 344 | 1.95 | 1.79 | 2.17 | 133 |
| 2 | chart only | burst 0.5 ATR | 0.25 | 3 | 3.0 | 1.5 | on | on | 46 | 83% | 347 | 1.97 | 1.79 | 2.20 | 133 |
| 3 | chart only | burst 0.5 ATR | 0.25 | 3 | 3.0 | 0.5 | on | off | 47 | 83% | 335 | 1.93 | 1.78 | 2.13 | 125 |
| 4 | chart only | burst 0.5 ATR | 0.25 | 3 | 3.0 | 0.5 | on | on | 47 | 83% | 338 | 1.94 | 1.78 | 2.17 | 125 |
| 5 | chart only | burst 0.5 ATR | 0.25 | 3 | 3.0 | 3.0 | on | off | 46 | 83% | 341 | 1.95 | 1.77 | 2.17 | 133 |
| 6 | chart only | burst 0.5 ATR | 0.25 | 3 | 3.0 | 3.0 | on | on | 46 | 83% | 344 | 1.96 | 1.77 | 2.21 | 133 |
| 7 | chart only | burst 0.5 ATR | 0.25 | 3 | 3.0 | 1.0 | on | off | 47 | 83% | 320 | 1.89 | 1.75 | 2.07 | 133 |
| 8 | chart only | burst 0.5 ATR | 0.25 | 3 | 3.0 | 1.0 | on | on | 47 | 83% | 322 | 1.90 | 1.75 | 2.10 | 133 |
| 9 | chart only | burst 0.5 ATR | 0.25 | 3 | 3.0 | 2.0 | on | off | 46 | 83% | 313 | 1.87 | 1.66 | 2.14 | 133 |
| 10 | chart only | burst 0.5 ATR | 0.25 | 3 | 3.0 | 2.0 | on | on | 46 | 83% | 316 | 1.88 | 1.66 | 2.17 | 133 |

## SPX 30m  (positive cells 58%, best PF 2.71)

| # | zones | signal | dist ATR | hold | SL ATR | TP R | trail | close opp | trades | win | net | PF | PF h1 | PF h2 | max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | chart only | burst 0.5 ATR | 0.25 | 3 | 1.5 | 0.5 | on | off | 51 | 78% | 436 | 2.71 | 2.71 | 2.72 | 57 |
| 2 | chart+2x+4x (2 aligned) | burst 0.25 ATR | 0.25 | 3 | 1.5 | 0.5 | on | off | 65 | 83% | 413 | 2.02 | 2.01 | 2.02 | 171 |
| 3 | chart+2x+4x (2 aligned) | burst 0.25 ATR | 0.25 | 3 | 1.5 | 0.5 | on | on | 65 | 83% | 422 | 2.06 | 2.01 | 2.09 | 166 |
| 4 | chart only | burst 0.5 ATR | 0.25 | 3 | 1.5 | 1.5 | on | off | 50 | 68% | 417 | 2.03 | 2.10 | 1.97 | 65 |
| 5 | chart only | burst 0.5 ATR | 0.25 | 3 | 1.5 | 2.0 | on | off | 48 | 67% | 378 | 1.94 | 1.93 | 1.95 | 63 |
| 6 | chart only | burst 0.5 ATR | 0.25 | 3 | 1.5 | 0.5 | off | off | 51 | 78% | 259 | 2.02 | 2.23 | 1.84 | 57 |
| 7 | chart only | burst 0.25 ATR | 0.25 | 3 | 1.5 | 3.0 | on | off | 77 | 69% | 674 | 1.95 | 1.81 | 2.13 | 155 |
| 8 | chart+2x+4x (2 aligned) | burst 1.0 ATR | 0.25 | 0 | 2.0 | 1.0 | off | on | 117 | 61% | 1,508 | 1.94 | 1.80 | 2.12 | 221 |
| 9 | chart only | burst 0.5 ATR | 0.25 | 3 | 1.5 | 3.0 | on | off | 49 | 67% | 382 | 1.95 | 2.10 | 1.79 | 63 |
| 10 | chart+2x+4x (2 aligned) | burst 1.0 ATR | 0.25 | 0 | 1.0 | 1.5 | off | off | 134 | 50% | 1,004 | 1.79 | 1.80 | 1.79 | 277 |

## SPX 60m  (positive cells 66%, best PF 8.97)

| # | zones | signal | dist ATR | hold | SL ATR | TP R | trail | close opp | trades | win | net | PF | PF h1 | PF h2 | max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | chart+2x+4x (2 aligned) | burst 0.5 ATR | 0.25 | 3 | 1.0 | 0.5 | on | off | 36 | 89% | 401 | 4.96 | 4.83 | 5.09 | 35 |
| 2 | chart+2x+4x (2 aligned) | burst 0.5 ATR | 0.25 | 3 | 1.0 | 0.5 | on | on | 36 | 89% | 401 | 4.96 | 4.83 | 5.09 | 35 |
| 3 | chart+2x+4x+8x (3 aligned) | burst 0.25 ATR | 0.25 | 3 | 2.0 | 1.5 | on | off | 43 | 81% | 1,369 | 4.83 | 5.32 | 4.54 | 134 |
| 4 | chart+2x+4x+8x (3 aligned) | burst 0.25 ATR | 0.25 | 3 | 2.0 | 1.5 | on | on | 43 | 81% | 1,369 | 4.83 | 5.32 | 4.54 | 134 |
| 5 | 2x+4x+8x (2 aligned) | burst 0.25 ATR | 0.25 | 3 | 2.0 | 1.5 | on | off | 43 | 81% | 1,369 | 4.83 | 5.32 | 4.54 | 134 |
| 6 | 2x+4x+8x (2 aligned) | burst 0.25 ATR | 0.25 | 3 | 2.0 | 1.5 | on | on | 43 | 81% | 1,369 | 4.83 | 5.32 | 4.54 | 134 |
| 7 | chart only | burst 0.5 ATR | 0.25 | 3 | 1.0 | 0.5 | on | off | 39 | 90% | 423 | 4.66 | 4.96 | 4.43 | 42 |
| 8 | chart only | burst 0.5 ATR | 0.25 | 3 | 1.0 | 0.5 | on | on | 39 | 90% | 423 | 4.66 | 4.96 | 4.43 | 42 |
| 9 | chart+2x+4x (2 aligned) | burst 0.5 ATR | 0.25 | 3 | 1.5 | 0.5 | on | off | 36 | 89% | 643 | 4.41 | 4.30 | 4.50 | 58 |
| 10 | chart+2x+4x (2 aligned) | burst 0.5 ATR | 0.25 | 3 | 1.5 | 0.5 | on | on | 36 | 89% | 643 | 4.41 | 4.30 | 4.50 | 58 |
