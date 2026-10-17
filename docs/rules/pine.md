# Pine Script rules (TradingView)

Read this before writing or changing any `.pine` file. Each rule exists because
breaking it has already cost a wrong backtest or a rewrite in this repo.

## Version and declaration

- New scripts use `//@version=6`. Do not upgrade an existing v5 script as part
  of another change; do it as its own change.
- Strategies declare costs and fills explicitly, never TradingView defaults:
  `commission_type = strategy.commission.percent`, `commission_value = 0.02`
  (or the broker's real figure), `slippage` in ticks, `initial_capital`,
  `default_qty_type` / `default_qty_value`.
- If `calc_on_every_tick` or `process_orders_on_close` is true, the header must
  say why. Both change fills and make history disagree with realtime.

## No repainting, no lookahead

- Higher-timeframe data comes from the last closed bar:
  `request.security(sym, tf, expr[1], lookahead = barmerge.lookahead_on)`
  (the `[1]` + `lookahead_on` idiom). `lookahead_on` without `[1]` reads the
  future and is a bug.
- Plain `request.security(..., lookahead_off)` on a higher timeframe repaints
  in realtime. It may stay only behind an input that defaults to the
  non-repainting read (as `htfNoRepaint` does in the FlashGold strategies).
- Signals are decided on `barstate.isconfirmed` data unless the script states
  that it is an intrabar strategy.
- A script may make at most 40 `request.security` calls. Return tuples from one
  call instead of calling once per value.

```pine
// Right: last closed higher-timeframe bar, same in history and realtime
htfDir = request.security(syminfo.tickerid, "240", tdiDir()[1], lookahead = barmerge.lookahead_on)

// Wrong: reads the forming 4h bar, so the backtest sees the future
htfDir = request.security(syminfo.tickerid, "240", tdiDir(), lookahead = barmerge.lookahead_on)
```

## Inputs and layout

- Strategy-only inputs go in numbered groups: `"S1. Entries"`, `"S2. Exits"`,
  `"S3. Sizing"`. Inputs kept from the original indicator keep their
  indicator group names, so the two can be compared side by side.
- Every input added on top of an indicator has a tooltip that starts with
  `STRATEGY ADDITION.`
- Exits support ATR and points units. Default to ATR units: points do not carry
  across symbols or volatility regimes.

## File header

Every strategy starts with a comment block that says:

1. Its source: which indicator or earlier version it converts or fuses.
2. What was kept unchanged, and what the strategy adds.
3. **CALIBRATION:** symbol, exchange feed, timeframe, date range, bar count,
   position size, which inputs were swept, and the results under
   [validation.md](validation.md) (TradingView fill model, worst case, with
   fees, both halves). Say what was *not* tested.

`FlashGold_v5_Strategy_BTCUSD.pine` is the reference example of this header.

## Versions and fusions

- A new version is a new file (`name_vX.Y_strategy.pine`). The old file stays
  until the new one is calibrated.
- A fused filter keeps the `_FGF` suffix (FlashGold Direction Filter) and a
  master switch input. With the switch off, the strategy must trade exactly
  like the unfused file. Check that before calling the fusion done.
- Keep the TradingView and MQL5 versions of the same idea on the same version
  number, and note any fill-model difference in both headers.
