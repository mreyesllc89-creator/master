# XPW Breakout BTCUSD calibration sweep

Engine: `calibration/xpw_backtest.py` (TradingView broker-emulator replica, no bar magnifier). Sizing fixed 1.0 BTC, initial capital 100000. Grid per TF: SL {pct 0.1/0.25/0.5/1.0, atr 1.0/1.5/2.0/3.0} x TP R {1,1.5,2,2.5,3} x BarsN {3,5,8} x buffer ATR {0.5,1,2} x trail {off, bar, tick} x cost {none, exchange, cfd_std, cfd_raw} = 4320 configs per TF.

## READ THIS FIRST: sample-size caveat

Each timeframe has ~600 bars (15m: 7.6 days, 30m: 12 days, 60m: 25 days, 240m: 99 days; **1m: only ~10 hours**). Most configs produce 5-40 trades. This sweep calibrates **cost and geometry sanity** (is the TP big enough to pay the spread, does the SL sit inside or outside typical noise, does the trail help or hurt at a given bar size). It does **not** prove an edge, and any single 'best' config is mostly noise. Prefer the plateau readings (neighbour-positive fraction, neighbourhood mean) over the raw best.

## Data / timing

- TF 15m: 730 bars, 4320 configs, 3.7s
- TF 30m: 596 bars, 4320 configs, 2.9s
- TF 60m: 596 bars, 4320 configs, 2.8s
- TF 240m: 596 bars, 4320 configs, 3.0s
- TF 1m: 613 bars, 4320 configs, 3.2s

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
| 15 | none | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 19 | 47 | 1026 | 0 | 1026 | 0.00 | 2.27 | 0.66 | 345 | 0.8 | 37 | 47/53/0/0 | - | - |
| 15 | exchange | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 19 | 47 | 1050 | 1596 | -546 | 0.61 | 0.67 | -0.36 | 698 | 0.8 | 37 | 47/53/0/0 | - | - |
| 15 | cfd_std | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 19 | 47 | 1188 | 392 | 796 | 0.15 | 1.82 | 0.51 | 399 | 0.9 | 37 | 47/53/0/0 | - | - |
| 15 | cfd_raw | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 19 | 47 | 1122 | 346 | 776 | 0.13 | 1.81 | 0.49 | 401 | 0.7 | 37 | 47/53/0/0 | - | - |
| 30 | none | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 18 | 50 | 1048 | 0 | 1048 | 0.00 | 2.49 | 0.75 | 156 | 0.4 | 72 | 50/50/0/0 | - | - |
| 30 | exchange | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 18 | 50 | 1058 | 1459 | -402 | 0.59 | 0.72 | -0.28 | 605 | 0.4 | 72 | 50/50/0/0 | - | - |
| 30 | cfd_std | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 18 | 50 | 1115 | 364 | 751 | 0.15 | 1.83 | 0.54 | 210 | 0.4 | 72 | 50/50/0/0 | - | - |
| 30 | cfd_raw | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 18 | 50 | 1088 | 324 | 764 | 0.13 | 1.87 | 0.55 | 200 | 0.4 | 72 | 50/50/0/0 | - | - |
| 60 | none | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 12 | 67 | 1249 | 0 | 1249 | 0.00 | 4.98 | 1.33 | 154 | 0.1 | 92 | 67/33/0/0 | - | - |
| 60 | exchange | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 12 | 67 | 1251 | 971 | 280 | 0.52 | 1.44 | 0.30 | 368 | 0.1 | 92 | 67/33/0/0 | - | - |
| 60 | cfd_std | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 12 | 67 | 1263 | 216 | 1047 | 0.12 | 3.56 | 1.12 | 194 | 0.1 | 92 | 67/33/0/0 | - | - |
| 60 | cfd_raw | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 12 | 67 | 1257 | 200 | 1057 | 0.11 | 3.68 | 1.13 | 190 | 0.1 | 92 | 67/33/0/0 | - | - |
| 240 | none | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 17 | 71 | 1674 | 0 | 1674 | 0.00 | 5.73 | 1.47 | 192 | 0.2 | 76 | 71/29/0/0 | - | - |
| 240 | exchange | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 17 | 71 | 1682 | 1210 | 473 | 0.51 | 1.65 | 0.44 | 393 | 0.2 | 76 | 71/29/0/0 | - | - |
| 240 | cfd_std | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 17 | 65 | 1507 | 310 | 1196 | 0.14 | 3.22 | 1.05 | 246 | 0.2 | 76 | 65/35/0/0 | - | - |
| 240 | cfd_raw | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 17 | 65 | 1485 | 286 | 1199 | 0.13 | 3.28 | 1.05 | 242 | 0.2 | 76 | 65/35/0/0 | - | - |
| 1 | none | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 9 | 78 | 596 | 0 | 596 | 0.00 | 4.50 | 0.78 | 86 | 5.2 | 0 | 33/22/33/11 | - | - |
| 1 | exchange | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 9 | 44 | 606 | 795 | -189 | 0.85 | 0.67 | -0.24 | 356 | 5.2 | 0 | 33/22/33/11 | - | - |
| 1 | cfd_std | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 9 | 44 | 589 | 202 | 386 | 0.20 | 2.22 | 0.51 | 101 | 4.9 | 0 | 33/33/33/0 | - | - |
| 1 | cfd_raw | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 9 | 44 | 636 | 174 | 462 | 0.18 | 3.03 | 0.61 | 100 | 5.2 | 0 | 33/22/33/11 | - | - |

