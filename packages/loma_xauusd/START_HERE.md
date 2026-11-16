# Loma EA v1.35 for XAUUSD: start here

`XAUUSD_Loma_TrendPullback.mq5` trades the "loma" (MACD hump) method on gold in MetaTrader 5, buys and sells. This zip holds the EA, the six gold presets of the first calibration and the trailing presets of the re-calibration.

> **Do not trade these presets with real money.**
> - **Year-by-year test: no gold result passed.** Set up on three years and traded on the next, 2016 to 2025, with 58 entry conditions tried one at a time at VT Markets' costs: none of the 472 timeframe-and-condition cells held a profit factor of 1.3 over at least two years with 50 trades without a losing year (the best by profit factor of the cells with at least 100 unseen trades, H1 MACD of both higher timeframes on the trade's side, made 1.53 on 165 trades with no losing year in 2016 – 2025, but only one of its years had 50 trades, and it made 0.36 on 43 trades in the 2026 months kept back).
> - **The six `Loma_Top` presets** lost on the months after their calibration: on VT Markets real ticks (1 June – 6 November 2026) profit factor 0.74 before commission and 0.67 at VT's $0.60 per lot, on 247 trades. Dukascopy prices agree.
> - **The `Loma_T15_Gold_*` trailing presets** come from four combinations of timeframe and trailing system whose setups together reached a profit factor of 1.3 on the 2026 months at FTMO's spread without commission. At VT's costs 2 of the 4 stay at 1.3 or more (M5 hump structure 1.31 and M10 ATR at entry 1.61) and M5 chandelier (1.23) and M10 percent of price (1.24) fall under it; 7 of the 16 presets were under 1.3 on their own, and the four groups lost on July – December 2024. Unproven: Strategy Tester and demo only.
> - The EA follows the backtest: in the VT run in MT5 (v1.33) the Dukascopy backtest found 240 of its 247 trades, and v1.35 took the backtest's trades in a simulated terminal (about 97% of them when the spread changes by the hour). v1.35 has not been compiled or run in MetaTrader yet.

## The year-by-year test on gold

Dukascopy gold one-minute prices from 2013 to 2024, FTMO for 2025 to 15 May 2026 and Dukascopy after, all in broker server time (the daily reopen at 01:00 server time checked year by year). For every year from 2016 to 2025, 12,000 setups per timeframe (M1 to H1) were scored on the three years before it, with each of 58 entry conditions added one at a time (market regime, location, confirmation, timing, the XLZC rules, and three random halves of the signals as controls) and the method without one, and the best of them, up to 10 (one per direction, session and trend-filter family, each with a profit factor of at least 1.3 in all three years at normal and stressed costs and an average cost under 1/8 of the risk), were traded on that year unchanged. Costs are VT Markets' own: a 1.5-pip spread shaped by the hour and $0.60 commission per ounce, scaled with the price like every dollar distance of a setup. A cell passes with a profit factor of 1.3 or more over its unseen years together, 1.1 or more stressed, at least two years with 50 trades and no such year below 1.0.

**Nothing passed.** The method without an extra condition, by timeframe:

| Timeframe | Unseen 2016 – 2025: PF (trades) | Stressed | Unseen years with 50+ trades below 1.0 |
|---|---|---|---|
| M1 | no setup held PF 1.3 in three years running at normal and stressed costs | – | – |
| M2 | no setup held PF 1.3 in three years running at normal and stressed costs | – | – |
| M3 | no setup held PF 1.3 in three years running at normal and stressed costs | – | – |
| M5 | 0.92 (248) | 0.88 | 2016, 2017 |
| M10 | 0.65 (286) | 0.55 | 2017, 2022, 2023 |
| M15 | 0.71 (134) | 0.63 | 2017 |
| M30 | 0.89 (703) | 0.83 | 2016, 2019, 2021, 2023, 2025 |
| H1 | 1.08 (1146) | 1.00 | 2016, 2018, 2019, 2024, 2025 |

