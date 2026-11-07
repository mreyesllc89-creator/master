# XLZC Bearish EA v1.10: start here

A short-only Expert Advisor for XAUUSD (gold) in MetaTrader 5. It sells when MACD crosses below zero on a short timeframe while the higher-timeframe trend is down. It places the stop above the latest liquidity high and the target at the next liquidity low. *No signal = no trade.*

## What is in the package

| File | What it is |
|---|---|
| `MQL5/Experts/XAUUSD_M1_LiquidityZeroCross_Bearish.mq5` | The EA **without** a direction filter. |
| `MQL5/Experts/XAUUSD_M1_LiquidityZeroCross_Bearish_FGF.mq5` | The same EA **with** the FlashGold Direction Filter v1.2. It is a short file that includes the one above, so keep both files in the same folder. |
| `MQL5/Indicators/FlashGold_Direction_Filter_v1_2.ex5` (+ `.mq5`) | The FlashGold indicator, needed only by the FGF version. |
| `MQL5/Include/FlashGold/*.mqh` | Include files for the indicator source. |
| `MQL5/Presets/*.set` | Input presets (table below). |
| `README.md` | Full documentation: rules, inputs, calibration and FlashGold results. |
| `MQL5/Include/EVK/EVK.mqh` + `EVK/` | The EA Validation Kit: runs the same tests on any EA from MT5 optimization results. See `EVK/README.md`. The XLZC EA already includes it. |
| `calibration_report.html` | The backtest report with charts, the walk-forward test and the code-review log. Open it in a browser. |

## Install

1. In MT5 choose **File > Open Data Folder**.
2. Copy the package's `MQL5` folder over the data folder's `MQL5` folder. This adds the files and replaces nothing else.
3. The EA includes `EVK/EVK.mqh` (copied with the `MQL5` folder). It only records trades in the Strategy Tester. If you remove EVK, delete the `#include <EVK/EVK.mqh>` line.
4. In MetaEditor, compile `XAUUSD_M1_LiquidityZeroCross_Bearish.mq5` and/or `XAUUSD_M1_LiquidityZeroCross_Bearish_FGF.mq5`. If you want to rebuild the indicator from source, compile `FlashGold_Direction_Filter_v1_2.mq5` too; otherwise the supplied `.ex5` is used.
5. Attach the EA to an XAUUSD chart (any timeframe: the EA reads its own timeframes). In the **Inputs** tab click **Load** and pick a preset.
6. Enable **Algo Trading**.

The code has not been compiled by me (no MetaEditor was available). If the compiler reports an error, send it to me.

## Signals run on M2/M3 even on an M1 chart

The EA computes its signals on `TriggerTimeframe` (M3 or M2 in the calibrated presets) and its trend filter on `HTF_Timeframe` (H1). The timeframe of the chart it is attached to does not matter. MT5 builds M2/M3 bars from its one-minute history. To see this for yourself:

- **Journal at start:** `Signals are computed on M3 bars (TriggerTimeframe) with the H1 trend filter (HTF_Timeframe). This chart is M1: the chart timeframe does not change the signals.`
- **Status panel** (top left, `ShowStatusPanel`): shows `Signals on: M3 bars | Trend filter: H1`, the last closed M3 bar and its close time, and the M3 MACD values the signal uses. It marks "(zero-cross DOWN)" when the signal fires. It also shows the H1 bias, the session, the spread and the open positions. It refreshes on each new M3 bar and once a minute.
- **Signal arrows** (`MarkSignals`): a red sell arrow at every valid signal. Hover over it to see "M3 signal: MACD(M3) crossed below zero on the M3 bar closed at ...". On an M1 chart the arrows appear only every 3 minutes or more, at M3 bar closes.
- **Switch the chart** (`SwitchChartToTriggerTF=true`): the EA switches its own chart to M3 when it starts, so the candles you see are the candles it trades. MT5 has M2/M3 charts too: right-click the chart and choose **Timeframes**.

## Which preset to use

