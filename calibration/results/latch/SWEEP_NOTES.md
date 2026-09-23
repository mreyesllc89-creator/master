# XPW Breakout BTCUSD calibration sweep

Variant dimensions in this sweep: arm_mode = latch, v201; levels = pivot, pivot+don20. arm_mode 'v201' cancels the stop on every bar whose close is inside the buffer (v2.01 defect F11); 'latch' arms once on the buffer and lets the stop rest (v2.10). 'pivot+don20' = nearest of confirmed pivot and prior-20-bar Donchian.

Engine: `calibration/xpw_backtest.py` (TradingView broker-emulator replica, no bar magnifier). Sizing fixed 1.0 BTC, initial capital 100000. Grid per TF: SL {pct 0.1/0.25/0.5/1.0, atr 1.0/1.5/2.0/3.0} x TP R {1,1.5,2,2.5,3} x BarsN {3,5,8} x buffer ATR {0.5,1,2} x trail {off, bar, tick} x cost {none, exchange, cfd_std, cfd_raw} = 4320 configs per TF.

## READ THIS FIRST: sample-size caveat

Each timeframe has ~600 bars (15m: 7.6 days, 30m: 12 days, 60m: 25 days, 240m: 99 days; **1m: only ~10 hours**). Most configs produce 5-40 trades. This sweep calibrates **cost and geometry sanity** (is the TP big enough to pay the spread, does the SL sit inside or outside typical noise, does the trail help or hurt at a given bar size). It does **not** prove an edge, and any single 'best' config is mostly noise. Prefer the plateau readings (neighbour-positive fraction, neighbourhood mean) over the raw best.

## Data / timing

- TF 15m: 730 bars, 17280 configs, 26.0s
- TF 30m: 596 bars, 17280 configs, 21.8s
- TF 60m: 596 bars, 17280 configs, 22.2s
- TF 240m: 596 bars, 17280 configs, 22.1s
- TF 1m: 613 bars, 17280 configs, 20.7s

## Cost geometry (median ATR, round-trip cost per 1 BTC)

Round-trip cost = 2 x commission (pct x price, or cash) + full spread + 2 x slippage. 'min TP' = TP distance at which the round trip is 20% of TP.

| TF | median close | median ATR (USD) | median ATR % | preset | RT cost USD/BTC | cost % price | cost/ATR | cost/SL(0.1%) | cost/SL(1.5 ATR) | min TP USD (cost<20%) | min TP % | min TP in ATR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | 81132 | 196.8 | 0.240 | none | 0.00 | 0.0000 | 0.000 | 0.000 | 0.000 | 0.0 | 0.000 | 0.00 |
| 15m | 81132 | 196.8 | 0.240 | exchange | 85.13 | 0.1049 | 0.433 | 1.049 | 0.288 | 425.7 | 0.525 | 2.16 |
| 15m | 81132 | 196.8 | 0.240 | cfd_std | 27.00 | 0.0333 | 0.137 | 0.333 | 0.091 | 135.0 | 0.166 | 0.69 |
| 15m | 81132 | 196.8 | 0.240 | cfd_raw | 22.00 | 0.0271 | 0.112 | 0.271 | 0.075 | 110.0 | 0.136 | 0.56 |
| 15m | 81132 | 196.8 | 0.240 | v201 | 0.61 | 0.0007 | 0.003 | 0.007 | 0.002 | 3.0 | 0.004 | 0.02 |
| 30m | 77864 | 279.7 | 0.353 | none | 0.00 | 0.0000 | 0.000 | 0.000 | 0.000 | 0.0 | 0.000 | 0.00 |
| 30m | 77864 | 279.7 | 0.353 | exchange | 81.86 | 0.1051 | 0.293 | 1.051 | 0.195 | 409.3 | 0.526 | 1.46 |
| 30m | 77864 | 279.7 | 0.353 | cfd_std | 27.00 | 0.0347 | 0.097 | 0.347 | 0.064 | 135.0 | 0.173 | 0.48 |
| 30m | 77864 | 279.7 | 0.353 | cfd_raw | 22.00 | 0.0283 | 0.079 | 0.283 | 0.052 | 110.0 | 0.141 | 0.39 |
| 30m | 77864 | 279.7 | 0.353 | v201 | 0.61 | 0.0008 | 0.002 | 0.008 | 0.001 | 3.0 | 0.004 | 0.01 |
| 60m | 78552 | 404.6 | 0.512 | none | 0.00 | 0.0000 | 0.000 | 0.000 | 0.000 | 0.0 | 0.000 | 0.00 |
| 60m | 78552 | 404.6 | 0.512 | exchange | 82.55 | 0.1051 | 0.204 | 1.051 | 0.136 | 412.8 | 0.525 | 1.02 |
| 60m | 78552 | 404.6 | 0.512 | cfd_std | 27.00 | 0.0344 | 0.067 | 0.344 | 0.044 | 135.0 | 0.172 | 0.33 |
| 60m | 78552 | 404.6 | 0.512 | cfd_raw | 22.00 | 0.0280 | 0.054 | 0.280 | 0.036 | 110.0 | 0.140 | 0.27 |
| 60m | 78552 | 404.6 | 0.512 | v201 | 0.61 | 0.0008 | 0.001 | 0.008 | 0.001 | 3.0 | 0.004 | 0.01 |
| 240m | 64546 | 721.3 | 1.031 | none | 0.00 | 0.0000 | 0.000 | 0.000 | 0.000 | 0.0 | 0.000 | 0.00 |
| 240m | 64546 | 721.3 | 1.031 | exchange | 68.55 | 0.1062 | 0.095 | 1.062 | 0.063 | 342.7 | 0.531 | 0.48 |
| 240m | 64546 | 721.3 | 1.031 | cfd_std | 27.00 | 0.0418 | 0.037 | 0.418 | 0.025 | 135.0 | 0.209 | 0.19 |
| 240m | 64546 | 721.3 | 1.031 | cfd_raw | 22.00 | 0.0341 | 0.031 | 0.341 | 0.020 | 110.0 | 0.170 | 0.15 |
| 240m | 64546 | 721.3 | 1.031 | v201 | 0.61 | 0.0009 | 0.001 | 0.009 | 0.001 | 3.0 | 0.005 | 0.00 |
| 1m | 85480 | 44.0 | 0.052 | none | 0.00 | 0.0000 | 0.000 | 0.000 | 0.000 | 0.0 | 0.000 | 0.00 |
| 1m | 85480 | 44.0 | 0.052 | exchange | 89.48 | 0.1047 | 2.032 | 1.047 | 1.354 | 447.4 | 0.523 | 10.16 |
| 1m | 85480 | 44.0 | 0.052 | cfd_std | 27.00 | 0.0316 | 0.613 | 0.316 | 0.409 | 135.0 | 0.158 | 3.07 |
| 1m | 85480 | 44.0 | 0.052 | cfd_raw | 22.00 | 0.0257 | 0.499 | 0.257 | 0.333 | 110.0 | 0.129 | 2.50 |
| 1m | 85480 | 44.0 | 0.052 | v201 | 0.61 | 0.0007 | 0.014 | 0.007 | 0.009 | 3.0 | 0.004 | 0.07 |