The best cells with at least 100 unseen trades: H1 MACD of both higher timeframes on the trade's side: 1.53 on 165 trades (fewer than two years with 50 trades); H1 MACD two timeframes up on the trade's side: 1.47 on 271 trades (losing 2024); M3 signal candle range at least 1 ATR: 1.44 on 133 trades (fewer than two years with 50 trades); H1 beyond the 01:00-09:00 range in the trade's direction: 1.39 on 170 trades (losing 2024); H1 with the daily trend: 1.29 on 600 trades (under 1.3; losing 2018). The year-by-year tables are in `Loma_OOS_Review.html`, section 6.

## The trailing presets `Loma_T15_Gold_*` (unproven)

These are the 4 combinations of timeframe and trailing system whose setups together reached a profit factor of 1.3 on at least 100 unseen trades in 16 May – 13 November 2026, out of 23 trailing systems tested on every timeframe (16 presets: every setup behind each combination). The backtest's costs were FTMO's spread by hour and no commission (stressed: one minute late, pessimistic trailing, $0.10 slippage and $0.07 commission per ounce). **At VT Markets' costs** (1.5-pip spread and $0.60 per ounce) on the same months, 2 of the 4 stay at 1.3 or more (M5 hump structure 1.31, M10 ATR at entry 1.61) and M5 chandelier (1.23) and M10 percent of price (1.24) fall under it. The setups were chosen on January 2025 – 15 May 2026 only. Then each combination was run on July – December 2024, before the calibration data: **none reached 1.3 there**; all four lost. With 23 systems on 8 timeframes, some combinations reach 1.3 on one period by chance. On their own, 7 of the 16 presets were under 1.3 in the 2026 months.

| Combination | Trailing (TrailMode) | Presets | Unseen 2026, backtest costs: PF (trades) | Stressed | Unseen 2026 at VT's costs: PF (trades) | VT stressed | Jul – Dec 2024: PF (trades) | Presets under 1.3 on their own in 2026 |
|---|---|---|---|---|---|---|---|---|
| M5 | hump structure (13) | 4 | 1.41 (141) | 1.12 | 1.31 (141) | 1.12 | 0.75 (116) | 2 of 4 |
| M5 | chandelier (5) | 4 | 1.31 (157) | 1.21 | 1.23 (157) | 1.14 | 0.80 (110) | 2 of 4 |
| M10 | percent of price (2) | 4 | 1.31 (181) | 1.25 | 1.24 (181) | 1.16 | 0.74 (137) | 2 of 4 |
| M10 | ATR at entry (1) | 4 | 1.57 (206) | 1.45 | 1.61 (206) | 1.39 | 0.70 (154) | 1 of 4 |

- Every preset's header gives its own figures for the calibration period, the 2026 months (also at VT's costs) and July – December 2024; `GOLD_TRAILING15_SUMMARY.csv` lists them all.
- The test is of each combination's setups together, not of the best of them by their 2026 result.
- They need v1.35 (`TrailMode`, `TrailParam`). Strategy Tester and demo only.

## What is in the zip

| File | What it is |
|---|---|
| `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` | The EA, v1.35 (the same file runs on gold and on BTCUSD). |
| `MQL5/Include/EVK/EVK.mqh` | Records trades in the Strategy Tester only (EA Validation Kit). The EA needs it to compile. |
| `MQL5/Presets/Loma_Top01 … Top07 *.set` | The six gold presets of the first calibration (table below). |
| `MQL5/Presets/Loma_T15_Gold_*.set` | The trailing presets (unproven). |
| `GOLD_PRESETS_SUMMARY.csv` | Backtest and out-of-sample figures of the six Top presets. |
| `GOLD_TRAILING15_SUMMARY.csv` | Every trailing preset with its figures. |
| `Loma_OOS_Review.html` | The out-of-sample report: VT Markets run, Dukascopy cross-check, walk-forward, re-calibration (section 5) and the year-by-year test (section 6). Open it in a browser. |

## Install

1. In MT5 choose **File > Open Data Folder**.
2. Copy the zip's `MQL5` folder over the data folder's `MQL5` folder. This adds files and replaces nothing else.
3. In MetaEditor open `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` and press **F7** (compile).
4. Attach the EA to an XAUUSD chart (any timeframe: it reads its own). In **Inputs** click **Load** and pick a preset (`Loma_T15` presets need this v1.35).
5. Enable **Algo Trading**.

