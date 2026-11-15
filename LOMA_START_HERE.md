# Loma EA v1.34: start here

`XAUUSD_Loma_TrendPullback.mq5` trades the "loma" (MACD hump) method in MetaTrader 5, buys and sells, on XAUUSD and (with its own presets) BTCUSD. It is separate from the XLZC Bearish EA.

> **Status: not recommended for live trading.** The presets were fitted to January 2025 – 15 May 2026.
> - **Gold:** on the months after that, which they never saw, the six shipped gold presets together lost money even before commission on VT Markets real ticks: profit factor 0.74 on 247 trades, 1 June – 6 November 2026 (0.67 at VT's $0.60 commission per lot). Dukascopy prices agree.
> - **BTC:** the four presets together broke even: profit factor 1.05 on 193 trades, 16 May – 13 November 2026.
> - **Re-calibration (15 November 2026):** every timeframe from M1 to H1, with eleven kinds of trailing stop, was re-calibrated on the same period and tested on the months after it. No timeframe holds a profit factor of 1.3 on unseen data, on gold (0.72–1.04) or on BTC (0.56–1.20 with at least 100 trades).
> - **The EA itself** reproduces the backtest's trades.

## Downloads

| Zip | Contents |
|---|---|
| `dist/Loma_XAUUSD_v1_34.zip` | The EA, the six gold presets, `GOLD_PRESETS_SUMMARY.csv` and the out-of-sample report `Loma_OOS_Review.html`. Guide: `packages/loma_xauusd/START_HERE.md`. |
| `dist/Loma_BTCUSD_v1_34.zip` | The same EA and the four BTC presets with `BTC_PRESETS_SUMMARY.csv`. Guide: `packages/loma_btcusd/START_HERE.md`. |

The out-of-sample report is also in the repository: `research/reports/loma_oos_review.html`.

## The rules

A **hump** (loma) is a run of bars with the MACD on one side of zero.

1. **Trend first.** A big hump below zero means a bearish trend; a big hump above zero means a bullish trend. "Big" means its peak is at least `BigHumpMultiplier` times the median of the last `BigHumpHistory` humps and it lasts at least `BigHumpMinBars` bars. If `RequireStochLevel` is on, the Stochastic must also reach `StochLow` (bearish) or `StochHigh` (bullish) during it: 20/80 by default, 25/75 in Top04, 15/85 in BTC04. Top01, Top02, Top03 and Top05 do not require it. With no big hump in force the market is **lineal** and the EA does not trade.
2. **Trend break.** An opposite hump as large as `TrendBreakRatio` times the big hump ends the trend.
3. **Sell signal** (bearish trend): a pullback hump above zero that lasts at least `PullbackMinBars` bars and is no larger than `PullbackMaxRatio` times the big hump, then the first bar with the MACD back below zero. Top01, Top04 and Top07 use `PullbackMinBars=1`, so a single bar across zero counts as a pullback.
4. **Stop loss:** above the highest high of the pullback hump (including the signal bar), plus `SL_Buffer_Points` and the spread. No hump, no stop, no trade.
5. **Take profit:** every shipped preset uses a fixed multiple of the risk (`TP_Mode=TP_FIXED_RR`, `TP_RR`). The other mode, `TP_PREV_HUMP`, aims at the previous hump's extreme, taken a little early (`TP_Anticipation`).
6. **Weak signals are skipped:** only the first `MaxSignalsPerBigHump` signals after a big hump are traded, and the trend lapses after `TrendMaxBars` bars without a new big hump.
7. **Buys** are the exact mirror.
8. **Trend filter** (`UseHTFFilter`): sell only if the last closed `HTF_Timeframe` bar closed below its EMA(`HTF_EMA_Period`), buy only if above. Each preset sets its own timeframe and period; Top02 and BTC03 use no filter.

## Install

1. In MT5 choose **File > Open Data Folder**.
2. Copy the zip's `MQL5` folder over the data folder's `MQL5` folder.
3. In MetaEditor compile `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5`. It needs `MQL5/Include/EVK/EVK.mqh`, which is in the zip.
4. Attach the EA to an XAUUSD or BTCUSD chart (any timeframe: it reads its own). In **Inputs** click **Load** and pick a preset for that symbol.
5. Enable **Algo Trading**.

v1.33 compiled in MetaEditor (MT5 build 6302) with 0 errors and 0 warnings. v1.34 was checked line by line by independent reviews but has not been compiled here (no MetaEditor available). If the compiler reports anything, send the log rather than editing the file.

## What changed in v1.34

- **Trailing stop:** after a failed stop change (for example while the market is closed at the daily open) it pauses for 5 seconds instead of retrying on every tick, and it does not try while Algo Trading is off. Each new failure reason is printed once.
- **Trailing after a restart:** the original risk (1R) is read from the opening deal, so a crash, an account switch or a move to another terminal no longer shrinks the trailing distance.
- **Netting accounts:** a warning at start, and no entry while any other position on the symbol is open.
- **Weekend close:** a Friday close that was missed (EA or Algo Trading off, broker closed early) is made up on the next tick, on any day.
- **`MaxHoldMinutes`:** no early close when the one-minute history is not loaded yet.
- **New input `CommissionPerLot`** (0 = off): your round-trip commission per lot is counted in the risk, so a stop-out costs `RiskPercent` including commission.
- **Lot size:** `MaxLotSize` is rounded to the volume step. With `SkipIfBelowMinLot=false`, the minimum lot is refused when it would risk more than twice `RiskPercent`. Margin cuts are logged.
- **Slippage setting** is rounded up, so BTC quotes with 0 or 1 digits no longer turn it into 0.
- **Checks and messages:** `HTF_Timeframe=MN1` is rejected; a data stall prints a warning every 5 bars; gold presets on BTC (or the reverse) print a warning.
- **Chart:** the previous-hump line is drawn only when it is the target (`TP_PREV_HUMP`).
- **BTC presets:** `MaxSlippage_Points=1000` ($10) and `TrailStep_Points=200` ($2), instead of the gold-sized $0.20 and $0.10.

**v1.33:** Strategy Tester fix. The EA requests an indicator value before checking that the indicator is ready; in the non-visual tester v1.32 never traded.

**v1.32:** `MaxHoldMinutes` (market minutes) and `CloseAtEndOfDay` / `EndOfDayTime`. **v1.31:** `SkipBigPullback` and the Friday close (`CloseBeforeWeekend`, `WeekendCloseTime`).

## Shipped presets and their out-of-sample results

**Gold** (`dist/Loma_XAUUSD_v1_34.zip`). Backtest: FTMO one-minute data, January 2025 – 15 May 2026. Out of sample: 1 June – 6 November 2026.

| Preset | Chart | Direction | Session (server time) | Trend filter | Backtest trades / PF | VT trades, Jun – Nov 6 | VT PF before commission / at $0.60 per lot | Dukascopy PF |
|---|---|---|---|---|---|---|---|---|
| `Loma_Top01` | M10 | both | 07:00-20:00 | H1 EMA 20 | 129 / 2.09 | 32 | 0.46 / 0.43 | 0.69 |
| `Loma_Top02` | M3 | sell | all day | none | 143 / 1.98 | 48 | 1.04 / 0.91 | 0.77 |
| `Loma_Top03` | M2 | sell | 12:00-20:00 | H1 EMA 20 | 117 / 2.03 | 44 | 0.77 / 0.69 | 0.83 |
| `Loma_Top04` | M5 | both | 07:00-12:00 | H1 EMA 50 | 124 / 1.82 | 42 | 0.58 / 0.51 | 0.45 |
| `Loma_Top05` | M10 | buy | all day | M30 EMA 20 | 141 / 1.96 | 49 | 0.87 / 0.81 | 0.84 |
| `Loma_Top07` | M5 | buy | all day | H1 EMA 50 | 135 / 2.17 | 32 | 0.72 / 0.64 | 0.62 |

**BTC** (`dist/Loma_BTCUSD_v1_34.zip`). Binance BTCUSDT one-minute data with an assumed $10 spread. Backtest: January 2025 – 15 May 2026. Out of sample: 16 May – 13 November 2026. Stress = entry one minute late, pessimistic trailing, $3 slippage and $2 commission.

| Preset | Chart | Direction | Session (server time) | Trend filter | Backtest trades / PF | Out of sample: trades, PF, net | Stress PF | PF at $20 spread |
|---|---|---|---|---|---|---|---|---|
| `Loma_BTC01` | M3 | both | 07:00-12:00 | M15 EMA 20 | 136 / 2.22 | 56, 0.86, −4.9R | 0.79 | 0.78 |
| `Loma_BTC02` | M5 | both | 12:00-16:30 | H4 EMA 50 | 129 / 2.22 | 41, 1.79, +7.9R | 1.04 | 1.61 |
| `Loma_BTC03` | M10 | sell | 07:00-20:00 | none | 124 / 2.21 | 51, 1.24, +4.9R | 1.19 | 1.22 |
| `Loma_BTC04` | M10 | sell | 07:00-20:00 | M30 EMA 50 | 132 / 1.72 | 45, 0.90, −3.0R | 0.82 | 0.90 |

## Read before trading

- **Broker server time:** sessions, `WeekendCloseTime` and `EndOfDayTime` are calibrated on a GMT+2 (winter) / GMT+3 (summer) clock. VT Markets matches. Shift all three if your broker's clock differs.
- **Commission:** the VT Strategy Tester run charged $6 per lot round trip (1 lot = 1 ounce), ten times VT's real $0.60 per lot (as reported by the account owner). At $0.60 the run's loss shrinks from $8,914 to $1,664, but the unseen months still lose (PF 0.67). On the calibration data the presets score PF 1.60–1.92 at $0.60 and 0.53–0.97 at $6. On VT set `CommissionPerLot=0.6` (1.2 if the $0.60 is per side).
- **Account size:** lots are rounded down to the broker's step, and with `SkipIfBelowMinLot=true` a trade whose lot would be below the minimum is skipped. With a 100-ounce gold contract (minimum 0.01 lot) and `RiskPercent=0.5`, use about $10,000 or more; on smaller balances the wide-stop trades are skipped.
- **Several presets on one account** only on a **hedging** account. On a netting account every EA and manual trade on a symbol shares one position.
- **News filter** (`UseNewsFilter`, on in the presets) was not in the backtest. It does nothing in the Strategy Tester, so tester results equal `UseNewsFilter=false`. Live, the presets skip entries within 30 minutes of high-impact USD news.
- **Holidays:** the backtest closes before any closure of a day or more; the EA knows only Friday closes. A Friday close missed because the market closed early is made up on the next tick.

## What you see on the chart

- **Status panel:** trend state (BEARISH / BULLISH / LINEAL), the big hump's size, signals used, the current hump, the session and the last reason a signal was skipped.
- **Labels** on big humps and **arrows** on signals.
- **Dashed red line:** the pullback hump's extreme (the stop reference). **Dashed blue line:** the previous hump's extreme, only when it is the target (`TP_PREV_HUMP`). **Dotted lines:** the stop and target of the trade that was opened.

## History: in-sample calibration (January 2025 – May 2026)

The sections below describe how the presets were found. Their figures are in-sample and are superseded by the out-of-sample results above.

### Top-10 presets (`Loma_Top01` to `Loma_Top10`)

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
- Superseded: out of sample (June – 6 November 2026) the six tested presets lost. See the table at the top.

### BTCUSD presets (`Loma_BTC01` to `Loma_BTC04`)

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

### Original five presets

Backtest: FTMO XAUUSD one-minute data, January 2025 to May 2026, real spreads, risk-% sizing. Settings were chosen with 2025 only; 2026 is out of sample. The two v1.31 rules were added after seeing all the data.

| Preset | Chart / trend filter | Session (server time) | Trades | PF | 2025 PF | 2026 PF |
|---|---|---|---|---|---|---|
| `Loma_Gold_M5_Buy_H1.set` | M5 buys / H1 | all day | 135 | 2.17 | 2.27 | 1.84 |
| `Loma_Gold_M5_Buy_H4.set` | M5 buys / H4 | all day | 126 | 2.05 | 2.03 | 2.14 |
| `Loma_Gold_M2_Sell_London_H1.set` | M2 sells / H1 | 07:00-12:00 | 116 | 2.22 | 2.30 | 2.00 |
| `Loma_Gold_M3_Sell_H4.set` | M3 sells / H4 | 07:00-20:00 | 124 | 2.05 | 2.14 | 1.89 |
| `Loma_Gold_M2_Sell_NY_H1.set` | M2 sells / H1 | 12:00-20:00 | 106 | 1.74 | 1.80 | 1.61 |

### Stop, target and trailing units (sweep of 13 November 2026)

Every combination of units was tested on the five presets (393,900 backtests): stop at the hump, in points, in percent of price or in ATR; target at the previous hump, as a multiple of the risk, in points, percent or ATR; trailing off, in multiples of the risk, points, percent or ATR.

- **Stop:** the hump stop is the best unit (median 2026 PF 1.95, against 1.56 for ATR, 1.25 for percent and 1.03 for points).
- **Target:** multiples of the risk and ATR are about equal; the previous-hump target is the weakest.
- **Trailing:** no unit is reliably better. Very tight trailing in points (0.30 behind price) scores PF 4 to 6 on one-minute bars but falls to about 1.2 with slippage and commission: it is an artefact, not an edge.
- **One preset changed:** `Loma_Gold_M5_Buy_H1` now uses a 60-point stop buffer and a target of 6 x risk (was 100 points and 3 x). Under the worst combination its PF is 1.92 (was 1.61). The stress table below still shows its old exits.
- The EA keeps the hump stop and risk-multiple target and trailing: nothing else earned a new input.

### Stress test of v1.31 (13 November 2026)

The backtest engine was audited by three independent reviews: no look-ahead was found (corrupting future data left every earlier signal and trade unchanged in 40 of 40 runs), and a from-scratch re-implementation reproduced two presets trade for trade.

"Worst combination" = entry one minute late + pessimistic trailing + 0.10 slippage + commission.

| Preset | Normal PF (2026) | Slippage 0.10 + commission | Worst combination (2026) | Same at 2x spread | No trailing (2026) | 400 nudged versions: median PF, share profitable in 2026 |
|---|---|---|---|---|---|---|
| M5 Buy H1 | 1.84 (1.49) | 1.76 | 1.61 (1.37) | 1.49 | 1.38 (0.78) | 1.42, 68% |
| M5 Buy H4 | 2.05 (2.14) | 1.96 | 1.49 (2.22) | 1.26 | 1.44 (0.77) | 1.38, 83% |
| M2 Sell London H1 | 2.22 (2.00) | 2.02 | 1.25 (1.65) | 1.14 | 1.30 (1.42) | 1.57, 94% |
| M3 Sell H4 | 2.05 (1.89) | 1.77 | 1.21 (0.88) | 1.06 | 1.43 (1.62) | 1.58, 98% |
| M2 Sell NY H1 | 1.74 (1.61) | 1.69 | 1.42 (1.59) | 1.32 | 1.30 (1.23) | 1.60, 97% |

- **Superseded by the out-of-sample test at the top of this guide.** The presets are the best of a family (setups calibrated the same way but not shipped had a median 2026 PF of 1.05), each has only 30 to 44 trades in 2026, and the v1.31 rules were chosen with all the data in view.
- **The trailing stop still carries much of the edge**, most of all for the buy presets (2026 PF below 1 without it). One-minute bars judge trailing optimistically: real ticks are required.
- **Entry timing matters for the sells:** the worst combination cuts them to PF 1.2-1.4, and M3 Sell H4 loses in 2026 under it (0.88); at triple spread it is at break-even over the whole period.
- **M5 Buy H1 lost its weekend-gap profit** with the weekend close: 2026 PF 2.35 fell to 1.49. What is left is the honest figure.
- **The two buy presets take about 80% the same trades.** Run one, not both.
- **What held:** every preset stays profitable over the whole period under every stress except M3 Sell H4 at triple spread; no losing quarter; the hump filter beats random selection (chance by luck under 2% for each); 98-100% of nudged versions stay profitable over the whole period.
- **One-year risk at the harsher costs:** 95th-percentile drawdown 6.4R to 11.3R per preset; losing streaks up to 9 trades.
- **Not tested here:** data before 2025 and swaps. Data after May 2026 was tested later; see the top of this guide.

Use these presets for Strategy Tester (real ticks) and demo testing only until they are confirmed there.

