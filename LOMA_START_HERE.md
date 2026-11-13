# Loma EA v1.32: start here

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

## What changed in v1.31

- **`SkipBigPullback` (on):** when the pullback hump is itself a big opposite hump, that is a trend change, so no signal is taken. In the backtest those trades were about break-even.
- **`CloseBeforeWeekend` (on in the presets, off by default in the EA):** positions are closed on Friday from `WeekendCloseTime` (23:00 server time) and no new trades open after it. This removes the dependence on weekend gaps. A position still open on Saturday or Sunday is closed on the first tick.

## What changed in v1.32

- **`MaxHoldMinutes` (0 = off):** closes a position once it has been open that many market minutes.
- **`CloseAtEndOfDay` with `EndOfDayTime` (server time):** closes positions when the server clock reaches that time. A trade opened after that time is kept until the next day's time.
- Neither blocks new entries on later bars. Both are off by default and off in the five original presets below; seven of the top-10 presets use them.

## Top-10 presets (`Loma_Top01` to `Loma_Top10`)

These are the ten best all-round setups from both gold calibrations (about 54,000 random setups plus refinement, with indicator periods, trend-filter timeframe and EMA, M10/M15 and the time exits included). **They were chosen with all the data, 2025 and 2026: there is no unseen test behind them.** A ranking on 2025 alone did not predict 2026 (about half of its top ten lost in 2026), so this list keeps only setups that pass 2025, 2025 under stress, 2026 and 2026 under stress.

| # | Chart | Direction | Session | Trend filter | MACD | Max hold | End-of-day | Trades | PF | 2026 PF | Stress PF (2026) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | M10 | both | 07:00-20:00 | H1 EMA 20 | 16/35 | off | 23:00 | 129 | 2.09 | 1.72 | 2.08 (1.97) |
| 2 | M3 | sell | all day | none | 16/35 | 2 h | 22:00 | 143 | 1.98 | 2.07 | 1.81 (2.03) |
| 3 | M2 | sell | 12:00-20:00 | H1 EMA 20 | 12/26 | 4 h | 22:00 | 117 | 2.03 | 1.46 | 1.90 (1.63) |
| 4 | M5 | both | 07:00-12:00 | H1 EMA 50 | 8/17 | 4 h | 23:00 | 124 | 1.82 | 1.40 | 1.76 (1.66) |
| 5 | M10 | buy | all day | M30 EMA 20 | 16/35 | 4 h | 23:00 | 141 | 1.96 | 1.47 | 1.80 (1.38) |
| 6 | M2 | sell | 12:00-20:00 | H4 EMA 50 | 12/26 | off | off | 104 | 1.56 | 1.31 | 1.49 (1.60) |
| 7 | M5 | buy | all day | H1 EMA 50 | 12/26 | off | off | 135 | 2.17 | 1.84 | 1.92 (1.73) |
| 8 | M5 | buy | all day | H4 EMA 50 | 12/26 | off | off | 138 | 1.83 | 1.19 | 1.77 (1.17) |
| 9 | M5 | both | 07:00-20:00 | none | 10/22 | 8 h | 22:00 | 191 | 1.92 | 1.17 | 1.67 (1.12) |
| 10 | M3 | both | 07:00-12:00 | none | 8/17 | off | 21:00 | 140 | 1.65 | 1.11 | 1.50 (1.09) |

- Stress = entry one minute late, pessimistic trailing, 0.10 slippage and commission.
- Six of the ten run **without a trailing stop**, so they do not depend on the trailing behaviour that one-minute bars cannot judge.
- #7 is the same setup as `Loma_Gold_M5_Buy_H1`; #8 is a variant of `Loma_Gold_M5_Buy_H4`. Do not run a top-10 preset together with its twin.
- Several use MACD periods other than 12/26: set your chart's MACD to the preset's values if you want the chart to match what the EA sees.
- Expect roughly PF 1.1-1.4 live. Strategy Tester with real ticks, then demo, before anything else.