v1.33 was compiled in MetaEditor (MT5 build 6302) with 0 errors and 0 warnings. v1.34 and v1.35 (the file in this zip) were checked line by line and run through a compile harness and a simulated terminal, but have not been compiled in MetaEditor yet. If the compiler reports anything, send me the log rather than editing the file.

## New in v1.35

- **`TrailMode`** chooses the trailing system. `TrailStartR` and `TrailDistanceR` are read in its units (R, ATR multiples, percent of the entry price or the share of profit kept, as the comments of the `TrailMode` choices say; their own input labels still say R), and the new **`TrailParam`** is the period, number of bars, candle minutes or variant of the level systems. 0 = the EA's own (multiples of the risk, as before), 1 = ATR at entry, 2 = percent of price, 3 = profit lock, 4 = stepped, 5 = chandelier, 6 = candle lows / highs, 7 = EMA, 8 = SMA, 9 = Parabolic SAR, 10 = Bollinger band, 11 = higher-timeframe candle, 12 = swing pivots, 13 = hump structure. Every system except 0 and 4 moves the stop once per closed one-minute bar, as the backtest does; the stop only ever moves closer.
- **`UseStochTurnFilter`** (with `StochTurnBars`, `StochTurnHigh`, `StochTurnLow`): enter only when the Stochastic (7, 1, 7) of the trigger timeframe came from 80 (sells) or 20 (buys) within the last 5 bars and turned.
- **`ScaleWithPrice`** with **`ReferencePrice`**: the stop buffer, minimum and maximum stop follow the price, relative to the price they were calibrated at (the spread, slippage and trailing-step limits do not).
- With these inputs at their defaults v1.35 trades like v1.34, with two differences: a spread exactly equal to `MaxSpread_Points` is now always accepted, as in the backtest (v1.34 refused it about half the time, by floating-point rounding), and after a restart in the middle of a trigger bar the EA does not decide that bar's signal a second time (v1.34 could enter it twice). The earlier presets work unchanged.
- v1.35 was checked in a C++ compile harness (the same diagnostics as v1.34) and in a simulated terminal that replays real one-minute prices, where it took the same trades as the Python backtest on the shipped setups. Independent reviews found defects in the first version, mostly in rare cases (the spread test above, the order of a history check, the entry minute of the stepped trailing, restarts of the EA in the middle of a bar); all were fixed and checked again in the simulated terminal. It has not been compiled in MetaEditor: if the compiler reports anything, send me the log rather than editing the file.

## The six Top presets (lost out of sample)

Backtest: FTMO one-minute data, January 2025 – 15 May 2026, the period the presets were chosen on. Out of sample: 1 June – 6 November 2026, never used for calibration. "PF" is the profit factor.

| Preset | Chart | Direction | Session (server time) | Trend filter | Backtest trades / PF | 2026 PF (in sample) | VT trades, Jun – Nov 6 | VT PF before commission / at $0.60 per lot | Dukascopy PF |
|---|---|---|---|---|---|---|---|---|---|
| `Loma_Top01` | M10 | both | 07:00-20:00 | H1 EMA 20 | 129 / 2.09 | 1.72 | 32 | 0.46 / 0.43 | 0.70 |
| `Loma_Top02` | M3 | sell | all day | none | 143 / 1.98 | 2.07 | 48 | 1.04 / 0.91 | 0.81 |
| `Loma_Top03` | M2 | sell | 12:00-20:00 | H1 EMA 20 | 117 / 2.03 | 1.46 | 44 | 0.77 / 0.69 | 0.83 |
| `Loma_Top04` | M5 | both | 07:00-12:00 | H1 EMA 50 | 124 / 1.82 | 1.40 | 42 | 0.58 / 0.51 | 0.46 |
| `Loma_Top05` | M10 | buy | all day | M30 EMA 20 | 141 / 1.96 | 1.47 | 49 | 0.87 / 0.81 | 0.84 |
| `Loma_Top07` | M5 | buy | all day | H1 EMA 50 | 135 / 2.17 | 1.84 | 32 | 0.72 / 0.64 | 0.67 |

