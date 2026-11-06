# request.security, lookahead and repainting

## request.security
```pine
request.security(symbol, timeframe, expression, gaps = barmerge.gaps_off, lookahead = barmerge.lookahead_off, ignore_invalid_symbol = false, currency = currency.NONE, calc_bars_count = na)
```
- Returns the `expression` evaluated on `timeframe` for `symbol` (`syminfo.tickerid` = the
  chart's), aligned to the chart bars.
- **Higher timeframe, no repaint** (the idiom these strategies call "lookahead_on + [1]"):
  `request.security(syminfo.tickerid, "60", expr[1], lookahead = barmerge.lookahead_on)`.
  The `[1]` inside the expression takes the *last closed* HTF bar; `lookahead_on` makes
  that value available from the first chart bar of the HTF bar instead of the last. History
  and realtime then agree. Without `[1]`, `lookahead_on` leaks the future (classic
  repainting backtest); with `lookahead_off` and no `[1]`, history shows the HTF bar's
  final value during the whole HTF bar (also future-leaking in history) while realtime
  shows the forming value.
- **Lower timeframe** on a higher chart: use `request.security_lower_tf`, which returns an
  array of intrabar values per chart bar.
- Same timeframe as the chart: returns the expression unchanged (the repo's "Chart" option).
- `gaps = barmerge.gaps_on` returns `na` on chart bars where the HTF has no new bar;
  `gaps_off` (default) repeats the last value.
- Calls are expensive and limited (40). Group several values in a tuple:
  `[r, f, s] = request.security(sym, tf, [rsi, fast, slow])`.
- Seconds timeframes ("1S".."45S") exist only where the plan allows; the repo's
  `ignoreNaZones` handles child zones returning `na` there.

## Repainting types and remedies
| Cause | Symptom | Remedy |
|-------|---------|--------|
| Using the forming bar (`close` while `barstate.isrealtime`) | history signals never flicker, live ones appear/disappear | act on `barstate.isconfirmed`, or use `[1]` |
| HTF data without `[1]` | backtest too good | the idiom above |
| `varip` state | history cannot reproduce intrabar sequence | keep `varip` for display only, or accept the difference |
| `calc_on_every_tick` + `strategy.entry` on `close` | fills differ from history | guard with `barstate.isconfirmed` |
| Future-referencing offsets (`plot(x, offset = -n)`), `ta.pivothigh` (needs right bars) | signal "appears" n bars late | use only confirmed pivots (`[rightBars]`) |
| Changing data (dividends/adjustments, broker feed differences) | old signals move | cannot fix; document |

## Realtime vs history
- History: one execution per bar with final OHLC. Realtime: one execution per tick, and
  the script's variables roll back to their values at the bar open before each tick
  (except `varip`). `barstate.isnew`, `.isrealtime`, `.islast`, `.isconfirmed`,
  `.ishistory` tell where you are.
- A strategy's history is recalculated on every reload; alerts and live fills are not.
  Keep a journal (order comments with time and price) when verifying.
- Bar magnifier (`use_bar_magnifier`) uses intrabar data for fills in history only.

## Checklist before trusting a backtest
1. No `request.security` without `[1]` + `lookahead_on` on higher timeframes (or
   explicitly accepted).
2. Entries guarded by `barstate.isconfirmed` or using the previous bar.
3. Commission and slippage set; spread modelled when the symbol has one.
4. Enough history (`calc_bars_count`), and results not dominated by one trade.
5. Compare a few trades against a different engine (Python engine or MT5).
