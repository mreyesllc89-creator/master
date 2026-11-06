# Strategy API

## strategy() properties that change results
| Property | Effect |
|----------|--------|
| `pyramiding = n` | max entries in the same direction (0/1 = one position; v2.8 uses 100 so every label trades) |
| `default_qty_type / default_qty_value` | `strategy.fixed` (contracts), `strategy.cash`, `strategy.percent_of_equity` |
| `initial_capital`, `currency` | sizing base |
| `commission_type / commission_value`, `slippage` | costs; `strategy.commission.percent / cash_per_contract / cash_per_order` |
| `process_orders_on_close = true` | orders created on a bar fill at that bar's close instead of the next open |
| `calc_on_every_tick = true` | strategy logic runs on every realtime tick (history still bar by bar) |
| `calc_on_order_fills = true` | re-run the script right after a fill |
| `use_bar_magnifier = true` | intrabar data for fills (Premium); closer to MT5 "every tick" |
| `fill_orders_on_standard_ohlc` | fill with standard OHLC when charting Heikin Ashi |
| `margin_long / margin_short` | margin % |
| `close_entries_rule = "FIFO"` | for FIFO-only markets |
| `overlay` | draw on price (true) or separate pane; `max_bars_back`, `max_labels_count`, `max_lines_count` |

## Orders
```pine
strategy.entry(id, direction, qty = na, limit = na, stop = na, oca_name = "", oca_type = strategy.oca.none, comment = "", alert_message = "")
strategy.order(id, direction, qty, limit, stop, oca_name, oca_type, comment)       // does not reverse; adds to position
strategy.exit(id, from_entry = "", qty = na, qty_percent = na, profit = na, limit = na, loss = na, stop = na,
              trail_price = na, trail_points = na, trail_offset = na, oca_name = "", comment = "", comment_profit = "", comment_loss = "", comment_trailing = "", alert_message = "")
strategy.close(id, comment, qty, qty_percent, alert_message, immediately)
strategy.close_all(comment, alert_message, immediately)
strategy.cancel(id)   /  strategy.cancel_all()
```
- `strategy.entry` with `stop=` is a stop order; with `limit=` a limit; both = stop-limit;
  neither = market at next open. An entry in the opposite direction **reverses** the
  position (closes and opens, size = position + qty).
- Resubmitting `strategy.entry` with the same id on a later bar **modifies** the pending
  order (new price). A pending order stays until filled or cancelled with
  `strategy.cancel(id)`; it does not expire by itself, so the strategies here cancel
  explicitly after `entryValidBars`.
- `strategy.exit`: `loss`/`profit` in ticks, `stop`/`limit` in price, `trail_points`
  (ticks of profit to activate) + `trail_offset` (ticks behind). `qty_percent = 30` creates
  the partial; a second `strategy.exit` with another id for the rest = the runner. Exits
  referencing `from_entry` only act once that entry is filled.
- OCA groups: `strategy.oca.cancel` cancels sibling orders when one fills (bracket
  entries), `strategy.oca.reduce` reduces siblings' size.
- Order comments appear in the List of Trades; the repo's v2.8 puts the rung and label
  name in them so each fill is traceable.

## Position state
`strategy.position_size` (+ long, − short, 0 flat), `strategy.position_avg_price`,
`strategy.opentrades`, `strategy.opentrades.entry_price(i)`, `.entry_bar_index(i)`,
`.entry_time(i)`, `.size(i)`, `.entry_id(i)`, `.profit(i)`, `strategy.closedtrades` and
the same accessors with `.exit_price`, `.exit_bar_index`, `strategy.equity`,
`strategy.netprofit`, `strategy.openprofit`, `strategy.wintrades`, `strategy.losstrades`,
`strategy.max_drawdown`, `strategy.initial_capital`.

Bars held: `bar_index - strategy.opentrades.entry_bar_index(strategy.opentrades - 1)`.

## Fill model (no bar magnifier)
- Market orders fill at the next bar's open (or this bar's close with
  `process_orders_on_close`).
- Stop/limit orders fill when the bar's high/low reaches the price; if the bar opens
  beyond the price, at the open. One price series: there is no spread unless you model
  it (the FlashGold strategies do: `spreadPoints`).
- When SL and TP are both inside one bar, the broker emulator assumes the intrabar path
  from the open: if the open is closer to the high than to the low, open→high→low→close,
  otherwise open→low→high→close. Differences from MT5 "every tick" are expected; compare
  trade counts and direction, not cent-exact P&L.
- Realtime: fills happen on ticks; `calc_on_every_tick` changes when logic runs but not
  when orders fill.

## Sizing patterns
```pine
riskPct   = input.float(1.0, "Risk %")
slDist    = slAtrMult * ta.atr(14)
qty       = math.floor((strategy.equity * riskPct / 100) / (slDist * syminfo.pointvalue) / minQtyStep) * minQtyStep
```
`syminfo.pointvalue` is the value of a 1.0 price move per contract; `syminfo.mintick` the
tick size; `syminfo.minmove / syminfo.pricescale` relate to it.

## Common strategy bugs
- Entry conditions using `close` of the current bar in realtime (`barstate.isconfirmed`
  guards it, or accept that history and realtime differ).
- `strategy.exit` without `from_entry` while several entries are open: it attaches to all.
- Forgetting that `pyramiding = 0` silently ignores extra entries.
- Exits in ticks (`loss = 100`) but intending price distance: multiply by
  `1 / syminfo.mintick`, or pass `stop =` a price.
- `strategy.close` on a bar also carrying `strategy.entry` in the opposite direction:
  the entry reverses anyway; the repo's `exitOnOpposite` + `allowReverse` inputs make
  this explicit.
