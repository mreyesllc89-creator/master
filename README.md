# master

## pine/GVLiveV2_Poly_AnyChart_AnySymbol.pine

GVLiveV2 Polymarket pre-candle strategy, recalibrated so the same settings work on any chart timeframe, any pair, and any instrument type (crypto, forex, index/futures, stocks, CFDs).

### What changed versus the previous version

| Area | Before | Now |
|---|---|---|
| Trailing stop | `trail_points` / `trail_offset` were passed a price distance, but Pine expects ticks. On BTC (tick 0.01) the trail was 100x too far away; on ES (tick 0.25) 4x too close. | Converted to ticks with `syminfo.mintick`. Activation and offset fractions are now inputs. |
| Point value | Preset list of two options. | `Auto From Symbol` uses `syminfo.pointvalue`, with a manual override. |
| Quantity step / min qty | Fixed 0.01. | `Auto By Symbol Type` (crypto 0.001, forex 1000, stocks/futures/CFD 1), or manual. |
| Max stop distance | Absolute price points. | Percent of price. |
| Max live spread for the bridge | Absolute price points. | Percent of price; alert JSON carries both the percent and the converted points. |
| Daily loss lock | Fixed dollar amount. | Percent of day-start equity by default, currency mode still available. |
| VoVix / DEVMA regime | Raw ATR with a fixed `1e-6` epsilon, which dominated on low-priced tokens. | ATR as percent of price, so the regime detector is scale-free. |
| Order prices | Raw floats. | Rounded to tick with `math.round_to_mintick`. |
| Labels | `#.##` formatting (lost precision on DOGE / forex). | `format.mintick`. |
| Polymarket window | Hard-coded 5 minutes. | Derived from the router timeframe input. Optional bar-close timing reference. |
| Series slug | BTC or DOGE only. | Auto-built from `syminfo.basecurrency`, presets for BTC/ETH/SOL/XRP/DOGE, or custom. |
| Sessions / daily reset | New York only. | Timezone input (default still New York). |
| Volume filters | Would block symbols without a volume feed. | RVOL check is skipped automatically when the symbol has no volume. |
| Alert JSON | Symbol-blind. | Adds symbol type, exchange, base/quote currency, tick size, price scale, point value, qty step, ATR and ATR%, normalized spread / trend distance / range features. |

### Defaults to review per instrument

- `Fixed Trade Quantity` is 1 unit. That is 1 BTC on a crypto chart and 1 share on a stock chart, so set it or switch on `Use Dynamic Risk %`.
- `Max Daily Loss (% Of Day-Start Equity)` defaults to 0.15 percent of the 100k paper account, which matches the old 150 dollar limit.
- Session filter stays off by default. Turn it on for index futures or equities and set the timezone.
