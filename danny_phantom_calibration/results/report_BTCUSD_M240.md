# BTCUSD_M240 — individual backtest report

Preset `presets/DPFX_BTCUSD_M240_calibrated.set`, chart BTCUSD M240, spread model **modern**, $10,000 start, 1 % risk per trade, Python replica of the EA (see REPORT.md for the method).

## Segment 2015-2019 (2014-12-31 → 2019-12-31)

| Metric | Value |
|---|---|
| Trades | 1103 |
| Trades per year | 221.4 |
| Net profit | $58,473 (585 %) |
| CAGR | 47.1 % |
| Profit factor | 1.61 |
| Win rate | 39.3 % |
| Average trade | $53.01 (+0.180 R) |
| Average win / loss | $356.28 / $-142.98 |
| Largest win / loss | $2,470.90 / $-709.73 |
| Max drawdown | 8.1 % ($4,613) |
| Longest losing streak | 12 |
| Average bars held | 5.6 |
| Long / short trades | 592 / 511 |
| Long / short net | $36,502 / $21,971 |
| Sharpe (per-trade, annualised) | 2.2 |

### By year

| Year | Trades | Net | Win % | Avg R | Sample |
|---|---|---|---|---|---|
| 2015 | 209 | $2,521 | 35 | +0.11 | in-sample |
| 2016 | 176 | $7,993 | 40 | +0.29 | in-sample |
| 2017 | 225 | $21,058 | 45 | +0.32 | in-sample |
| 2018 | 229 | $14,450 | 39 | +0.13 | out-of-sample |
| 2019 | 264 | $12,452 | 38 | +0.08 | out-of-sample |

### By month

48 of 58 months profitable; worst month $-2,430, best $4,016.

### By exit reason

| Exit | Trades | Net | Avg R |
|---|---|---|---|
| blackout close | 215 | $13,654 | +0.21 |
| end of data | 1 | $651 | +0.96 |
| reversal | 508 | $-21,259 | -0.13 |
| stop | 222 | $-40,818 | -0.47 |
| target | 150 | $103,991 | +2.11 |
| time stop | 7 | $2,254 | +1.04 |

### Last 15 trades

| entry_time          | exit_time           | side   |   bars_held |   pnl_usd |   r_multiple | exit           |   equity | segment   |
|:--------------------|:--------------------|:-------|------------:|----------:|-------------:|:---------------|---------:|:----------|
| 2019-12-11 14:00:00 | 2019-12-12 10:00:00 | short  |           5 |     27.03 |        0.04  | reversal       |  67767.2 | 2015-2019 |
| 2019-12-12 10:00:00 | 2019-12-13 22:00:00 | long   |           9 |    303.48 |        0.448 | blackout close |  68070.7 | 2015-2019 |
| 2019-12-16 02:00:00 | 2019-12-16 10:00:00 | short  |           2 |   -370.44 |       -0.544 | reversal       |  67700.2 | 2015-2019 |
| 2019-12-16 10:00:00 | 2019-12-16 18:00:00 | long   |           2 |   -676.93 |       -1     | stop           |  67023.3 | 2015-2019 |
| 2019-12-16 18:00:00 | 2019-12-18 10:00:00 | short  |          10 |   1340.21 |        2     | target         |  68363.5 | 2015-2019 |
| 2019-12-18 14:00:00 | 2019-12-18 22:00:00 | long   |           2 |   1367.06 |        2     | target         |  69730.6 | 2015-2019 |
| 2019-12-19 18:00:00 | 2019-12-20 02:00:00 | long   |           2 |   -152.05 |       -0.218 | reversal       |  69578.5 | 2015-2019 |
| 2019-12-20 02:00:00 | 2019-12-20 18:00:00 | short  |           4 |   -290.28 |       -0.417 | reversal       |  69288.3 | 2015-2019 |
| 2019-12-20 18:00:00 | 2019-12-20 22:00:00 | long   |           1 |   -159.1  |       -0.23  | blackout close |  69129.2 | 2015-2019 |
| 2019-12-23 06:00:00 | 2019-12-24 06:00:00 | short  |           6 |    542.4  |        0.785 | reversal       |  69671.6 | 2015-2019 |
| 2019-12-24 06:00:00 | 2019-12-24 14:00:00 | long   |           2 |   -348.12 |       -0.5   | reversal       |  69323.4 | 2015-2019 |
| 2019-12-24 14:00:00 | 2019-12-26 14:00:00 | short  |          12 |   -280.63 |       -0.405 | stop           |  69042.8 | 2015-2019 |
| 2019-12-26 14:00:00 | 2019-12-26 22:00:00 | long   |           2 |   -690.43 |       -1     | stop           |  68352.4 | 2015-2019 |
| 2019-12-27 06:00:00 | 2019-12-27 22:00:00 | short  |           4 |   -529.51 |       -0.775 | blackout close |  67822.9 | 2015-2019 |
| 2019-12-30 06:00:00 | 2019-12-31 22:00:00 | short  |          10 |    650.59 |        0.959 | end of data    |  68473.5 | 2015-2019 |

