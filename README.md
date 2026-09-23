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

**The signal is read at the beginning of the candle.** It uses the candle's
open plus the completed candles before it, nothing from the candle's close:
the EMAs are updated with the open, a breakout is the open crossing the
previous range, an engulfing pattern is the previous candle. So the signal is
known the moment the candle opens, the entry is that open, and it can be traded
live. The label sits on that candle, the dot marks its open, and the move
(ticks and timing) is measured from that open; the candle itself counts toward
the move.

*Signal read at* = *Candle close* gives the classic close-based reading; with it,
*Entry point* chooses whether the mark goes to the signal candle's open (placed
once that candle closes) or to the next candle's open.

A table (top-right by default) lists the most recent entries: side, signal time,
entry price, best / worst ticks, time to the best point, result and duration.
Every entry is also available as an alert (`Long entry`, `Short entry`, `Any entry`);
alerts fire when the mark is placed.

## Any timeframe on any chart

*Signal timeframe* lets you compute entries on one timeframe (for example `60`)
and see them on any chart timeframe (for example a 5-minute chart). The mark
goes to the first chart candle of the signal bar, at its open, and is placed
once that signal bar **closes**. Leave it blank to use the chart's own timeframe.

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

- **The trade is taken on the signal candle.** To enter and exit at the
  **beginning** of the signal candle, put the chart on a lower timeframe than
  the *Signal timeframe* (for example chart `1`, signal timeframe `10`): the
  strategy then fills on the first chart candle of each signal candle, and exits
  by reversal fill there too. On the chart's own timeframe a fill can only
  happen once the signal exists, i.e. at the signal candle's close. The Strategy
  Tester and the table's summary row use the real fills.
- **Live-tradeable.** With the default *Candle beginning* reading, the signal
  of a 10-minute candle depends only on its open and the candles before it, so
  reading it on its first 1-minute candle is exact and matches real time. Only
  the *Candle close* reading uses the candle's final value early (history only).
- **Same marks as the indicator.** The LONG / SHORT label and dot sit at the
  open of the signal candle, and the move in ticks and time is measured from
  that open, exactly as in the indicator. The label tooltip shows both the mark
  price (open) and the real fill price (close).
- **Exits.** An opposite signal reverses the position on its signal candle. Optional
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
