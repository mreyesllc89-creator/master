## Verdicts at a glance

| Chart | Verdict | What it means for you | On 2021-2023, which it was not chosen on | Last three years, where it was chosen | File |
|---|---|---|---|---|---|
| [1m](#1m-paper-trade) | PAPER-TRADE | watch with alerts only; no money | +54.8R in 93 trades, positive in 93% of resamples; 77% of it in 2023 | +107.1R in 145 trades | `AMVI_FGF_BTCUSDT_1m.pine` |
| [2m](#2m-not-recommended) | NOT RECOMMENDED | nothing to load | +1.3R in 108 trades (-3.4R at stressed costs); 96% of it in 2023 | +12.0R in 97 trades | none |
| [3m](#3m-usable) | USABLE | test with alerts first; small size at most | +20.6R in 72 trades; 80% of it in 2023 | +23.4R in 79 trades | `AMVI_FGF_BTCUSDT_3m.pine` |
| [5m](#5m-not-recommended) | NOT RECOMMENDED | nothing to load | -1.0R in 70 trades | +16.1R in 68 trades | none |
| [10m](#10m-not-recommended) | NOT RECOMMENDED | nothing to load | +8.7R in 65 trades, positive in 81% of resamples; all of it in 2023 (the other years together lost) | +14.5R in 85 trades | none |
| [15m](#15m-usable) | USABLE | test with alerts first; small size at most | +19.7R in 232 trades; 69% of it in 2021 | +21.1R in 284 trades | `AMVI_FGF_BTCUSDT_15m.pine` |
| [30m](#30m-do-not-trade) | DO NOT TRADE | nothing to load | +4.8R in 68 trades, positive in 77% of resamples; 80% of it in 2022 | +20.2R in 74 trades | none |
| [1h](#1h-not-recommended) | NOT RECOMMENDED | nothing to load | +7.5R in 98 trades, positive in 86% of resamples | +22.0R in 101 trades | none |
| [4h](#4h-usable) | USABLE | test with alerts first; small size at most | +21.4R in 69 trades; 84% of it in 2023 | +35.2R in 100 trades | `AMVI_FGF_BTCUSDT_4h.pine` |

## Results by timeframe

Net of 0.05% per side, 1 tick slippage and funding. R = amount risked per trade; PF = profit factor (gross profit / gross loss);
DD = largest drawdown. The untouched period comes first because the pick was not chosen on it; the search-window figure is the best
of thousands of settings and is flattered by that choice.

| Chart | Verdict | Untouched 2021-01 to 2023-10 (not chosen on it) | Stressed costs | Positive in resamples of its weeks | Search window 2023-11 to 2026-10 (chosen here) | Halves | File |
|---|---|---|---|---|---|---|---|
| 1m | PAPER-TRADE | +54.8R, 93 trades, PF 1.75, DD 15.2R | +49.0R | 93% | +107.1R, 145 trades, PF 1.83, DD 29.2R | +50.2 / +56.9R | `presets/AMVI_FGF_BTCUSDT_1m.pine` |
| 2m | NOT RECOMMENDED | +1.3R, 108 trades, PF 1.05, DD 4.2R | -3.4R | 60% | +12.0R, 97 trades, PF 1.81, DD 2.6R | +6.5 / +5.5R | none |
| 3m | USABLE | +20.6R, 72 trades, PF 2.56, DD 2.9R | +16.9R | 100% | +23.4R, 79 trades, PF 2.13, DD 2.9R | +11.3 / +12.0R | `presets/AMVI_FGF_BTCUSDT_3m.pine` |
| 5m | NOT RECOMMENDED | -1.0R, 70 trades, PF 0.98, DD 6.7R | -4.8R | 45% | +16.1R, 68 trades, PF 1.51, DD 5.2R | +7.1 / +9.1R | none |
| 10m | NOT RECOMMENDED | +8.7R, 65 trades, PF 1.31, DD 6.4R | +6.0R | 81% | +14.5R, 85 trades, PF 1.44, DD 5.7R | +7.3 / +7.2R | none |
| 15m | USABLE | +19.7R, 232 trades, PF 1.41, DD 7.0R | +14.7R | 99% | +21.1R, 284 trades, PF 1.35, DD 3.7R | +10.7 / +10.4R | `presets/AMVI_FGF_BTCUSDT_15m.pine` |
| 30m | DO NOT TRADE | +4.8R, 68 trades, PF 1.22, DD 3.8R | +3.1R | 77% | +20.2R, 74 trades, PF 2.22, DD 3.3R | +12.3 / +8.0R | none |
| 1h | NOT RECOMMENDED | +7.5R, 98 trades, PF 1.29, DD 6.0R | +3.8R | 86% | +22.0R, 101 trades, PF 2.32, DD 3.2R | +11.1 / +10.9R | none |
| 4h | USABLE | +21.4R, 69 trades, PF 1.71, DD 8.3R | +18.9R | 98% | +35.2R, 100 trades, PF 1.84, DD 5.7R | +22.4 / +12.9R | `presets/AMVI_FGF_BTCUSDT_4h.pine` |

## What the search itself says

Best 40 = the 40 steadiest settings of one part of the search window, scored on another part. A test passes when their mean is
positive, above 95% of random groups of 40, and stays positive in 95% of resamples of the months. The last column is the same test
for the 25 steadiest candidates (12 on 1m), chosen on the whole search window and scored on the untouched period.
The three "Positive" columns are shares of the settings with at least 30 trades in each half and a trade in at least 60% of its
months: 57,920 of the 110,000 tried. "Beaten" in the last column: the candidates' mean is above 95% of random groups with
their own trade directions (results/untouched_check.txt prints this comparison with the 95% resample condition included, so its
line for 30m reads "fail").

| Chart | Settings tried | Positive before costs | Positive after costs | Positive in both halves | First half -> second (best 40) | Second -> first | Walk-forward (two years -> the third) | Search window -> untouched period (25 steadiest candidates) |
|---|---|---|---|---|---|---|---|---|
| 1m | 6,000 | 58% | 2% | 0.9% | -9.9R, 25% positive, 22% of resamples (fail) | -0.3R, 50% positive, 46% of resamples (fail) | -3.2R, 38% positive, 38% of resamples (fail) | +60.3R, 83% positive, 96.9% of resamples (pass); random settings of the same directions -1438.1R (beaten) |
| 2m | 8,000 | 51% | 6% | 2.8% | -3.7R, 48% positive, 25% of resamples (fail) | +10.6R, 52% positive, 87% of resamples (fail) | +6.2R, 62% positive, 77% of resamples (fail) | +54.0R, 72% positive, 96.1% of resamples (pass); random settings of the same directions -50.2R (beaten) |
| 3m | 8,000 | 52% | 6% | 3.3% | -5.0R, 40% positive, 12% of resamples (fail) | +3.3R, 60% positive, 61% of resamples (fail) | -1.1R, 50% positive, 35% of resamples (fail) | +18.6R, 80% positive, 98.7% of resamples (pass); random settings of the same directions -72.3R (beaten) |
| 5m | 12,000 | 54% | 7% | 3.2% | -6.2R, 32% positive, 16% of resamples (fail) | +9.4R, 55% positive, 80% of resamples (fail) | -4.5R, 32% positive, 22% of resamples (fail) | +27.0R, 76% positive, 99.1% of resamples (pass); random settings of the same directions -150.2R (beaten) |
| 10m | 12,000 | 51% | 13% | 6.3% | -4.3R, 35% positive, 3% of resamples (fail) | +1.1R, 50% positive, 56% of resamples (fail) | +0.7R, 48% positive, 59% of resamples (fail) | +25.3R, 80% positive, 99.5% of resamples (pass); random settings of the same directions -19.8R (beaten) |
| 15m | 16,000 | 49% | 15% | 7.1% | -5.5R, 28% positive, 11% of resamples (fail) | -3.3R, 40% positive, 9% of resamples (fail) | -2.8R, 32% positive, 18% of resamples (fail) | +14.7R, 84% positive, 100.0% of resamples (pass); random settings of the same directions -16.1R (beaten) |
| 30m | 16,000 | 50% | 19% | 8.6% | -5.0R, 42% positive, 20% of resamples (fail) | +2.2R, 57% positive, 80% of resamples (fail) | -6.3R, 35% positive, 20% of resamples (fail) | +12.1R, 84% positive, 93.2% of resamples (fail); random settings of the same directions -8.6R (beaten) |
| 1h | 16,000 | 51% | 23% | 9.9% | -2.0R, 45% positive, 37% of resamples (fail) | +0.9R, 55% positive, 79% of resamples (fail) | -2.8R, 32% positive, 26% of resamples (fail) | +17.1R, 92% positive, 99.6% of resamples (pass); random settings of the same directions +4.7R (beaten) |
| 4h | 16,000 | 50% | 32% | 15.3% | -3.6R, 30% positive, 17% of resamples (fail) | -1.1R, 45% positive, 16% of resamples (fail) | -2.6R, 35% positive, 31% of resamples (fail) | +12.5R, 68% positive, 96.6% of resamples (pass); random settings of the same directions +11.9R (not beaten) |

## The two trade directions on data the search never saw

400 random settings of the search per timeframe (at least 30 trades in each half of the search window), run over the untouched
period and split by trade direction; then the same split on the search window for all settings of the search with at least 30
trades in each half (58,800 of the 110,000).
"Positive" = net result above zero over the whole period after 0.05% per side, 1 tick and funding. The last two columns:
positive in both halves of the search window, after costs / before costs.

| Chart | Untouched: with the filter positive | Median | Untouched: inverted positive | Median | Search window: with the filter positive | Median | Inverted positive | Median | Both halves, with the filter | Both halves, inverted |
|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 10% of 202 | -134.5R | 2% of 198 | -181.1R | 4% | -241.3R | 1% | -292.3R | 1.4% / 38.3% | 0.4% / 33.0% |
| 2m | 16% of 198 | -28.4R | 11% of 202 | -28.0R | 8% | -45.0R | 3% | -48.1R | 4.1% / 30.6% | 1.4% / 23.1% |
| 3m | 15% of 202 | -26.3R | 10% of 198 | -34.6R | 11% | -41.1R | 2% | -60.4R | 5.8% / 41.9% | 0.9% / 19.0% |
| 5m | 26% of 184 | -24.0R | 6% of 216 | -55.6R | 13% | -47.3R | 2% | -76.7R | 6.0% / 48.0% | 0.6% / 16.1% |
| 10m | 30% of 212 | -9.6R | 16% of 188 | -15.8R | 21% | -15.1R | 6% | -29.0R | 10.4% / 41.0% | 2.2% / 13.7% |
| 15m | 43% of 208 | -3.4R | 9% of 192 | -25.1R | 25% | -12.7R | 5% | -34.7R | 12.8% / 47.7% | 1.6% / 12.0% |
| 30m | 55% of 199 | +1.4R | 10% of 201 | -28.3R | 31% | -7.9R | 7% | -29.8R | 15.0% / 48.3% | 2.3% / 11.9% |
| 1h | 66% of 210 | +5.1R | 4% of 190 | -26.0R | 37% | -4.4R | 8% | -24.7R | 16.7% / 47.0% | 3.0% / 10.7% |
| 4h | 83% of 203 | +8.1R | 10% of 197 | -14.1R | 53% | +0.7R | 11% | -12.6R | 27.1% / 47.7% | 3.5% / 8.2% |

## Is there more here than luck?

To see what luck alone produces, the search results were scrambled 1,000 times per chart: months were drawn at random and, in
each month, the before-cost results of all settings were flipped together by one coin toss. No setting has an edge after that,
but fees, trade counts and the similarity between settings stay as they are. These are the luck-only worlds. A real count inside
the luck-only range is no evidence of an edge.

| Chart | Positive in both halves: real | Luck alone (5% to 95% of worlds) | Worlds with at least as many | Candidates: real | Luck alone | Worlds with at least as many | With the filter minus inverted: real | Luck alone | Worlds with a gap this large |
|---|---|---|---|---|---|---|---|---|---|
| 1m | 0.9% | 0.5% (0.2 to 1.1%) | 10% | 12 | 5 (1 to 20) | 17% | +1.1 points | -0.5 to +1.1 | 6% |
| 2m | 2.8% | 1.4% (0.6 to 2.7%) | 4% | 39 | 13 (3 to 37) | 5% | +2.8 points | -1.7 to +1.9 | 3% |
| 3m | 3.3% | 1.6% (0.7 to 2.9%) | 2% | 52 | 18 (6 to 44) | 2% | +5.0 points | -1.8 to +2.8 | 0% |
| 5m | 3.2% | 1.6% (0.8 to 3.2%) | 5% | 79 | 32 (12 to 88) | 7% | +5.3 points | -2.1 to +3.1 | 1% |
| 10m | 6.3% | 4.1% (2.2 to 7.1%) | 10% | 115 | 66 (27 to 152) | 12% | +8.4 points | -6.1 to +7.4 | 5% |
| 15m | 7.1% | 4.2% (2.3 to 7.1%) | 5% | 221 | 111 (49 to 236) | 7% | +11.3 points | -6.3 to +7.6 | 2% |
| 30m | 8.6% | 5.4% (3.2 to 8.9%) | 7% | 302 | 167 (82 to 341) | 9% | +12.9 points | -8.1 to +9.7 | 2% |
| 1h | 9.9% | 7.1% (4.0 to 11.9%) | 15% | 423 | 262 (128 to 526) | 14% | +14.0 points | -10.3 to +13.6 | 6% |
| 4h | 15.3% | 11.9% (7.0 to 19.3%) | 20% | 751 | 551 (291 to 1074) | 22% | +23.8 points | -23.0 to +25.6 | 11% |

What a pick is worth when nothing is there: the steadiest candidate of each luck-only world, on the months it was chosen on and
on further months it was not chosen on, and how often luck alone meets the conditions of each verdict (the neighbour test of
section 3 taken as passed, months standing in for weeks).

| Chart | Luck's pick where it was chosen (median, 95th percentile) | Luck's pick on months it was not chosen on | Positive there | Positive there at base and stressed costs with 50+ trades | Luck passes at least one of the four tests | Luck earns PAPER-TRADE or better | USABLE or better | RECOMMENDED |
|---|---|---|---|---|---|---|---|---|
| 1m | +65.4R, +365.5R | -12.1R | 33% | 20% | 2.9% | 6.5% | 1.1% | 0.0% |
| 2m | +52.2R, +236.4R | -9.0R | 32% | 20% | 3.4% | 4.9% | 0.6% | 0.0% |
| 3m | +45.3R, +180.9R | -7.9R | 33% | 21% | 3.3% | 4.9% | 0.3% | 0.0% |
| 5m | +36.1R, +152.0R | -8.4R | 28% | 17% | 3.1% | 4.8% | 0.1% | 0.0% |
| 10m | +31.0R, +122.8R | -5.1R | 32% | 20% | 3.7% | 5.4% | 0.2% | 0.0% |
| 15m | +28.9R, +95.4R | -4.6R | 33% | 21% | 3.3% | 5.1% | 0.4% | 0.0% |
| 30m | +28.4R, +103.0R | -4.9R | 32% | 20% | 3.4% | 4.6% | 0.7% | 0.0% |
| 1h | +27.3R, +88.7R | -3.9R | 34% | 22% | 5.2% | 5.2% | 0.3% | 0.0% |
| 4h | +24.3R, +74.7R | -2.7R | 36% | 27% | 6.4% | 7.3% | 0.7% | 0.0% |

## The shipped inputs on BTCUSDT

The inputs of AMVI_FGF_Inverted_XAUUSD_15m.pine unchanged (calibrated for gold on 15m: 60m filter, trade direction Inverted), run on
each BTC chart timeframe. On the 2m and 10m charts the 15m AMVI does not line up with the chart's candles; the numbers there are what
a reloaded chart shows.

| Chart | Search window (2023-11 to 2026-10) | Stressed costs | Untouched 2021-01 to 2023-10 |
|---|---|---|---|
| 1m | -597.0R, 726 trades, PF 0.52, DD 686.9R | -1187.4R | -616.0R, 674 trades, PF 0.40 |
| 2m | -507.2R, 742 trades, PF 0.54, DD 541.6R | -946.0R | -376.1R, 652 trades, PF 0.57 |
| 3m | -420.7R, 754 trades, PF 0.60, DD 453.1R | -794.4R | -376.1R, 657 trades, PF 0.56 |
| 5m | -294.8R, 755 trades, PF 0.69, DD 372.4R | -598.3R | -372.4R, 688 trades, PF 0.56 |
| 10m | -214.8R, 561 trades, PF 0.68, DD 285.6R | -394.8R | -35.7R, 527 trades, PF 0.94 |
| 15m | -188.7R, 597 trades, PF 0.72, DD 244.6R | -338.1R | -49.6R, 541 trades, PF 0.91 |
| 30m | -137.5R, 529 trades, PF 0.75, DD 177.5R | -239.0R | -72.0R, 472 trades, PF 0.85 |
| 1h | -105.0R, 902 trades, PF 0.87, DD 141.6R | -239.5R | -238.0R, 811 trades, PF 0.68 |
| 4h | -97.6R, 671 trades, PF 0.80, DD 115.2R | -149.8R | -57.7R, 575 trades, PF 0.86 |

## What one trade costs

Commission of a round trip at 0.05% per side, in R, when the stop is 1 x ATR(14) of the chart (a 2 x ATR stop halves it). The market
moved more per candle on the untouched period, so the same commission was a smaller share of the risk then.

| Chart | Search window: median ATR(14) as % of price | Round-trip commission in R | Untouched period: median ATR(14) | Round-trip commission in R |
|---|---|---|---|---|
| 1m | 0.058% | 1.73R | 0.089% | 1.12R |
| 2m | 0.089% | 1.12R | 0.134% | 0.75R |
| 3m | 0.114% | 0.88R | 0.170% | 0.59R |
| 5m | 0.155% | 0.65R | 0.229% | 0.44R |
| 10m | 0.231% | 0.43R | 0.334% | 0.30R |
| 15m | 0.295% | 0.34R | 0.419% | 0.24R |
| 30m | 0.433% | 0.23R | 0.607% | 0.16R |
| 1h | 0.630% | 0.16R | 0.883% | 0.11R |
| 4h | 1.305% | 0.08R | 1.859% | 0.05R |

## Trailing stop

The same settings (a random sample of the search: 300 per timeframe, 200 on 5m and below) with the trailing stop off and with
each of the 42 Trail Activation x Trail Offset pairs, nothing else changed, on the second-by-second price path. "Both halves" =
share of the settings positive after costs in both halves of the search window. The best of 42 pairs is partly the luckiest of
42, so it was chosen on one random half of the settings and is read on the other half. The last three columns are for a tight
pair (0.5 / 0.5 ATR): what a walk on the chart's candles shows, how much profit per trade that invents, and the real figure.

| Chart | Trailing off: both halves | With trailing: median of the 42 pairs | Pairs above "off" | Best pair chosen on half the settings (activation / offset) | On the other half: with it vs trailing off | Shipped pair 1.5 / 1.0 | It makes a setting better / leaves it unchanged / worse | Tight pair on chart candles | Profit it invents per trade | Tight pair second by second |
|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 0.0% | 0.0% | 7 of 42 | 0.5 / 0.5 | 0.0% vs 0.0% | 0.0% | 42% / 10% / 49% | 0.0% | +0.07R | 0.0% |
| 2m | 6.5% | 1.0% | 0 of 42 | 1 / 2 | 0.0% vs 7.0% | 1.0% | 44% / 18% / 38% | 0.5% | +0.05R | 0.0% |
| 3m | 3.0% | 1.0% | 0 of 42 | 2 / 0.5 | 1.0% vs 3.0% | 1.0% | 42% / 10% / 48% | 0.0% | +0.07R | 0.0% |
| 5m | 4.5% | 1.5% | 0 of 42 | 6 / 3 | 0.0% vs 1.0% | 1.5% | 34% / 16% / 50% | 1.5% | +0.08R | 0.0% |
| 10m | 7.3% | 3.5% | 0 of 42 | 6 / 1.5 | 4.7% vs 8.7% | 2.7% | 37% / 16% / 48% | 7.7% | +0.07R | 0.7% |
| 15m | 11.3% | 6.8% | 0 of 42 | 6 / 1.5 | 12.0% vs 14.0% | 6.0% | 38% / 13% / 49% | 13.3% | +0.09R | 0.3% |
| 30m | 10.0% | 6.8% | 1 of 42 | 3 / 3 | 5.3% vs 8.7% | 4.3% | 33% / 16% / 51% | 20.0% | +0.09R | 0.7% |
| 1h | 13.0% | 9.2% | 0 of 42 | 4 / 3 | 7.3% vs 11.3% | 7.0% | 33% / 13% / 53% | 43.0% | +0.10R | 3.3% |
| 4h | 14.7% | 14.2% | 17 of 42 | 0.5 / 3 | 20.7% vs 17.3% | 8.7% | 38% / 17% / 45% | 49.0% | +0.08R | 4.3% |

All 42 pairs for every timeframe: `results/TRAILING.md`.

## Direction and exits across timeframes

Share of the search's settings positive in both halves, by one input's value (all other inputs random). Each cell: after costs /
before costs / the commission a typical setting of the group paid in three years. Where two values differ after costs but not
before, the difference is commission, not better trades.

| Chart | With the filter | Inverted | Trailing off | Trailing on | Stop up to 1 ATR | Stop 4 ATR and more | No target | Target on | No time stop | Time stop on |
|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 1.4% / 38.3% / 257R | 0.4% / 33.0% / 284R | 1.4% / 32.2% / 267R | 0.1% / 40.9% / 277R | 0.7% / 46.9% / 809R | 1.3% / 30.5% / 119R | 2.3% / 39.8% / 242R | 0.2% / 33.6% / 284R | 1.6% / 35.6% / 286R | 0.1% / 35.7% / 253R |
| 2m | 4.1% / 30.6% / 48R | 1.4% / 23.1% / 42R | 3.9% / 26.1% / 45R | 1.1% / 28.1% / 46R | 0.4% / 26.3% / 165R | 4.3% / 31.1% / 18R | 5.8% / 25.3% / 47R | 1.3% / 27.7% / 45R | 4.7% / 26.2% / 44R | 0.6% / 27.7% / 47R |
| 3m | 5.8% / 41.9% / 51R | 0.9% / 19.0% / 51R | 4.8% / 29.5% / 50R | 1.2% / 31.1% / 52R | 0.5% / 29.8% / 173R | 5.2% / 30.6% / 22R | 5.3% / 30.6% / 47R | 2.3% / 30.0% / 54R | 5.0% / 30.5% / 51R | 1.4% / 29.8% / 50R |
| 5m | 6.0% / 48.0% / 61R | 0.6% / 16.1% / 63R | 4.2% / 32.0% / 62R | 1.8% / 31.2% / 63R | 1.0% / 34.3% / 226R | 4.5% / 29.3% / 27R | 6.1% / 34.3% / 60R | 1.8% / 30.4% / 65R | 4.7% / 32.4% / 64R | 1.5% / 30.8% / 62R |
| 10m | 10.4% / 41.0% / 22R | 2.2% / 13.7% / 21R | 7.7% / 27.5% / 21R | 4.4% / 27.1% / 22R | 2.3% / 27.6% / 78R | 8.6% / 27.4% / 8R | 9.5% / 27.9% / 20R | 4.7% / 27.1% / 22R | 8.5% / 28.7% / 21R | 3.7% / 25.8% / 22R |
| 15m | 12.8% / 47.7% / 24R | 1.6% / 12.0% / 24R | 8.8% / 30.3% / 24R | 4.7% / 28.2% / 24R | 2.6% / 26.6% / 81R | 9.7% / 29.4% / 9R | 9.8% / 28.7% / 22R | 5.7% / 29.8% / 24R | 9.3% / 30.4% / 24R | 4.6% / 28.4% / 24R |
| 30m | 15.0% / 48.3% / 19R | 2.3% / 11.9% / 19R | 10.1% / 30.9% / 19R | 6.3% / 27.9% / 19R | 4.4% / 29.3% / 68R | 9.7% / 26.7% / 7R | 12.7% / 31.8% / 19R | 6.5% / 28.6% / 19R | 9.7% / 29.3% / 19R | 7.2% / 30.1% / 19R |
| 1h | 16.7% / 47.0% / 14R | 3.0% / 10.7% / 15R | 11.6% / 29.7% / 14R | 7.3% / 27.4% / 15R | 4.8% / 26.5% / 56R | 11.7% / 26.1% / 6R | 13.6% / 31.0% / 14R | 8.0% / 27.6% / 15R | 11.0% / 29.1% / 14R | 8.5% / 28.4% / 15R |
| 4h | 27.1% / 47.7% / 6R | 3.5% / 8.2% / 6R | 16.0% / 27.6% / 6R | 14.3% / 28.2% / 6R | 10.5% / 25.1% / 23R | 16.1% / 26.1% / 2R | 19.3% / 30.4% / 6R | 13.3% / 26.6% / 6R | 15.6% / 27.8% / 6R | 14.9% / 27.9% / 6R |

Every input, value by value, for every timeframe: `results/INPUTS.md`.

## Settings per timeframe

### 1m: PAPER-TRADE

PAPER-TRADE because it made money on 2021-2023, which it was not chosen on, at base and stressed costs, but only in 93% of resamples of its weeks (95% needed). File: `presets/AMVI_FGF_BTCUSDT_1m.pine` (watch with alerts only; no money).

- On data it was not chosen on (untouched 2021-01 to 2023-10): 93 trades (49L/44S), +54.8R, PF 1.75, 26% winners, max DD 15.2R, longest losing streak 12, 16 of 34 months positive; stressed costs +49.0R; positive in 93% of resamples of its weeks. 77% of that result came in 2023. +22.1R of it is a trade still open at the end of the period, marked at the last close (without it +32.7R).
- Where it was chosen (search window): 145 trades (73L/72S), +107.1R, PF 1.83, 18% winners, max DD 29.2R, longest losing streak 11, 13 of 36 months positive; halves +50.2 / +56.9R. The best month (2026-08) made +70.3R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +65R here (95th percentile +365R) and -12R on months it was not chosen on.
- Holding time: 3.6 days on average and 47.7 days at most in the search window (6.4 days and 46.5 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +53.6% in three years with a worst drawdown of about 14.6% (no compounding), and the untouched period about +27.4% with a worst drawdown of 7.6%. The stop is 1.29% of price on average, so 0.5% risk asks for about 0.4x leverage.
- Costs (search window): Bitget 0.06% +104.3R; no costs +124.5R; stressed +92.8R; break-even commission 0.424% per side. Fees took 14.3R and funding +3.0R.
- Price path (search window): second by second +107.1R; on 1-minute bars +107.1R; on the chart's candles +107.1R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 145 trades, 18% profitable, profit factor about 1.8, net profit about +54% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 12 steadiest candidates made +60.3R on average (83% of them made money; positive in 96.9% of resamples of the months): pass. Random groups with the candidates' trade directions (1 of 12 inverted) made -1438.1R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 88% of 25 neighbouring settings positive in both halves; sensitive to: Time Stop; Normalization Period; Take Profit.
- Concentration (search window): 10 biggest trades +207.5R, all others -100.4R; positive in 91.0% of resamples of its weeks.
- Same inputs, other trade direction: -22.5R.

| Input | Shipped | This file |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 14 |
| StdDev Period (`stdDevPeriod`) | 20 | 10 |
| Candle Range Period (`candleRangePeriod`) | 20 | 30 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.55 |
| VR Weight (`vrWeight`) | 0.25 | 0.15 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.15 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 8.0 |
| Filter timeframe (`fgfTf`) | "60" | "D" |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "D" |
| Minimum child zones aligned (`fgfMinAligned`) | 0 | 1 |
| 15m (`en15`) | true | false |
| 4h (`en240`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 23 | +18.4 | 35% | 11.1 |
| 2022 (untouched) | 39 | -5.6 | 18% | 14.1 |
| 2023 (Jan-Oct, untouched) | 31 | +42.0 | 29% | 13.3 |
| 2023 (Nov-Dec) | 10 | +7.4 | 10% | 5.6 |
| 2024 | 43 | +35.0 | 28% | 10.9 |
| 2025 | 55 | -14.7 | 15% | 22.5 |
| 2026 (Jan-Oct) | 37 | +79.4 | 14% | 12.0 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 118 | -129.6 | -1.10 |
| reversal | 27 | +236.7 | +8.77 |

### 2m: NOT RECOMMENDED

NOT RECOMMENDED because it does not hold up on 2021-2023 (it loses there at stressed costs), although the 25 steadiest candidates passed the test there as a group. No file was written. The inputs below are listed only so that the result can be reproduced; they are not a setup to trade.

- On data it was not chosen on (untouched 2021-01 to 2023-10): 108 trades (53L/55S), +1.3R, PF 1.05, 77% winners, max DD 4.2R, longest losing streak 4, 16 of 34 months positive; stressed costs -3.4R; positive in 60% of resamples of its weeks. 96% of that result came in 2023.
- Where it was chosen (search window): 97 trades (46L/51S), +12.0R, PF 1.81, 86% winners, max DD 2.6R, longest losing streak 2, 24 of 36 months positive; halves +6.5 / +5.5R. The best month (2024-05) made +1.4R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +52R here (95th percentile +236R) and -9R on months it was not chosen on.
- Holding time: 6 hours on average and 5.5 days at most in the search window (6 hours and 2.3 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +6.0% in three years with a worst drawdown of about 1.3% (no compounding), and the untouched period about +0.6% with a worst drawdown of 2.1%. The stop is 2.20% of price on average, so 0.5% risk asks for about 0.2x leverage.
- Costs (search window): Bitget 0.06% +10.9R; no costs +17.1R; stressed +6.8R; break-even commission 0.166% per side. Fees took 5.2R and funding -0.0R.
- Price path (search window): second by second +12.0R; on 1-minute bars +12.0R; on the chart's candles +12.0R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 97 trades, 86% profitable, profit factor about 1.7, net profit about +5% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +54.0R on average (72% of them made money; positive in 96.1% of resamples of the months): pass. Random groups with the candidates' trade directions (4 of 25 inverted) made -50.2R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 92% of 25 neighbouring settings positive in both halves; sensitive to: No-trade band, ATR mult; Time Stop.
- Concentration (search window): 10 biggest trades +3.5R, all others +8.4R; positive in 99.5% of resamples of its weeks.
- Same inputs, other trade direction: -22.4R.

| Input | Shipped | This pick |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 10 |
| StdDev Period (`stdDevPeriod`) | 20 | 30 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.2 |
| VR Weight (`vrWeight`) | 0.25 | 0.5 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.15 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 50.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Candles to wait after an entry (0 = off) (`amviWait`) | 0 | 20 |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 8.0 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 3.0 |
| Filter timeframe (`fgfTf`) | "60" | "240" |
| Level (`fgfLvMode`) | "Signal close" | "Entry price" |
| No-trade band, ATR mult (`fgfBandAtr`) | 0.5 | 1.5 |
| Entry distance, ATR mult (ATR unit) (`fgfEntryDistAtr`) | 0.25 | 0.1 |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "D" |
| 15m (`en15`) | true | false |
| 30m (`en30`) | false | true |
| 1h (`en60`) | true | false |
| 4h (`en240`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 30 | -0.9 | 73% | 2.8 |
| 2022 (untouched) | 40 | +1.0 | 78% | 3.1 |
| 2023 (Jan-Oct, untouched) | 38 | +1.2 | 79% | 2.6 |
| 2023 (Nov-Dec) | 6 | +2.0 | 100% | 0.0 |
| 2024 | 36 | +3.6 | 83% | 1.8 |
| 2025 | 24 | +2.1 | 83% | 2.1 |
| 2026 (Jan-Oct) | 31 | +4.4 | 87% | 1.1 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 14 | -14.7 | -1.05 |
| take profit | 83 | +26.7 | +0.32 |

### 3m: USABLE

USABLE because it made money on 2021-2023, which it was not chosen on, at base and stressed costs and in 100% of resamples of its weeks; the 25 steadiest candidates did too as a group; the three hold-out tests inside the last three years fail. File: `presets/AMVI_FGF_BTCUSDT_3m.pine` (test with alerts first; small size at most).

- On data it was not chosen on (untouched 2021-01 to 2023-10): 72 trades (37L/35S), +20.6R, PF 2.56, 54% winners, max DD 2.9R, longest losing streak 4, 20 of 34 months positive; stressed costs +16.9R; positive in 100% of resamples of its weeks. 80% of that result came in 2023.
- Where it was chosen (search window): 79 trades (45L/34S), +23.4R, PF 2.13, 61% winners, max DD 2.9R, longest losing streak 4, 19 of 36 months positive; halves +11.3 / +12.0R. The best month (2024-08) made +4.4R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +45R here (95th percentile +181R) and -8R on months it was not chosen on.
- Holding time: 4 hours on average and 5 hours at most in the search window (4 hours and 5 hours on the untouched period): inside your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +11.7% in three years with a worst drawdown of about 1.4% (no compounding), and the untouched period about +10.3% with a worst drawdown of 1.4%. The stop is 1.72% of price on average, so 0.5% risk asks for about 0.3x leverage.
- Costs (search window): Bitget 0.06% +22.2R; no costs +29.0R; stressed +17.7R; break-even commission 0.258% per side. Fees took 5.6R and funding +0.1R.
- Price path (search window): second by second +23.4R; on 1-minute bars +23.4R; on the chart's candles +23.4R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 79 trades, 58% profitable, profit factor about 2.1, net profit about +11% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +18.6R on average (80% of them made money; positive in 98.7% of resamples of the months): pass. Random groups with the candidates' trade directions (2 of 25 inverted) made -72.3R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 93% of 28 neighbouring settings positive in both halves; sensitive to: Burst threshold, ATR mult; Min TFs Above High Vol.
- Concentration (search window): 10 biggest trades +14.4R, all others +9.0R; positive in 99.6% of resamples of its weeks.
- Same inputs, other trade direction: -24.3R.

| Input | Shipped | This file |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 5 |
| Slow ATR Period (`slowATRPeriod`) | 100 | 50 |
| Candle Range Period (`candleRangePeriod`) | 20 | 30 |
| Normalization Period (`normalizationPeriod`) | 200 | 400 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.2 |
| VR Weight (`vrWeight`) | 0.25 | 0.5 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.15 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 70.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Candles to wait after an entry (0 = off) (`amviWait`) | 0 | 20 |
| Exit ATR Length (`exitAtrLen`) | 14 | 7 |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 4.0 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 6.0 |
| Time Stop (bars, 0 = off) (`maxBars`) | 0 | 96 |
| Filter timeframe (`fgfTf`) | "60" | "240" |
| No-trade band, ATR mult (`fgfBandAtr`) | 0.5 | 1.5 |
| Allow trading against the signal (`fgfAgainst`) | true | false |
| Require burst gate (`fgfUseBurst`) | false | true |
| Allow any combo (`fgfAnyCombo`) | true | false |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "240" |
| Minimum child zones aligned (`fgfMinAligned`) | 0 | 2 |
| 15m (`en15`) | true | false |
| 30m (`en30`) | false | true |
| 1h (`en60`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 24 | +4.4 | 58% | 2.5 |
| 2022 (untouched) | 15 | -0.2 | 40% | 2.9 |
| 2023 (Jan-Oct, untouched) | 33 | +16.4 | 58% | 1.7 |
| 2023 (Nov-Dec) | 6 | -0.8 | 50% | 1.2 |
| 2024 | 22 | +11.9 | 73% | 2.2 |
| 2025 | 31 | +6.0 | 55% | 2.9 |
| 2026 (Jan-Oct) | 20 | +6.3 | 60% | 2.9 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 14 | -15.1 | -1.08 |
| take profit | 23 | +32.5 | +1.41 |
| time stop | 42 | +6.0 | +0.14 |

### 5m: NOT RECOMMENDED

NOT RECOMMENDED because it does not hold up on 2021-2023 (it lost there), although the 25 steadiest candidates passed the test there as a group. No file was written. The inputs below are listed only so that the result can be reproduced; they are not a setup to trade.

- On data it was not chosen on (untouched 2021-01 to 2023-10): 70 trades (44L/26S), -1.0R, PF 0.98, 46% winners, max DD 6.7R, longest losing streak 5, 20 of 34 months positive; stressed costs -4.8R; positive in 45% of resamples of its weeks.
- Where it was chosen (search window): 68 trades (38L/30S), +16.1R, PF 1.51, 56% winners, max DD 5.2R, longest losing streak 3, 20 of 36 months positive; halves +7.1 / +9.1R. The best month (2024-02) made +5.0R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +36R here (95th percentile +152R) and -8R on months it was not chosen on.
- Holding time: 22 hours on average and 8.5 days at most in the search window (23 hours and 7.9 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +8.1% in three years with a worst drawdown of about 2.6% (no compounding), and the untouched period about -0.5% with a worst drawdown of 3.3%. The stop is 1.80% of price on average, so 0.5% risk asks for about 0.3x leverage.
- Costs (search window): Bitget 0.06% +15.2R; no costs +20.7R; stressed +11.6R; break-even commission 0.229% per side. Fees took 4.5R and funding +0.0R.
- Price path (search window): second by second +16.1R; on 1-minute bars +16.1R; on the chart's candles +16.1R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 68 trades, 56% profitable, profit factor about 1.5, net profit about +8% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +27.0R on average (76% of them made money; positive in 99.1% of resamples of the months): pass. Random groups with the candidates' trade directions (4 of 25 inverted) made -150.2R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 96% of 28 neighbouring settings positive in both halves; sensitive to: Burst threshold, ATR mult.
- Concentration (search window): 10 biggest trades +13.0R, all others +3.2R; positive in 96.0% of resamples of its weeks.
- Same inputs, other trade direction: -26.8R.

| Input | Shipped | This pick |
|---|---|---|
| Slow ATR Period (`slowATRPeriod`) | 100 | 200 |
| Candle Range Period (`candleRangePeriod`) | 20 | 30 |
| Normalization Period (`normalizationPeriod`) | 200 | 400 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.2 |
| VR Weight (`vrWeight`) | 0.25 | 0.5 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.15 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Candles to wait after an entry (0 = off) (`amviWait`) | 0 | 10 |
| Exit ATR Length (`exitAtrLen`) | 14 | 21 |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 6.0 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 8.0 |
| Filter timeframe (`fgfTf`) | "60" | "240" |
| Level (`fgfLvMode`) | "Signal close" | "Entry price" |
| Check price on (`fgfCheckIn`) | "Tick" | "Level at candle open" |
| No-trade band, ATR mult (`fgfBandAtr`) | 0.5 | 1.5 |
| Allow trading against the signal (`fgfAgainst`) | true | false |
| Entry distance, ATR mult (ATR unit) (`fgfEntryDistAtr`) | 0.25 | 0.1 |
| Require burst gate (`fgfUseBurst`) | false | true |
| Allow any combo (`fgfAnyCombo`) | true | false |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "240" |
| 5m (`en5`) | false | true |
| 15m (`en15`) | true | false |
| 1h (`en60`) | true | false |
| 4h (`en240`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 19 | +0.9 | 47% | 5.5 |
| 2022 (untouched) | 24 | -2.2 | 42% | 5.9 |
| 2023 (Jan-Oct, untouched) | 27 | +0.4 | 48% | 5.4 |
| 2023 (Nov-Dec) | 3 | -0.9 | 33% | 2.1 |
| 2024 | 23 | +8.3 | 61% | 3.1 |
| 2025 | 23 | +1.1 | 48% | 5.2 |
| 2026 (Jan-Oct) | 19 | +7.6 | 63% | 2.2 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 30 | -31.9 | -1.06 |
| take profit | 38 | +48.0 | +1.26 |

### 10m: NOT RECOMMENDED

NOT RECOMMENDED because it does not hold up on 2021-2023 (its gain there stays positive in only 81% of resamples of its weeks, so a few good weeks carry it), although the 25 steadiest candidates passed the test there as a group. No file was written. The inputs below are listed only so that the result can be reproduced; they are not a setup to trade.

- On data it was not chosen on (untouched 2021-01 to 2023-10): 65 trades (38L/27S), +8.7R, PF 1.31, 58% winners, max DD 6.4R, longest losing streak 6, 14 of 34 months positive; stressed costs +6.0R; positive in 81% of resamples of its weeks. All of that result came in 2023; the other years together lost.
- Where it was chosen (search window): 85 trades (45L/40S), +14.5R, PF 1.44, 62% winners, max DD 5.7R, longest losing streak 4, 18 of 36 months positive; halves +7.3 / +7.2R. The best month (2025-11) made +3.8R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +31R here (95th percentile +123R) and -5R on months it was not chosen on.
- Holding time: 17 hours on average and 6.8 days at most in the search window (22 hours and 6.8 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +7.3% in three years with a worst drawdown of about 2.9% (no compounding), and the untouched period about +4.4% with a worst drawdown of 3.2%. The stop is 2.13% of price on average, so 0.5% risk asks for about 0.2x leverage.
- Costs (search window): Bitget 0.06% +13.6R; no costs +19.2R; stressed +10.2R; break-even commission 0.211% per side. Fees took 4.5R and funding +0.1R.
- Price path (search window): second by second +14.5R; on 1-minute bars +14.5R; on the chart's candles +16.8R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 85 trades, 62% profitable, profit factor about 1.5, net profit about +8% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +25.3R on average (80% of them made money; positive in 99.5% of resamples of the months): pass. Random groups with the candidates' trade directions (4 of 25 inverted) made -19.8R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 94% of 31 neighbouring settings positive in both halves; sensitive to: Candle Range Period; Time Stop.
- Concentration (search window): 10 biggest trades +14.3R, all others +0.2R; positive in 95.3% of resamples of its weeks.
- Same inputs, other trade direction: -28.7R.
- Trailing stop restarted at every candle close (if TradingView does that): search window +15.4R, untouched +7.8R.

| Input | Shipped | This pick |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 10 |
| StdDev Period (`stdDevPeriod`) | 20 | 30 |
| Normalization Period (`normalizationPeriod`) | 200 | 400 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.2 |
| VR Weight (`vrWeight`) | 0.25 | 0.15 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.5 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 80.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Candles to wait after an entry (0 = off) (`amviWait`) | 0 | 1 |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 4.0 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 6.0 |
| Use ATR Trailing Stop (`useTrail`) | false | true |
| Trail Activation (x ATR) (`trailActMul`) | 1.5 | 4.0 |
| Trail Offset (x ATR) (`trailOffMul`) | 1.0 | 1.5 |
| Filter timeframe (`fgfTf`) | "60" | "240" |
| Allow trading against the signal (`fgfAgainst`) | true | false |
| Prior drift bars (`fgfDriftBars`) | 60 | 120 |
| Use prior drift filter (`fgfUseDrift`) | false | true |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "240" |
| 15m (`en15`) | true | false |
| 30m (`en30`) | false | true |
| 4h (`en240`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 17 | -1.0 | 47% | 6.4 |
| 2022 (untouched) | 20 | -2.7 | 50% | 6.0 |
| 2023 (Jan-Oct, untouched) | 28 | +12.4 | 71% | 2.1 |
| 2023 (Nov-Dec) | 8 | -0.2 | 50% | 2.1 |
| 2024 | 23 | +5.6 | 65% | 3.1 |
| 2025 | 27 | +8.8 | 70% | 3.2 |
| 2026 (Jan-Oct) | 27 | +0.4 | 56% | 5.7 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 31 | -32.6 | -1.05 |
| take profit | 10 | +14.3 | +1.43 |
| trailing stop | 43 | +33.1 | +0.77 |
| open at the end | 1 | -0.3 | -0.29 |

### 15m: USABLE

USABLE because it made money on 2021-2023, which it was not chosen on, at base and stressed costs and in 99% of resamples of its weeks; the 25 steadiest candidates did too as a group; the three hold-out tests inside the last three years fail. File: `presets/AMVI_FGF_BTCUSDT_15m.pine` (test with alerts first; small size at most).

- On data it was not chosen on (untouched 2021-01 to 2023-10): 232 trades (112L/120S), +19.7R, PF 1.41, 56% winners, max DD 7.0R, longest losing streak 5, 22 of 34 months positive; stressed costs +14.7R; positive in 99% of resamples of its weeks. 69% of that result came in 2021.
- Where it was chosen (search window): 284 trades (134L/150S), +21.1R, PF 1.35, 54% winners, max DD 3.7R, longest losing streak 5, 24 of 36 months positive; halves +10.7 / +10.4R. The best month (2026-06) made +3.8R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +29R here (95th percentile +95R) and -5R on months it was not chosen on.
- Holding time: 19 hours on average and 24 hours at most in the search window (18 hours and 24 hours on the untouched period): inside your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +10.6% in three years with a worst drawdown of about 1.8% (no compounding), and the untouched period about +9.8% with a worst drawdown of 3.5%. The stop is 4.27% of price on average, so 0.5% risk asks for about 0.1x leverage.
- Costs (search window): Bitget 0.06% +19.6R; no costs +28.8R; stressed +13.6R; break-even commission 0.191% per side. Fees took 7.5R and funding +0.1R.
- Price path (search window): second by second +21.1R; on 1-minute bars +21.1R; on the chart's candles +21.1R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 284 trades, 54% profitable, profit factor about 1.3, net profit about +10% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +14.7R on average (84% of them made money; positive in 100.0% of resamples of the months): pass. Random groups with the candidates' trade directions (1 of 25 inverted) made -16.1R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 100% of 23 neighbouring settings positive in both halves.
- Concentration (search window): 10 biggest trades +7.4R, all others +13.7R; positive in 98.9% of resamples of its weeks.
- Same inputs, other trade direction: -32.6R.

| Input | Shipped | This file |
|---|---|---|
| Slow ATR Period (`slowATRPeriod`) | 100 | 50 |
| Candle Range Period (`candleRangePeriod`) | 20 | 10 |
| Normalization Period (`normalizationPeriod`) | 200 | 400 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.55 |
| VR Weight (`vrWeight`) | 0.25 | 0.15 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.15 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 70.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 8.0 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 6.0 |
| Time Stop (bars, 0 = off) (`maxBars`) | 0 | 96 |
| Filter timeframe (`fgfTf`) | "60" | "D" |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "D" |
| 1h (`en60`) | true | false |
| 4h (`en240`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 75 | +13.5 | 64% | 1.9 |
| 2022 (untouched) | 75 | +2.5 | 53% | 3.0 |
| 2023 (Jan-Oct, untouched) | 82 | +3.7 | 51% | 7.0 |
| 2023 (Nov-Dec) | 15 | -0.2 | 47% | 1.5 |
| 2024 | 105 | +10.7 | 55% | 3.7 |
| 2025 | 98 | +3.7 | 51% | 3.6 |
| 2026 (Jan-Oct) | 66 | +7.0 | 56% | 2.9 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 25 | -25.7 | -1.03 |
| take profit | 93 | +67.2 | +0.72 |
| reversal | 7 | -4.2 | -0.60 |
| time stop | 159 | -16.2 | -0.10 |

### 30m: DO NOT TRADE

DO NOT TRADE because it does not hold up on 2021-2023 (its gain there stays positive in only 77% of resamples of its weeks, so a few good weeks carry it), and none of the four tests passes. No file was written. The inputs below are listed only so that the result can be reproduced; they are not a setup to trade.

- On data it was not chosen on (untouched 2021-01 to 2023-10): 68 trades (35L/33S), +4.8R, PF 1.22, 65% winners, max DD 3.8R, longest losing streak 3, 18 of 34 months positive; stressed costs +3.1R; positive in 77% of resamples of its weeks. 80% of that result came in 2022.
- Where it was chosen (search window): 74 trades (38L/36S), +20.2R, PF 2.22, 76% winners, max DD 3.3R, longest losing streak 2, 23 of 36 months positive; halves +12.3 / +8.0R. The best month (2026-08) made +3.6R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +28R here (95th percentile +103R) and -5R on months it was not chosen on.
- Holding time: 46 hours on average and 15.8 days at most in the search window (2.2 days and 25.2 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +10.1% in three years with a worst drawdown of about 1.7% (no compounding), and the untouched period about +2.4% with a worst drawdown of 1.9%. The stop is 3.83% of price on average, so 0.5% risk asks for about 0.1x leverage.
- Costs (search window): Bitget 0.06% +19.8R; no costs +22.4R; stressed +18.0R; break-even commission 0.510% per side. Fees took 2.2R and funding -0.1R.
- Price path (search window): second by second +20.2R; on 1-minute bars +21.5R; on the chart's candles +21.4R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 72 trades, 75% profitable, profit factor about 2.3, net profit about +10% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +12.1R on average (84% of them made money; positive in 93.2% of resamples of the months): fail. Random groups with the candidates' trade directions (1 of 25 inverted) made -8.6R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 100% of 25 neighbouring settings positive in both halves.
- Concentration (search window): 10 biggest trades +12.2R, all others +8.1R; positive in 99.8% of resamples of its weeks.
- Same inputs, other trade direction: -17.2R.
- Trailing stop restarted at every candle close (if TradingView does that): search window +24.0R, untouched +6.7R.

| Input | Shipped | This pick |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 14 |
| StdDev Period (`stdDevPeriod`) | 20 | 10 |
| Normalization Period (`normalizationPeriod`) | 200 | 100 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.25 |
| ACR Weight (`acrWeight`) | 0.15 | 0.25 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 50.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Candles to wait after an entry (0 = off) (`amviWait`) | 0 | 20 |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 6.0 |
| Use ATR Trailing Stop (`useTrail`) | false | true |
| Trail Activation (x ATR) (`trailActMul`) | 1.5 | 4.0 |
| Trail Offset (x ATR) (`trailOffMul`) | 1.0 | 1.5 |
| Filter timeframe (`fgfTf`) | "60" | "30" |
| No-trade band, ATR mult (`fgfBandAtr`) | 0.5 | 2.0 |
| 15m (`en15`) | true | false |
| 30m (`en30`) | false | true |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 14 | -1.3 | 57% | 3.3 |
| 2022 (untouched) | 30 | +3.9 | 67% | 3.4 |
| 2023 (Jan-Oct, untouched) | 24 | +2.3 | 67% | 3.8 |
| 2023 (Nov-Dec) | 4 | -0.7 | 50% | 2.1 |
| 2024 | 23 | +9.7 | 87% | 2.0 |
| 2025 | 28 | +7.7 | 75% | 2.1 |
| 2026 (Jan-Oct) | 19 | +3.5 | 68% | 2.7 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 15 | -15.4 | -1.03 |
| trailing stop | 56 | +36.8 | +0.66 |
| reversal | 3 | -1.2 | -0.39 |

### 1h: NOT RECOMMENDED

NOT RECOMMENDED because it does not hold up on 2021-2023 (its gain there stays positive in only 86% of resamples of its weeks, so a few good weeks carry it), although the 25 steadiest candidates passed the test there as a group. No file was written. The inputs below are listed only so that the result can be reproduced; they are not a setup to trade.

- On data it was not chosen on (untouched 2021-01 to 2023-10): 98 trades (98L/0S), +7.5R, PF 1.29, 74% winners, max DD 6.0R, longest losing streak 3, 19 of 34 months positive; stressed costs +3.8R; positive in 86% of resamples of its weeks.
- Where it was chosen (search window): 101 trades (101L/0S), +22.0R, PF 2.32, 84% winners, max DD 3.2R, longest losing streak 3, 25 of 36 months positive; halves +11.1 / +10.9R. The best month (2026-08) made +2.2R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +27R here (95th percentile +89R) and -4R on months it was not chosen on.
- Holding time: 13 hours on average and 5.8 days at most in the search window (8 hours and 3.2 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +11.0% in three years with a worst drawdown of about 1.6% (no compounding), and the untouched period about +3.7% with a worst drawdown of 3.0%. The stop is 2.63% of price on average, so 0.5% risk asks for about 0.2x leverage.
- Costs (search window): Bitget 0.06% +21.2R; no costs +26.5R; stressed +17.8R; break-even commission 0.312% per side. Fees took 4.2R and funding +0.3R.
- Price path (search window): second by second +22.0R; on 1-minute bars +22.0R; on the chart's candles +22.0R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 101 trades, 84% profitable, profit factor about 2.3, net profit about +11% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +17.1R on average (92% of them made money; positive in 99.6% of resamples of the months): pass. Random groups of with-the-filter settings made +4.7R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 100% of 22 neighbouring settings positive in both halves.
- Concentration (search window): 10 biggest trades +4.7R, all others +17.3R; positive in 100.0% of resamples of its weeks.
- Same inputs, other trade direction: -23.4R.

| Input | Shipped | This pick |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 10 |
| Slow ATR Period (`slowATRPeriod`) | 100 | 200 |
| StdDev Period (`stdDevPeriod`) | 20 | 10 |
| Candle Range Period (`candleRangePeriod`) | 20 | 30 |
| Normalization Period (`normalizationPeriod`) | 200 | 100 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 70.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Candles to wait after an entry (0 = off) (`amviWait`) | 0 | 5 |
| Exit ATR Length (`exitAtrLen`) | 14 | 30 |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 4.0 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 2.0 |
| No-trade band, ATR mult (`fgfBandAtr`) | 0.5 | 2.0 |
| Allow sells (`fgfAllowSell`) | true | false |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "240" |
| TDI RSI length (`fgfRsiLen`) | 14 | 7 |
| 15m (`en15`) | true | false |
| 30m (`en30`) | false | true |
| 4h (`en240`) | true | false |
| 1D (`enD`) | false | true |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 26 | +1.6 | 73% | 2.6 |
| 2022 (untouched) | 38 | +4.2 | 76% | 2.2 |
| 2023 (Jan-Oct, untouched) | 34 | +1.7 | 74% | 6.0 |
| 2023 (Nov-Dec) | 5 | +0.8 | 80% | 1.0 |
| 2024 | 34 | +9.6 | 88% | 1.6 |
| 2025 | 33 | +3.0 | 76% | 3.2 |
| 2026 (Jan-Oct) | 29 | +8.7 | 90% | 1.1 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 16 | -16.7 | -1.04 |
| take profit | 85 | +38.7 | +0.46 |

### 4h: USABLE

USABLE because it made money on 2021-2023, which it was not chosen on, at base and stressed costs and in 98% of resamples of its weeks; the 25 steadiest candidates did too as a group; the three hold-out tests inside the last three years fail. File: `presets/AMVI_FGF_BTCUSDT_4h.pine` (test with alerts first; small size at most).

- On data it was not chosen on (untouched 2021-01 to 2023-10): 69 trades (41L/28S), +21.4R, PF 1.71, 58% winners, max DD 8.3R, longest losing streak 6, 19 of 34 months positive; stressed costs +18.9R; positive in 98% of resamples of its weeks. 84% of that result came in 2023.
- Where it was chosen (search window): 100 trades (46L/54S), +35.2R, PF 1.84, 60% winners, max DD 5.7R, longest losing streak 5, 24 of 36 months positive; halves +22.4 / +12.9R. The best month (2025-04) made +5.1R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +24R here (95th percentile +75R) and -3R on months it was not chosen on.
- Holding time: 28 hours on average and 8.4 days at most in the search window (35 hours and 4.9 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +17.6% in three years with a worst drawdown of about 2.8% (no compounding), and the untouched period about +10.7% with a worst drawdown of 4.1%. The stop is 2.33% of price on average, so 0.5% risk asks for about 0.2x leverage.
- Costs (search window): Bitget 0.06% +34.3R; no costs +40.0R; stressed +30.5R; break-even commission 0.422% per side. Fees took 4.7R and funding +0.0R.
- Price path (search window): second by second +35.2R; on 1-minute bars +35.2R; on the chart's candles +32.9R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 100 trades, 59% profitable, profit factor about 1.7, net profit about +16% for 2023-11-01 to 2026-10-31; TradingView can replay this file only from about 2024-01-19 (as of 2026-11-26; a day later every day): from then about 94 trades, 61% profitable, net profit about +17%.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +12.5R on average (68% of them made money; positive in 96.6% of resamples of the months): pass. Random groups with the candidates' trade directions (3 of 25 inverted) made +11.9R on average; the candidates do not beat 95% of such groups, so the choice adds nothing measurable beyond the direction.
- Not fragile: 100% of 30 neighbouring settings positive in both halves.
- Concentration (search window): 10 biggest trades +13.2R, all others +22.1R; positive in 99.8% of resamples of its weeks.
- Same inputs, other trade direction: -31.0R.
- This setting reads 15m candles from a 4h chart. TradingView keeps about 100,000 candles of a lower timeframe per request on plans up to Premium (Ultimate is documented with 200,000; not checked), so on those plans its tester can replay it only back to about 2024-01-19 as of 2026-11-26, a day later for every later day (the day you check minus about 1,042 days); earlier trades of this record cannot be checked there.

| Input | Shipped | This file |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 10 |
| Candle Range Period (`candleRangePeriod`) | 20 | 10 |
| Normalization Period (`normalizationPeriod`) | 200 | 400 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.2 |
| VR Weight (`vrWeight`) | 0.25 | 0.5 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.15 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 65.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 1.5 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 2.0 |
| Filter timeframe (`fgfTf`) | "60" | "D" |
| Check price on (`fgfCheckIn`) | "Tick" | "Level at candle open" |
| No-trade band, ATR mult (`fgfBandAtr`) | 0.5 | 1.5 |
| Burst threshold, ATR mult (ATR unit) (`fgfBurstAtr`) | 0.5 | 0.25 |
| Require burst gate (`fgfUseBurst`) | false | true |
| Allow any combo (`fgfAnyCombo`) | true | false |
| Prior drift bars (`fgfDriftBars`) | 60 | 120 |
| Use prior drift filter (`fgfUseDrift`) | false | true |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "D" |
| Minimum child zones aligned (`fgfMinAligned`) | 0 | 2 |
| 1h (`en60`) | true | false |
| 4h (`en240`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 28 | +6.1 | 54% | 3.1 |
| 2022 (untouched) | 16 | -2.6 | 38% | 7.0 |
| 2023 (Jan-Oct, untouched) | 25 | +17.9 | 76% | 2.1 |
| 2023 (Nov-Dec) | 4 | +0.4 | 50% | 2.1 |
| 2024 | 33 | +14.5 | 64% | 5.7 |
| 2025 | 31 | +12.0 | 61% | 2.1 |
| 2026 (Jan-Oct) | 32 | +8.3 | 56% | 3.2 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 40 | -41.8 | -1.04 |
| take profit | 60 | +77.0 | +1.28 |