## Segment 2026 (2026-07-01 → 2026-08-31)

| Metric | Value |
|---|---|
| Trades | 37 |
| Trades per year | 245.7 |
| Net profit | $418 (4 %) |
| CAGR | 31.3 % |
| Profit factor | 1.38 |
| Win rate | 43.2 % |
| Average trade | $11.30 (+0.119 R) |
| Average win / loss | $95.82 / $-53.09 |
| Largest win / loss | $404.21 / $-103.20 |
| Max drawdown | 3.9 % ($403) |
| Longest losing streak | 3 |
| Average bars held | 5.5 |
| Long / short trades | 18 / 19 |
| Long / short net | $552 / $-134 |
| Sharpe (per-trade, annualised) | 1.69 |

### By month

2 of 2 months profitable; worst month $96, best $323.

| Month | Trades | Net |
|---|---|---|
| 2026-07 | 17 | $323 |
| 2026-08 | 20 | $96 |

### By exit reason

| Exit | Trades | Net | Avg R |
|---|---|---|---|
| blackout close | 8 | $308 | +0.39 |
| end of data | 1 | $-29 | -0.28 |
| reversal | 14 | $-233 | -0.16 |
| stop | 9 | $-678 | -0.74 |
| target | 4 | $1,006 | +2.53 |
| time stop | 1 | $44 | +0.43 |

### Last 15 trades

| entry_time          | exit_time           | side   |   bars_held |   pnl_usd |   r_multiple | exit           |   equity |   segment |
|:--------------------|:--------------------|:-------|------------:|----------:|-------------:|:---------------|---------:|----------:|
| 2026-08-10 09:00:00 | 2026-08-11 09:00:00 | short  |           6 |     74.89 |        0.745 | reversal       | 10176.5  |      2026 |
| 2026-08-11 09:00:00 | 2026-08-11 13:00:00 | long   |           1 |   -101.21 |       -1     | stop           | 10075.3  |      2026 |
| 2026-08-11 13:00:00 | 2026-08-12 01:00:00 | short  |           3 |    -30.45 |       -0.303 | reversal       | 10044.8  |      2026 |
| 2026-08-12 01:00:00 | 2026-08-13 13:00:00 | long   |           9 |    -65.82 |       -0.656 | stop           |  9979.02 |      2026 |
| 2026-08-13 13:00:00 | 2026-08-15 13:00:00 | short  |           8 |      4.94 |        0.05  | blackout close |  9983.96 |      2026 |
| 2026-08-17 01:00:00 | 2026-08-18 13:00:00 | long   |           9 |    198.64 |        2     | target         | 10182.6  |      2026 |
| 2026-08-18 13:00:00 | 2026-08-19 01:00:00 | long   |           3 |    -56.14 |       -0.556 | reversal       | 10126.5  |      2026 |
| 2026-08-19 01:00:00 | 2026-08-19 13:00:00 | short  |           3 |   -100.88 |       -1     | stop           | 10025.6  |      2026 |
| 2026-08-19 13:00:00 | 2026-08-21 13:00:00 | long   |           7 |    404.21 |        4.116 | target         | 10429.8  |      2026 |
| 2026-08-21 17:00:00 | 2026-08-21 21:00:00 | long   |           1 |     11.37 |        0.11  | blackout close | 10441.2  |      2026 |
| 2026-08-24 09:00:00 | 2026-08-25 09:00:00 | long   |           6 |      0    |        0     | stop           | 10441.2  |      2026 |
| 2026-08-25 17:00:00 | 2026-08-27 05:00:00 | short  |           9 |    -61.61 |       -0.592 | reversal       | 10379.5  |      2026 |
| 2026-08-27 05:00:00 | 2026-08-28 05:00:00 | long   |           6 |    -13.61 |       -0.132 | reversal       | 10365.9  |      2026 |
| 2026-08-28 05:00:00 | 2026-08-28 21:00:00 | short  |           4 |     81.08 |        0.799 | blackout close | 10447    |      2026 |
| 2026-08-31 09:00:00 | 2026-08-31 13:00:00 | short  |           1 |    -28.83 |       -0.278 | end of data    | 10418.2  |      2026 |

## Files

Full trade list: `results/trades_BTCUSD_M240.csv`; equity chart: `results/report_BTCUSD_M240.png`.