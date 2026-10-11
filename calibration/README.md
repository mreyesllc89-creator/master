# BTC/USD calibration of the FlashGold v5 + FDF strategy

This folder holds the calibration behind the presets in `flashgold_v5_fdf_strategy.pine`
(input group "P. Calibrated preset", on by default). Each preset also sets the signal-quality filter
(group "Q") and the re-entry after a trailing / target exit (group "R") for its timeframe.

## Data and engine

- Bitstamp BTC/USD 1-minute candles from 2023-01-01 to 2026-10-11 (1,985,897 candles, no gaps), from
  [ff137/bitstamp-btcusd-minute-data](https://github.com/ff137/bitstamp-btcusd-minute-data). `prep_data.py` builds `btc_1m.parquet`.
- `fgengine.py` / `fgrun.py` are a numba replica of the Pine strategy: the FlashGold signal (bid/ask model, TDI
  parent + zones, burst, entry stop), the Fractal Direction Framework (pivots, protected levels, breaks,
  divergence, pullback, Hurst h(2) and width), and the strategy's orders (entry stops with OCA and expiry, reversal,
  stop loss, target, trailing stop, exit on the opposite signal, exit on the parent's break, re-entry).
- Higher timeframes are read the way TradingView reads them historically: the parent and zones above the chart from
  their last closed candle, an interval that does not divide the day restarts at 00:00 UTC, an interval above a day
  is a whole number of days.
- Parity check against a TradingView export (BITGET:BTCUSDT 1H, 446 candles, parent 4H): every BUY / SELL, entry
  price (within 0.1), protected level, break and divergence matches after the indicators' warm-up.
- Fills: along the 1-minute path inside each candle (the 1m chart: the candle itself), 0.05% fee per side, no
  slippage. TradingView's bar magnifier (on in the script, Premium plans) uses coarser intrabars - 2-minute candles on
  15m, 5m on 30m, 10m on 1H-2H, 30m on 4H-8H, 1H on 1D - and only the last 200,000 of them; `tv_check.py` re-runs
  the presets on those intrabars (results below).

## Method (`pipe2.py`, then `reselect.py`)

In-sample 2023-01 .. 2025-06, out-of-sample 2025-07 .. 2026-10. Every choice uses the in-sample period only, needs
each in-sample year (2023, 2024, 2025 H1) positive, and takes the most common value of each setting among the 60
best sets (a plateau rather than a single peak). The out-of-sample period is only reported.

1. **Signal and quality filter** (`features.py`, `stage_b.py`): parent x1 / x4 / x8, zones aligned 1 or 2 of
   chart x1 / x2 / x4, framework timeframe x1 / x4, trade with the parent or not, Hurst gate (off, H >= 0.5,
   H < 0.5), burst 0.5 - 2 ATR, chart TDI fast line bounds per side, parent TDI fast bound per side, volatility floor
   (ATR(14) / its 100-candle average). Ranked by the t-statistic of the move in the signal's direction over the next
   20 candles, in ATR.
2. **Exits and re-entry** (`pipe2.stage_c`): stop loss 1 / 1.5 / 2 / 3 ATR, target off / 4 / 8 R, trailing stop off
   or activation 1 / 2 / 4 ATR with distance 0.5 / 1 / 2 ATR, re-entry off / market (max 2, 5) / stop (max 2, 5), exit
   on the opposite signal, exit on the parent's break: 2,400 sets per timeframe on 1-minute fills (1m charts: the 1m candles themselves). Ranked by
   in-sample total return in ATR (`reselect.py`; ranking by the t-statistic favoured tight trails with many small
   wins, and on 4H that pick lost out of sample while the total-return pick won; both are in `presets/*.json`).
3. **Checks on the preset** (`pipe2.finalize`): without the re-entry, with the framework's divergence gate, with the
   pullback gate, without the quality filter, and the previous settings.

## Results

| Chart | Parent / FDF | Quality filter (buy / sell / vol) | Exits | Re-entry | In-sample trades, avg ATR, PF | Out-of-sample trades, avg ATR, PF | Quality filter off (OOS PF) | Your previous settings (OOS PF) |
|---|---|---|---|---|---|---|---|---|
| 1m | x1 (2 zones) / x4, H<0.5, burst 2 ATR | fast 50-100, parent>=0 / fast 30-40, parent<=100 / - | SL 3 ATR, no trail | off | 7612, -2.18, 0.60 | 4043, -2.83, 0.54 | 0.39 | 0.11 |
| 5m | x1 (1 zone) / x4, H<0.5, burst 0.5 ATR | fast 50-100, parent>=50 / fast 30-40, parent<=50 / ATR ratio>=0.8 | SL 3 ATR, no trail | off | 3009, +0.01, 1.01 | 1637, -0.43, 0.82 | 0.43 | 0.18 |
| 15m | x1 (1 zone) / x4, H<0.5, burst 0.5 ATR | fast 50-80, parent>=50 / fast 0-50, parent<=50 / ATR ratio>=1.2 | SL 3 ATR, no trail, exit on break | off | 721, +0.43, 1.24 | 379, +0.66, 1.39 | 0.63 | 0.20 |
| 30m | x8 (1 zone) / x4, with parent, H<0.5, burst 0.5 ATR | fast 50-80, parent>=50 / fast 0-40, parent<=50 / ATR ratio>=1.2 | SL 1.5 ATR, trail 2/2 ATR | market (max 2) | 359, +0.30, 1.36 | 192, -0.16, 0.84 | 0.83 | 0.22 |
| 1H | x1 (1 zone) / x4, burst 0.5 ATR | fast 0-100, parent>=0 / fast 0-40, parent<=50 / - | SL 3 ATR, no trail, exit on break | off | 720, +0.28, 1.23 | 392, +0.07, 1.06 | 0.94 | 0.33 |
| 2H | x4 (1 zone) / x4, with parent, H<0.5, burst 0.5 ATR | fast 50-80, parent>=50 / fast 0-40, parent<=50 / - | SL 2 ATR, TP 4R, trail 4/2 ATR, exit on break | stop (max 2) | 133, +0.68, 1.60 | 77, +0.14, 1.11 | 1.13 | 0.79 |
| 4H | x1 (1 zone) / x1, burst 0.5 ATR | fast 0-100, parent>=0 / fast 30-40, parent<=50 / - | SL 3 ATR, no trail, exit on break | off | 203, +0.96, 1.89 | 134, +0.25, 1.22 | 1.13 | 0.26 |
| 8H | x1 (1 zone) / x4, with parent, H<0.5, burst 0.5 ATR | fast 0-100, parent>=0 / fast 30-50, parent<=50 / - | SL 3 ATR, TP 8R, no trail, exit on opposite | stop (max 2) | 79, +0.39, 1.57 | 56, -0.23, 0.68 | 1.06 | 0.96 |
| 1D | x1 (1 zone) / x1, burst 0.5 ATR | fast 0-100, parent>=0 / fast 30-100, parent<=100 / - | SL 3 ATR, trail 1/1 ATR | market (max 2) | 138, +0.25, 1.50 | 66, +0.23, 1.52 | 1.37 | 1.05 |

On TradingView's bar-magnifier intrabars (`tv_check.py`, whole history magnified):

| Chart | Intrabar | PF in-sample, 1m paths / TradingView | PF out-of-sample, 1m paths / TradingView |
|---|---|---|---|
| 15m | 2m | 1.24 / 1.23 | 1.39 / 1.37 |
| 30m | 5m | 1.36 / 1.34 | 0.84 / 0.84 |
| 1H | 10m | 1.23 / 1.24 | 1.06 / 1.06 |
| 2H | 10m | 1.60 / 1.60 | 1.11 / 1.11 |
| 4H | 30m | 1.89 / 1.89 | 1.22 / 1.22 |
| 8H | 30m | 1.57 / 1.57 | 0.68 / 0.68 |
| 1D | 60m | 1.50 / 1.50 | 1.52 / 1.52 |

Average per trade and drawdowns are in ATR(14) of the entry candle, after fees. "Your previous settings" = the strategy
as it was before this calibration (framework with the PDF gates, parent 4 x the chart, Points exits 5000 / 50000 /
4500 / 1000).

What held up out of sample: **15m (PF 1.39), 4H (1.22), 1D (1.52)**, weakly 1H (1.06) and 2H (1.11).
What did not: 30m, 8H, and 1m / 5m, where the 0.1% round-trip fee is 2.3 x (1m) and 0.8 x (5m) the median ATR.

## Limits

- One market (BTC/USD, Bitstamp), one regime split. 30m, 8H, 5m and 1m did not hold up out of sample; 1H and 2H only
  weakly. Treat the presets as a starting point, not a promise.
- Multi-day zones (2D, 4D on a 1D chart) are binned from 2023-01-01 here; TradingView may anchor them differently. The
  1D preset does not depend on them (parent = chart, 1 zone of 3 aligned, and zone 1 is the chart itself).
- Intraday intervals that do not divide the day (e.g. 960 = 16H) restart at 00:00 UTC, as TradingView builds them on
  a 24/7 symbol.
- The strategy header's costs are XAUUSD's ($0.13 per contract, 5 ticks): set the commission in percent for BTC.

## Re-running

```
python prep_data.py <bitstamp historical.csv.gz> <bitstamp latest.csv> .
python pipe2.py 60          # one timeframe in minutes; writes results3/{F,B,C}_60.parquet and preset_60.json
python reselect.py 60       # exits by total return
python report.py results3   # print every preset
python gen_pine_presets.py results3   # the Pine preset table
python tv_check.py          # the presets on TradingView's bar-magnifier intrabars
```
Needs numpy, pandas, pyarrow and numba.