## BTCUSD presets (`Loma_BTC01` to `Loma_BTC04`)

The same EA runs on BTCUSD with these four presets. **Do not load them on gold, or the gold presets on BTC:** the distances are BTC-sized (points are 0.01 USD, so 2000 points = 20 USD), `MaxSpread_Points` is 3000 (30 USD) and the weekend close is off.

Backtest: Binance BTCUSDT one-minute data, January 2025 to May 2026, an assumed 10 USD spread. Stress = entry one minute late, pessimistic trailing, 3 USD slippage and 2 USD commission. Figures in brackets are with a 20 USD spread.

| # | Chart | Direction | Session (server time) | Trend filter | Trades | PF | 2026 PF | Stress PF | Stress 2026 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | M3 | both | 07:00-12:00 | M15 EMA 20 | 136 | 2.22 (2.11) | 2.14 (2.12) | 1.85 (1.83) | 1.80 (1.80) |
| 2 | M5 | both | 12:00-16:30 | H4 EMA 50 | 129 | 2.22 (2.20) | 2.80 (3.15) | 1.64 (1.42) | 1.98 (1.49) |
| 3 | M10 | sell | 07:00-20:00 | none | 124 | 2.21 (2.06) | 1.86 (1.64) | 2.08 (1.96) | 1.51 (1.57) |
| 4 | M10 | sell | 07:00-20:00 | M30 EMA 50 | 132 | 1.72 (1.53) | 1.50 (1.36) | 1.49 (1.42) | 1.48 (1.34) |

- **BTC is much weaker evidence than gold.** Across 54,000 random BTC setups, a good 2025 did not predict 2026 (median 2026 PF about 1.0), and only 56% of the 48 refined setups were profitable in 2026. These four are the ones that stay at PF 1.3 or better on every measure, chosen with all the data: four survivors out of 48 is not far from what luck gives.
- #3 and #4 are both M10 sells in the same session and share many trades: run one of them.
- The data is Binance spot; your broker's BTC CFD has its own prices, spread, commission, swaps and weekend behaviour.
- Demo and Strategy Tester (real ticks) only until confirmed there.

## Original five presets

Backtest: FTMO XAUUSD one-minute data, January 2025 to May 2026, real spreads, risk-% sizing. Settings were chosen with 2025 only; 2026 is out of sample. The two v1.31 rules were added after seeing all the data.

| Preset | Chart / trend filter | Session (server time) | Trades | PF | 2025 PF | 2026 PF |
|---|---|---|---|---|---|---|
| `Loma_Gold_M5_Buy_H1.set` | M5 buys / H1 | all day | 135 | 2.17 | 2.27 | 1.84 |
| `Loma_Gold_M5_Buy_H4.set` | M5 buys / H4 | all day | 126 | 2.05 | 2.03 | 2.14 |
| `Loma_Gold_M2_Sell_London_H1.set` | M2 sells / H1 | 07:00-12:00 | 116 | 2.22 | 2.30 | 2.00 |
| `Loma_Gold_M3_Sell_H4.set` | M3 sells / H4 | 07:00-20:00 | 124 | 2.05 | 2.14 | 1.89 |
| `Loma_Gold_M2_Sell_NY_H1.set` | M2 sells / H1 | 12:00-20:00 | 106 | 1.74 | 1.80 | 1.61 |

## Stop, target and trailing units (sweep of 13 November 2026)

Every combination of units was tested on the five presets (393,900 backtests): stop at the hump, in points, in percent of price or in ATR; target at the previous hump, as a multiple of the risk, in points, percent or ATR; trailing off, in multiples of the risk, points, percent or ATR.

