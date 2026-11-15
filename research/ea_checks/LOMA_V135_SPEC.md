# XAUUSD_Loma_TrendPullback.mq5 v1.35: specification

Source to change: `/workspace/master/XAUUSD_Loma_TrendPullback.mq5` (v1.34, 60 inputs). Do NOT edit that file.
Write the new version to `<scratchpad>/v135/XAUUSD_Loma_TrendPullback.mq5` and a change list to
`<scratchpad>/v135/CHANGES.md`. Everything that is not named here stays byte-for-byte as it is, and with the new
inputs at their defaults the EA must behave exactly like v1.34 (existing presets must keep working).

The Python backtest is the reference. The EA must do, on real ticks, what the backtest simulates on one-minute
bars. Reference code, all in `/workspace/master/research/`:
- `hump_engine.py` `simulate()`: entry, stop, target, the EA's own trailing (kind R), time exits.
- `hump_trail.py`: `simulate_x()` kinds 5 breakeven and 6 step; `psar_levels()`, `hump_levels()`; `MarketX._levels()`
  (candles, ema); `MarketX._tb()` (which trigger bar an M1 bar may use).
- `hump_trail2.py`: `simulate_y()` (all kinds, with `closed = 1`), `wilder_atr()`, `pivot_levels()`,
  `MarketY._levels()` (bollinger, sma, htfcandle), module docstring.
- `hump_wf.py`: `outcomes()` (price scale `ps`), `Feat` (`xs_dn`, `xs_up`: the Stochastic turn rule), `conditions()`.

## A. Trailing systems

New inputs, appended to the group "R8: Trailing stop" right after `TrailStep_Points` (existing inputs keep their
names, order and defaults):

```
input ENUM_LOMA_TRAIL_MODE TrailMode = TRAIL_RISK;  // Trailing system (units of TrailStartR / TrailDistanceR depend on it)
input int     TrailParam               = 0;     // Period, bars or variant of the level-based systems
```

| TrailMode | Python kind | TrailStartR means | TrailDistanceR means | TrailParam |
|---|---|---|---|---|
| TRAIL_RISK = 0 | R | profit in R that starts trailing (0 = off) | distance in R | unused |
| TRAIL_ATR_ENTRY = 1 | atr | profit in ATR multiples (must be > 0) | distance in ATR multiples | unused |
| TRAIL_PERCENT = 2 | percent | profit in % of the entry price (> 0) | distance in % of the entry price | unused |
| TRAIL_PROFIT_LOCK = 3 | profitlock | profit in R (> 0) | share of the best profit kept (0..1) | unused |
| TRAIL_STEP = 4 | step | step size in R (> 0) | unused | unused |
| TRAIL_CHANDELIER = 5 | chandelier | profit in R (0 = from the minute after entry) | multiple of the live ATR(14) | unused |
| TRAIL_CANDLES = 6 | candles | profit in R (0 = from the minute after entry) | unused | number of closed trigger candles |
| TRAIL_EMA = 7 | ema | same | unused | EMA period |
| TRAIL_SMA = 8 | sma | same | unused | SMA period |
| TRAIL_PSAR = 9 | psar | same | unused | 0 = 0.02 / 0.2, 1 = 0.01 / 0.1, 2 = 0.04 / 0.2 |
| TRAIL_BOLLINGER = 10 | bollinger | same | unused | 0 = SMA(20) -/+ 1 sd, 1 = -/+ 2 sd |
| TRAIL_HTF_CANDLE = 11 | htfcandle | same | unused | minutes of the higher candle (15, 30, 60, 240) |
| TRAIL_PIVOTS = 12 | pivots | same | unused | bars on each side of the swing |
| TRAIL_HUMP = 13 | hump | same | unused | unused |

Rules that hold for every mode:
1. The stop is only ever tightened. The take profit is never changed.
2. TRAIL_RISK is the existing code, unchanged (every tick). TRAIL_STEP also works on every tick: with
   `fav` = best profit seen so far in price and `a = TrailStartR x 1R`, `k = floor(fav / a)`; when `k >= 1` the stop
   goes to `entry + (k - 1) x a` for a buy (`entry - (k - 1) x a` for a sell). `TrailStep_Points` applies to these two only.
