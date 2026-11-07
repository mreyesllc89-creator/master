# XAUUSD M1 Liquidity Zero-Cross Bearish (MT5 EA) v1.00

Short-only MQL5 Expert Advisor for XAUUSD on M1. *"No señal = no operación"*: no signal means no trade.

Files:
- `XAUUSD_M1_LiquidityZeroCross_Bearish.mq5` is the EA source. Copy it to `MQL5/Experts/` and compile it in MetaEditor.
- `presets/XLZC_Bearish_Conservative.set` and `presets/XLZC_Bearish_Aggressive.set` are input presets. Copy them to `MQL5/Presets/`, then load them from the EA's Inputs tab.

## Rule map

| Rule | Implementation | Type |
|---|---|---|
| R1 HTF bias | M15 (or M5) MACD(12,26,9) main < 0 **and** close < EMA(50) on the last closed HTF bar | Mechanical, `UseHTF_Filter` |
| R2 M1 trigger | MACD main at bar[2] ≥ 0 and at bar[1] < 0, checked once per new M1 bar on closed bars only, so it does not repaint | Mechanical |
| R3 Stochastic(7,1,7) | Main reached ≥ 80 within the last `Stoch_LookbackBars` bars and is now below its signal line or below 80 | Soft quality filter (`StochHardBlock` makes it hard) |
| R4 Liquidity | **SL:** the most recent liquidity candle (a bar that swept an older swing high and closed back below it). If there is none, the most recent swing high above price. Add `SL_Buffer_Points` plus the spread. **TP:** the nearest swing low below price that gives at least `MinRewardRisk`. If neither exists within `LiquidityLookbackBars`, the trade is skipped | Mechanical, simplified |
| R5 Risk | `RiskPercent` of equity, lot size from the SL distance (`OrderCalcProfit`), margin check, at most 1 position, `MaxSpread_Points`, trailing (server or hybrid) and an optional partial close | Mechanical |
| R6 Session/news | `TradingHoursStart`/`End` (default 12:00–16:30 GMT, the London/NY overlap), plus a ±30 min high-impact USD news filter using the MT5 calendar | Mechanical |
| Optional | RSI(12) < 50, manual SL/TP prices, HTF swing lows as extra TP candidates | Discretionary, default OFF |

## Notes
- Point inputs assume a 2-digit gold quote, where 1 point = 0.01 and 40 points = 4 pips. `AutoScalePoints` multiplies them by 10 on 3-digit feeds.
- Execution: a signal stays valid for the M1 bar that follows the cross. Spread, session, news and structure are checked again on every tick within that bar. Requotes and price changes are retried up to 3 times. Hard errors drop the signal.
- Hybrid trailing keeps the original broker SL as a catastrophe stop and closes at market when the virtual trailing level is hit. Virtual levels and partial-close state are stored in terminal global variables, so they survive a restart.

## Known limitations
- Liquidity detection is simplified to fractal swings plus one sweep pattern. Hand-drawn "blue rectangle" zones, order blocks and equal-high/low clusters are **not** auto-detected in v1. `DrawLiquidityZone()` is the hook for adding them.
- The economic calendar is unavailable in the Strategy Tester, so the news filter is bypassed there.
- `TimeGMT()` equals server time in the tester. Set `TesterGMTOffsetHours` to the broker's offset when backtesting.
- "Stochastic(7,1,7)" is mapped as %K=7, Slowing=1, %D=7. All three are inputs.
- The source code was not compiled in this environment because MetaEditor is not available on Linux CI. Compile it and run a visual backtest before going live.
