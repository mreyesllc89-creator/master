# Tokio732_VolLab — best of 20 trend timeframes, XAUUSD and BTCUSD

Date: 2026-11-15. Same port, data, rescaling and protocol as `REPORT.md`; read its limits first.

## What was done

The EA takes its direction from an EMA pair on `MainTimeframe` / `MicroTimeframe`. For each of
the 20 MT5 timeframes M1, M2, M3, M4, M5, M6, M10, M12, M15, M20, M30, H1, H2, H3, H4, H6, H8, H12,
D1 and W1, that timeframe was fixed and the other 19 inputs were calibrated separately:
1,200 random settings scored on the in-sample years (gold 2011–2014, bitcoin 2015–2017), the 24
best checked out-of-sample (gold 2015–2018, bitcoin 2018–2019), four refined by one-input hill
climbing, and the refined candidate with the best out-of-sample score kept. All scoring uses one
evaluation per M1 close. The EMAs now run on the continuous history, so slow timeframes start
warmed up. That is 40 presets in `presets/by_timeframe/`.

The 20 timeframes are then ranked by the out-of-sample t-statistic of basket returns (mean / sd ×
√n, independent of lot size). July–August 2026 was not used for any choice.

"Typical growth" is exp(mean log growth) of a 1,000 USD account started on 1 January and 1 July
of each year and held to year end. The 2026 column is one start on the real Octa bid/ask.

## Winners

**XAUUSD: H6** — `presets/TOKIO_VolLab_XAUUSD_BEST_H6.set`
**BTCUSD: H6** — `presets/TOKIO_VolLab_BTCUSD_BEST_H6.set`

Every monthly start, 1,000 USD, held to year end (`results/best_timeframe_summary.csv`):

| Symbol | Sample | Ticks | Starts | Ruined % | Losing % | Median final | 10th pct | 90th pct | Median DD % | Worst DD % | Median, spread ×2 | Median, +0.25 slip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| XAUUSD | in | M1 close | 38 | 0 | 11 | 1,631 | 1,051 | 2,188 | 29 | 41 | 1,680 | 1,694 |
| XAUUSD | out | M1 close | 35 | 0 | 11 | 1,798 | 841 | 2,645 | 33 | 54 | 1,995 | 1,400 |
| XAUUSD | out | interpolated | 35 | 0 | 11 | 1,941 | 813 | 5,253 | 34 | 57 | 4,548 | 3,036 |
| XAUUSD | Jul–Aug 2026 | M1 close | 1 | 0 | 0 | 1,016 | | | 9 | 9 | 1,012 | 1,000 |
| BTCUSD | in | M1 close | 33 | 0 | 9 | 1,910 | 1,312 | 4,570 | 31 | 59 | 770 | 1,198 |
| BTCUSD | out | M1 close | 22 | 0 | 0 | 1,674 | 1,164 | 3,935 | 24 | 29 | 2,995 | 3,224 |
| BTCUSD | out | interpolated | 22 | 0 | 5 | 2,023 | 1,191 | 2,737 | 20 | 25 | 2,727 | 2,780 |
| BTCUSD | Jul–Aug 2026 | M1 close | 1 | 0 | 100 | 810 | | | 29 | 29 | 817 | 817 |

Per year, 1 January start, M1 close (final balance, drawdown):

| | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | Jul–Aug 2026 |
|---|---|---|---|---|---|---|---|---|---|---|
| XAUUSD H6 | 3,675 / 22 % | 1,635 / 34 % | 2,451 / 34 % | 1,444 / 41 % | 2,671 / 48 % | 2,608 / 39 % | 2,377 / 37 % | 636 / 47 % (to June) | | 1,016 / 9 % |
| BTCUSD H6 | | | | | 2,029 / 51 % | 1,437 / 46 % | 4,568 / 31 % | 3,784 / 21 % | 3,952 / 24 % | 810 / 29 % |

Comparison with the earlier single calibration (`REPORT.md`, M10 for both): gold H6 has a lower
typical result but a smaller worst drawdown out-of-sample (54 % vs 81 %) and was flat rather than
−21 % in July–August 2026. Bitcoin H6 has similar out-of-sample results with a much smaller worst
drawdown (29 % vs 51 %) but lost 19 % in July–August 2026, where the M10 preset was flat.

## Inputs of the two winners

