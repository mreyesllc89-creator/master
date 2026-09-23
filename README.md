# Candle Entry Labels (TradingView / Pine Script v6)

Two scripts that share the same signal engine:

| File | Type | Use it to |
|---|---|---|
| `pine/entry_labels.pine` | Indicator | Label entry candles and measure the move that follows, in **ticks** and **time** |
| `pine/entry_strategy.pine` | Strategy | Trade the market with market orders exactly as the indicator signals, backtest it, and draw the same labels from the real fills |

## What you get on the chart

| Element | Long | Short |
|---|---|---|
| Entry label on the entry candle | green `LONG ▲` **below** the candle | red `SHORT ▼` **above** the candle |
| Entry point | dot at the candle **open** (the entry price) | same |
| Label contents | entry price (the open), signal time (your timezone), signal timeframe | same |
| Best point of the move (MFE) | dashed line from entry + `▲ best +N ticks · 2h 15m · 14:30` | `▼ best +N ticks …` |
| Worst point of the move (MAE) | dotted line + `worst -N ticks · time` | same |
| End of move | `END +N ticks · duration · bars · time` | same |
| Live label while the move is open | current ticks, best ticks and when, elapsed time | same |

**The entry is at the open of the candle that follows the signal bar.** The
signal bar closes, the next candle opens, and that open is the entry: the label
sits on that candle, the dot marks its open, and the move (ticks and timing) is
measured from that open. The entry candle itself counts toward the move.

A table (top-right by default) lists the most recent entries: side, signal time,
entry price, best / worst ticks, time to the best point, result and duration.
Every entry is also available as an alert (`Long entry`, `Short entry`, `Any entry`);
alerts fire at the open of the entry candle.

## Any timeframe on any chart

*Signal timeframe* lets you compute entries on one timeframe (for example `60`)
and see them on any chart timeframe (for example a 5-minute chart). The entry
candle is the first chart candle after the signal bar **closes**, and the entry
is its open, so nothing repaints. Leave it blank to use the chart's own timeframe.

Times are shown with the *Time format* and *Timezone* inputs
(e.g. `HH:mm`, `America/New_York`). Blank timezone = exchange timezone.

## Signal types

| Type | Long | Short |
|---|---|---|
| EMA cross (default) | fast EMA crosses above slow EMA | crosses below |
| Engulfing candle | bullish engulfing | bearish engulfing |
| Breakout | close breaks the highest high of the lookback | breaks the lowest low |
| External | *External long source* turns `> 0` | *External short source* turns `> 0` |

**External** lets you plug in your own strategy: pick another indicator's plot
as the source and this script will label and measure its entries.

## Ticks

A tick is `syminfo.mintick` for the symbol (0.25 on ES, 0.01 on most stocks, …).
Turn on *Show money value per contract* to also print `ticks × tick value`.

## Install

1. TradingView → Pine Editor → paste the contents of `pine/entry_labels.pine`.
2. *Add to chart*. Configure in the indicator settings (gear icon).

## Strategy version (`pine/entry_strategy.pine`)

Same signals, same labels, but the script actually trades:

- **Market order filled at the open of the entry candle.** The order is sent
  when the signal bar closes and fills at the next candle's open: the same
  candle and the same price the indicator marks. LONG label below the candle,
  SHORT label above it, dot at the fill price, both showing the fill and signal time.
- **Exits.** An opposite signal reverses the position at the next open. Optional
  *Stop loss* and *Take profit* are set in **ticks** and can fill inside a candle.
  Optional *Time stop* closes after N bars. *Take long / short entries* toggles
  let you run one side only.
- **Move marks from real fills.** Best / worst point in ticks and time, and the
  `END` label uses the strategy's real exit price and exit time (stop, target,
  time stop or reversal).
- **Table.** Recent trades plus a summary row: closed trades, win rate, net profit.
- Open the *Strategy Tester* tab for the full backtest report.

Position size, initial capital and commission are set in the strategy's
*Properties* tab.
