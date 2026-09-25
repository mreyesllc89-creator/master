# GVLiveV2 backtest review (XAUUSD, OANDA and VANTAGE)

Reviewed on 2026-09-25. Inputs: seven TradingView "List of trades" exports of the
`Gold VoVix DEVMA v2` strategy and eight chart bar exports (see `data/`).

## Verdict

The v2 backtests are not usable as evidence of an edge. Every export, from the 1-minute
chart to the daily chart, shows the same fingerprint of a units bug in the trailing stop:

| Export | TF | Trades | Net $ | Win % | PF | Exits after 1 bar | Winners' PnL / MFE |
|---|---|---|---|---|---|---|---|
| OANDA 1m | 1m | 7320 | 6928 | 95.8 | 7.72 | 91% | 0.99 |
| VANTAGE 1m | 1m | 5293 | 4586 | 87.6 | 3.09 | 76% | 0.96 |
| VANTAGE 5m | 5m | 1531 | 3914 | 92.2 | 4.70 | 83% | 0.97 |
| VANTAGE 30m | 30m | 213 | 1429 | 91.1 | 4.28 | 82% | 0.98 |
| VANTAGE 60m | 60m | 118 | 1553 | 94.1 | 10.11 | 85% | 0.98 |
| VANTAGE 240m | 240m | 36 | 545 | 4.89 | 94.4 | 89% | 0.98 |
| VANTAGE 1D | 1D | 52 | 795 | 10.05 | 94.2 | 94% | 0.98 |

Winners capture 96 to 99 percent of their own maximum favorable excursion. No real exit
does that. Joining the trade exits to the exported bars confirms the mechanism: on every
timeframe, 88 to 100 percent of one-bar winners exit within 10 percent of the exit bar's
range from the bar's best price (the high for longs, the low for shorts). On OANDA 1m the
median gap between exit price and bar extreme is $0.006, on VANTAGE 1m $0.07, which is one
tick of rounding plus the two-tick slippage setting. Full output is in `join_check.out.txt`.

## Root cause

`strategy.exit()` takes `trail_points` and `trail_offset` in **ticks**, not price points.
v2 passes price distances:

```pine
trail_points=profit_distance * 0.9, trail_offset=stop_distance * 0.3
```

On XAUUSD the tick is 0.01 (VANTAGE) or 0.001 (OANDA). With a 1-minute ATR near 0.5, the
trail activates after about one tick of favorable movement and follows price at an offset
of a fraction of a tick. TradingView's broker emulator then walks its assumed intrabar path
(open, then one extreme, then the other, then close), activates the trail at the first
favorable tick, and fills the exit at the favorable extreme of the bar. The result is a
near-guaranteed small profit on any bar that moves in the trade's favor at all, and a
close-of-bar loss (`Max Bars Exit`) on the few bars that never do. Both are artifacts.

Everything downstream of this is contaminated:

- The "trades held longer than one bar were net negative" observation that motivated
  `maxBarsInTrade = 1` is just the set of bars where the phantom trail never fired.
- The per-hour and per-session findings behind the Balanced preset were measured on the
  same phantom fills.
- The ATR stop and take-profit almost never execute, so their multipliers are untested.

## Second problem: costs

The commission column is zero in every export, although the script declares 0.62 per
contract. Either the property was overridden in the Strategy Tester or the export was made
with commissions off. Subtracting a 1.24 round trip (0.62 x 2) turns both 1-minute runs
negative before any spread is considered:

| Export | Net $ as exported | Net $ after 1.24 round trip | PF after cost |
|---|---|---|---|
| OANDA 1m | 6928 | -2149 | 0.62 |
| VANTAGE 1m | 4586 | -1977 | 0.61 |
| VANTAGE 5m | 3914 | 2016 | 2.44 |

The median winning trade on the 1-minute charts is 0.6 to 0.9 gold points, which is about
the size of a normal retail XAUUSD spread. Even if the fills were real, a 1-minute version
of this strategy would be trading inside the spread.

## Other things noticed in the exports

- Entries run from 04:00 to 22:29 on the chart clock on every intraday export, so these
  runs were not made with the script's default sessions (entry 09:45 to 15:30 New York,
  flat outside 09:30 to 15:45). Record the inputs used alongside each export.
- `Max Bars Exit` trades last four bars, so `maxBarsInTrade` was also not at its default
  of 1 when these were run.
- Two 1-minute OANDA trades and one VANTAGE trade do not land on a plotted signal bar in
  the bar export. That is small enough to be a chart-refresh difference, but worth a look
  once the fixed script is re-run.

## What changed in v2.1

`strategies/gold_vovix_devma_v2_1.pine` converts the trail parameters to ticks:

```pine
trail_activation_ticks = profit_distance * trailActivationMult / syminfo.mintick
trail_offset_ticks = stop_distance * trailOffsetMult / syminfo.mintick
```

The 0.9 and 0.3 multipliers are now inputs so they can be re-tuned, and the tooltip and
comment that cited the one-bar finding were rewritten. Nothing else in the logic changed.
Expect the re-run to look completely different: far fewer one-bar exits, real stop-loss and
take-profit hits, and a win rate nowhere near 90 percent.

## Suggested next steps

1. Re-run v2.1 on the 15-minute chart it was designed for, with commissions and the
   default sessions on, and export again.
2. Enable the spread in the test by backtesting on the ask or bid series, or by adding a
   per-trade cost input of at least 0.3 points on top of commission.
3. Only then revisit the session windows, the Balanced preset blocks, and `maxBarsInTrade`.
   The current values were fitted to phantom fills.
4. Before any live bridge test, confirm the fix by checking that winners no longer capture
   roughly 100 percent of their MFE (`python3 analysis/analyze_trades.py`).

## Reproducing

```
python3 analysis/analyze_trades.py 1.24   # per-file stats, optional round-trip cost
python3 analysis/join_check.py            # exits vs exported bar extremes
```

## Follow-up

`CALIBRATION.md` covers the earlier-entry and profit-aware time-exit work done after this
review, and `strategies/gold_vovix_devma_v2_2.pine` implements it.
