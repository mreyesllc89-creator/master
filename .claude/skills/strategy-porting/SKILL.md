---
name: strategy-porting
description: Workflow for porting a trading strategy between platforms with verified parity - TradingView Pine Script → MQL5 Expert Advisor (MetaTrader 5), Pine → Python backtest, MQL5 → Python, or Python → MQL5 - covering input mapping, indicator smoothing parity (Wilder RSI, ATR SMA vs RMA, SMA-on-RSI TDI), bar-close vs tick execution, stop-order entries, spread models, SL/TP/trailing/partial+runner exits, position sizing, multi-timeframe without lookahead, and a trade-by-trade comparison plan. Use whenever the user says port, convert, translate, rewrite, "make an EA from this Pine", "same strategy in MT5/Python", or asks whether two implementations should match.
---

# Porting a strategy between Pine, MQL5 and Python

The goal of a port is the *same trades*, not merely similar code. Follow the steps; the
mapping tables are in the references. Load the `pine-script`, `mql5` and
`python-trading` skills for the platform details.

| Direction | Read |
|-----------|------|
| Pine → MQL5 (EA) | `references/pine-to-mql5.md` and `mql5/assets/EA_Template.mq5` |
| Pine → Python / MQL5 → Python | `references/pine-to-python.md` and `python-trading/scripts/indicators.py` |

## Steps

1. **Specification first.** Read the source completely (header, inputs with tooltips,
   every `strategy.*`/`OrderSend` call). Write a spec table before coding:

   | Rule | Source expression | Default | Unit | Target equivalent |
   |------|-------------------|---------|------|-------------------|

   Include: data model (single series + spread vs bid/ask), evaluation timing (bar
   close / next open / tick), entry type, cancellation rules, every exit, sizing, costs,
   direction filters, multi-timeframe inputs and their repaint handling.

2. **Decide the unmatchable items explicitly.** Some things cannot be identical:
   seconds timeframes (no MT5 equivalent), Pine's fill model vs MT5 ticks, Pine's spread
   model vs the real spread, `process_orders_on_close` live. Write them in the header
   comment of the target file as "Differences from the Pine version".

3. **Indicators with the same smoothing.** Verify each `ta.*` against its target
   (`pine-to-mql5.md` table). ATR is the usual trap (Pine RMA vs MT5 SMA).

4. **Inputs 1:1.** Same names (adapted to the target's naming style), same defaults,
   same groups and order, same tooltips as comments. A reviewer should be able to read
   both side by side.

5. **Build in layers and test each**: data/indicators → signal → entry orders → exits →
   sizing → filters. After each layer compare against the source on a fixed window.

6. **Trade-by-trade comparison.** Export the source platform's trade list (TradingView
   "List of Trades" CSV; MT5 Backtest → Save as report; Python engine DataFrame). Align by
   entry time (±1 bar) and direction; compare entry price, exit reason, bars held. Target:
   ≥90% of trades matched in time and direction with price differences explained by the
   spread/fill model. Report the unmatched ones and why.

7. **Document** in the target file header: source file and version, date, the spec
   table summary, the known differences, and the comparison result.

## Red flags that a port is wrong
- Trade count differs by more than ~20% on the same window and settings.
- The target wins where the source loses on most trades: the exit logic (SL/TP side) or
  the spread sign is inverted.
- Trades at the same timestamps but shifted by one bar: evaluation timing (bar 0 vs bar 1,
  fill at close vs next open).
- Good history, bad live: the source repaints (HTF lookahead) and the port does not.
