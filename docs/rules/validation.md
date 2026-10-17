# Validation rules (both platforms)

A backtest result is only quoted alongside the checks below. This comes from
the FlashGold BTCUSD calibration: one setting showed +219k in TradingView,
+27k in the worst case, and about -12k with a 0.02% fee, because a tight
trailing stop booked exits at the bar extreme, which live fills can't do.

## Every result shows

1. **TradingView fill model** (or MT5 "Every tick based on real ticks").
2. **Worst case:** when a bar touches both stop and target, the stop is hit
   first, and a trailing stop exits as soon as it activates.
3. **With costs:** commission (for example 0.02% per side), real spread and
   slippage.
4. **Both halves:** the test period split in two, and each half positive on
   its own.
5. Profit factor, win rate, number of trades and max drawdown, not net profit
   alone.

## Parameter sweeps

- Choose a setting from a stable area, not a single peak. For example, "SL 0.08
  to 0.12 ATR × TP 3 to 10R is positive in every case" is better than one best
  cell.
- Report how many combinations were tried.
- Test more than one timeframe and say which were not tested and why (for
  example, no data below 60m, or fees dominate tight stops on 1m to 15m).

## Before going live

- Compare the MT5 Strategy Tester against TradingView on the same period. Trade
  counts and direction should roughly agree. Explain any gap with the fill
  differences listed in the EA header.
- Forward-test on a demo account before risking real money.
- Treat fewer than about 100 trades or one month of data as preliminary, and
  label it that way in the header.