## Recommendations

### TF 15m, preset cfd_std

- configs: 1080, with >= 15 trades: 597, net positive: 602, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 45, eligible (positive, enough trades, measurable): 297, max trades any config: 61
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | cfd_std | pct | 1.0 | 2.5 | 5 | 0.5 | bar | 26 | 50 | 5718 | 675 | 5043 | 0.06 | 2.57 | 0.24 | 1321 | 13.2 | 0 | 8/12/77/4 | 0.88 | 3102 |
| 15 | cfd_std | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 19 | 47 | 1188 | 392 | 796 | 0.15 | 1.82 | 0.51 | 399 | 0.9 | 37 | 47/53/0/0 | - | - |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | cfd_std | pct | 1.0 | 2.5 | 5 | 0.5 | bar | 26 | 50 | 5718 | 675 | 5043 | 0.06 | 2.57 | 0.24 | 1321 | 13.2 | 0 | 8/12/77/4 | 0.88 | 3102 |
| 15 | cfd_std | pct | 1.0 | 3.0 | 5 | 0.5 | bar | 26 | 50 | 6518 | 675 | 5843 | 0.05 | 2.82 | 0.28 | 1321 | 13.3 | 0 | 8/12/77/4 | 0.86 | 3012 |
| 15 | cfd_std | pct | 1.0 | 3.0 | 8 | 0.5 | bar | 17 | 65 | 5343 | 432 | 4911 | 0.04 | 2.91 | 0.35 | 1293 | 13.7 | 0 | 12/18/71/0 | 0.67 | 2914 |
| 15 | cfd_std | atr | 3.0 | 1.0 | 5 | 0.5 | off | 17 | 71 | 4455 | 297 | 4158 | 0.03 | 2.32 | 0.44 | 1887 | 22.6 | 12 | 71/24/0/6 | 0.86 | 2898 |
| 15 | cfd_std | pct | 1.0 | 2.0 | 5 | 0.5 | bar | 26 | 50 | 4919 | 675 | 4244 | 0.06 | 2.32 | 0.20 | 1321 | 13.2 | 0 | 8/12/77/4 | 0.75 | 2858 |

### TF 15m, preset exchange

- configs: 1080, with >= 15 trades: 590, net positive: 336, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 45, eligible (positive, enough trades, measurable): 84, max trades any config: 61
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | exchange | atr | 2.0 | 3.0 | 5 | 0.5 | off | 17 | 47 | 7409 | 1416 | 5993 | 0.10 | 2.52 | 0.69 | 2327 | 23.2 | 6 | 47/47/0/6 | 0.75 | 2174 |
| 15 | exchange | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 19 | 47 | 1050 | 1596 | -546 | 0.61 | 0.67 | -0.36 | 698 | 0.8 | 37 | 47/53/0/0 | - | - |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | exchange | atr | 2.0 | 3.0 | 5 | 0.5 | off | 17 | 47 | 7409 | 1416 | 5993 | 0.10 | 2.52 | 0.69 | 2327 | 23.2 | 6 | 47/47/0/6 | 0.75 | 2174 |
| 15 | exchange | atr | 3.0 | 1.5 | 3 | 0.5 | off | 16 | 56 | 5103 | 1348 | 3755 | 0.11 | 1.85 | 0.31 | 2000 | 28.6 | 0 | 56/38/0/6 | 0.71 | 1788 |
| 15 | exchange | pct | 1.0 | 2.5 | 5 | 0.5 | bar | 27 | 37 | 4519 | 2293 | 2226 | 0.19 | 1.44 | 0.10 | 2937 | 11.4 | 0 | 7/15/74/4 | 0.88 | 1716 |
| 15 | exchange | atr | 3.0 | 1.5 | 5 | 0.5 | off | 15 | 53 | 3693 | 1258 | 2435 | 0.11 | 1.55 | 0.24 | 2080 | 28.3 | 7 | 53/40/0/7 | 0.75 | 1684 |
| 15 | exchange | atr | 2.0 | 3.0 | 3 | 0.5 | off | 19 | 42 | 5685 | 1588 | 4097 | 0.11 | 1.76 | 0.50 | 3187 | 23.5 | 5 | 42/53/0/5 | 0.71 | 1638 |

