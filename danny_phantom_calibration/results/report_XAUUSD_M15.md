# XAUUSD_M15 — individual backtest report

Preset `presets/DPFX_XAUUSD_M15_calibrated.set`, chart XAUUSD M15, spread model **modern**, $10,000 start, 1 % risk per trade, Python replica of the EA (see REPORT.md for the method).

## Segment 2011-2018 (2011-05-10 → 2018-06-19)

| Metric | Value |
|---|---|
| Trades | 561 |
| Trades per year | 79.1 |
| Net profit | $15,814 (158 %) |
| CAGR | 14.3 % |
| Profit factor | 1.54 |
| Win rate | 61.5 % |
| Average trade | $28.19 (+0.175 R) |
| Average win / loss | $131.22 / $-136.37 |
| Largest win / loss | $817.37 / $-265.10 |
| Max drawdown | 7.8 % ($1,405) |
| Longest losing streak | 7 |
| Average bars held | 24.7 |
| Long / short trades | 287 / 274 |
| Long / short net | $6,416 / $9,398 |
| Sharpe (per-trade, annualised) | 1.65 |

### By year

| Year | Trades | Net | Win % | Avg R | Sample |
|---|---|---|---|---|---|
| 2011 | 45 | $-414 | 51 | -0.09 | in-sample |
| 2012 | 74 | $2,853 | 65 | +0.36 | in-sample |
| 2013 | 131 | $4,149 | 62 | +0.22 | in-sample |
| 2014 | 101 | $1,710 | 59 | +0.10 | in-sample |
| 2015 | 101 | $3,380 | 61 | +0.18 | in-sample |
| 2016 | 52 | $3,830 | 77 | +0.33 | out-of-sample |
| 2017 | 35 | $1,003 | 60 | +0.11 | out-of-sample |
| 2018 | 22 | $-696 | 45 | -0.15 | out-of-sample |

### By month

58 of 82 months profitable; worst month $-716, best $1,366.

### By exit reason

| Exit | Trades | Net | Avg R |
|---|---|---|---|
| blackout close | 46 | $-597 | -0.09 |
| reversal | 8 | $-964 | -0.68 |
| stop | 495 | $17,125 | +0.21 |
| target | 1 | $817 | +8.00 |
| time stop | 11 | $-567 | -0.25 |

### Last 15 trades

| entry_time          | exit_time           | side   |   bars_held |   pnl_usd |   r_multiple | exit           |   equity | segment   |
|:--------------------|:--------------------|:-------|------------:|----------:|-------------:|:---------------|---------:|:----------|
| 2018-04-11 14:45:00 | 2018-04-11 15:45:00 | long   |           4 |    192.21 |        0.711 | stop           |  27219.2 | 2011-2018 |
| 2018-04-24 16:15:00 | 2018-04-25 05:15:00 | long   |          44 |   -243.92 |       -1     | stop           |  26975.3 | 2011-2018 |
| 2018-04-26 12:45:00 | 2018-04-26 14:00:00 | long   |           5 |   -215.42 |       -1     | stop           |  26759.8 | 2011-2018 |
| 2018-04-26 14:15:00 | 2018-04-26 18:30:00 | short  |          17 |    119.11 |        0.445 | stop           |  26879   | 2011-2018 |
| 2018-04-30 14:45:00 | 2018-04-30 17:15:00 | short  |          10 |   -244.22 |       -1     | stop           |  26634.7 | 2011-2018 |
| 2018-05-01 14:30:00 | 2018-05-01 16:00:00 | short  |           6 |   -232.69 |       -1     | stop           |  26402   | 2011-2018 |
| 2018-05-15 12:45:00 | 2018-05-15 14:00:00 | short  |           5 |    214.11 |        0.878 | stop           |  26616.2 | 2011-2018 |
| 2018-05-24 15:15:00 | 2018-05-25 18:15:00 | long   |         100 |   -102.82 |       -0.496 | time stop      |  26513.3 | 2011-2018 |
| 2018-05-29 08:30:00 | 2018-05-29 12:15:00 | long   |          15 |   -232.82 |       -1     | stop           |  26280.5 | 2011-2018 |
| 2018-06-05 15:30:00 | 2018-06-05 18:45:00 | long   |          13 |      0    |        0     | stop           |  26280.5 | 2011-2018 |
| 2018-06-07 20:00:00 | 2018-06-08 08:15:00 | short  |          41 |   -152.56 |       -1     | stop           |  26128   | 2011-2018 |
| 2018-06-13 18:15:00 | 2018-06-13 18:45:00 | short  |           2 |   -170.99 |       -1     | stop           |  25957   | 2011-2018 |
| 2018-06-13 19:30:00 | 2018-06-14 07:15:00 | long   |          39 |     93.95 |        0.362 | stop           |  26050.9 | 2011-2018 |
| 2018-06-14 12:15:00 | 2018-06-14 13:00:00 | long   |           3 |   -197.33 |       -1     | stop           |  25853.6 | 2011-2018 |
| 2018-06-15 15:30:00 | 2018-06-15 20:45:00 | short  |          21 |    -39.61 |       -0.153 | blackout close |  25814   | 2011-2018 |

## Segment 2026 (2026-07-01 → 2026-08-31)

0 trade(s) only.

## Files

Full trade list: `results/trades_XAUUSD_M15.csv`; equity chart: `results/report_XAUUSD_M15.png`.