## Parity vs TradingView ('Trail' column non-null = TV in position)

The TV export was evidently NOT run at the v2.01 header defaults. From the Trail column: initial trail = avg x 0.999 (SL 0.1% confirmed), implied entry = stop level +/- 0.30 in most episodes (30-tick slippage confirmed), every trail ratchet step has (close - trail)/ATR = 1.900 on every TF (ATR replica confirmed to 3 decimals; trail distance was 1.9 ATR, not 1.5), and positions were held through bars exceeding a 0.25% TP but never a 0.5% one (TP was 0.5%, not 0.25%). Both variants are compared below.

| TF | variant | bars | TV bars in pos | engine bars in pos | overlap | Jaccard | recall of TV | TV episodes | engine episodes | identical episodes | TV fills at level+/-slip | median |trail diff| | max |trail diff| |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | v201_defaults | 730 | 22 | 15 | 11 | 0.42 | 0.50 | 12 | 12 | 8 | 10/12 | 0.00 | 42.6 |
| 15m | tv_inferred | 730 | 22 | 29 | 22 | 0.76 | 1.00 | 12 | 14 | 11 | 10/12 | 0.00 | 42.6 |
| 30m | v201_defaults | 596 | 14 | 8 | 8 | 0.57 | 0.57 | 8 | 5 | 5 | 8/8 | 0.00 | 34.7 |
| 30m | tv_inferred | 596 | 14 | 14 | 14 | 1.00 | 1.00 | 8 | 8 | 8 | 8/8 | 0.00 | 0.4 |
| 60m | v201_defaults | 596 | 2 | 1 | 1 | 0.50 | 0.50 | 2 | 1 | 1 | 2/2 | 0.00 | 0.0 |
| 60m | tv_inferred | 596 | 2 | 4 | 2 | 0.50 | 1.00 | 2 | 4 | 2 | 2/2 | 0.00 | 0.0 |
| 240m | v201_defaults | 596 | 4 | 4 | 3 | 0.60 | 0.75 | 4 | 4 | 3 | 4/4 | 0.00 | 0.0 |
| 240m | tv_inferred | 596 | 4 | 5 | 4 | 0.80 | 1.00 | 4 | 5 | 4 | 4/4 | 0.00 | 0.0 |
| 1m | v201_defaults | 613 | 72 | 57 | 56 | 0.77 | 0.78 | 10 | 10 | 5 | 9/10 | 0.00 | 55.9 |
| 1m | tv_inferred | 613 | 72 | 72 | 71 | 0.97 | 0.99 | 10 | 10 | 8 | 9/10 | 0.00 | 43.6 |

Remaining differences: (a) a few TV fills sit at the bar close + slippage rather than at the stop level (15m bars 129 and 275), and a few TV episodes are absent where the engine holds through the fill bar (15m 542, 687; 240m 248) - both are consistent with TradingView having used bar magnifier (intrabar path different from the OHLC assumption); (b) TV's ATR/pivot history starts before the CSV window (swingH/swingL are seeded from the first CSV row in parity mode, ATR is seeded inside the window); (c) the 1m file is ~10 hours. Perfect parity is not expected and is not claimed; the held-bar trail values match to <1e-6 where both hold, which is the part that matters for calibrating geometry. Episode ranges are printed by `python3 xpw_backtest.py parity`.