### TF 30m, preset cfd_std

- configs: 1080, with >= 15 trades: 464, net positive: 708, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 186, eligible (positive, enough trades, measurable): 326, max trades any config: 38
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | cfd_std | atr | 3.0 | 2.5 | 8 | 0.5 | bar | 15 | 73 | 5901 | 378 | 5523 | 0.03 | 2.72 | 0.54 | 3137 | 17.3 | 7 | 13/20/67/0 | 1.00 | 4365 |
| 30 | cfd_std | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 18 | 50 | 1115 | 364 | 751 | 0.15 | 1.83 | 0.54 | 210 | 0.4 | 72 | 50/50/0/0 | - | - |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | cfd_std | atr | 3.0 | 2.5 | 8 | 0.5 | bar | 15 | 73 | 5901 | 378 | 5523 | 0.03 | 2.72 | 0.54 | 3137 | 17.3 | 7 | 13/20/67/0 | 1.00 | 4365 |
| 30 | cfd_std | atr | 3.0 | 3.0 | 8 | 0.5 | bar | 15 | 73 | 6763 | 378 | 6385 | 0.03 | 2.99 | 0.61 | 3137 | 17.3 | 7 | 13/20/67/0 | 1.00 | 4361 |
| 30 | cfd_std | pct | 1.0 | 2.0 | 3 | 0.5 | bar | 20 | 60 | 10073 | 446 | 9627 | 0.03 | 3.74 | 0.59 | 2453 | 15.1 | 5 | 35/20/45/0 | 1.00 | 4279 |
| 30 | cfd_std | atr | 3.0 | 2.0 | 8 | 0.5 | bar | 15 | 73 | 6595 | 324 | 6271 | 0.03 | 2.95 | 0.68 | 3137 | 15.8 | 7 | 40/20/40/0 | 1.00 | 4204 |
| 30 | cfd_std | atr | 3.0 | 3.0 | 8 | 0.5 | tick | 19 | 79 | 6624 | 486 | 6138 | 0.04 | 2.89 | 0.48 | 3137 | 8.3 | 5 | 11/16/74/0 | 1.00 | 4105 |

### TF 30m, preset exchange

- configs: 1080, with >= 15 trades: 467, net positive: 343, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 186, eligible (positive, enough trades, measurable): 187, max trades any config: 38
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | exchange | atr | 3.0 | 3.0 | 8 | 0.5 | bar | 17 | 53 | 7074 | 1410 | 5664 | 0.10 | 2.42 | 0.42 | 3335 | 13.7 | 6 | 12/18/71/0 | 1.00 | 3974 |
| 30 | exchange | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 18 | 50 | 1058 | 1459 | -402 | 0.59 | 0.72 | -0.28 | 605 | 0.4 | 72 | 50/50/0/0 | - | - |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | exchange | atr | 3.0 | 3.0 | 8 | 0.5 | bar | 17 | 53 | 7074 | 1410 | 5664 | 0.10 | 2.42 | 0.42 | 3335 | 13.7 | 6 | 12/18/71/0 | 1.00 | 3974 |
| 30 | exchange | atr | 3.0 | 3.0 | 8 | 0.5 | tick | 19 | 68 | 6578 | 1574 | 5004 | 0.12 | 2.40 | 0.40 | 3318 | 8.3 | 5 | 11/16/74/0 | 1.00 | 3590 |
| 30 | exchange | atr | 3.0 | 2.5 | 8 | 0.5 | bar | 17 | 53 | 6357 | 1408 | 4950 | 0.11 | 2.24 | 0.44 | 3335 | 13.5 | 6 | 18/18/65/0 | 1.00 | 3469 |
| 30 | exchange | atr | 3.0 | 3.0 | 5 | 0.5 | bar | 21 | 43 | 4693 | 1746 | 2946 | 0.12 | 1.50 | 0.23 | 3986 | 8.6 | 5 | 14/29/57/0 | 1.00 | 3101 |
| 30 | exchange | atr | 3.0 | 2.0 | 8 | 0.5 | bar | 17 | 53 | 6589 | 1401 | 5188 | 0.10 | 2.30 | 0.46 | 3335 | 12.4 | 6 | 35/18/47/0 | 1.00 | 3098 |

