# XPW Shape Map — MQL5 port

Files:

| File | What it is |
|---|---|
| `XPW_ShapeMap.mq5` | Indicator. Port of Shape Map v0.7 (squares, turns, ticks, CONT, predict price). Map only, no trades. Built in 8 numbered "bites". |
| `XPW_ShapeMap_EA.mq5` | Expert Advisor. Port of Shape Map v0.9 strategy. Reads every signal from the indicator through `iCustom`, so map and EA always agree. |
| `calibrate.py` | Python replay of the same rules for grid-searching exits and CONT thresholds on exported bars. |
| `calibration/` | Reports produced by `calibrate.py`. |

## Install

1. Copy `XPW_ShapeMap.mq5` to `MQL5\Indicators\` and `XPW_ShapeMap_EA.mq5` to `MQL5\Experts\` (MetaEditor: File > Open Data Folder).
2. Compile the indicator first, then the EA (the EA loads the indicator by file name, input `IndicatorName`).
3. Drop the indicator on a chart to see the map. Attach the EA to trade.

The indicator's inputs are in the same order as the EA's "indicator inputs" block. If you add or reorder an input in the indicator, mirror it in the EA's `iCustom` call.

## Bites (indicator)

1. TDI: Wilder RSI(14) -> SMA(2) fast / SMA(7) slow, red/lime fill (`InvertFill` = fast above slow paints red).
2. Areas: position of the slow line in its 20-bar range, LOW below 0.20, HIGH above 0.67.
3. BOT / TOP squares: odd-colour wedge, drawn as a box in the panel with a label.
4. Turn arrows: the cross back that holds for `TurnHold` bars after a square.
5. Ticks: long wick candles, arrows on the price chart.
6. CONT: continuation without a cross (big candle -> little odd area -> pinch -> candle in trend direction).
7. Predict price: the close where fast would cross slow on the next bar (buffer 22), used by the EA's Predict entry.
8. Panel (Comment) and signal buffers 10-21 (1.0 on the bar a signal is confirmed).

Signals are committed once per closed bar and never repaint. `PreviewFormingBar` lets the EA see a preview on the forming bar for "enter on tick".

## Points

"Points" in the EA = MetaTrader `_Point`.

| Symbol | Typical point | $1 of price | TradingView v0.8 default SL 7000 pts at 0.1 tick ($700) becomes |
|---|---|---|---|
| XAUUSD | 0.01 | 100 pts | 70,000 pts for $700/oz, use the calibration below instead |
| BTCUSD | 0.01 | 100 pts | 70,000 pts |
| BTCUSD | 0.1 | 10 pts | 7,000 pts |

Check `Symbol > Specification > Digits` on your broker and scale the inputs.

## Calibration

```
python3 calibrate.py bars.csv --symbol BTCUSD --out calibration/BTCUSD_30m_report.md
python3 calibrate.py bars.csv --symbol XAUUSD --out calibration/XAUUSD_30m_report.md
```

Bars can be a TradingView export (`time,open,high,low,close,...`) or an MT5 export. To export from MT5: View > Symbols > pick the symbol > Bars tab > set the period and dates > Request > Export Bars. Or open the chart and use File > Save As (CSV).

Costs in `calibrate.py` are a flat spread per unit (XAUUSD 0.25, BTCUSD 20) and no commission. Edit `SYMBOLS` to match your broker.

Exit model in the replay is conservative: stop and target levels are checked against the level set by previous bars, a bar that opens beyond a level fills at the open, the trailing level only moves after the bar's exit checks, and any data gap over 3 hours (weekend, missing days) closes the position at the last close before it.

### Presets

`presets.py` writes the best 10 input sets per file as MT5 `.set` files (tester: Inputs tab > Load). Each candidate needs 15+ trades and a positive result on both halves of the data; ranking is net return minus 1.5 x max drawdown, at most 3 presets per entry mode.

| Folder | Data |
|---|---|
| `calibration/presets_BTCUSD/` | BITGET BTCUSDT M30, 4 Sep to 11 Oct 2026, spread $20 |
| `calibration/presets_XAUUSD_M15/`, `_M30/`, `_H1/` | VT Markets XAUUSD-ECNc ticks 1 to 14 Jul, 20 to 29 Jul, 30 Jul to 7 Aug 2026, built into bars; spread 0.12 + 0.07 commission |

Best preset per file (1% risk, $10k):

| File | Mode | Dir | SL $ | Trail act / dist $ | Trades | Win | PF | Net | Max DD | Half 1 / 2 |
|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSD M30 | CONT stop 0.8/1.5/4 | long | 500 | 800 / 10 | 42 | 57% | 1.85 | 12.4% | 3.2% | 9.6% / 2.9% |
| XAUUSD M15 | Square | both | 5 | 20 / 5 | 143 | 44% | 1.50 | 50.1% | 10.7% | 30.1% / 20.0% |
| XAUUSD M15 | CONT at close | both | 12 | 5 / 2 | 79 | 76% | 2.52 | 22.1% | 3.7% | 12.4% / 9.7% |
| XAUUSD M30 | Turn after hold | both | 5 | 20 / 5 | 37 | 32% | 2.02 | 32.7% | 9.0% | 18.3% / 14.4% |
| XAUUSD M30 | Turn after hold | long | 12 | 8 / 5 | 21 | 86% | 8.06 | 17.4% | 1.0% | 11.3% / 6.1% |
| XAUUSD H1 | CONT stop 0.8/1.5/4 | both | 5 | 20 / 5 | 23 | 61% | 5.36 | 80.7% | 4.2% | 35.1% / 45.6% |

The gold sample is five trading weeks that include a $230 rally in the last week, so the H1 CONT result is partly that trend. The $5 stop on gold is below the M30 average bar range ($11): it works with 1% risk only because the trail cuts winners short, and it will be sensitive to VT's execution. Verify every preset in the MT5 tester on tick data before using it.

### BTCUSD 30m (BITGET BTCUSDT, 4 Sep to 11 Oct 2026, 1798 bars)

Full report: `calibration/BTCUSD_30m_report.md`. Best exits per entry mode, 1% risk per trade, $10k account:

| Mode | SL | Trail act | Trail dist | Dir | Trades | Win | PF | Net | Max DD |
|---|---|---|---|---|---|---|---|---|---|
| Turn predict | $300 | $400 | $10 | long | 69 | 54% | 1.84 | 30.6% | 7.2% |
| Square | $300 | $100 | $10 | long | 71 | 75% | 2.12 | 20.6% | 3.9% |
| Turn at cross | $300 | $100 | $10 | long | 71 | 72% | 1.90 | 16.4% | 2.1% |
| Turn after hold | $500 | $200 | $10 | long | 46 | 80% | 3.26 | 16.1% | 2.1% |
| CONT stop | $300 | $100 | $10 | both | 53 | 70% | 1.78 | 14.6% | 3.8% |
| CONT at close | $700 | $400 | $10 | both | 59 | 63% | 1.60 | 11.5% | 3.1% |
| Tick | $500 | $100 | $10 | both | 48 | 83% | 2.27 | 11.1% | 2.9% |

CONT thresholds: `ContBigAtr 0.8, ContPinch 1.5, ContAfter 4-6` roughly doubled CONT net on this file (20-27%) at 3-6% drawdown, against the shipped defaults of 1.0 / 1.0 / 6.

Caveats: 37 days of one market, one timeframe, and a long-biased period, so "long" winning most modes is partly the sample. Treat these as starting points for the MT5 strategy tester, not finished settings. A $10 trail distance on BTC is tight; widen it if your broker's spread is above $20.

### XAUUSD

Bars built from VT Markets tick exports with `ticks2bars.py` (usage: `python3 ticks2bars.py <folder of unzipped tick csv folders> <out dir>`) (bid prices, server time). Reports: `calibration/XAUUSD_M15_report.md`, `XAUUSD_M30_report.md`, `XAUUSD_H1_report.md`. Bars used are in `calibration/bars_XAUUSD/`.