## Sub-bar geometry is an emulator artefact, not evidence

Without bar magnifier the emulator assumes the intrabar path open-low-high-close (or open-high-low-close). After a buy-stop fills on the way up, the assumed path always continues to the bar high BEFORE it can revisit the stop, so any TP that sits inside the bar's remaining range is 'hit' first. A 0.1% SL / 0.25% TP on bars whose ATR is 0.24% (15m) to 1.0% (240m) therefore resolves inside the fill bar almost every time (v2.01 baseline: 0.1-0.9 bars held, 100% same-bar exits on 240m) and the win rate is a property of the path assumption. TradingView shows the same artefact without bar magnifier; the TV export (evidently WITH bar magnifier) already disagreed with the OHLC path on 3 of 34 fill bars. Configs with more than 50% same-bar exits are therefore reported (column 'same-bar %') but excluded from the recommendation picks. The 'exchange' preset also shows the true cost picture for that geometry: ~$85 round trip against an $80 SL and $200 TP.

## v2.01 gold defaults on BTCUSD (SL 0.1%, TP 0.25% = 2.5R, BarsN 5, buffer 1.0 ATR, trail bar)

**v2.01 baseline by cost preset**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## Recommendations

### TF 15m, preset cfd_std

- configs: 4320, with >= 15 trades: 3171, net positive: 3090, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 321, eligible (positive, enough trades, measurable): 2086, max trades any config: 122
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | cfd_std | pct | 1.0 | 3.0 | 3 | 0.5 | bar | 31 | 58 | 7700 | 810 | 6890 | 0.05 | 2.47 | 0.27 | 2415 | 15.8 | 0 | 6/16/74/3 | 1.00 | 5684 |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | cfd_std | pct | 1.0 | 3.0 | 3 | 0.5 | bar | 31 | 58 | 7700 | 810 | 6890 | 0.05 | 2.47 | 0.27 | 2415 | 15.8 | 0 | 6/16/74/3 | 1.00 | 5684 |
| 15 | cfd_std | atr | 3.0 | 2.5 | 3 | 0.5 | bar | 32 | 62 | 7560 | 824 | 6737 | 0.06 | 2.72 | 0.37 | 2159 | 15.4 | 0 | 9/16/72/3 | 1.00 | 5636 |
| 15 | cfd_std | pct | 1.0 | 2.5 | 5 | 0.5 | bar | 31 | 61 | 7343 | 810 | 6533 | 0.06 | 2.70 | 0.26 | 1359 | 14.5 | 0 | 6/13/77/3 | 1.00 | 5626 |
| 15 | cfd_std | pct | 1.0 | 2.5 | 8 | 0.5 | bar | 28 | 71 | 7524 | 729 | 6795 | 0.05 | 2.84 | 0.30 | 1190 | 15.1 | 0 | 7/14/75/4 | 1.00 | 5617 |
| 15 | cfd_std | pct | 1.0 | 3.0 | 5 | 0.5 | bar | 31 | 58 | 7627 | 810 | 6817 | 0.05 | 2.74 | 0.27 | 1359 | 14.5 | 0 | 6/13/77/3 | 1.00 | 5545 |

### TF 15m, preset exchange

- configs: 4320, with >= 15 trades: 3156, net positive: 1528, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 318, eligible (positive, enough trades, measurable): 776, max trades any config: 122
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | exchange | pct | 1.0 | 3.0 | 3 | 0.5 | bar | 33 | 48 | 8822 | 2811 | 6011 | 0.17 | 2.22 | 0.22 | 2928 | 14.6 | 0 | 6/12/79/3 | 1.00 | 4161 |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | exchange | pct | 1.0 | 3.0 | 3 | 0.5 | bar | 33 | 48 | 8822 | 2811 | 6011 | 0.17 | 2.22 | 0.22 | 2928 | 14.6 | 0 | 6/12/79/3 | 1.00 | 4161 |
| 15 | exchange | pct | 1.0 | 2.5 | 3 | 0.5 | bar | 33 | 48 | 8024 | 2810 | 5213 | 0.18 | 2.06 | 0.19 | 2928 | 14.6 | 0 | 6/12/79/3 | 1.00 | 3908 |
| 15 | exchange | atr | 3.0 | 2.5 | 3 | 0.5 | bar | 34 | 50 | 7907 | 2892 | 5015 | 0.21 | 2.15 | 0.24 | 2671 | 14.2 | 0 | 9/12/76/3 | 1.00 | 3790 |
| 15 | exchange | atr | 3.0 | 3.0 | 3 | 0.5 | bar | 34 | 50 | 8642 | 2893 | 5749 | 0.20 | 2.32 | 0.29 | 2671 | 14.3 | 0 | 9/12/76/3 | 1.00 | 3640 |
| 15 | exchange | pct | 1.0 | 2.0 | 3 | 0.5 | bar | 33 | 48 | 7536 | 2808 | 4728 | 0.19 | 1.96 | 0.17 | 2928 | 14.5 | 0 | 9/12/76/3 | 1.00 | 3524 |