### TF 60m, preset cfd_std

- configs: 1080, with >= 15 trades: 441, net positive: 552, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 444, eligible (positive, enough trades, measurable): 226, max trades any config: 45
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | cfd_std | atr | 3.0 | 3.0 | 3 | 0.5 | tick | 27 | 70 | 10207 | 688 | 9518 | 0.03 | 2.78 | 0.29 | 2220 | 8.6 | 0 | 11/19/70/0 | 1.00 | 5746 |
| 60 | cfd_std | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 12 | 67 | 1263 | 216 | 1047 | 0.12 | 3.56 | 1.12 | 194 | 0.1 | 92 | 67/33/0/0 | - | - |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | cfd_std | atr | 3.0 | 3.0 | 3 | 0.5 | tick | 27 | 70 | 10207 | 688 | 9518 | 0.03 | 2.78 | 0.29 | 2220 | 8.6 | 0 | 11/19/70/0 | 1.00 | 5746 |
| 60 | cfd_std | atr | 3.0 | 3.0 | 3 | 0.5 | bar | 21 | 52 | 5029 | 526 | 4502 | 0.02 | 1.53 | 0.17 | 5381 | 13.0 | 0 | 14/38/48/0 | 1.00 | 5301 |
| 60 | cfd_std | atr | 3.0 | 2.5 | 3 | 0.5 | tick | 27 | 70 | 8429 | 688 | 7740 | 0.04 | 2.45 | 0.23 | 2220 | 8.4 | 0 | 11/19/70/0 | 1.00 | 5202 |
| 60 | cfd_std | atr | 3.0 | 3.0 | 3 | 1.0 | tick | 15 | 60 | 5994 | 378 | 5616 | 0.03 | 2.66 | 0.31 | 2460 | 5.7 | 7 | 13/20/67/0 | 0.86 | 5048 |
| 60 | cfd_std | atr | 3.0 | 3.0 | 3 | 1.0 | bar | 15 | 60 | 8658 | 364 | 8294 | 0.02 | 3.03 | 0.43 | 3145 | 9.4 | 7 | 20/27/53/0 | 0.86 | 4651 |

### TF 60m, preset exchange

- configs: 1080, with >= 15 trades: 440, net positive: 363, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 444, eligible (positive, enough trades, measurable): 145, max trades any config: 45
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | exchange | atr | 3.0 | 3.0 | 3 | 0.5 | tick | 26 | 62 | 11361 | 2154 | 9207 | 0.11 | 3.01 | 0.27 | 2863 | 9.5 | 0 | 12/15/73/0 | 1.00 | 4882 |
| 60 | exchange | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 12 | 67 | 1251 | 971 | 280 | 0.52 | 1.44 | 0.30 | 368 | 0.1 | 92 | 67/33/0/0 | - | - |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | exchange | atr | 3.0 | 3.0 | 3 | 0.5 | tick | 26 | 62 | 11361 | 2154 | 9207 | 0.11 | 3.01 | 0.27 | 2863 | 9.5 | 0 | 12/15/73/0 | 1.00 | 4882 |
| 60 | exchange | atr | 3.0 | 2.5 | 3 | 0.5 | tick | 26 | 62 | 9583 | 2153 | 7430 | 0.12 | 2.62 | 0.21 | 2863 | 9.3 | 0 | 12/15/73/0 | 1.00 | 4405 |
| 60 | exchange | atr | 3.0 | 3.0 | 3 | 1.0 | tick | 15 | 47 | 5948 | 1233 | 4715 | 0.10 | 2.24 | 0.25 | 2866 | 5.7 | 7 | 13/20/67/0 | 0.86 | 4373 |
| 60 | exchange | atr | 3.0 | 3.0 | 3 | 0.5 | bar | 21 | 52 | 4902 | 1736 | 3166 | 0.08 | 1.34 | 0.10 | 6175 | 13.0 | 0 | 14/38/48/0 | 1.00 | 4286 |
| 60 | exchange | atr | 3.0 | 3.0 | 3 | 1.0 | bar | 15 | 60 | 8589 | 1233 | 7357 | 0.07 | 2.66 | 0.36 | 3673 | 9.4 | 7 | 20/27/53/0 | 0.86 | 3844 |

### TF 240m, preset cfd_std

