# Bar-by-bar backtesting of stop-order strategies

The strategies here cannot be backtested with a pure vectorised approach: an entry is a
stop order with a lifetime, exits are SL/TP with partial + runner and trailing, and
"one entry per bar" and `pyramiding` rules depend on state. Write a small engine.

## Engine skeleton
```python
@dataclass
class Pending:
    side: int            # +1 buy, -1 sell
    price: float         # stop trigger
    placed_bar: int
    valid_bars: int      # 0 = until filled
    sl: float; tp: float; qty: float

@dataclass
class Position:
    side: int; entry: float; qty: float; sl: float; tp: float
    entry_bar: int; runner: bool = False; be_done: bool = False

for i in range(warmup, n):
    o, h, l, c = open_[i], high[i], low[i], close[i]
    # 1. pending orders: fill if the bar's range reaches the stop price
    #    buy stop fills at max(price, o) (gap through), sell stop at min(price, o)
    # 2. open positions: check SL and TP against this bar's range
    #    if both hit in one bar decide by rule (see below), then trailing/BE updates
    # 3. time stop: bars held >= maxBarsHeld -> close at c
    # 4. signals computed from bars <= i (closed) -> new pending for bar i+1,
    #    or, with process_orders_on_close, fill at c now
    # 5. expire pendings older than valid_bars; cancel on opposite signal if the rule says so
```
Keep every price in float, every quantity in float, and record trades to a list of
dicts; build a DataFrame at the end.

## Fill assumptions, stated explicitly
- **Stop entry**: fills at the stop price if `low <= price <= high`; if the bar opens
  beyond the price (gap), fill at the open. Add slippage in points if the strategy does.
- **SL and TP in one bar** (TradingView without bar magnifier): the emulator assumes the
  path open→high→low→close when the open is closer to the high than to the low, otherwise
  open→low→high→close. Choose and document one of: *worst case* (SL first), *TradingView
  path* (the rule above), or *intrabar data* (resolve with M1 candles, the equivalent of
  bar magnifier / MT5 every-tick).
- **Spread**: with mid prices, buys fill at `price + spread/2`, sells at `price - spread/2`,
  matching `spreadPoints` in the Pine files. With bid/ask data, buy on ask, sell on bid.
- **Commission**: per side, per unit or percent, from the Pine strategy settings.
- **Order processing**: Pine default fills orders at the *next bar's open*;
  `process_orders_on_close=true` (v2.8) fills at the current bar's close. Match it.

## Exits as implemented in FlashGold v5 (`ExitMode`, `TpStyle`)
- SL distance and TP distance from `Pips`, `Points` or `ATR` mode; TP as an R multiple
  (`tpR * slDistance`) in Pips/ATR mode.
- `Fixed`: one TP for the full position; optional trailing stop with activation and
  distance.
- `Partial + runner`: at the TP level close `partPct` %, move the runner's stop to
  breakeven (`runBE`), then trail by `runTrailAtr * ATR` (or points/pips) from the best
  price since the TP was reached. The trail starts at the TP level.
- Time stop: close at the close of the bar when `bars_held >= maxBarsHeld`.
- Opposite signal: `exitOnOpposite` closes at the signal bar's close; `allowReverse`
  places the opposite stop so a fill closes and reverses.

## Sizing (`QtyMode`)
- `Fixed`: `fixedQty` units.
- `Risk %`: `qty = equity * riskPct / (slDistancePrice * pointValuePerUnit)`; floor to the
  symbol's volume step, clamp to min/max. Equity is the account value at the time of the
  order, not initial capital.

## Metrics
```python
pnl = trades["pnl"]
net = pnl.sum(); gross_win = pnl[pnl > 0].sum(); gross_loss = -pnl[pnl < 0].sum()
profit_factor = gross_win / gross_loss if gross_loss else float("inf")
equity = initial + pnl.cumsum(); max_dd = (equity.cummax() - equity).max()
win_rate = (pnl > 0).mean(); avg_r = (pnl / trades["risk"]).mean()
```
Always report: date range, bars, trades, net, profit factor, max drawdown (money and %),
win rate, average R, longest losing streak, and the fill assumptions used.

## Parameter sweeps
- Use `itertools.product` over a small grid; run in a `ProcessPoolExecutor`.
- Report the neighbourhood, not just the best cell. A good parameter has good neighbours
  (the Pine tooltips note tested ranges like "0.08 to 0.12, all positive").
- Walk-forward: optimise on window A, test on window B, roll. Out-of-sample results are
  the ones to quote.

## Libraries, if you need them
- `backtesting.py`: simple, supports stop orders and trailing via `Strategy.next()`;
  single position per direction unless `exclusive_orders=False`.
- `vectorbt`: fast vectorised portfolios; stop-order and partial logic is awkward.
- Custom loop (above) is usually the right choice for these strategies; `numba.njit` the
  inner loop if a sweep is slow.
