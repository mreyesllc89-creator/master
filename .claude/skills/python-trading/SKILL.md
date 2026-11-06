---
name: python-trading
description: Python for trading research - indicators that match TradingView Pine and MetaTrader 5 maths (RSI/Wilder, TDI, ATR, SMA/EMA), bar-by-bar backtests of stop-order strategies with SL/TP/trailing/partials, position sizing, the MetaTrader5 Python package for live data and orders, and loading chart exports. Use this whenever the user wants to backtest, analyse, replicate, optimise, or automate a trading strategy in Python, port a Pine or MQL5 strategy to Python, pull candles or place orders from Python, or verify indicator values against a chart. Also use it for "quick" questions like "how do I compute TDI in pandas".
---

# Python for trading

The strategies in this repository (FlashGold v5, XPW Orientation TDI, the FlashGold
direction filter) are TradingView Pine v6 strategies built on the Traders Dynamic Index
(RSI → fast/slow SMA), ATR-scaled stops, stop-order entries, partial take profits and
runners. Python is used to reproduce them, backtest them with real control over fills,
and talk to MetaTrader 5. Load the general `python` skill for engineering practice.

| Need | Read / use |
|------|------------|
| Indicator formulas and platform parity (Pine vs MT5 vs pandas) | `references/indicators.md`, `scripts/indicators.py` |
| Event-driven backtest of stop entries, SL/TP, trailing, partial + runner, time stop | `references/backtesting.md` |
| MetaTrader5 package: connect, candles, ticks, orders, positions | `references/mt5-python.md` |

## Workflow for "replicate this strategy in Python"

1. **Read the Pine source header first.** These files document every rule and every
   calibrated default in the header comment and in input tooltips. Build a table of
   inputs → defaults → unit (points, pips, ATR multiple) before writing code.
2. **Match the data model.** Pine runs on one price series; these strategies model the
   spread themselves (`spreadPoints`: half added to ask, half subtracted from bid). In
   Python either model the same spread on mid prices or use real bid/ask candles, but not
   both.
3. **Indicators with the platform's smoothing.** Pine `ta.rsi` and `ta.atr` are Wilder
   (RMA) smoothed; MT5 `iRSI` is Wilder, MT5 `iATR` is a plain SMA of true range. Use
   `scripts/indicators.py`, which implements both and is tested against the formulas.
4. **Higher-timeframe inputs without lookahead.** Compute on the HTF, shift by one bar
   (last closed bar), forward fill onto the chart timeframe. This mirrors the strategies'
   `htfNoRepaint` option.
5. **Bar-by-bar engine for orders.** Stop-order entries, lifetimes, one-entry-per-bar,
   trailing stops and partials are path dependent. Write a loop over numpy arrays (see the
   backtesting reference) rather than vectorised approximations, and decide explicitly
   how an intrabar fill is priced when both SL and TP are touched in one bar (the
   reference lists TradingView's path rule and the alternatives).
6. **Verify on a handful of trades.** Export the TradingView strategy tester "List of
   Trades" to CSV and compare entry time, entry price and exit reason for the first ten
   trades before trusting aggregate statistics.
7. **Report honestly.** Net profit, max drawdown, profit factor, number of trades, average
   trade in R, and the date range. State the fill assumptions in the same table.

## Quick formulas (details and code in the references)

```python
from indicators import rsi_wilder, sma, atr_wilder, tdi
r = rsi_wilder(close, 14)
fast, slow = sma(r, 2), sma(r, 7)          # TDI white (fast) and slow lines
direction = np.sign(fast - fast.shift(1))  # fast rising = BUY bias (FlashGold rule)
a = atr_wilder(high, low, close, 14)       # Pine ta.atr
```

Position size for a risk percentage:
`qty = (equity * risk_pct) / (stop_distance_price * value_per_point_per_unit)`, then
round down to the symbol's volume step and clamp to min/max volume.

## Pitfalls specific to this domain

- `ta.rsi` on the first bars is NaN in pandas but TradingView prints values from bar
  `len`; both versions converge, so skip the first 5×len bars when comparing.
- TradingView session/timezone: labels in these scripts use `America/New_York`; data is
  exchange time. MT5 data is broker server time. Normalise to UTC in Python.
- A `strategy.exit` with `qty_percent` creates partial exits; a Python engine must track
  remaining quantity and the runner's stop separately.
- Commission and slippage: the Pine strategies take them from the strategy properties and
  a cost input. Include the same cost in Python or the comparison is meaningless.
- `pyramiding=100` with `strategy.fixed` (v2.8) means many simultaneous entries; the
  Python engine needs a list of open positions, not a single one.
