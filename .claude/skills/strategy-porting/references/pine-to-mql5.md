# Pine → MQL5 mapping

## Execution model
| Pine | MQL5 |
|------|------|
| Script runs once per bar (history), per tick (realtime) | `OnTick()` runs per tick; emulate bar logic with `IsNewBar()` and read bar 1 |
| `close`, `high[1]` | `iClose(_Symbol,_Period,0)`, `iHigh(_Symbol,_Period,1)` or `CopyRates` + `ArraySetAsSeries` |
| `bar_index` | `Bars(_Symbol,_Period)` or `iBarShift` for distances |
| `time`, `time_close` | `iTime(..., i)`, `iTime(..., i) + PeriodSeconds()` |
| `barstate.isconfirmed` | logic on the first tick of the new bar, bar 1 |
| `var x = ...` | global or `static` variable (initialised once) |
| `varip` | plain global (ticks are real) |
| `na`, `nz(x)` | `EMPTY_VALUE` / `DBL_MAX` sentinels; check `CopyBuffer` count |
| `syminfo.mintick` | `_Point` (or `SYMBOL_TRADE_TICK_SIZE` for price rounding) |
| `syminfo.pointvalue` | `SYMBOL_TRADE_TICK_VALUE / SYMBOL_TRADE_TICK_SIZE` per lot |
| `timeframe.period`, `"60"` | `_Period`, `PERIOD_H1`; `PeriodSeconds()` |
| `str.format_time(t, fmt, tz)` | `TimeToString(t, TIME_DATE|TIME_MINUTES)`; server time only, convert with an offset input |

## Indicators
| Pine | MQL5 handle | Note |
|------|-------------|------|
| `ta.rsi(close, n)` | `iRSI(sym, tf, n, PRICE_CLOSE)` | identical (Wilder) |
| `ta.sma(src, n)` | `iMA(sym, tf, n, 0, MODE_SMA, srcHandleOrPrice)` | pass the RSI handle for TDI lines |
| `ta.ema` | `iMA(..., MODE_EMA, ...)` | seed differs, converges |
| `ta.rma` | `iMA(..., MODE_SMMA, ...)` | identical |
| `ta.atr(n)` | hand-rolled Wilder ATR (see `mql5/references/indicators-and-data.md`) | `iATR` is SMA-based: not identical |
| `ta.stdev` | `iStdDev(..., MODE_SMA, ...)` | population std both |
| `ta.highest(h, n)` / `ta.lowest` | `iHighest(sym, tf, MODE_HIGH, n, shift)` → `iHigh` | returns index |
| `ta.cum(x)` | running sum in a global | |
| `ta.crossover(a, b)` | `a1 > b1 && a2 <= b2` on bars 1 and 2 | |
| `ta.change(x)` | `x1 - x2` | |
| `request.security(sym, tf, expr[1], lookahead_on)` | handle on `tf`, `CopyBuffer(..., 1, ...)` index 1 | no repaint |
| `request.security(sym, tf, expr)` (repainting) | index 0 of the HTF handle | reproduces the repaint; usually undesirable |
| Seconds timeframes | none | document as unmatchable |

## Inputs
| Pine | MQL5 |
|------|------|
| `g = "S1. Entries"` + `group = g` | `input group "S1. Entries"` |
| `input.int(3, "Title", minval=0, tooltip=...)` | `input int InpX = 3; // Title` + validate in `OnInit` (`INIT_PARAMETERS_INCORRECT`) |
| `input.string("ATR", options=["ATR","Points"])` | `enum` with commented members |
| `input.bool` | `input bool` |
| `input.timeframe("60")` | `input ENUM_TIMEFRAMES InpTf = PERIOD_H1;` |
| `input.float(0.1, step=0.01)` | `input double`; step set in tester Inputs tab |
| `input.color`, `input.source` | `input color`, `input ENUM_APPLIED_PRICE` |

## Orders and position
| Pine | MQL5 |
|------|------|
| `strategy.entry(id, strategy.long, stop = p)` | `trade.BuyStop(lots, p, _Symbol, sl, tp, ORDER_TIME_SPECIFIED, expiry, comment)` |
| `strategy.entry(id, strategy.short, stop = p)` | `trade.SellStop(...)` |
| market `strategy.entry` | `trade.Buy / trade.Sell` on the new bar's first tick |
| entry reverses opposite position | netting: larger opposite order; hedging: close opposite in `OnTradeTransaction` on fill |
| `strategy.cancel(id)` / lifetime | `trade.OrderDelete(ticket)` on new bar when older than N bars, or `ORDER_TIME_SPECIFIED` expiration |
| `strategy.exit(stop=, limit=)` | SL/TP on the order/position (`PositionModify`) |
| `strategy.exit(qty_percent = 30, limit = tp)` + runner exit | EA closes `PositionClosePartial` when price reaches TP, then trails the rest |
| `strategy.exit(trail_points, trail_offset)` | EA trailing in `OnTick` with activation and distance |
| `strategy.close(id)` / `strategy.close_all()` | `PositionClose` loop |
| `strategy.position_size` | signed sum of `POSITION_VOLUME` over own positions |
| `strategy.position_avg_price` | `POSITION_PRICE_OPEN` (netting) or volume-weighted over positions |
| `strategy.opentrades.entry_bar_index(i)` | `iBarShift(_Symbol, _Period, POSITION_TIME)` |
| `strategy.equity` | `AccountInfoDouble(ACCOUNT_EQUITY)` |
| `pyramiding = n` | count own positions in the direction before entering |
| `process_orders_on_close = true` | not reproducible live; nearest = act on new bar at open |
| commission / slippage properties | broker's real costs; tester "Delay" and spread settings |
| `spreadPoints` input (synthetic spread) | remove; MT5 has real bid/ask. Keep an input only to reproduce the Pine backtest |

## Visuals
| Pine | MQL5 |
|------|------|
| `label.new` | `ObjectCreate(OBJ_TEXT / OBJ_ARROW_*)` |
| `line.new` | `OBJ_TREND` / `OBJ_HLINE` |
| `table.new` + `table.cell` | `OBJ_LABEL` grid or `Comment()` |
| `plot()` in a strategy | a companion indicator or chart objects; EAs cannot plot buffers |

## Structure of the port
1. Inputs in the same groups and order.
2. Handles in `OnInit`; one `Signal()` function that mirrors the Pine signal block with
   the same variable names.
3. `PlaceEntry`, `ManagePositions`, `ExpireOldOrders`, `TimeStop` as in the template.
4. Header comment: source file + version, differences, comparison result.
