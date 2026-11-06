---
name: pine-script
description: TradingView Pine Script v6 reference for the strategies in this repo (FlashGold v5, FlashGold Direction Filter, XPW Orientation TDI) and Pine work in general - strategy() settings, strategy.entry/exit/close/cancel with stop orders, partial exits, trailing, request.security without repainting, ta.* functions, inputs with groups and tooltips, arrays, labels/lines/tables, version migration (v4/v5 → v6), and the conventions used in this repository (header changelog, STRATEGY ADDITION tooltips, calibrated defaults, FGF filter block). Use this for ANY .pine file, any TradingView indicator or strategy, any question about backtest results or repainting on TradingView, before editing a file in this repo, and when reading a Pine file to port it elsewhere.
---

# Pine Script v6

Pine is TradingView's language: one script = one indicator or strategy that executes
once per historical bar and then once per tick on the realtime bar. Values are
**series** (a history per bar, indexed with `[n]`), the script is re-run from scratch on
every recompile, and the engine, not you, handles the loop over bars.

| Need | Read |
|------|------|
| `strategy()` properties, orders, exits, position state, tester semantics | `references/strategy-api.md` |
| `request.security`, lookahead, repainting, realtime vs history, `varip` | `references/repainting-and-security.md` |
| How this repo's strategies are built: inputs, groups, FGF block, conventions | `references/repo-strategies.md` |
| Language essentials, v6 changes, limits, debugging | below |

## Essentials
```pine
//@version=6
strategy("Name", "SHORT", overlay = true, pyramiding = 0, initial_capital = 10000,
     default_qty_type = strategy.fixed, default_qty_value = 1, process_orders_on_close = false,
     calc_on_every_tick = false, commission_type = strategy.commission.percent, commission_value = 0.05)

gS1 = "S1. Entries"
len   = input.int(14, "RSI length", minval = 2, group = gS1, tooltip = "...")
mode  = input.string("ATR", "Unit", options = ["ATR", "Points"], group = gS1)
tf    = input.timeframe("60", "Parent timeframe", group = gS1)

var float level = na          // var: initialised once, keeps its value across bars
varip int ticks = 0           // varip: keeps value across realtime ticks too

rsi  = ta.rsi(close, len)
fast = ta.sma(rsi, 2)
up   = fast > fast[1]         // [1] = previous bar's value
atr  = ta.atr(14)

f_dist(unit, atrMult, pts) => unit == "ATR" ? atrMult * atr : pts * syminfo.mintick

if barstate.isconfirmed and up and strategy.position_size == 0
    strategy.entry("L", strategy.long, stop = close + f_dist(mode, 0.25, 50))
```
- Types: `int float bool string color line label box table array<T> matrix<T> map<K,V>`
  plus user `type` and `enum` (v6). `na` is the missing value; test with `na(x)`,
  replace with `nz(x, 0)`. In v6 `bool` is never `na`.
- Functions: `f(a, b) => expr` single-line, or indented block returning the last
  expression; a tuple `[a, b]`. Methods: `method f(array<float> a) => ...`.
- Conditionals: `if`, `switch`, ternary. Loops: `for i = 0 to n - 1`, `for [i, v] in arr`,
  `while`. Scripts run per bar, so loops are for arrays, not for history.
- Every `ta.*` call must execute on every bar to keep its history consistent; call them at
  global scope and use the result inside `if`, never call `ta.sma` inside a conditional.
- `request.security` calls are limited (40 per script); `max_bars_back` controls how far
  `[n]` can look; `max_labels_count/max_lines_count/max_boxes_count` up to 500.
- Drawing: `label.new(bar_index, y, text, style=..., color=...)`, `line.new(x1, y1, x2, y2)`,
  `box.new`, `table.new(position.top_right, cols, rows)` + `table.cell`. Delete old
  objects or rely on the count limit.
- Strings: `str.tostring(x, "#.##")`, `str.format("{0} at {1}", a, b)`,
  `str.format_time(time, "yyyy-MM-dd HH:mm", "America/New_York")`.
- `alert()` / `alertcondition()` for alerts; strategies also fire order-fill alerts.

## v6 changes worth knowing (from v5)
- Dynamic requests: `request.security` accepts series strings for symbol/timeframe.
- `bool` cannot be `na`; `enum` types; `text_formatting` in labels; negative array
  indices; `strategy.exit` requires at least one exit condition; `syminfo.mintick`-based
  rounding helpers; `timeframe.from_seconds`; `for ... in` over maps.
- Migration from v4: `study()` → `indicator()`, `security()` → `request.security()`,
  `rsi()` → `ta.rsi()`, `input(..., type=...)` → typed `input.*`, `transp` → `color.new`.

## Debugging and verification
- `plot()`/`plotchar()` any series, or write it into a `label` on the last bar
  (`barstate.islast`). `log.info()` prints to the Pine Logs panel (v6).
- Strategy Tester → "List of Trades" shows each fill: entry/exit time, price, signal
  comment. Export to CSV to compare with Python or MQL5 runs.
- Check "Properties" of the strategy for commission, slippage, order size, bar
  magnifier, `process_orders_on_close` before comparing results across platforms.
- Realtime behaviour differs from history: read `repainting-and-security.md` before
  claiming a backtest is reproducible live.

## Editing files in this repo
Preserve the header changelog format, add a version bump line describing *what changed
and why*, keep input groups and tooltip style ("STRATEGY ADDITION." prefix for logic the
original indicator did not have, calibrated values stated in the tooltip), and never
change the original indicator's calculations "line for line" blocks without saying so in
the header. Details in `references/repo-strategies.md`.