### TF 30m, preset cfd_std

- configs: 4320, with >= 15 trades: 3020, net positive: 2690, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 663, eligible (positive, enough trades, measurable): 1600, max trades any config: 101
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | cfd_std | atr | 3.0 | 3.0 | 3 | 0.5 | bar | 21 | 57 | 7573 | 540 | 7033 | 0.04 | 2.73 | 0.36 | 2542 | 17.8 | 0 | 10/29/62/0 | 1.00 | 5143 |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | cfd_std | atr | 3.0 | 3.0 | 3 | 0.5 | bar | 21 | 57 | 7573 | 540 | 7033 | 0.04 | 2.73 | 0.36 | 2542 | 17.8 | 0 | 10/29/62/0 | 1.00 | 5143 |
| 30 | cfd_std | pct | 1.0 | 2.0 | 8 | 0.5 | bar | 24 | 58 | 9694 | 540 | 9154 | 0.03 | 2.75 | 0.47 | 3061 | 12.5 | 8 | 33/25/38/4 | 1.00 | 4865 |
| 30 | cfd_std | pct | 1.0 | 2.0 | 8 | 0.5 | bar | 17 | 71 | 8790 | 378 | 8412 | 0.03 | 4.34 | 0.62 | 1540 | 15.2 | 6 | 35/18/47/0 | 1.00 | 4858 |
| 30 | cfd_std | atr | 3.0 | 2.5 | 3 | 0.5 | bar | 21 | 57 | 7504 | 526 | 6978 | 0.03 | 2.72 | 0.35 | 2542 | 17.7 | 5 | 14/29/57/0 | 1.00 | 4715 |
| 30 | cfd_std | pct | 1.0 | 3.0 | 8 | 0.5 | bar | 16 | 69 | 7056 | 405 | 6651 | 0.03 | 3.64 | 0.52 | 1540 | 17.9 | 0 | 12/19/69/0 | 1.00 | 4638 |

### TF 30m, preset exchange

- configs: 4320, with >= 15 trades: 3035, net positive: 1106, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 666, eligible (positive, enough trades, measurable): 713, max trades any config: 101
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | exchange | atr | 3.0 | 3.0 | 8 | 0.5 | bar | 17 | 53 | 7919 | 1412 | 6507 | 0.11 | 3.26 | 0.46 | 2151 | 15.8 | 0 | 12/12/76/0 | 1.00 | 4512 |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | exchange | atr | 3.0 | 3.0 | 8 | 0.5 | bar | 17 | 53 | 7919 | 1412 | 6507 | 0.11 | 3.26 | 0.46 | 2151 | 15.8 | 0 | 12/12/76/0 | 1.00 | 4512 |
| 30 | exchange | atr | 3.0 | 2.5 | 8 | 0.5 | bar | 17 | 53 | 7993 | 1407 | 6586 | 0.11 | 3.29 | 0.54 | 2151 | 15.5 | 0 | 24/12/65/0 | 1.00 | 4405 |
| 30 | exchange | atr | 3.0 | 3.0 | 8 | 1.0 | bar | 17 | 41 | 5799 | 1412 | 4387 | 0.13 | 2.25 | 0.28 | 1925 | 13.2 | 0 | 12/24/65/0 | 1.00 | 4065 |
| 30 | exchange | atr | 3.0 | 3.0 | 8 | 0.5 | tick | 22 | 64 | 7525 | 1831 | 5694 | 0.15 | 2.98 | 0.38 | 2508 | 8.6 | 5 | 9/9/82/0 | 0.83 | 4017 |
| 30 | exchange | atr | 3.0 | 3.0 | 8 | 0.5 | bar | 17 | 53 | 7074 | 1410 | 5664 | 0.10 | 2.42 | 0.42 | 3335 | 13.7 | 6 | 12/18/71/0 | 1.00 | 3974 |

### TF 60m, preset cfd_std

- configs: 4320, with >= 15 trades: 3195, net positive: 2699, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 1196, eligible (positive, enough trades, measurable): 1711, max trades any config: 105
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | cfd_std | atr | 3.0 | 3.0 | 8 | 1.0 | tick | 32 | 66 | 10497 | 837 | 9660 | 0.04 | 2.44 | 0.23 | 3371 | 8.3 | 0 | 6/19/75/0 | 1.00 | 6910 |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | cfd_std | atr | 3.0 | 3.0 | 8 | 1.0 | tick | 32 | 66 | 10497 | 837 | 9660 | 0.04 | 2.44 | 0.23 | 3371 | 8.3 | 0 | 6/19/75/0 | 1.00 | 6910 |
| 60 | cfd_std | atr | 3.0 | 3.0 | 5 | 1.0 | tick | 30 | 60 | 10659 | 770 | 9889 | 0.03 | 2.46 | 0.25 | 3620 | 9.3 | 0 | 10/20/67/3 | 0.88 | 6831 |
| 60 | cfd_std | atr | 3.0 | 3.0 | 5 | 0.5 | tick | 30 | 60 | 11111 | 770 | 10341 | 0.03 | 2.41 | 0.28 | 2913 | 11.8 | 0 | 10/17/73/0 | 0.86 | 6542 |
| 60 | cfd_std | atr | 3.0 | 2.5 | 8 | 1.0 | tick | 32 | 66 | 9914 | 824 | 9090 | 0.04 | 2.35 | 0.22 | 3371 | 8.2 | 0 | 9/19/72/0 | 1.00 | 6432 |
| 60 | cfd_std | atr | 3.0 | 2.5 | 5 | 0.5 | tick | 34 | 56 | 10076 | 878 | 9198 | 0.04 | 2.26 | 0.18 | 2913 | 8.4 | 0 | 9/18/74/0 | 0.88 | 6239 |