| Input | Shipped | XAUUSD H6 | BTCUSD H6 |
|---|---|---|---|
| MainTimeframe / MicroTimeframe | M6 | H6 | H6 |
| MainFastEMA / MainSlowEMA | 20 / 50 | 13 / 26 | 11 / 48 |
| LotsWithTrend | 0.10 | 0.08 | 0.4972 |
| LotsAgainstTrend | 0.01 | 0.0001 (rounds to zero: goes flat against the trend) | 0.0006 (same) |
| CushionEnabled | true (fixed lot) | false (lot follows balance) | false |
| VolLotGamma / VolATRRef | 1.0 / 4.74 | 1.5 / 4.74 | 1.5 / 81.22 |
| MinVolFactor | 2 | 0 (always on) | 3.0 |
| CrossAboveCenter / Below | 220 / 110 | 10 / 10 | 171.4 / 171.4 |
| MinMoveBetweenOrders | 0.5 | 0.4 | 7.37 |
| NewZonesEnabled | true | false | false |
| TrailArm / Giveback / Floor USD | 50 / 2 / 1 | 18.9 / 1.3 / 3.4 | 30.2 / 2.2 / 4.6 |
| CycleLossPct | 8 | 4.4 | 2.1 |
| StopCooldownMinutes | 240 | 720 | 720 |
| EntryHourFrom / To (server) | 0 / 12 | 12 / 24 | 0 / 8 |
| MaxBasketAgeMinutes | 2880 | 360 | 5760 |

Both winners became a trend follower with a small stop: the basket holds the with-trend lot when
price is more than 10 gold-USD (bitcoin: 171 USD) from the basket centre, holds nothing against
the trend, and exits on a stop of 2–4 % of balance or a modest trailing level. The chart
timeframe does not matter: the EA works on every tick and `MainTimeframe` only sets the trend.
Run it on M5 as before. The bitcoin preset still needs the `XAUUSD` symbol check in
`CheckAccount732` relaxed.

## All 20 timeframes

### XAUUSD

| Rank | Trend TF | OOS t-stat | OOS typical growth | OOS worst DD % | OOS baskets | In-sample typical growth | Jul–Aug 2026: 1,000 USD → | 2026 DD % |
|---|---|---|---|---|---|---|---|---|
| 1 | H6 | 3.82 | ×1.85 | 48 | 1659 | ×2.01 | 1,016 | 9 |
| 2 | M10 | 3.70 | ×1.75 | 38 | 1319 | ×1.85 | 680 | 43 |
| 3 | H4 | 3.09 | ×1.45 | 46 | 1405 | ×1.75 | 684 | 38 |
| 4 | M2 | 2.97 | ×1.57 | 32 | 1065 | ×1.47 | 986 | 13 |
| 5 | D1 | 2.81 | ×1.39 | 35 | 721 | ×1.47 | 1,000 | 9 |
| 6 | M4 | 2.73 | ×1.42 | 50 | 977 | ×1.69 | 1,017 | 16 |
| 7 | H12 | 2.67 | ×1.25 | 33 | 949 | ×1.38 | 1,015 | 10 |
| 8 | M1 | 2.52 | ×1.26 | 23 | 826 | ×1.33 | 912 | 12 |
| 9 | M20 | 2.46 | ×1.18 | 24 | 592 | ×1.35 | 909 | 11 |
| 10 | M12 | 2.45 | ×1.41 | 56 | 597 | ×1.57 | 1,149 | 22 |
| 11 | H8 | 2.31 | ×1.28 | 49 | 929 | ×1.46 | 958 | 12 |
| 12 | M3 | 2.17 | ×1.22 | 30 | 1118 | ×1.67 | 1,107 | 15 |
| 13 | H1 | 2.16 | ×1.35 | 48 | 790 | ×1.63 | 937 | 21 |
| 14 | M5 | 1.88 | ×1.19 | 32 | 889 | ×1.34 | 1,048 | 9 |
| 15 | H3 | 1.87 | ×1.26 | 44 | 1090 | ×1.51 | 971 | 14 |
| 16 | M30 | 1.81 | ×1.21 | 33 | 1367 | ×1.77 | 1,052 | 14 |
| 17 | W1 | 1.37 | ×1.11 | 36 | 870 | ×1.24 | 1,000 | 0 |
| 18 | M6 | 0.86 | ×1.05 | 36 | 1366 | ×1.37 | 828 | 24 |
| 19 | M15 | 0.64 | ×1.03 | 39 | 1311 | ×1.68 | 842 | 21 |
| 20 | H2 | 0.55 | ×1.02 | 16 | 1041 | ×1.18 | 960 | 7 |