- The VT Markets figures come from Codex's MT5 run with 100% real ticks. That run charged $6 per lot round trip; VT's real commission is $0.60 per lot, as you reported it, and the table uses the real rate. If the $0.60 is per side, the figures are a little lower.
- Dukascopy is a third price source, separate from FTMO (calibration) and VT. It found 240 of the 247 VT trades. The tester run ends at 00:00 on 6 November, so the last trading day in both columns is 5 November.
- A walk-forward test (recalibrating every few months on recent data) did not rescue the method: only one of five schedules passed, and only on four windows that include the 2025–26 gold rally.
- **Re-calibration per timeframe (15 November 2026):** every timeframe from M1 to H1 was re-calibrated on January 2025 – 15 May 2026, once with the EA's own trailing stop and once with 23 trailing systems (69,000 setups per timeframe), and the best setups of each, up to 10 and only with an in-sample score of 1.3 or more (none qualified on M1 and H1), were run on 16 May – 13 November 2026. No gold timeframe holds a profit factor of 1.3 there: on the six timeframes with setups the range is 0.67 to 1.08 (0.61 to 1.01 at VT's costs), and M5 is the best in both runs (1.08 with the EA's own trailing, 0.98 with the 23 systems). Four single combinations of timeframe and trailing system reached 1.3 on the unseen months at the backtest's costs, FTMO's spread without commission (M5 hump-structure, M5 chandelier, M10 percent and M10 ATR-at-entry); at VT's costs they score 1.31, 1.23, 1.24 and 1.61, and on July – December 2024, before the calibration data, 0.75, 0.80, 0.74 and 0.70. The tables are in `Loma_OOS_Review.html`, section 5.

## If you still want to test it

- **Strategy Tester:** model "Every tick based on real ticks", your broker's XAUUSD, deposit currency equal to your account's (USC for a cent account). In the tester, the Load dialog of the Inputs tab usually opens in `MQL5\Profiles\Tester`; browse to `MQL5\Presets` for these files. Test January 2025 – May 2026 and June 2026 – today **separately**, and compare profit before commission, commission and swap.
- **Demo only.** Top02 and Top05 were the least bad out of sample. Expect break-even minus costs at best.
- **Server time:** session, weekend and end-of-day times are broker server time, calibrated on a GMT+2 (winter) / GMT+3 (summer) clock. VT Markets matches. Shift them if your broker's clock differs.
- **VT Markets costs:** a 1.5-pip spread ($0.15 per ounce) and $0.60 commission per lot (1 lot = 1 ounce), as you reported them: about $0.75 per ounce for a round trip. The Strategy Tester run used VT's real spread but charged $6 per lot, ten times the real commission. At $0.60 the whole run's loss shrinks from $8,914 to $1,664, but the unseen months still lose (PF 0.67). On the calibration data the presets score PF 1.60–1.92 at $0.60 and 0.53–0.97 at $6. On VT set `CommissionPerLot` to the round-trip commission per lot in your account's currency: 0.6 on a USD account, 60 on a USC cent account (double it if the $0.60 is per side), so a stop-out costs `RiskPercent` including commission. In the Strategy Tester, set the commission to match.
- **Account size:** the EA skips a trade when the lot for `RiskPercent` falls below the symbol's minimum lot. On VT's XAUUSD-ECNc one lot is 1 ounce, so that limit is rarely reached (the VT test, on $10,000, traded 0.66 to 16 lots). On a broker with a 100-ounce contract (minimum 0.01 lot = 1 ounce) and `RiskPercent=0.5`, use about $10,000 or more.
- **One account, several presets:** only on a **hedging** account. On a netting account all presets on one symbol share a single position, so one preset's trade changes another's. The EA warns on a netting account and sends no entry while another position on the symbol is open.
- **News filter** (`UseNewsFilter`) is on in the presets but was not in the backtest. It does nothing in the Strategy Tester, so tester results equal `UseNewsFilter=false`.

### Asking Codex to compile without changing anything

```
Compile one MQL5 Expert Advisor with MetaEditor and report the result. This is a compile-only task.
Rules:
- Do NOT edit, reformat, rename or "fix" any .mq5 or .mqh file. Do not create new source files.
- If the compile fails, do NOT try to fix it. Stop and show me the full log.
Steps:
1. Find the MT5 data folder (File > Open Data Folder). Call it <DATA>.
2. Record the SHA-256 hash of <DATA>\MQL5\Experts\XAUUSD_Loma_TrendPullback.mq5 and
   <DATA>\MQL5\Include\EVK\EVK.mqh (Get-FileHash "<path>" -Algorithm SHA256).
3. Compile: "<MT5 folder>\metaeditor64.exe" /compile:"<DATA>\MQL5\Experts\XAUUSD_Loma_TrendPullback.mq5" /include:"<DATA>\MQL5" /log
4. Show me the full XAUUSD_Loma_TrendPullback.log, the number of errors and warnings, and
   whether XAUUSD_Loma_TrendPullback.ex5 was created.
5. Hash both files again and confirm they are unchanged.
```

## The rules in short

1. **Trend first:** a big MACD hump below zero (bearish) or above zero (bullish). "Big" = peak at least `BigHumpMultiplier` times the median of the last `BigHumpHistory` humps and at least `BigHumpMinBars` bars. With `RequireStochLevel` on (Top04 at 25/75 and Top07 at 20/80; among the `Loma_T15_Gold` presets Chandelier 2of4, Percent 2of4 at 20/80; Hump 2of4, Hump 3of4, Chandelier 4of4, ATRentry 1of4, ATRentry 2of4 at 25/75) the Stochastic must also reach `StochLow` / `StochHigh`; the other presets do not require it. No big hump in force = lineal market = no trades.
2. **Trend break:** an opposite hump as large as `TrendBreakRatio` times the big hump.
3. **Signal:** a pullback hump of at least `PullbackMinBars` bars (1 in Top01, Top04, Top07 and the `Loma_T15_Gold` presets Hump 1of4, Percent 1of4, so one bar across zero counts) and at most `PullbackMaxRatio` times the big hump, then the first bar with the MACD back across zero. Only `MaxSignalsPerBigHump` signals per big hump, and none after `TrendMaxBars` bars.
4. **Stop:** beyond the pullback hump's extreme, plus `SL_Buffer_Points` and (for sells) the spread. **Target:** `TP_RR` times the risk in every preset.
5. **Filters and exits:** higher-timeframe EMA filter, trading hours, spread limit, trailing in multiples of the risk (Top presets) or the system set in `TrailMode` (ATR at entry, percent, chandelier or hump structure in the `Loma_T15_Gold` presets), maximum holding time, end-of-day close and Friday close, as set in each preset.

## What changed

**v1.35** (this zip)
- The trailing systems, the Stochastic turn filter and the price scaling of "New in v1.35" above.

**v1.34**
- **Trailing stop:** after a failed stop change (the MT5 test logged 295, all while the market was closed at the daily open) it pauses for 5 seconds instead of retrying on every tick, and it does not try while Algo Trading is off. Its original risk (1R) is read from the opening deal, so a crash or a move to another terminal no longer shrinks the trailing distance.
- **Weekend close:** a Friday close that was missed (EA or Algo Trading off, market closed early) is made up on the next tick.
- **Netting accounts:** a warning, and no entry while another position on the symbol is open.
- **`MaxHoldMinutes`:** no early close when the one-minute history is not loaded yet.
- **New input `CommissionPerLot`** (0 = off), counted in the risk. `MaxLotSize` is rounded to the volume step; margin cuts are logged.
- **Checks:** `HTF_Timeframe=MN1` is rejected, a data stall prints a warning every 5 bars, and a BTC preset loaded on gold prints a warning.
- **Chart:** the previous-hump line is drawn only when it is the target, which is never the case in these presets.

**v1.33**
- Strategy Tester fix: the EA now asks for an indicator value before checking that the indicator is ready. In the non-visual tester, v1.32 never traded.

**v1.31 and v1.32** added `SkipBigPullback`, the Friday close (`CloseBeforeWeekend`), `MaxHoldMinutes` and the end-of-day close (`CloseAtEndOfDay`).

## What you see on the chart

- **Status panel:** trend state (BEARISH / BULLISH / LINEAL), the big hump's size, signals used, the current hump, the session and the last reason a signal was skipped.
- **Labels** on big humps and **arrows** on signals. **Dashed red line:** the pullback hump's extreme (the stop reference). **Dotted lines:** the stop and target of the trade that was opened.
