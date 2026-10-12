# Pre-registration: the fractal direction score (big timeframe to small)

Frozen before the real run (the commit adding this file is the freeze point; the script is `wf_fractal.py` at that
commit). Code checks ran only on a dry window, 2017H2, which is not evaluated below. BTC only. No Pine or MT5
default changes. The user's choices that shaped this design: predict M5; readings = FDF structure trend and TDI
fast-line direction; top timeframe W1; fitted frozen weights.

## Question
Does reading the direction state of every higher timeframe, from W1 down to M5, forecast the next 5-minute direction
better than (a) the filter's zone alone and (b) the local option-2 veto, which already reads TDI at M5 / M10 / M20
and FDF at M5? The point of the test is whether the higher stack (W1, D1, H4, H1, M15) adds anything the local
reading does not have.

## Features (at the close of each M5 candle; every read causal)
For each of the six timeframes T in {M5, M15, H1, H4, D1, W1} (W1 = TradingView's week, opening Monday 00:00 UTC,
confirmed on a MEXC BTCUSDT 1W export; the chart's own TF read from the closed candle;
every higher TF from its last bar closed by the M5 candle's open, the `map_prev_on` rule the veto uses):
- `fdf_T`: FDF structure direction, +1 / -1 / 0 (pivots L = 5, R = 3, as the strategy).
- `tdi_T`: TDI fast-line direction, +1 / -1 / 0 (RSI 14 -> SMA 2, rising / falling).
- `tdi_lvl_T`: (fast line - 50) / 50, the level the veto already uses at the local TFs.
Plus three alignment summaries, computed from the twelve direction readings above (so they add no new data):
- `align_fdf` = sum of fdf_T over the six TFs (-6 .. +6); `align_tdi` likewise.
- `depth`: the number of consecutive TFs from W1 downward whose FDF agrees with W1's (0 .. 6; 0 when W1 is flat).
Twenty-one inputs. Missing (warm-up, no W1 history) -> not scored, as in the veto.

## Models
- **FR** (fractal score): L2 logistic regression (L2 = 1, 30 Newton steps, standardised on training rows) on the 21
  inputs; one model per horizon H. Permission **FRP**: BUY above the training 58.5% quantile, SELL below 41.5%
  (the veto's coverage convention, about 83%).
- **FRV** (fractal veto, the candidate for the Pine filter): keep the zone's BUY / SELL only where FRP agrees.
- **CNT** (interpretable baseline, no fitting): score = align_fdf + align_tdi; permission at the same training
  quantiles; veto **CNTV** = zone kept where CNT agrees.
- Baselines on identical candles: **P0** the zone alone; **R2s** the option-2 veto (H = 3 model) as frozen in
  `veto_model_2026.json`'s procedure, refitted per window by the same rule; **G2P** the option-2 score alone.

## Data, windows, labels
Bitstamp 1-minute from 2014-01-01 (UTC). M5 candles; labels sign(close[t+H] - close[t]), H = 1 (the next 5 minutes,
**primary**), 3, 10; ties dropped; labels end inside the period.
- **Primary, fresh: 2018H1 .. 2019H2** pooled, models trained on candles from 2015-01-01 whose labels end before
  each half-year starts (walk-forward; a later half-year's model includes the earlier fresh ones; no model sees its
  own half-year or later). 2014 = warm-up. Neither FR nor CNT has been evaluated on any window before this freeze.
- **Secondary: 2021H1 .. 2022H2 pooled; 2026-01 .. 2026-10**, models trained from 2020-01-01.
- Judge's caveat from the veto study carried over: Bitstamp 2018-19 prints carry a last-trade bounce worth about
  1-1.5 pt of raw accuracy to any contrarian rule at H = 1; the comparison with R2s on the same candles controls
  for it (both rules see the same bounce). The broker run is the bounce-free test.

## Metrics and confidence
Per H and mean of H: raw accuracy, 3-valued permission AUC (ties half), coverage, balanced precision / recall,
call and label counts; paired 48-hour block bootstrap (500 repeats, blocks shared across H and rules) for the
accuracies, AUCs and the differences FRV - P0, FRV - R2s, FRP - G2P, CNTV - P0. Plus the standardised
coefficients of FR per model, grouped by timeframe, and a drop-one-timeframe ablation on the fresh window
(exploratory, after the result).

## Reading rule (computed by the script, `fractal_reading_real.csv`)
**The fractal stack adds something** if, on fresh 2018-2019 pooled at **H = 1**: (1) FRV - P0 raw accuracy has a
95% CI above 0, (2) **FRV - R2s raw accuracy has a 95% CI above 0** (the stack beats the local veto at comparable
coverage, |coverage difference| <= 0.10), and (3) FRP - G2P AUC has a 95% CI above 0. A result that passes (1) but
not (2) means the fractal score works but only restates the local veto; it is reported as such. Secondary windows,
H = 3 / 10 and CNT are reported and do not change the verdict. Flag: any fresh half-year with a negative FRV - R2s
accuracy difference.

## For Pine
If the rule holds, FR's coefficients are exported as constants (`fractal_model_2026.json`, fitted on 2020-01-01 ..
labels before 2026-01-01) and the Pine filter gets an optional "Fractal veto" switch, off by default, with six
`request.security` reads of a tuple (FDF direction, TDI direction, TDI level) per timeframe. If it does not hold,
nothing is added to Pine and the reason is written down.

## Known limits before running
- One asset, one venue for the fresh window. W1 has about 200 bars in the training window: its weight will be noisy.
- Next-5-minute direction is the hardest target; the user chose it knowingly, and H = 3 / 10 are reported next to it.
