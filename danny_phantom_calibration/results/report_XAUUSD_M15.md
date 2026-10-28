# XAUUSD_M15 — individual backtest report

Preset `presets/DPFX_XAUUSD_M15_calibrated.set`, chart XAUUSD M15, spread model **modern**, $10,000 start, 1 % risk per trade, Python replica of the EA (see REPORT.md for the method).

## Segment 2011-2018 (2011-05-10 → 2018-06-19)

| Metric | Value |
|---|---|
| Trades | 561 |
| Trades per year | 79.0 |
| Net profit | $15,725 (157 %) |
| CAGR | 14.2 % |
| Profit factor | 1.54 |
| Win rate | 61.5 % |
| Average trade | $28.03 (+0.175 R) |
| Average win / loss | $130.20 / $-135.15 |
| Largest win / loss | $815.25 / $-261.34 |
| Max drawdown | 8.0 % ($1,147) |
| Longest losing streak | 7 |
| Average bars held | 23.8 |
| Long / short trades | 287 / 274 |
| Long / short net | $6,170 / $9,555 |
| Sharpe (per-trade, annualised) | 1.66 |

### By year

| Year | Trades | Net | Win % | Avg R | Sample |
|---|---|---|---|---|---|
| 2011 | 45 | $-439 | 51 | -0.10 | in-sample |
| 2012 | 74 | $2,835 | 64 | +0.36 | in-sample |
| 2013 | 131 | $4,206 | 63 | +0.23 | in-sample |
| 2014 | 101 | $1,541 | 59 | +0.09 | in-sample |
| 2015 | 101 | $3,329 | 61 | +0.17 | in-sample |
| 2016 | 52 | $3,608 | 73 | +0.32 | out-of-sample |
| 2017 | 35 | $1,054 | 60 | +0.11 | out-of-sample |
| 2018 | 22 | $-409 | 55 | -0.08 | out-of-sample |

### By month

57 of 82 months profitable; worst month $-716, best $1,364.

### By exit reason

| Exit | Trades | Net | Avg R |
|---|---|---|---|
| blackout close | 46 | $-549 | -0.09 |
| reversal | 8 | $-963 | -0.68 |
| stop | 496 | $16,814 | +0.21 |
| target | 1 | $815 | +8.00 |
| time stop | 10 | $-391 | -0.20 |

### Last 15 trades

| entry_time          | exit_time           | side   |   bars_held |   pnl_usd |   r_multiple | exit           |   equity | segment   |
|:--------------------|:--------------------|:-------|------------:|----------:|-------------:|:---------------|---------:|:----------|
| 2018-04-11 15:00:00 | 2018-04-11 15:45:00 | long   |           3 |    189.88 |        0.713 | stop           |  26833.5 | 2011-2018 |
| 2018-04-24 16:30:00 | 2018-04-25 05:15:00 | long   |          43 |   -243.92 |       -1     | stop           |  26589.6 | 2011-2018 |
| 2018-04-26 13:00:00 | 2018-04-26 14:00:00 | long   |           4 |   -215.42 |       -1     | stop           |  26374.2 | 2011-2018 |
| 2018-04-26 14:30:00 | 2018-04-26 18:30:00 | short  |          16 |    113.69 |        0.431 | stop           |  26487.8 | 2011-2018 |
| 2018-04-30 15:00:00 | 2018-04-30 17:15:00 | short  |           9 |   -244.22 |       -1     | stop           |  26243.6 | 2011-2018 |
| 2018-05-01 14:45:00 | 2018-05-01 16:15:00 | short  |           6 |   -232.69 |       -1     | stop           |  26010.9 | 2011-2018 |
| 2018-05-15 13:00:00 | 2018-05-15 14:00:00 | short  |           4 |    213.41 |        0.876 | stop           |  26224.3 | 2011-2018 |
| 2018-05-24 15:30:00 | 2018-05-25 18:45:00 | long   |         101 |   -104.5  |       -0.504 | time stop      |  26119.8 | 2011-2018 |
| 2018-05-29 08:45:00 | 2018-05-29 12:15:00 | long   |          14 |   -232.82 |       -1     | stop           |  25887   | 2011-2018 |
| 2018-06-05 15:45:00 | 2018-06-05 18:45:00 | long   |          12 |      0    |        0     | stop           |  25887   | 2011-2018 |
| 2018-06-07 20:15:00 | 2018-06-08 05:30:00 | short  |          29 |     71.71 |        0.47  | stop           |  25958.7 | 2011-2018 |
| 2018-06-13 18:30:00 | 2018-06-13 18:45:00 | short  |           1 |   -170.99 |       -1     | stop           |  25787.7 | 2011-2018 |
| 2018-06-13 19:45:00 | 2018-06-14 07:15:00 | long   |          38 |     95.97 |        0.372 | stop           |  25883.7 | 2011-2018 |
| 2018-06-14 12:30:00 | 2018-06-14 13:00:00 | long   |           2 |   -197.33 |       -1     | stop           |  25686.4 | 2011-2018 |
| 2018-06-15 15:45:00 | 2018-06-17 22:00:00 | short  |          21 |     38.69 |        0.151 | blackout close |  25725.1 | 2011-2018 |

## Segment 2026 (2026-07-01 → 2026-08-31)

0 trade(s) only.

## Files

Full trade list: `results/trades_XAUUSD_M15.csv`; equity chart: `results/report_XAUUSD_M15.png`.