- configs: 1080, with >= 15 trades: 537, net positive: 617, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 345, eligible (positive, enough trades, measurable): 203, max trades any config: 46
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 240 | cfd_std | pct | 1.0 | 1.5 | 3 | 1.0 | tick | 20 | 60 | 7394 | 392 | 7002 | 0.02 | 2.53 | 0.51 | 1325 | 3.4 | 35 | 55/30/15/0 | 1.00 | 5137 |
| 240 | cfd_std | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 17 | 65 | 1507 | 310 | 1196 | 0.14 | 3.22 | 1.05 | 246 | 0.2 | 76 | 65/35/0/0 | - | - |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 240 | cfd_std | pct | 1.0 | 1.5 | 3 | 1.0 | tick | 20 | 60 | 7394 | 392 | 7002 | 0.02 | 2.53 | 0.51 | 1325 | 3.4 | 35 | 55/30/15/0 | 1.00 | 5137 |
| 240 | cfd_std | pct | 0.5 | 3.0 | 3 | 1.0 | tick | 21 | 48 | 5880 | 446 | 5435 | 0.03 | 2.37 | 0.77 | 925 | 1.5 | 48 | 43/48/10/0 | 1.00 | 5057 |
| 240 | cfd_std | pct | 1.0 | 1.5 | 3 | 1.0 | bar | 20 | 60 | 7092 | 378 | 6714 | 0.02 | 2.21 | 0.49 | 1325 | 4.0 | 35 | 60/40/0/0 | 1.00 | 5015 |
| 240 | cfd_std | pct | 1.0 | 1.5 | 3 | 1.0 | off | 20 | 60 | 7092 | 378 | 6714 | 0.02 | 2.21 | 0.49 | 1325 | 4.0 | 35 | 60/40/0/0 | 1.00 | 4886 |
| 240 | cfd_std | pct | 0.5 | 3.0 | 3 | 1.0 | bar | 21 | 48 | 6497 | 432 | 6065 | 0.03 | 2.50 | 0.87 | 1007 | 1.5 | 48 | 48/52/0/0 | 1.00 | 4836 |

### TF 240m, preset exchange

- configs: 1080, with >= 15 trades: 536, net positive: 479, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 345, eligible (positive, enough trades, measurable): 161, max trades any config: 46
- verdict: **plateau pick**

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 240 | exchange | pct | 1.0 | 1.5 | 3 | 1.0 | tick | 20 | 60 | 7278 | 1426 | 5852 | 0.09 | 2.18 | 0.42 | 1420 | 3.4 | 35 | 55/30/15/0 | 0.88 | 3956 |
| 240 | exchange | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 17 | 71 | 1682 | 1210 | 473 | 0.51 | 1.65 | 0.44 | 393 | 0.2 | 76 | 71/29/0/0 | - | - |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 240 | exchange | pct | 1.0 | 1.5 | 3 | 1.0 | tick | 20 | 60 | 7278 | 1426 | 5852 | 0.09 | 2.18 | 0.42 | 1420 | 3.4 | 35 | 55/30/15/0 | 0.88 | 3956 |
| 240 | exchange | pct | 0.5 | 3.0 | 3 | 1.0 | tick | 21 | 48 | 5777 | 1509 | 4267 | 0.11 | 1.94 | 0.61 | 1072 | 1.5 | 48 | 43/48/10/0 | 1.00 | 3874 |
| 240 | exchange | pct | 1.0 | 1.5 | 3 | 1.0 | bar | 20 | 60 | 6942 | 1423 | 5520 | 0.08 | 1.92 | 0.40 | 1420 | 4.0 | 35 | 60/40/0/0 | 0.88 | 3836 |
| 240 | exchange | pct | 1.0 | 1.5 | 3 | 1.0 | off | 20 | 60 | 6942 | 1423 | 5520 | 0.08 | 1.92 | 0.40 | 1420 | 4.0 | 35 | 60/40/0/0 | 0.88 | 3704 |
| 240 | exchange | pct | 0.5 | 3.0 | 3 | 1.0 | bar | 21 | 48 | 6371 | 1507 | 4864 | 0.11 | 2.05 | 0.70 | 1165 | 1.5 | 48 | 48/52/0/0 | 1.00 | 3649 |

### TF 1m, preset cfd_std

