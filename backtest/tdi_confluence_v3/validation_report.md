**Verdict: NOT PASSED: edge not significant at the 98% level**

| Test | p | Pass mark | Result |
|---|---|---|---|
| T1a: profit, month-clustered t-test | 0.875262 | < 0.02 | fail |
| T1b: profit, 6-month-block t-test | 0.811355 | < 0.02 | fail |
| T2: beats random entry timing | 0.891212 | < 0.02 | fail |
| T3: long/short calls carry information | 0.926681 | < 0.02 | fail |
| T4: consistent without any single year (worst p) | 0.9408 | < 0.05 | fail |
| Realistic execution: T1a / T1b | 0.9831 / 0.9459 | < 0.02 | fail |

98% one-sided bounds on the average: above -78.1 bp and below +22.3 bp per trade (month-clustered).

Months without trading (stale prices, Amendment 1): 2017-08, 2017-09, 2017-10, 2017-11.

### Primary test: BTCUSDT, unseen history

| Cost per side | Trades | Win % | Avg bp/trade | Profit factor | Month-clustered t / p | 6-month-clustered t / p | Bootstrap p (as first registered) |
|---|---|---|---|---|---|---|---|
| 0.00% | 626 | 46 | -23.9 | 0.90 | -0.99 / 0.8383 | -0.78 / 0.7761 | 0.8370 |
| 0.02% | 626 | 46 | -27.9 | 0.88 | -1.16 / 0.8753 | -0.91 / 0.8114 | 0.8765 |
| 0.05% | 626 | 46 | -33.9 | 0.86 | -1.41 / 0.9188 | -1.11 / 0.8566 | 0.9214 |
| 0.10% | 626 | 45 | -43.9 | 0.82 | -1.83 / 0.9643 | -1.44 / 0.9131 | 0.9689 |
| Realistic execution | 626 | 46 | -52.9 | 0.79 | -2.16 / 0.9831 | -1.73 / 0.9459 | 0.9878 |
| Without the stale-price exclusion | 666 | 46 | -31.1 | 0.87 | -1.33 / 0.9062 | -1.24 / 0.8816 | 0.9127 |
| Shorts dropped before 2019-09-13 | 551 | 47 | -17.2 | 0.93 | -0.71 / 0.7603 | -0.68 / 0.7468 | 0.7579 |

In R (return ÷ stop distance): 626 trades, average -0.076 R, month-clustered p 0.9552, 6-month p 0.9339.
Month boundaries shifted by 0–29 days: month-clustered p between 0.8633 and 0.8902 (median 0.8728).

- **Random timing (T2):** 10000 runs with 681 trades each on average (real: 626); their average +2.0 bp vs the rule's -27.9 bp. Verdict statistic: month-clustered t -1.24, p = 0.8912. Permutation p-values, reported only (not the verdict, see Amendment 1): on the trade-level t 0.9036 (9036 runs reached it), on the raw average 0.9258 (9258 runs).
- **Shuffled long/short labels (T3):** 10000 runs with 685 trades each on average (real: 626); their average +7.3 bp vs the rule's -27.9 bp. Verdict statistic: month-clustered t -1.47, p = 0.9267. Permutation p-values, reported only (not the verdict, see Amendment 1): on the trade-level t 0.9400 (9400 runs reached it), on the raw average 0.9473 (9473 runs).
- **Risk:** worst drawdown 26672 bp of one position's notional, worst trade -2279 bp.
- **Power, each test alone:** an edge of about 71 bp would pass T1a, and about 96 bp T1b, 80% of the time on this data (67 bp if trades were independent). The full verdict needs all five tests and has lower power (Amendment 1, 8.5).

| Year | Trades | Win % | Avg bp/trade | Total bp | Without this year: avg bp / month-clustered p (T4) |
|---|---|---|---|---|---|
| 2017 | 12 | 50 | +46.5 | +559 | -29.3 / 0.883 |
| 2018 | 76 | 32 | -224.1 | -17034 | -0.8 / 0.514 |
| 2019 | 79 | 44 | +21.9 | +1730 | -35.1 / 0.907 |
| 2020 | 75 | 48 | -45.2 | -3391 | -25.5 / 0.831 |
| 2021 | 107 | 51 | +9.5 | +1012 | -35.6 / 0.908 |
| 2022 | 100 | 54 | +40.5 | +4047 | -40.9 / 0.941 |
| 2023 | 85 | 36 | -49.1 | -4178 | -24.5 / 0.815 |
| 2024 | 92 | 49 | -2.2 | -204 | -32.3 / 0.882 |

| Side | Trades | Win % | Avg bp/trade | Profit factor | Month-clustered t / p | 6-month-clustered t / p | Bootstrap p (as first registered) |
|---|---|---|---|---|---|---|---|
| Long | 305 | 46 | -10.4 | 0.96 | -0.29 / 0.6147 | -0.29 / 0.6112 | 0.6053 |
| Short | 321 | 45 | -44.5 | 0.80 | -1.56 / 0.9388 | -1.31 / 0.8928 | 0.9417 |

### Neighbours on the same unseen BTC data (descriptive)

