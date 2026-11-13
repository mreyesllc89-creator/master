# Loma EA v1.30: start here

`XAUUSD_Loma_TrendPullback.mq5` trades the "loma" (MACD hump) method on XAUUSD in MetaTrader 5, buys and sells. It is a new, separate EA: the XLZC Bearish EA is not changed.

## The rules

A **hump** (loma) is a run of bars with the MACD on one side of zero.

1. **Trend first.** A big hump below zero means a bearish trend; a big hump above zero means a bullish trend. "Big" means its peak is at least `BigHumpMultiplier` times the usual hump, it lasts at least `BigHumpMinBars` bars and, if `RequireStochLevel` is on, the Stochastic reached 20 (bearish) or 80 (bullish) during it. With no big hump in force the market is **lineal** and the EA does not trade.
2. **Trend break.** An opposite hump as large as `TrendBreakRatio` times the big hump ends the trend.
3. **Sell signal** (bearish trend): a small pullback hump above zero (at least `PullbackMinBars` bars, no larger than `PullbackMaxRatio` times the big hump), then the first bar with the MACD back below zero. A touch of zero without a hump is not a signal.
4. **Stop loss:** above the highest high of the pullback hump, plus `SL_Buffer_Points` and the spread. No hump, no stop, no trade.
5. **Take profit:** a fixed multiple of the risk (`TP_Mode=TP_FIXED_RR`, used by the presets) or the low of the previous hump, taken a little early (`TP_PREV_HUMP`, `TP_Anticipation`).
6. **Weak signals are skipped:** only the first `MaxSignalsPerBigHump` signals after a big hump are traded, and the trend lapses after `TrendMaxBars` bars without a new big hump.
7. **Buys** are the exact mirror.
8. **Higher-timeframe filter** (`UseHTFFilter`): sell only below, buy only above the EMA(50) of H1 or H4. The presets use it; the backtest needs it.

## Install

1. In MT5 choose **File > Open Data Folder**.
2. Copy this package's `MQL5` folder over the data folder's `MQL5` folder.
3. In MetaEditor compile `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5`. It needs `MQL5/Include/EVK/EVK.mqh`, which is in the package.
4. Attach the EA to an XAUUSD chart (any timeframe: it reads its own). In **Inputs** click **Load** and pick a preset. Each preset has its own magic number, so several can run on one account.
5. Enable **Algo Trading**.

The EA has not been compiled here (no MetaEditor was available). Two independent reviews read it for compile errors and found none. If MetaEditor reports an error, send it to me.

## Presets

Backtest: FTMO XAUUSD one-minute data, January 2025 to May 2026, real spreads, risk-% sizing. Settings were chosen with 2025 only; 2026 is out of sample.

| Preset | Chart / trend filter | Session (server time) | Trades | PF | 2025 PF | 2026 PF |
|---|---|---|---|---|---|---|
| `Loma_Gold_M5_Buy_H1.set` | M5 buys / H1 | all day | 144 | 2.24 | 2.20 | 2.35 |
| `Loma_Gold_M5_Buy_H4.set` | M5 buys / H4 | all day | 138 | 2.06 | 2.03 | 2.17 |
| `Loma_Gold_M2_Sell_London_H1.set` | M2 sells / H1 | 07:00-12:00 | 130 | 2.16 | 2.35 | 1.71 |
| `Loma_Gold_M3_Sell_H4.set` | M3 sells / H4 | 07:00-20:00 | 165 | 1.70 | 1.86 | 1.41 |
| `Loma_Gold_M2_Sell_NY_H1.set` | M2 sells / H1 | 12:00-20:00 | 140 | 1.70 | 1.90 | 1.36 |

All five stay profitable with the spread doubled, and the hump rules beat taking every zero-cross in the same setting (PF 1.0-1.3, with three to six times the drawdown).

## Read before trading

- **Small samples.** Each preset has 28 to 55 trades in 2026. The direction is consistent; the exact numbers are not reliable.
- **Second selection.** These five were kept after looking at 2026, so expect live results below the table.
- **Buy presets ran in a rising gold market** (2025-26). The sell presets are the harder test.
- **Trailing** is in R multiples and tight (0.3 to 1.0 R). One-minute bars cannot fully judge it: run each preset in the MT5 Strategy Tester with **Every tick based on real ticks**, then on demo.
- **Session hours are broker server time**, calibrated on FTMO (GMT+2 winter, GMT+3 summer). Shift them if your broker's clock differs.
- **News filter** is on in the presets but was not in the backtest. Set `UseNewsFilter=false` to match it.
- **Not built yet:** extending the target to the middle of a liquidity candle.

## What you see on the chart

- **Status panel:** trend state (BEARISH / BULLISH / LINEAL), the big hump's size, signals used, the current hump and the last reason a signal was skipped.
- **Labels** on big humps, **arrows** on signals, and the stop and target lines of the last signal.