- configs: 1080, with >= 15 trades: 192, net positive: 812, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 0, eligible (positive, enough trades, measurable): 164, max trades any config: 34
- verdict: **plateau pick**  (1m file is ~10 hours; ignore for calibration)

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cfd_std | pct | 1.0 | 3.0 | 5 | 0.5 | tick | 15 | 87 | 1862 | 405 | 1457 | 0.22 | 43.50 | 0.11 | 20 | 15.5 | 0 | 0/0/100/0 | 1.00 | 1423 |
| 1 | cfd_std | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 9 | 44 | 589 | 202 | 386 | 0.20 | 2.22 | 0.51 | 101 | 4.9 | 0 | 33/33/33/0 | - | - |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cfd_std | pct | 1.0 | 3.0 | 5 | 0.5 | tick | 15 | 87 | 1862 | 405 | 1457 | 0.22 | 43.50 | 0.11 | 20 | 15.5 | 0 | 0/0/100/0 | 1.00 | 1423 |
| 1 | cfd_std | pct | 1.0 | 2.5 | 5 | 0.5 | tick | 15 | 87 | 1862 | 405 | 1457 | 0.22 | 43.50 | 0.11 | 20 | 15.5 | 0 | 0/0/100/0 | 1.00 | 1284 |
| 1 | cfd_std | pct | 1.0 | 2.0 | 5 | 0.5 | tick | 15 | 87 | 1862 | 405 | 1457 | 0.22 | 43.50 | 0.11 | 20 | 15.5 | 0 | 0/0/100/0 | 1.00 | 1244 |
| 1 | cfd_std | pct | 1.0 | 1.5 | 5 | 0.5 | tick | 15 | 87 | 1862 | 405 | 1457 | 0.22 | 43.50 | 0.11 | 20 | 15.5 | 0 | 0/0/100/0 | 1.00 | 1188 |
| 1 | cfd_std | pct | 0.5 | 3.0 | 5 | 0.5 | tick | 16 | 81 | 1509 | 432 | 1077 | 0.19 | 3.30 | 0.16 | 448 | 12.8 | 0 | 0/6/94/0 | 1.00 | 1167 |

### TF 1m, preset exchange

- configs: 1080, with >= 15 trades: 205, net positive: 377, excluded as same-bar artefacts (> 50% of trades exit in the fill bar): 0, eligible (positive, enough trades, measurable): 21, max trades any config: 32
- verdict: **plateau pick**  (1m file is ~10 hours; ignore for calibration)

**pick (first row) vs v2.01 default (second row)**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | exchange | pct | 1.0 | 3.0 | 5 | 0.5 | tick | 16 | 38 | 1809 | 1425 | 384 | 0.75 | 1.61 | 0.03 | 327 | 13.4 | 0 | 0/0/100/0 | 0.86 | 637 |
| 1 | exchange | pct | 0.1 | 2.5 | 5 | 1.0 | bar | 9 | 44 | 606 | 795 | -189 | 0.85 | 0.67 | -0.24 | 356 | 5.2 | 0 | 33/22/33/11 | - | - |

**top 5 by neighbourhood mean**

| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | exchange | pct | 1.0 | 3.0 | 5 | 0.5 | tick | 16 | 38 | 1809 | 1425 | 384 | 0.75 | 1.61 | 0.03 | 327 | 13.4 | 0 | 0/0/100/0 | 0.86 | 637 |
| 1 | exchange | pct | 1.0 | 2.5 | 5 | 0.5 | tick | 16 | 38 | 1809 | 1425 | 384 | 0.75 | 1.61 | 0.03 | 327 | 13.4 | 0 | 0/0/100/0 | 0.88 | 458 |
| 1 | exchange | pct | 1.0 | 2.0 | 5 | 0.5 | tick | 16 | 38 | 1809 | 1425 | 384 | 0.75 | 1.61 | 0.03 | 327 | 13.4 | 0 | 0/0/100/0 | 0.88 | 415 |
| 1 | exchange | pct | 0.5 | 3.0 | 5 | 0.5 | tick | 16 | 38 | 1809 | 1425 | 384 | 0.75 | 1.61 | 0.06 | 327 | 13.4 | 0 | 0/0/100/0 | 0.75 | 371 |
| 1 | exchange | pct | 1.0 | 1.5 | 5 | 0.5 | tick | 16 | 38 | 1809 | 1425 | 384 | 0.75 | 1.61 | 0.03 | 327 | 13.4 | 0 | 0/0/100/0 | 0.88 | 355 |

## Marginal views (mean net over all other grid dims, all TFs except 1m)

**by trail**