### TF 60m, preset exchange

- configs: 4320, with >= 15 trades: 3192, net positive: 1481, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 1196, eligible (positive, enough trades, measurable): 1051, max trades any config: 105
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | exchange | atr | 3.0 | 3.0 | 3 | 1.0 | tick | 30 | 60 | 10744 | 2498 | 8247 | 0.10 | 2.07 | 0.20 | 3909 | 10.4 | 0 | 10/20/67/3 | 0.86 | 5436 |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | exchange | atr | 3.0 | 3.0 | 3 | 1.0 | tick | 30 | 60 | 10744 | 2498 | 8247 | 0.10 | 2.07 | 0.20 | 3909 | 10.4 | 0 | 10/20/67/3 | 0.86 | 5436 |
| 60 | exchange | atr | 3.0 | 3.0 | 5 | 1.0 | tick | 31 | 52 | 11642 | 2578 | 9065 | 0.11 | 2.38 | 0.21 | 4060 | 8.7 | 0 | 10/16/71/3 | 0.88 | 5352 |
| 60 | exchange | atr | 3.0 | 3.0 | 8 | 1.0 | tick | 32 | 59 | 10405 | 2663 | 7741 | 0.11 | 2.04 | 0.17 | 3867 | 8.3 | 0 | 6/19/75/0 | 1.00 | 5336 |
| 60 | exchange | atr | 3.0 | 3.0 | 3 | 1.0 | tick | 17 | 53 | 7133 | 1407 | 5726 | 0.10 | 2.50 | 0.26 | 2866 | 5.8 | 6 | 12/18/65/6 | 0.86 | 5226 |
| 60 | exchange | atr | 3.0 | 3.0 | 5 | 0.5 | tick | 31 | 45 | 11897 | 2576 | 9321 | 0.11 | 2.31 | 0.24 | 2764 | 10.9 | 0 | 10/13/77/0 | 0.86 | 5203 |

### TF 240m, preset cfd_std

- configs: 4320, with >= 15 trades: 3264, net positive: 2455, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 1323, eligible (positive, enough trades, measurable): 978, max trades any config: 122
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 240 | cfd_std | pct | 0.5 | 2.0 | 3 | 2.0 | tick | 46 | 57 | 11768 | 891 | 10877 | 0.04 | 2.51 | 0.67 | 1237 | 1.0 | 50 | 57/41/2/0 | 0.88 | 7688 |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 240 | cfd_std | pct | 0.5 | 2.0 | 3 | 2.0 | tick | 46 | 57 | 11768 | 891 | 10877 | 0.04 | 2.51 | 0.67 | 1237 | 1.0 | 50 | 57/41/2/0 | 0.88 | 7688 |
| 240 | cfd_std | pct | 0.5 | 2.0 | 3 | 2.0 | off | 46 | 57 | 11576 | 891 | 10685 | 0.04 | 2.45 | 0.66 | 1237 | 1.0 | 50 | 57/43/0/0 | 0.88 | 7607 |
| 240 | cfd_std | pct | 0.5 | 3.0 | 3 | 0.5 | tick | 57 | 37 | 10269 | 1269 | 9000 | 0.04 | 1.79 | 0.46 | 2242 | 2.1 | 28 | 35/53/12/0 | 1.00 | 7595 |
| 240 | cfd_std | pct | 0.5 | 2.0 | 3 | 1.0 | tick | 64 | 47 | 9939 | 1323 | 8616 | 0.04 | 1.73 | 0.39 | 2246 | 1.0 | 48 | 47/50/3/0 | 1.00 | 7534 |
| 240 | cfd_std | pct | 0.5 | 2.0 | 3 | 2.0 | tick | 41 | 59 | 11416 | 783 | 10633 | 0.03 | 2.77 | 0.74 | 1237 | 1.1 | 49 | 59/39/2/0 | 0.88 | 7520 |

### TF 240m, preset exchange