| Preset | EA file | Timeframes | Backtest result | How much to trust it |
|---|---|---|---|---|
| `XLZC_Bearish_M2_H1_NY.set` | without filter | M2 trigger, H1 bias, 12:00-16:30 server time | 186 trades, PF 1.55, +19.9R, max drawdown 4.9R. **2026: PF 1.61 on 43 trades, data it was not chosen on.** | **Best-tested.** Chosen with 2025 data only, so 2026 is a real out-of-sample check. Weak spot: if every same-bar trailing touch is a stop-out, PF is 1.05. |
| `XLZC_Bearish_M3_H1_NY.set` | without filter | M3 trigger, H1 bias, 12:00-16:30 server time | 77 trades, PF 2.48 (1.82 in the worst trailing case), +20.8R, max drawdown 1.1R. | **Highest numbers, but in-sample.** All 17 months were used to choose it. The M3/H1 combination held up out of sample; the exact values are not proven. |
| `XLZC_Bearish_M3_H1_NY_FGF.set` | **with** filter | Same as M3/H1 + FlashGold defaults | 28 trades, PF 3.18, +8.7R. | Higher PF, a third of the trades, less than half the profit. In-sample. |
| `XLZC_Bearish_BTCUSD_M3_M30.set` | without filter | **BTCUSD**: M3 trigger, M30 bias, 12:00-16:30 server time | With a 5 USD spread: 117 trades, PF 1.45, +15.8R; **2026: PF 1.31 on 38 trades (out of sample)**. | **Low-cost brokers only.** At a 20 USD spread nothing held up. The 10 USD spread cap blocks trading when costs are higher. Worst-case trailing fills: PF 0.96. |
| `XLZC_Bearish_BTCUSD_M3_H1.set` | without filter | **BTCUSD**: M3 trigger, H1 bias, 12:00-16:30 server time | With a 5 USD spread: 102 trades, PF 1.52, +19.8R; 2026: PF 1.21 on 32 trades (out of sample). | Same conditions as above. Worst-case trailing fills: PF 0.99. |
| `XLZC_Bearish_Calibrated_M1_M15.set` | without filter | M1 trigger, M15 bias, 12:00-16:30 server time | 51 trades, PF about 1.7 (first calibration pass). | Fragile: small changes drop PF to about 1.05. Kept for reference. |
| `XLZC_Bearish_Conservative.set` | without filter | M1 / M15, 12:00-16:30 GMT | Not calibrated. | Built from the original strategy spec, not from the backtest. |
| `XLZC_Bearish_Aggressive.set` | without filter | M1 / M5, 07:00-20:00 GMT | Not calibrated. | Built from the original strategy spec; uses partial close and hybrid trailing. |
| `FlashGold_Direction_Filter_v1_2_Default.set` | indicator | | | The indicator's own default inputs. |

All presets risk 0.5% per trade (1% for Aggressive). Change `RiskPercent` to suit you. Each preset uses its own magic number, so two presets can run side by side.

## Things to check before trading

- **Session clock.** The calibrated presets use **broker server time** (`TradingHoursAreGMT=false`). They were built on FTMO data, whose clock is GMT+2 in winter and GMT+3 in US summer (New York close). If your broker's clock differs, shift `TradingHoursStart` and `TradingHoursEnd`.
- **Spread.** Every preset allows up to 60 points (`MaxSpread_Points`). If your broker's gold spread is usually wider, the EA will not trade at all.
- **News filter.** It is on in the presets but was not part of the backtest, because no calendar history was available. Set `UseNewsFilter=false` to match the backtest exactly.
- **FlashGold filter.** It helped on M3 triggers and hurt on M1 triggers and on M2/H1. There is no FGF version of the M2/H1 preset for that reason.
- **Test first.** Run each preset in the MT5 **Strategy Tester** with **Every tick based on real ticks** on your broker, then on a demo account, before trading real money. To repeat our hold-out and walk-forward tests on your broker, optimize the EA in MT5 and run `python -m evk analyze` on the CSV it writes (see `EVK/README.md`).

## Words used in the results

- **R**: one unit of the risk taken on a trade. +20R means the profit was 20 times the amount risked per trade.
- **PF (profit factor)**: total won divided by total lost. Above 1 makes money; 1.5 means $1.50 won for every $1 lost.
- **In-sample**: measured on the same data used to choose the settings. Usually too optimistic.
- **Out-of-sample / walk-forward**: settings chosen on one period (2025) and measured on a later period they never saw (2026). The fairer test.
- **Max drawdown**: the largest drop from a peak in the backtest, in R.

## How the results were produced

The EA's rules were replayed in Python on 16.5 months of FTMO XAUUSD one-minute data (January 2025 to May 2026), with the broker's measured spreads. The research searched 126,360 EA setups and 80,640 FlashGold settings. A multi-agent code review with independent verification checked the EA, the presets, the backtest and the claims, and every confirmed finding was fixed or documented. This is a replica of the EA, not the MT5 Strategy Tester, so confirm it in MT5. Details are in `README.md` and `calibration_report.html`; the scripts are in the repository's `research/` folder.