### BTCUSD

| Rank | Trend TF | OOS t-stat | OOS typical growth | OOS worst DD % | OOS baskets | In-sample typical growth | Jul–Aug 2026: 1,000 USD → | 2026 DD % |
|---|---|---|---|---|---|---|---|---|
| 1 | H6 | 3.44 | ×2.36 | 27 | 490 | ×2.38 | 810 | 29 |
| 2 | M30 | 3.39 | ×3.55 | 46 | 301 | ×3.94 | 50 | 100 |
| 3 | M12 | 3.28 | ×2.76 | 48 | 885 | ×5.62 | 1,371 | 30 |
| 4 | H1 | 3.18 | ×3.19 | 63 | 311 | ×3.67 | 2,312 | 51 |
| 5 | H2 | 2.85 | ×2.16 | 45 | 278 | ×3.38 | 860 | 62 |
| 6 | M1 | 2.79 | ×2.26 | 33 | 689 | ×2.32 | 790 | 31 |
| 7 | H8 | 2.56 | ×2.39 | 69 | 768 | ×2.88 | 995 | 28 |
| 8 | H4 | 2.52 | ×2.00 | 48 | 233 | ×2.36 | 585 | 78 |
| 9 | W1 | 2.49 | ×2.01 | 71 | 654 | ×6.58 | 1,000 | 0 |
| 10 | M3 | 2.35 | ×1.99 | 50 | 683 | ×3.72 | 2,049 | 46 |
| 11 | M5 | 2.16 | ×1.71 | 49 | 1080 | ×4.00 | 1,263 | 24 |
| 12 | M2 | 2.07 | ×1.71 | 58 | 636 | ×3.96 | 921 | 27 |
| 13 | M15 | 1.98 | ×1.65 | 65 | 1002 | ×4.89 | 1,261 | 27 |
| 14 | M4 | 1.88 | ×1.50 | 57 | 532 | ×3.60 | 926 | 27 |
| 15 | M6 | 1.63 | ×1.42 | 64 | 236 | ×3.23 | 1,390 | 37 |
| 16 | M20 | 1.48 | ×1.26 | 48 | 390 | ×2.13 | 903 | 25 |
| 17 | M10 | 0.92 | ×1.09 | 52 | 438 | ×3.69 | 657 | 48 |
| 18 | H12 | 0.79 | ×1.08 | 38 | 367 | ×3.37 | 1,261 | 13 |
| 19 | H3 | 0.67 | ×1.05 | 41 | 643 | ×2.04 | 1,198 | 11 |
| 20 | D1 | 0.34 | ×0.95 | 53 | 443 | ×2.63 | 1,499 | 11 |

## How much to trust the ranking

* The out-of-sample years were used once per timeframe to choose among four refined candidates
  and again to rank the 20 timeframes. Picking the best of 20 inflates the winner's
  out-of-sample numbers; only July–August 2026 is untouched, and it has 20–26 baskets per winner.
* The top of the gold table is close: H6, M10, H4, M2 and D1 are all within t 2.8–3.8. On bitcoin,
  M30 ranks second but was ruined in July–August 2026; M12 and H1 made money there. Neighbouring
  timeframes did not always agree (bitcoin H6 is first, H3 and H12 are near the bottom), which
  points to noise in the per-timeframe searches as much as to a real timeframe effect.
* D1 and W1 opened few or no baskets in the two-month 2026 window; their 2026 column says little.
* All limits in `REPORT.md` apply: rescaled history, no tick data, no 2019–2025 data, constant
  spread, no swaps or commission.

Next step: run `TOKIO_VolLab_XAUUSD_BEST_H6.set` and, for comparison, the M10, H4 and M2 gold
presets from `presets/by_timeframe/` in the Strategy Tester on Exness real ticks 2022–2026 at
1 ms and 189 ms, from several start months.

## Reproduce

From `tools/`, with the data as in `REPORT.md`:

```bash
TOKIO_DATA=/path/to/data python tfsweep.py XAUUSD 1200 /path/to/TOKIO_3614_T50_PREDETERMINADO.set
```

```bash
TOKIO_DATA=/path/to/data python tfsweep.py BTCUSD 1200 /path/to/TOKIO_3614_T50_PREDETERMINADO.set
```

```bash
TOKIO_DATA=/path/to/data python best_eval.py /path/to/TOKIO_3614_T50_PREDETERMINADO.set
```