- **Stop:** the hump stop is the best unit (median 2026 PF 1.95, against 1.56 for ATR, 1.25 for percent and 1.03 for points).
- **Target:** multiples of the risk and ATR are about equal; the previous-hump target is the weakest.
- **Trailing:** no unit is reliably better. Very tight trailing in points (0.30 behind price) scores PF 4 to 6 on one-minute bars but falls to about 1.2 with slippage and commission: it is an artefact, not an edge.
- **One preset changed:** `Loma_Gold_M5_Buy_H1` now uses a 60-point stop buffer and a target of 6 x risk (was 100 points and 3 x). Under the worst combination its PF is 1.92 (was 1.61). The stress table below still shows its old exits.
- The EA keeps the hump stop and risk-multiple target and trailing: nothing else earned a new input.

## Stress test of v1.31 (13 November 2026)

The backtest engine was audited by three independent reviews: no look-ahead was found (corrupting future data left every earlier signal and trade unchanged in 40 of 40 runs), and a from-scratch re-implementation reproduced two presets trade for trade.

"Worst combination" = entry one minute late + pessimistic trailing + 0.10 slippage + commission.

| Preset | Normal PF (2026) | Slippage 0.10 + commission | Worst combination (2026) | Same at 2x spread | No trailing (2026) | 400 nudged versions: median PF, share profitable in 2026 |
|---|---|---|---|---|---|---|
| M5 Buy H1 | 1.84 (1.49) | 1.76 | 1.61 (1.37) | 1.49 | 1.38 (0.78) | 1.42, 68% |
| M5 Buy H4 | 2.05 (2.14) | 1.96 | 1.49 (2.22) | 1.26 | 1.44 (0.77) | 1.38, 83% |
| M2 Sell London H1 | 2.22 (2.00) | 2.02 | 1.25 (1.65) | 1.14 | 1.30 (1.42) | 1.57, 94% |
| M3 Sell H4 | 2.05 (1.89) | 1.77 | 1.21 (0.88) | 1.06 | 1.43 (1.62) | 1.58, 98% |
| M2 Sell NY H1 | 1.74 (1.61) | 1.69 | 1.42 (1.59) | 1.32 | 1.30 (1.23) | 1.60, 97% |

- **Expect roughly PF 1.1-1.5 live, not the table above.** The presets are the best of a family (setups calibrated the same way but not shipped had a median 2026 PF of 1.05), each has only 30 to 44 trades in 2026, and the v1.31 rules were chosen with all the data in view.
- **The trailing stop still carries much of the edge**, most of all for the buy presets (2026 PF below 1 without it). One-minute bars judge trailing optimistically: real ticks are required.
- **Entry timing matters for the sells:** the worst combination cuts them to PF 1.2-1.4, and M3 Sell H4 loses in 2026 under it (0.88); at triple spread it is at break-even over the whole period.
- **M5 Buy H1 lost its weekend-gap profit** with the weekend close: 2026 PF 2.35 fell to 1.49. What is left is the honest figure.
- **The two buy presets take about 80% the same trades.** Run one, not both.
- **What held:** every preset stays profitable over the whole period under every stress except M3 Sell H4 at triple spread; no losing quarter; the hump filter beats random selection (chance by luck under 2% for each); 98-100% of nudged versions stay profitable over the whole period.
- **One-year risk at the harsher costs:** 95th-percentile drawdown 6.4R to 11.3R per preset; losing streaks up to 9 trades.
- **Not tested:** data before 2025 or after May 2026 (the download source kept dropping connections), swaps.

Use these presets for Strategy Tester (real ticks) and demo testing only until they are confirmed there.

## Read before trading

- **Session hours are broker server time**, calibrated on FTMO (GMT+2 winter, GMT+3 summer). Shift them, and `WeekendCloseTime`, if your broker's clock differs.
- **News filter** is on in the presets but was not in the backtest. Set `UseNewsFilter=false` to match it.
- **Weekend close on holidays:** the backtest also closes before any closure of a day or more; the EA only knows Fridays and weekends.
- **Not built yet:** extending the target to the middle of a liquidity candle.

## What you see on the chart

- **Status panel:** trend state (BEARISH / BULLISH / LINEAL), the big hump's size, signals used, the current hump and the last reason a signal was skipped.
- **Labels** on big humps, **arrows** on signals, and the stop and target lines of the last signal.