| cost | trail | mean net | positive frac | mean trades | mean exp R |
|---|---|---|---|---|---|
| cfd_raw | bar | 435 | 0.59 | 14.7 | 0.133 |
| cfd_raw | off | 158 | 0.56 | 13.2 | 0.119 |
| cfd_raw | tick | 678 | 0.61 | 15.4 | 0.154 |
| cfd_std | bar | 402 | 0.57 | 14.6 | 0.128 |
| cfd_std | off | 117 | 0.55 | 13.2 | 0.108 |
| cfd_std | tick | 647 | 0.60 | 15.4 | 0.149 |
| exchange | bar | -442 | 0.36 | 14.7 | -0.110 |
| exchange | off | -608 | 0.36 | 13.2 | -0.122 |
| exchange | tick | -241 | 0.34 | 15.3 | -0.090 |
| none | bar | 758 | 0.63 | 14.7 | 0.206 |
| none | off | 449 | 0.61 | 13.1 | 0.194 |
| none | tick | 1012 | 0.66 | 15.3 | 0.226 |

**by sl_mode**

| cost | sl_mode | mean net | positive frac | mean trades | mean exp R |
|---|---|---|---|---|---|
| cfd_raw | atr | 52 | 0.48 | 13.3 | 0.001 |
| cfd_raw | pct | 795 | 0.69 | 15.5 | 0.271 |
| cfd_std | atr | -3 | 0.47 | 13.3 | -0.011 |
| cfd_std | pct | 780 | 0.68 | 15.5 | 0.268 |
| exchange | atr | -715 | 0.33 | 13.3 | -0.140 |
| exchange | pct | -145 | 0.37 | 15.5 | -0.074 |
| none | atr | 332 | 0.53 | 13.3 | 0.044 |
| none | pct | 1148 | 0.75 | 15.5 | 0.373 |

**by sl_value**

| cost | sl_value | mean net | positive frac | mean trades | mean exp R |
|---|---|---|---|---|---|
| cfd_raw | 0.1 | 870 | 0.87 | 18.1 | 0.643 |
| cfd_raw | 0.25 | 981 | 0.80 | 17.1 | 0.365 |
| cfd_raw | 0.5 | 642 | 0.59 | 15.0 | 0.116 |
| cfd_raw | 1.0 | 652 | 0.54 | 13.9 | 0.011 |
| cfd_raw | 1.5 | -134 | 0.44 | 14.2 | -0.032 |
| cfd_raw | 2.0 | 47 | 0.45 | 12.7 | 0.011 |
| cfd_raw | 3.0 | -321 | 0.45 | 10.7 | -0.041 |
| cfd_std | 0.1 | 870 | 0.86 | 18.1 | 0.638 |
| cfd_std | 0.25 | 965 | 0.78 | 17.1 | 0.361 |
| cfd_std | 0.5 | 597 | 0.57 | 15.0 | 0.111 |
| cfd_std | 1.0 | 606 | 0.53 | 13.9 | 0.004 |
| cfd_std | 1.5 | -178 | 0.43 | 14.2 | -0.047 |
| cfd_std | 2.0 | 3 | 0.44 | 12.7 | -0.006 |
| cfd_std | 3.0 | -360 | 0.45 | 10.6 | -0.041 |
| exchange | 0.1 | -259 | 0.25 | 18.1 | -0.172 |
| exchange | 0.25 | -105 | 0.42 | 17.1 | 0.033 |
| exchange | 0.5 | -186 | 0.41 | 14.8 | -0.038 |
| exchange | 1.0 | -145 | 0.38 | 13.9 | -0.140 |
| exchange | 1.5 | -967 | 0.28 | 14.1 | -0.182 |
| exchange | 2.0 | -711 | 0.34 | 12.6 | -0.105 |
| exchange | 3.0 | -924 | 0.36 | 10.7 | -0.112 |
| none | 0.1 | 1175 | 0.89 | 18.1 | 0.862 |
| none | 0.25 | 1248 | 0.83 | 17.1 | 0.447 |
| none | 0.5 | 1044 | 0.68 | 14.7 | 0.181 |
| none | 1.0 | 1047 | 0.62 | 13.8 | 0.068 |
| none | 1.5 | 149 | 0.48 | 14.1 | 0.015 |
| none | 2.0 | 289 | 0.49 | 12.6 | 0.041 |
| none | 3.0 | -80 | 0.49 | 10.7 | -0.013 |

**by tp_r**