- configs: 4320, with >= 15 trades: 3261, net positive: 1953, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 1323, eligible (positive, enough trades, measurable): 712, max trades any config: 122
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 240 | exchange | pct | 0.5 | 2.0 | 3 | 2.0 | tick | 41 | 61 | 11928 | 2982 | 8947 | 0.13 | 2.32 | 0.62 | 1429 | 1.0 | 49 | 61/39/0/0 | 0.88 | 5429 |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 240 | exchange | pct | 0.5 | 2.0 | 3 | 2.0 | tick | 41 | 61 | 11928 | 2982 | 8947 | 0.13 | 2.32 | 0.62 | 1429 | 1.0 | 49 | 61/39/0/0 | 0.88 | 5429 |
| 240 | exchange | pct | 0.5 | 2.0 | 3 | 2.0 | tick | 46 | 59 | 12257 | 3359 | 8898 | 0.13 | 2.10 | 0.56 | 1429 | 1.0 | 50 | 59/41/0/0 | 0.88 | 5395 |
| 240 | exchange | pct | 0.5 | 2.0 | 3 | 2.0 | off | 46 | 59 | 12257 | 3359 | 8898 | 0.13 | 2.10 | 0.56 | 1429 | 1.0 | 50 | 59/41/0/0 | 0.88 | 5333 |
| 240 | exchange | pct | 0.5 | 2.0 | 3 | 2.0 | off | 41 | 61 | 11928 | 2982 | 8947 | 0.13 | 2.32 | 0.62 | 1429 | 1.0 | 49 | 61/39/0/0 | 0.88 | 5288 |
| 240 | exchange | pct | 0.5 | 2.0 | 3 | 2.0 | bar | 46 | 59 | 12257 | 3359 | 8898 | 0.13 | 2.10 | 0.56 | 1429 | 1.0 | 50 | 59/41/0/0 | 0.88 | 5220 |

### TF 1m, preset cfd_std

- configs: 4320, with >= 15 trades: 2209, net positive: 2476, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 0, eligible (positive, enough trades, measurable): 1187, max trades any config: 70
- verdict: **plateau pick**  (1m file is ~10 hours; ignore for calibration)

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cfd_std | pct | 1.0 | 3.0 | 5 | 0.5 | bar | 18 | 89 | 3324 | 486 | 2838 | 0.15 | 92.81 | 0.18 | 24 | 17.4 | 0 | 0/0/94/6 | 1.00 | 2274 |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cfd_std | pct | 1.0 | 3.0 | 5 | 0.5 | bar | 18 | 89 | 3324 | 486 | 2838 | 0.15 | 92.81 | 0.18 | 24 | 17.4 | 0 | 0/0/94/6 | 1.00 | 2274 |
| 1 | cfd_std | pct | 1.0 | 2.0 | 5 | 0.5 | bar | 18 | 89 | 3324 | 486 | 2838 | 0.15 | 92.81 | 0.18 | 24 | 17.4 | 0 | 0/0/94/6 | 1.00 | 2203 |
| 1 | cfd_std | pct | 1.0 | 2.5 | 5 | 0.5 | bar | 18 | 89 | 3324 | 486 | 2838 | 0.15 | 92.81 | 0.18 | 24 | 17.4 | 0 | 0/0/94/6 | 1.00 | 2161 |
| 1 | cfd_std | pct | 1.0 | 1.5 | 5 | 0.5 | bar | 18 | 89 | 3380 | 472 | 2907 | 0.14 | 95.06 | 0.19 | 24 | 17.3 | 0 | 6/0/89/6 | 1.00 | 2106 |
| 1 | cfd_std | pct | 0.5 | 3.0 | 5 | 0.5 | bar | 18 | 89 | 3380 | 472 | 2907 | 0.14 | 95.06 | 0.38 | 24 | 17.3 | 0 | 6/0/89/6 | 0.88 | 1999 |

### TF 1m, preset exchange

- configs: 4320, with >= 15 trades: 2352, net positive: 776, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 0, eligible (positive, enough trades, measurable): 85, max trades any config: 69
- verdict: **plateau pick**  (1m file is ~10 hours; ignore for calibration)

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | exchange | pct | 1.0 | 3.0 | 5 | 0.5 | bar | 20 | 65 | 3376 | 1782 | 1594 | 0.52 | 4.27 | 0.09 | 219 | 13.8 | 0 | 0/0/95/5 | 1.00 | 1220 |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | exchange | pct | 1.0 | 3.0 | 5 | 0.5 | bar | 20 | 65 | 3376 | 1782 | 1594 | 0.52 | 4.27 | 0.09 | 219 | 13.8 | 0 | 0/0/95/5 | 1.00 | 1220 |
| 1 | exchange | pct | 1.0 | 2.0 | 5 | 0.5 | bar | 20 | 65 | 3376 | 1782 | 1594 | 0.52 | 4.27 | 0.09 | 219 | 13.8 | 0 | 0/0/95/5 | 1.00 | 1118 |
| 1 | exchange | pct | 1.0 | 2.5 | 5 | 0.5 | bar | 20 | 65 | 3376 | 1782 | 1594 | 0.52 | 4.27 | 0.09 | 219 | 13.8 | 0 | 0/0/95/5 | 1.00 | 1087 |
| 1 | exchange | pct | 1.0 | 1.5 | 5 | 0.5 | bar | 21 | 62 | 3374 | 1868 | 1505 | 0.54 | 3.42 | 0.08 | 219 | 13.0 | 0 | 5/0/90/5 | 1.00 | 975 |
| 1 | exchange | pct | 1.0 | 3.0 | 8 | 0.5 | tick | 19 | 53 | 2245 | 1690 | 555 | 0.69 | 1.87 | 0.03 | 327 | 13.4 | 0 | 0/0/100/0 | 1.00 | 894 |

