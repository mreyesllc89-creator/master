# Gold walk-forward (first half picks, second half scores)

Latch arming, pivot levels, gold_raw costs, fixed 1 oz. Net per ounce; multiply by 100 for one lot.

## xau10: 1080 bars in-sample (2026-09-02 to 2026-09-13), 1081 bars out-of-sample (2026-09-13 to 2026-09-23)

| candidate | settings | in-sample | out-of-sample |
|---|---|---|---|
| shipped | atr 1.5 / 2.5R / BarsN 3 / buf 1.0 / tick |  64 trades, net   +87.2, PF 1.30, expR +0.14, DD 109 |  70 trades, net    +7.6, PF 1.02, expR +0.05, DD 86 |
| plateau | pct 0.5 / 2.0R / BarsN 8 / buf 0.5 / off |  15 trades, net  +233.8, PF 2.76, expR +0.71, DD 67 |  16 trades, net   +80.2, PF 1.41, expR +0.23, DD 66 |
| best | pct 0.5 / 2.5R / BarsN 8 / buf 2.0 / off |  10 trades, net  +278.9, PF 5.18, expR +1.27, DD 44 |  12 trades, net  +143.0, PF 2.09, expR +0.55, DD 65 |

Out-of-sample grid: 86% of 1043 measurable cells positive, median net +75.

## xau15: 836 bars in-sample (2026-08-28 to 2026-09-10), 836 bars out-of-sample (2026-09-10 to 2026-09-23)

| candidate | settings | in-sample | out-of-sample |
|---|---|---|---|
| shipped | atr 1.5 / 2.5R / BarsN 3 / buf 1.0 / tick |  51 trades, net   +30.9, PF 1.12, expR +0.03, DD 94 |  49 trades, net  +176.9, PF 1.97, expR +0.27, DD 45 |
| plateau | atr 3.0 / 2.0R / BarsN 3 / buf 0.5 / off |  15 trades, net  +344.1, PF 3.16, expR +0.73, DD 72 |  16 trades, net   -41.9, PF 0.86, expR -0.18, DD 97 |
| best | atr 3.0 / 3.0R / BarsN 3 / buf 2.0 / off |   5 trades, net  +484.8, PF inf, expR +2.96, DD 0 |   7 trades, net  +223.4, PF 3.66, expR +0.85, DD 51 |

Out-of-sample grid: 90% of 1022 measurable cells positive, median net +85.

## xau30: 447 bars in-sample (2026-08-27 to 2026-09-10), 448 bars out-of-sample (2026-09-10 to 2026-09-23)

| candidate | settings | in-sample | out-of-sample |
|---|---|---|---|
| shipped | atr 1.5 / 2.5R / BarsN 3 / buf 1.0 / tick |  26 trades, net   +70.9, PF 1.41, expR +0.19, DD 102 |  26 trades, net   +79.3, PF 1.65, expR +0.20, DD 36 |
| plateau | atr 1.0 / 2.5R / BarsN 3 / buf 0.5 / off |  28 trades, net  +155.6, PF 1.78, expR +0.49, DD 39 |  27 trades, net   -12.6, PF 0.95, expR -0.05, DD 68 |
| best | pct 1.0 / 2.5R / BarsN 3 / buf 2.0 / off |   6 trades, net  +284.0, PF 4.22, expR +1.05, DD 88 |   3 trades, net   +21.9, PF 1.25, expR +0.16, DD 43 |

Out-of-sample grid: 76% of 928 measurable cells positive, median net +55.

## xau60: 447 bars in-sample (2026-07-30 to 2026-08-27), 448 bars out-of-sample (2026-08-27 to 2026-09-23)

| candidate | settings | in-sample | out-of-sample |
|---|---|---|---|
| shipped | atr 1.5 / 2.5R / BarsN 3 / buf 1.0 / tick |  29 trades, net    -5.0, PF 0.98, expR -0.01, DD 130 |  26 trades, net  +186.4, PF 1.89, expR +0.27, DD 75 |
| plateau | pct 0.5 / 3.0R / BarsN 8 / buf 1.0 / bar |  16 trades, net  +262.4, PF 2.67, expR +0.76, DD 70 |  17 trades, net   -85.4, PF 0.63, expR -0.23, DD 195 |
| best | atr 3.0 / 3.0R / BarsN 8 / buf 0.5 / off |   5 trades, net  +442.1, PF 11.08, expR +1.72, DD 44 |   9 trades, net  -395.8, PF 0.08, expR -0.83, DD 428 |

Out-of-sample grid: 67% of 925 measurable cells positive, median net +45.

## xau240: 447 bars in-sample (2026-02-25 to 2026-06-10), 448 bars out-of-sample (2026-06-10 to 2026-09-23)

| candidate | settings | in-sample | out-of-sample |
|---|---|---|---|
| shipped | atr 1.5 / 2.5R / BarsN 3 / buf 1.0 / tick |  26 trades, net  +193.2, PF 1.26, expR -0.01, DD 422 |  27 trades, net  +294.0, PF 1.60, expR +0.19, DD 160 |
| plateau | atr 3.0 / 1.5R / BarsN 3 / buf 1.0 / bar |  15 trades, net +1091.0, PF 3.24, expR +0.37, DD 176 |  19 trades, net  +434.9, PF 2.04, expR +0.20, DD 130 |
| best | atr 3.0 / 1.5R / BarsN 3 / buf 1.0 / bar |  15 trades, net +1091.0, PF 3.24, expR +0.37, DD 176 |  19 trades, net  +434.9, PF 2.04, expR +0.20, DD 130 |

Out-of-sample grid: 46% of 846 measurable cells positive, median net -10.

## Summary (out-of-sample net per oz)

| tf     |   best |   plateau |   shipped |
|:-------|-------:|----------:|----------:|
| xau10  |    143 |        80 |         8 |
| xau15  |    223 |       -42 |       177 |
| xau30  |     22 |       -13 |        79 |
| xau60  |   -396 |       -85 |       186 |
| xau240 |    435 |       435 |       294 |

Positive out of sample: shipped 5/5, plateau 2/5, best 4/5
