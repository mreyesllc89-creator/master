# XLZC Bearish EA v1.20: start here

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

**v1.20 presets (recommended).** These came from the final calibration: 39 timeframe pairs × 324 structure settings × 5 trailing settings × 2 sessions × Stochastic soft/hard, then the v1.20 options on the best setups. Every setting was chosen with **2025 data only**. They are shipped because they also held up in 2026 under all four ways of filling a trailing stop inside a bar.

| Preset | Chart / trend | Backtest, whole period | 2026 (out of sample) |
|---|---|---|---|
| `XLZC_v120_Gold_M2_H4.set` | M2 / H4, 12:00–16:30 | 154 trades, PF 2.00–2.11 | **PF 1.89–2.23** (37 trades) |
| `XLZC_v120_Gold_M3_H4.set` | M3 / H4, 12:00–16:30 | 106 trades, PF 1.78–2.16 | PF 1.76–2.42 (26 trades) |
| `XLZC_v120_Gold_M3_M15.set` | M3 / M15, 07:00–20:00 | 92 trades, PF 2.00–2.14 | PF 1.40–1.65 (23 trades) |
| `XLZC_v120_Gold_M3_H1.set` | M3 / H1, 07:00–20:00 | 101 trades, PF 1.77–1.87 | PF 1.44–1.58 (23 trades) |
| `XLZC_v120_Gold_M2_H1.set` | M2 / H1, 12:00–16:30 | 111 trades, PF 1.72–1.83 | PF 1.33–1.61 (31 trades) |
| `XLZC_v120_BTCUSD_M1_M15.set` | M1 / M15, 07:00–20:00 | 104 trades, PF 1.62–1.85 | **PF 1.67–1.89** (26 trades) |
| `XLZC_v120_BTCUSD_M5_H2.set` | M5 / H2, 07:00–20:00 | 108 trades, PF 1.82–2.20 | PF 1.51–1.74 (29 trades) |
| `XLZC_v120_BTCUSD_M3_D1.set` | M3 / D1, 12:00–16:30 | 176 trades, PF 1.60–1.87 | PF 1.26–1.45 (55 trades) |

- Times are broker server time. PF ranges cover the four trailing-fill assumptions.
- The BTC presets assume a 5 USD spread and refuse to trade above 10 USD. Use them with low-cost brokers only.
- **Caution:** each preset's settings were chosen on 2025, but these pairs were then shipped because they held up in 2026, which is a mild second selection. Expect live results below these figures.
- Most presets use tight trailing, which one-minute bars cannot fully judge. Run them in the MT5 Strategy Tester with real ticks first.

**v1.10 presets (earlier calibration, still valid).**

| Preset | EA file | Notes |
|---|---|---|
| `XLZC_Bearish_M2_H1_NY.set` | without filter | 186 trades, PF 1.55; 2026 PF 1.61 (chosen on 2025). |
| `XLZC_Bearish_M3_H1_NY.set` | without filter | 77 trades, PF 1.82–2.48; in-sample (chosen with all 17 months). |
| `XLZC_Bearish_M3_H4_NY.set` | without filter | 106 trades, PF 2.07; 2026 PF 2.15. Superseded by the v1.20 M3/H4. |
| `XLZC_Bearish_M3_H1_NY_FGF.set` | **with** filter | 28 trades, PF 3.18, less total profit. |
| `XLZC_Bearish_BTCUSD_M3_H1.set` / `_M3_M30.set` | without filter | BTC, low-cost brokers; M3/M30 is experimental. |
| `XLZC_Bearish_Calibrated_M1_M15.set`, `_Conservative.set`, `_Aggressive.set` | without filter | First pass or spec-based; reference only. |

Every preset risks 0.5% per trade (1% for Aggressive) and uses its own magic number.

## TradingView version

`XLZC_Liquidity_ZeroCross_Bearish_Strategy.pine` is the same strategy as a TradingView Pine v6 strategy. Its **Preset** dropdown holds all eight v1.20 presets (default: Gold M2/H4) and the five v1.10 presets, with the same values as the `.set` files.

1. Open the Pine Editor, paste the file, click **Add to chart**.
2. Put the chart on the trigger timeframe: **2 minutes** for the M2 presets, **3 minutes** for the M3 presets, **1 minute** for BTC M1/M15 and **5 minutes** for BTC M5/H2. The table in the top-right corner turns red when the chart is wrong.
3. In **Settings > Inputs**, pick the preset and set **Spread** to your broker's typical spread in price, for example 0.45 for gold or 5 for BTC.
4. In **Settings > Properties > Commission**, enter the value the table shows: half the spread per contract per side, plus your broker's commission. Without it the backtest leaves out the spread cost.

The Pine version now has the v1.20 options the presets use: the trend condition (MACD and/or EMA), take-profit at liquidity zones with a TP buffer, and the Stochastic AND/OR rule. The presets are written into the Pine file by `research/make_pine_presets.py`, so rerun it after changing a `.set` file.

Differences from MT5:
- The session is entered in New York time (server time − 7 h): 12:00–16:30 server = 05:00–09:30 New York, 07:00–20:00 server = 00:00–13:00 New York. The presets already do this conversion.
- TradingView has no spread data, so there is no spread cap.
- There is no news filter, partial close, hybrid trailing, RSI filter, second trend timeframe, manual zone levels or FlashGold build. None of the shipped presets uses them, except the news filter, which was not in the backtest either.
- Orders fill at the signal bar's close instead of the next bar's open (the same price on a continuous feed).
- Same-bar stop and trailing fills use TradingView's bar magnifier on Premium plans; otherwise TradingView guesses the order of prices inside each bar.

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