## Marginal views (mean net over all other grid dims, all TFs except 1m)

**by trail**

| cost | trail | mean net | positive frac | mean trades | mean exp R |
|---|---|---|---|---|---|
| cfd_raw | bar | 601 | 0.65 | 26.4 | 0.171 |
| cfd_raw | off | 281 | 0.62 | 23.5 | 0.162 |
| cfd_raw | tick | 1100 | 0.68 | 28.4 | 0.184 |
| cfd_std | bar | 561 | 0.63 | 26.4 | 0.166 |
| cfd_std | off | 202 | 0.61 | 23.6 | 0.152 |
| cfd_std | tick | 1017 | 0.66 | 28.4 | 0.176 |
| exchange | bar | -1008 | 0.36 | 26.4 | -0.069 |
| exchange | off | -1102 | 0.36 | 23.4 | -0.073 |
| exchange | tick | -590 | 0.33 | 28.4 | -0.055 |
| none | bar | 1133 | 0.71 | 26.4 | 0.245 |
| none | off | 764 | 0.68 | 23.4 | 0.237 |
| none | tick | 1722 | 0.76 | 28.3 | 0.260 |

**by sl_mode**

| cost | sl_mode | mean net | positive frac | mean trades | mean exp R |
|---|---|---|---|---|---|
| cfd_raw | atr | -97 | 0.54 | 21.8 | 0.046 |
| cfd_raw | pct | 1418 | 0.76 | 30.4 | 0.299 |
| cfd_std | atr | -172 | 0.52 | 21.9 | 0.039 |
| cfd_std | pct | 1359 | 0.74 | 30.4 | 0.291 |
| exchange | atr | -1346 | 0.34 | 21.8 | -0.085 |
| exchange | pct | -454 | 0.36 | 30.4 | -0.046 |
| none | atr | 382 | 0.61 | 21.7 | 0.095 |
| none | pct | 2031 | 0.82 | 30.3 | 0.400 |

**by sl_value**

| cost | sl_value | mean net | positive frac | mean trades | mean exp R |
|---|---|---|---|---|---|
| cfd_raw | 0.1 | 1916 | 0.95 | 41.2 | 0.678 |
| cfd_raw | 0.25 | 1827 | 0.85 | 34.3 | 0.361 |
| cfd_raw | 0.5 | 916 | 0.62 | 26.8 | 0.128 |
| cfd_raw | 1.0 | 579 | 0.56 | 23.7 | 0.048 |
| cfd_raw | 1.5 | -339 | 0.53 | 23.1 | 0.040 |
| cfd_raw | 2.0 | 129 | 0.57 | 19.7 | 0.059 |
| cfd_raw | 3.0 | -326 | 0.54 | 16.3 | 0.019 |
| cfd_std | 0.1 | 1895 | 0.94 | 41.2 | 0.664 |
| cfd_std | 0.25 | 1774 | 0.83 | 34.3 | 0.353 |
| cfd_std | 0.5 | 829 | 0.60 | 26.8 | 0.120 |
| cfd_std | 1.0 | 477 | 0.54 | 23.9 | 0.040 |
| cfd_std | 1.5 | -418 | 0.51 | 23.1 | 0.030 |
| cfd_std | 2.0 | 96 | 0.56 | 19.7 | 0.053 |
| cfd_std | 3.0 | -382 | 0.53 | 16.3 | 0.017 |
| exchange | 0.1 | -667 | 0.26 | 41.2 | -0.140 |
| exchange | 0.25 | -312 | 0.37 | 34.3 | 0.033 |
| exchange | 0.5 | -686 | 0.36 | 26.7 | -0.030 |
| exchange | 1.0 | -784 | 0.36 | 23.7 | -0.093 |
| exchange | 1.5 | -1736 | 0.29 | 23.0 | -0.105 |
| exchange | 2.0 | -1095 | 0.38 | 19.8 | -0.056 |
| exchange | 3.0 | -1135 | 0.42 | 16.3 | -0.044 |
| none | 0.1 | 2603 | 0.97 | 41.2 | 0.895 |
| none | 0.25 | 2405 | 0.92 | 34.3 | 0.448 |
| none | 0.5 | 1518 | 0.73 | 26.6 | 0.186 |
| none | 1.0 | 1201 | 0.67 | 23.6 | 0.111 |
| none | 1.5 | 90 | 0.58 | 23.0 | 0.087 |
| none | 2.0 | 479 | 0.61 | 19.8 | 0.088 |
| none | 3.0 | 154 | 0.59 | 16.3 | 0.051 |

**by tp_r**

