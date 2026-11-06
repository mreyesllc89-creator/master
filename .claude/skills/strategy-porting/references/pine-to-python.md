# Pine (or MQL5) → Python mapping

## Data
- Build a DataFrame `open high low close volume` on a UTC `DatetimeIndex` labelled by bar
  open time. From TradingView export: `time` is Unix seconds. From MT5
  (`copy_rates_*`): server time; shift to UTC with the broker offset.
- Pine `[n]` → `series.shift(n)` (vectorised) or `arr[i-n]` inside the loop.
- `na` → `NaN`; `nz(x, 0)` → `x.fillna(0)`.
- `syminfo.mintick` → a `point` constant per symbol; `syminfo.pointvalue` → value of a
  1.0 move per unit.

## Indicators
Use `python-trading/scripts/indicators.py`:
| Pine | Python |
|------|--------|
| `ta.rsi(close, n)` | `rsi_wilder(close, n)` |
| `ta.sma(x, n)` | `sma(x, n)` |
| `ta.ema(x, n)` | `ema(x, n)` |
| `ta.rma(x, n)` | `rma(x, n)` |
| `ta.atr(n)` | `atr_wilder(high, low, close, n)` (MT5 `iATR` → `atr_sma`) |
| `ta.stdev(x, n)` | `x.rolling(n).std(ddof=0)` |
| `ta.highest(x, n)` | `x.rolling(n).max()` |
| `ta.cum(x)` | `x.cumsum()` |
| `ta.crossover(a, b)` | `(a > b) & (a.shift() <= b.shift())` |
| `request.security(sym, tf, expr[1], lookahead_on)` | compute on resampled HTF frame, `htf_no_lookahead(htf_series, df.index)` |
| `request.security(sym, tf, expr)` plain | `htf.reindex(df.index, method="ffill")` **without** shift (repaints in history: avoid) |

## Control flow
- Global-scope Pine calculations → vectorised columns.
- `var` state, order lifetimes, position management → the bar loop in
  `python-trading/references/backtesting.md`.
- `if barstate.isconfirmed` → the loop acts on bar `i` using values of bar `i` and fills on
  `i+1` (or at `close[i]` when the source has `process_orders_on_close`).
- `strategy.entry(stop=p)` → a `Pending` object checked against the next bars' ranges.
- `strategy.exit(qty_percent, limit)` + runner → `Position` with `qty`, `runner`, `best`.
- `strategy.close_all()` → close every open position at the current close.
- Pine functions `f(a) => ...` → Python functions; keep the names.

## Costs and spread
- Pine synthetic spread (`spreadPoints`) → add/subtract half spread at fills.
- `commission_type = strategy.commission.percent, commission_value = v` → `pnl -= notional * v/100`
  per side; `cash_per_contract` → `qty * v` per side.
- `slippage = n` ticks → shift fill prices against the trade by `n * point`.

## Output for comparison
Produce `trades.csv` with columns `entry_time, exit_time, side, qty, entry_price,
exit_price, pnl, exit_reason, bars_held, comment`, matching TradingView's List of Trades so
a merge on `entry_time` (rounded to the bar) is one line of pandas:
```python
m = tv.merge(py, on=["entry_time", "side"], how="outer", suffixes=("_tv", "_py"), indicator=True)
print(m["_merge"].value_counts()); print((m.entry_price_tv - m.entry_price_py).describe())
```

## MQL5 → Python specifics
- `OnTick` logic → the bar loop if the EA is new-bar based; if it is tick based, use
  M1 bars (or ticks) as the loop granularity and aggregate.
- `CopyBuffer(h, 0, 1, ...)` index 1 → the previous row (`shift(1)` or `i-1`).
- `SYMBOL_TRADE_STOPS_LEVEL` and freeze level → clamp SL/TP distances in the engine too, or
  the EA will take different trades than the backtest.
- Hedging vs netting → list of positions vs a single net position in the engine.