| cost | tp_r | mean net | positive frac | mean trades | mean exp R |
|---|---|---|---|---|---|
| cfd_raw | 1.0 | 309 | 0.58 | 14.9 | 0.078 |
| cfd_raw | 1.5 | 355 | 0.61 | 14.6 | 0.121 |
| cfd_raw | 2.0 | 306 | 0.57 | 14.4 | 0.116 |
| cfd_raw | 2.5 | 463 | 0.58 | 14.2 | 0.151 |
| cfd_raw | 3.0 | 685 | 0.59 | 14.0 | 0.213 |
| cfd_std | 1.0 | 304 | 0.58 | 14.9 | 0.078 |
| cfd_std | 1.5 | 332 | 0.59 | 14.6 | 0.114 |
| cfd_std | 2.0 | 269 | 0.55 | 14.4 | 0.110 |
| cfd_std | 2.5 | 403 | 0.56 | 14.2 | 0.138 |
| cfd_std | 3.0 | 635 | 0.59 | 14.1 | 0.201 |
| exchange | 1.0 | -582 | 0.28 | 14.9 | -0.166 |
| exchange | 1.5 | -488 | 0.35 | 14.6 | -0.119 |
| exchange | 2.0 | -546 | 0.33 | 14.3 | -0.127 |
| exchange | 2.5 | -395 | 0.38 | 14.1 | -0.095 |
| exchange | 3.0 | -140 | 0.42 | 14.0 | -0.028 |
| none | 1.0 | 640 | 0.66 | 14.9 | 0.151 |
| none | 1.5 | 703 | 0.65 | 14.6 | 0.199 |
| none | 2.0 | 610 | 0.61 | 14.3 | 0.186 |
| none | 2.5 | 753 | 0.62 | 14.1 | 0.221 |
| none | 3.0 | 993 | 0.64 | 14.0 | 0.287 |

**by barsN**

| cost | barsN | mean net | positive frac | mean trades | mean exp R |
|---|---|---|---|---|---|
| cfd_raw | 3 | 681 | 0.68 | 17.2 | 0.213 |
| cfd_raw | 5 | 492 | 0.61 | 14.1 | 0.198 |
| cfd_raw | 8 | 98 | 0.47 | 12.0 | -0.012 |
| cfd_std | 3 | 644 | 0.67 | 17.3 | 0.206 |
| cfd_std | 5 | 459 | 0.60 | 14.1 | 0.191 |
| cfd_std | 8 | 64 | 0.45 | 12.0 | -0.020 |
| exchange | 3 | -325 | 0.44 | 17.2 | -0.023 |
| exchange | 5 | -354 | 0.37 | 14.0 | -0.041 |
| exchange | 8 | -611 | 0.25 | 12.0 | -0.264 |
| none | 3 | 1058 | 0.71 | 17.2 | 0.283 |
| none | 5 | 781 | 0.67 | 14.0 | 0.270 |
| none | 8 | 381 | 0.53 | 11.9 | 0.066 |

**by buf_atr**

| cost | buf_atr | mean net | positive frac | mean trades | mean exp R |
|---|---|---|---|---|---|
| cfd_raw | 0.5 | 808 | 0.72 | 26.8 | 0.183 |
| cfd_raw | 1.0 | 805 | 0.68 | 14.2 | 0.220 |
| cfd_raw | 2.0 | -342 | 0.35 | 2.2 | -0.022 |
| cfd_std | 0.5 | 729 | 0.70 | 26.9 | 0.175 |
| cfd_std | 1.0 | 786 | 0.68 | 14.2 | 0.216 |
| cfd_std | 2.0 | -348 | 0.34 | 2.2 | -0.034 |
| exchange | 0.5 | -775 | 0.38 | 26.8 | -0.053 |
| exchange | 1.0 | -42 | 0.42 | 14.2 | -0.021 |
| exchange | 2.0 | -474 | 0.25 | 2.2 | -0.274 |
| none | 0.5 | 1414 | 0.80 | 26.7 | 0.263 |
| none | 1.0 | 1115 | 0.75 | 14.2 | 0.296 |
| none | 2.0 | -309 | 0.36 | 2.2 | 0.039 |

## Caveats

- ~600 bars per TF; the 1m file covers ~10 hours. Nothing here is statistically significant; treat as cost/geometry sanity only.
- Emulator replica without bar magnifier: intrabar ordering is an assumption (open-low-high-close / open-high-low-close). Same-bar entry+exit is guesswork on both sides.
- Tick-mode trail is an approximation (ratchet at 4 path nodes per bar with the previous bar's ATR), not a true tick replay.
- ATR is seeded inside the CSV window (SMA of first 14 TRs); TradingView's ATR has longer history. Pivots start unseeded in the sweep (first ~2*BarsN bars untradable).
- Costs: spread is applied as half-spread on every stop/market fill, none on TP limit fills; slippage per side on stop/market fills. Commission on both sides. 'gross' = P&L at ideal fills (stop level / open / TP price); 'cost' = commission + spread + slippage actually paid; net = gross - cost.
- Open position at end of data is closed at the last close (market, with slippage) and tagged 'end'.
- Fixed 1.0 BTC sizing; equity effects of risk sizing are not in the sweep (engine supports --sizing risk).
