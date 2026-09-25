# Gold VoVix DEVMA strategy

TradingView Pine Script strategy for XAUUSD plus the backtest exports and analysis used to
review it.

- `strategies/gold_vovix_devma_v2.pine` is the v2 script as tested.
- `strategies/gold_vovix_devma_v2_1.pine` fixes the trailing-stop units bug (see report).
- `strategies/gold_vovix_devma_v2_2.pine` adds an earlier entry trigger and a profit-aware
  time exit on top of v2.1 (see `analysis/CALIBRATION.md`).
- `strategies/gold_vovix_devma_v2_3.pine` adds a same-candle entry: a stop order parked at
  the solved EMA cross price, filling inside the signal bar instead of at its close.
- `strategies/gold_vovix_devma_v2_4.pine` adds a Distance Unit selector so stop, target,
  cross buffer, arming distance and trailing stop can be set in ATR multiples, gold points or
  % of price, plus a Buy only / Sell only switch.
- `analysis/REPORT.md` is the review of the v2 backtests. Short version: the 88 to 96
  percent win rates come from the trailing stop being specified in price points where Pine
  expects ticks, which makes the backtester exit every trade at the bar's best price.
- `data/backtests/` holds the TradingView trade-list exports; `data/bars/` holds the chart
  bar exports used to verify fills.

```
python3 analysis/analyze_trades.py 1.24   # trade-list stats
python3 analysis/join_check.py            # exits vs bar extremes
python3 analysis/simulate.py 0.25 1.24    # bar-level re-simulation and calibration grid
python3 analysis/simulate_intrabar.py     # same-candle stop entry vs close entry
```