3. All other modes act once per closed one-minute bar, on the first tick of the next M1 bar of the chart symbol
   (use the M1 series of `_Symbol`, whatever the chart or trigger timeframe). On that tick:
   - `best` = the best price of the COMPLETED M1 bars from the entry bar on (the M1 bar in which the position
     was opened counts as a whole): for a buy the highest bid high; for a sell the lowest ask low, where ask low =
     bid low + that bar's spread (`MqlRates.spread x _Point`; if the bar's spread is 0 use the current spread).
   - `fav` = `best - entry` (buy) or `entry - best` (sell); `R` = the initial risk (the existing terminal global
     variable written from the opening deal).
   - Level modes and TRAIL_CHANDELIER are active when `TrailStartR <= 0` or `fav >= TrailStartR x R`; they never act
     on the entry minute itself (in Python the level is applied from the M1 bar after the entry bar: `j > e`).
   - the candidate stop `c` (below); if it is tighter than the current stop by at least one point:
     if the current price is already through `c` (bid <= c for a buy, ask >= c for a sell) close the position at
     market (the backtest fills at that minute's open); else if `c` is closer to the price than the broker's stops
     level skip this minute (one journal line per position); else modify the stop.
4. Level modes: `c = level - SL buffer` for a buy and `c = level + SL buffer + current spread` for a sell, where
   `SL buffer` is `SL_Buffer_Points` (after point scaling and, if on, price scaling, see C) and `level` comes from
   the last trigger-timeframe bar that had CLOSED when this M1 bar opened (shift 1 of `TriggerTimeframe` at that
   moment). Charts are bid prices, the backtest is mid prices: a level read from the bid chart with the spread added
   on the sell side is the same stop.
   - CANDLES: lowest low (buy) / highest high (sell) of the last `TrailParam` closed trigger bars.
   - EMA: EMA(`TrailParam`) of the trigger closes, the same value for both sides. The backtest seeds the EMA at the
     first bar of years of history (pandas `ewm(span=n, adjust=False)`); compute it over at least `max(500, 10 x n)`
     closed bars so that the seed no longer matters, or use `iMA(..., MODE_EMA, PRICE_CLOSE)`.
   - SMA: simple mean of the last `TrailParam` closes.
   - BOLLINGER: SMA(20) minus k standard deviations (buy) / plus k (sell), population standard deviation of the
     same 20 closes (`ddof = 0`), k = 1 for `TrailParam` 0 and 2 for 1.
   - PSAR: exactly `psar_levels()` in `hump_trail.py` (read it): the SAR for the next bar, used as support when the
     SAR is in up mode (buys only) and as resistance in down mode (sells only); no level for the other side in
     that mode. Either port the function and run it over at least 1,000 closed bars, or show that `iSAR` gives the
     same values on the harness data.
   - HTF_CANDLE: low (buy) / high (sell) of the last candle of `TrailParam` minutes that had closed by the close
     of that trigger bar.
   - PIVOTS: exactly `pivot_levels()` in `hump_trail2.py`: the last swing low (buy) / swing high (sell) that is
     strictly beyond the `TrailParam` bars on each side of it and is confirmed, `TrailParam` bars later.
   - HUMP: the low of the last COMPLETED negative MACD hump (buy) / the high of the last completed positive hump
     (sell), with the EA's own MACD: `hump_levels()` in `hump_trail.py`. The EA's hump state already holds these
     (`g_lastNegLo`, `g_lastPosHi`); check that they are the same thing, bar for bar.
   - no level available (not enough bars, NaN): no change this minute.
5. TRAIL_CHANDELIER: `c = best - TrailDistanceR x ATR` (buy) / `best + TrailDistanceR x ATR` (sell), where `ATR` is
   the Wilder ATR(14) of the last closed trigger bar and `best` is taken over all completed M1 bars since the entry
   (in Python `best` is updated at the end of each bar and read at the next bar's open).
6. TRAIL_ATR_ENTRY: `unit` = Wilder ATR(14) of the trigger timeframe at the signal bar (the last trigger bar closed
   before the position was opened). TRAIL_PERCENT: `unit` = 1% of the entry price. Both: when
   `fav >= TrailStartR x unit`, `c = best - TrailDistanceR x unit` (buy) / `best + TrailDistanceR x unit` (sell).
   The ATR at entry must be the same after a restart of the terminal: recompute it from history or store it in a
   terminal global variable next to the initial risk.
7. TRAIL_PROFIT_LOCK: when `fav >= TrailStartR x R`, `c = entry + TrailDistanceR x fav` (buy) /
   `entry - TrailDistanceR x fav` (sell).
8. Wilder ATR(14): true range smoothed with `alpha = 1/14` (`ewm(alpha=1/14, adjust=False, min_periods=14)` in
   `hump_engine.Market.tf`). MetaTrader's `iATR` is a simple average and is NOT this: compute it from `CopyRates`
   over at least 300 closed trigger bars.
9. Restart-safe: nothing may depend on memory that is lost when the terminal restarts. Recompute from history every
   minute, or keep terminal global variables as the initial risk does.
10. OnInit input checks for the new inputs (ranges per mode; `TrailParam` valid for the mode; HTF_CANDLE minutes
    larger than and a multiple of the trigger timeframe's minutes), with a clear `Print` and `INIT_PARAMETERS_INCORRECT`.
11. A failed modification or close is retried on the next tick with the existing throttle (`TrailFailed`), not
    once per minute.

## B. Entry condition: Stochastic turn (the XLZC Stochastic rule)

```
input bool    UseStochTurnFilter       = false; // Entry only when the Stochastic came from the extreme and turned
input int     StochTurnBars            = 5;     // ... within this many closed bars, the signal bar included
input double  StochTurnHigh            = 80.0;  // Sells: Stochastic was at or above this
input double  StochTurnLow             = 20.0;  // Buys: Stochastic was at or below this
```
Place them in a new group "=== R7b: Stochastic turn filter ===" after the higher-timeframe filter group.
It uses its own Stochastic (7, slowing 1, %D 7, SMA, low/high) on `TriggerTimeframe`, independent of `Stoch_K`
(reference: `B.stoch(t, 7, 1, 7)` and `Feat.xs_dn` / `xs_up` in `hump_wf.py`). With `main[i]` and `signal[i]` on
the signal bar i (the closed bar on which the MACD crossed):
- sell allowed when `max(main[i-StochTurnBars+1 .. i]) >= StochTurnHigh` and (`main[i] < signal[i]` or `main[i] < StochTurnHigh`);
- buy allowed when `min(main[i-StochTurnBars+1 .. i]) <= StochTurnLow` and (`main[i] > signal[i]` or `main[i] > StochTurnLow`).
It is applied where the higher-timeframe filter is applied: the signal still counts as used (as in the backtest,
where the condition is a mask on the signals), only the entry is skipped, with a skip reason in the journal and on
the panel. A not-ready indicator read is retried like the other reads.

## C. Price scaling of the dollar distances

```
input bool    ScaleWithPrice           = false; // Multiply the *_Points distances by price / ReferencePrice
input double  ReferencePrice           = 0.0;   // Price at which the *_Points values were calibrated
```
Place them in the group "R5: Stop loss / take profit" after `MaxSL_Points`. When on, `SL_Buffer_Points`,
`MinSL_Points` and `MaxSL_Points` are multiplied by `s = entry reference price / ReferencePrice` each time a trade
plan is built, where the entry reference price is the bid at that moment (reference: `ps[e] = open of the entry
bar / anchor` in `hump_wf.outcomes()`; buf, min_risk and max_risk are multiplied by it). The level-based trailing
uses the scaled buffer of the position's entry (store `s` per position in a terminal global variable, or
recompute it from the position's open price). Spread and slippage limits are not scaled. `ScaleWithPrice = true`
with `ReferencePrice <= 0` is an input error.

## D. Housekeeping
- `#property version "1.35"`, the version in the header comment and wherever the EA prints or draws its version.
- Header comment: one short paragraph per new feature.
- The status panel shows the trailing mode when it is not TRAIL_RISK.
- No other behaviour changes. No new dependencies. Keep the code style of the file.

## What "done" means
- The file compiles in the C++ shim harness with no new diagnostics compared with v1.34
  (`<scratchpad>/v134/final_check/`: `mq2cpp.py`, `mql5_shim.h`, see the `*.txt` outputs there for how it was run;
  extend the shim only with declarations the new code needs).
- `CHANGES.md` lists every changed or added function with one line each, and every place where the EA cannot do
  exactly what the backtest does, with the size of the difference if known.