| Change from the frozen rule | Trades | Win % | Avg bp/trade | Profit factor | Month-clustered t / p | 6-month-clustered t / p | Bootstrap p (as first registered) |
|---|---|---|---|---|---|---|---|
| none (frozen rule) | 626 | 46 | -27.9 | 0.88 | -1.16 / 0.8753 | -0.91 / 0.8114 | 0.8765 |
| pivot 3 | 670 | 48 | +4.3 | 1.02 | +0.19 / 0.4234 | +0.13 / 0.4510 | 0.4377 |
| pivot 4 | 653 | 48 | -15.6 | 0.93 | -0.74 / 0.7701 | -0.67 / 0.7423 | 0.7724 |
| pivot 6 | 569 | 44 | -42.6 | 0.84 | -1.74 / 0.9575 | -2.28 / 0.9799 | 0.9621 |
| pivot 8 | 548 | 44 | -16.5 | 0.93 | -0.63 / 0.7335 | -0.68 / 0.7470 | 0.7340 |
| swing 10-120 | 457 | 42 | -37.0 | 0.86 | -1.38 / 0.9151 | -1.43 / 0.9113 | 0.9165 |
| levels off | 1109 | 49 | -20.7 | 0.89 | -1.39 / 0.9161 | -1.50 / 0.9216 | 0.9214 |
| levels 38/62 | 488 | 43 | -23.3 | 0.91 | -0.75 / 0.7723 | -0.68 / 0.7470 | 0.7690 |
| levels 45/55 | 694 | 47 | -39.7 | 0.83 | -1.88 / 0.9681 | -1.41 / 0.9084 | 0.9720 |
| day start 00:00 | 664 | 48 | -29.5 | 0.87 | -1.17 / 0.8767 | -1.19 / 0.8730 | 0.8779 |
| day start 12:00 | 634 | 47 | -29.3 | 0.88 | -1.14 / 0.8717 | -0.81 / 0.7849 | 0.8720 |
| day start 14:00 | 606 | 46 | -30.7 | 0.87 | -1.15 / 0.8738 | -1.17 / 0.8693 | 0.8739 |
| stop 3xATR(60m) TP 2R | 762 | 40 | -17.9 | 0.90 | -1.06 / 0.8542 | -0.86 / 0.7967 | 0.8544 |
| stop 8xATR(60m) TP 3R | 533 | 53 | -48.2 | 0.83 | -1.50 / 0.9308 | -1.09 / 0.8530 | 0.9354 |
| stop 5xATR(240m) TP 2R | 500 | 56 | -45.9 | 0.84 | -1.33 / 0.9063 | -0.98 / 0.8263 | 0.9083 |

1 of 14 neighbours have a positive average. Pre-set reading: **isolated peak** (a plateau needs at least 9).

### Other coins (surviving large caps; supporting only, same calendar period as the BTC test)

| Coin, before 2024-11 | Trades | Win % | Avg bp/trade | Profit factor | Month-clustered t / p | 6-month-clustered t / p | Bootstrap p (as first registered) | Random timing p |
|---|---|---|---|---|---|---|---|---|
| ETHUSDT | 626 | 44 | -35.6 | 0.88 | -1.40 / 0.9176 | -2.17 / 0.9753 | 0.9226 | 0.9334 |
| BNBUSDT | 656 | 47 | -42.1 | 0.86 | -1.66 / 0.9497 | -2.84 / 0.9930 | 0.9556 | 0.9426 |
| SOLUSDT | 421 | 51 | +31.8 | 1.08 | +0.65 / 0.2595 | +0.74 / 0.2427 | 0.2603 | 0.2078 |
| XRPUSDT | 548 | 54 | +49.8 | 1.17 | +1.42 / 0.0800 | +1.56 / 0.0725 | 0.0770 | 0.0757 |
| DOGEUSDT | 316 | 44 | -124.8 | 0.71 | -2.42 / 0.9902 | -2.85 / 0.9876 | 0.9941 | 0.9867 |
| ADAUSDT | 517 | 51 | +35.9 | 1.12 | +0.88 / 0.1915 | +0.72 / 0.2437 | 0.1914 | 0.1978 |
| **All 6 pooled** | 3084 | 49 | -9.8 | 0.97 | -0.61 / 0.7278 | -1.12 / 0.8580 | 0.7272 | – |

Pooled: 3 of 6 coins positive, equal-weight average -14.2 bp, in R -0.019 (p 0.8351). Pre-set reading: **BTC-only or no edge** (pooled month-clustered p = 0.7278, 6-month p = 0.8580). Correlation of monthly results with BTC: 0.02.

| Coin, 2024-11 → 2026-11 (descriptive) | Trades | Win % | Avg bp/trade | Profit factor | Month-clustered t / p | 6-month-clustered t / p | Bootstrap p (as first registered) |
|---|---|---|---|---|---|---|---|
| ETHUSDT | 189 | 49 | -7.4 | 0.97 | -0.17 / 0.5659 | -0.17 / 0.5636 | 0.5789 |
| BNBUSDT | 243 | 52 | +3.8 | 1.03 | +0.14 / 0.4465 | +0.19 / 0.4306 | 0.4462 |
| SOLUSDT | 230 | 53 | +42.9 | 1.19 | +0.97 / 0.1713 | +0.92 / 0.2052 | 0.1658 |
| XRPUSDT | 218 | 52 | +14.1 | 1.06 | +0.33 / 0.3728 | +0.31 / 0.3873 | 0.3710 |
| DOGEUSDT | 215 | 53 | +56.3 | 1.23 | +1.48 / 0.0763 | +1.99 / 0.0584 | 0.0659 |
| ADAUSDT | 206 | 53 | +24.5 | 1.08 | +0.46 / 0.3256 | +0.39 / 0.3569 | 0.3076 |
| **All 6 pooled** | 1301 | 52 | +22.8 | 1.10 | +1.25 / 0.1125 | +1.60 / 0.0920 | 0.1041 |

*Run: commit `a51780cbfbf4`, started 2026-11-13T23:41:22.333873+00:00, finished 2026-11-13T23:49:51.004393+00:00; python 3.13.18, numpy 2.5.3, pandas 3.0.5, numba 0.68.1.*