| cost | tp_r | mean net | positive frac | mean trades | mean exp R |
|---|---|---|---|---|---|
| cfd_raw | 1.0 | 589 | 0.66 | 28.3 | 0.114 |
| cfd_raw | 1.5 | 512 | 0.65 | 26.7 | 0.147 |
| cfd_raw | 2.0 | 532 | 0.62 | 25.8 | 0.162 |
| cfd_raw | 2.5 | 703 | 0.65 | 25.1 | 0.197 |
| cfd_raw | 3.0 | 964 | 0.67 | 24.7 | 0.244 |
| cfd_std | 1.0 | 557 | 0.65 | 28.3 | 0.111 |
| cfd_std | 1.5 | 468 | 0.64 | 26.8 | 0.142 |
| cfd_std | 2.0 | 466 | 0.60 | 25.8 | 0.154 |
| cfd_std | 2.5 | 587 | 0.62 | 25.2 | 0.184 |
| cfd_std | 3.0 | 890 | 0.65 | 24.7 | 0.233 |
| exchange | 1.0 | -1115 | 0.28 | 28.2 | -0.127 |
| exchange | 1.5 | -1074 | 0.33 | 26.7 | -0.090 |
| exchange | 2.0 | -1001 | 0.34 | 25.8 | -0.078 |
| exchange | 2.5 | -809 | 0.38 | 25.1 | -0.043 |
| exchange | 3.0 | -500 | 0.42 | 24.6 | 0.008 |
| none | 1.0 | 1176 | 0.74 | 28.2 | 0.187 |
| none | 1.5 | 1088 | 0.72 | 26.6 | 0.224 |
| none | 2.0 | 1060 | 0.69 | 25.7 | 0.233 |
| none | 2.5 | 1219 | 0.70 | 25.1 | 0.271 |
| none | 3.0 | 1489 | 0.72 | 24.6 | 0.321 |

**by barsN**

| cost | barsN | mean net | positive frac | mean trades | mean exp R |
|---|---|---|---|---|---|
| cfd_raw | 3 | 692 | 0.66 | 29.4 | 0.173 |
| cfd_raw | 5 | 726 | 0.66 | 25.4 | 0.195 |
| cfd_raw | 8 | 563 | 0.63 | 23.6 | 0.150 |
| cfd_std | 3 | 621 | 0.64 | 29.4 | 0.166 |
| cfd_std | 5 | 661 | 0.64 | 25.4 | 0.189 |
| cfd_std | 8 | 498 | 0.61 | 23.6 | 0.139 |
| exchange | 3 | -1043 | 0.36 | 29.3 | -0.064 |
| exchange | 5 | -818 | 0.36 | 25.4 | -0.044 |
| exchange | 8 | -839 | 0.33 | 23.6 | -0.090 |
| none | 3 | 1327 | 0.72 | 29.3 | 0.244 |
| none | 5 | 1213 | 0.73 | 25.3 | 0.265 |
| none | 8 | 1079 | 0.70 | 23.5 | 0.232 |

**by buf_atr**

| cost | buf_atr | mean net | positive frac | mean trades | mean exp R |
|---|---|---|---|---|---|
| cfd_raw | 0.5 | 1011 | 0.72 | 37.9 | 0.162 |
| cfd_raw | 1.0 | 995 | 0.70 | 26.3 | 0.198 |
| cfd_raw | 2.0 | -25 | 0.53 | 14.1 | 0.157 |
| cfd_std | 0.5 | 912 | 0.69 | 38.0 | 0.155 |
| cfd_std | 1.0 | 922 | 0.68 | 26.3 | 0.191 |
| cfd_std | 2.0 | -53 | 0.52 | 14.1 | 0.147 |
| exchange | 0.5 | -1237 | 0.35 | 37.9 | -0.073 |
| exchange | 1.0 | -593 | 0.39 | 26.3 | -0.041 |
| exchange | 2.0 | -870 | 0.31 | 14.1 | -0.085 |
| none | 0.5 | 1816 | 0.80 | 37.8 | 0.239 |
| none | 1.0 | 1540 | 0.77 | 26.3 | 0.273 |
| none | 2.0 | 263 | 0.57 | 14.1 | 0.228 |

## Caveats

- ~600 bars per TF; the 1m file covers ~10 hours. Nothing here is statistically significant; treat as cost/geometry sanity only.
- Emulator replica without bar magnifier: intrabar ordering is an assumption (open-low-high-close / open-high-low-close). Same-bar entry+exit is guesswork on both sides.
- Tick-mode trail is an approximation (ratchet at 4 path nodes per bar with the previous bar's ATR), not a true tick replay.
- ATR is seeded inside the CSV window (SMA of first 14 TRs); TradingView's ATR has longer history. Pivots start unseeded in the sweep (first ~2*BarsN bars untradable).
- Costs: spread is applied as half-spread on every stop/market fill, none on TP limit fills; slippage per side on stop/market fills. Commission on both sides. 'gross' = P&L at ideal fills (stop level / open / TP price); 'cost' = commission + spread + slippage actually paid; net = gross - cost.
- Open position at end of data is closed at the last close (market, with slippage) and tagged 'end'.
- Fixed 1.0 BTC sizing; equity effects of risk sizing are not in the sweep (engine supports --sizing risk).
