# Gold VoVix DEVMA strategy

TradingView Pine Script strategy for XAUUSD plus the backtest exports and analysis used to
review it.

- `strategies/gold_vovix_devma_v2.pine` is the v2 script as tested.
- `strategies/gold_vovix_devma_v2_1.pine` fixes the trailing-stop units bug (see report).
- `analysis/REPORT.md` is the review of the v2 backtests. Short version: the 88 to 96
  percent win rates come from the trailing stop being specified in price points where Pine
  expects ticks, which makes the backtester exit every trade at the bar's best price.
- `data/backtests/` holds the TradingView trade-list exports; `data/bars/` holds the chart
  bar exports used to verify fills.

```
python3 analysis/analyze_trades.py 1.24
python3 analysis/join_check.py
```
