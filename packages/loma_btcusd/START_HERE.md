# Loma EA v1.35 for BTCUSD: start here

`XAUUSD_Loma_TrendPullback.mq5` trades the "loma" (MACD hump) method in MetaTrader 5, buys and sells. The file name says XAUUSD, but the same EA runs on BTCUSD with these presets. **Do not load them on gold, or the gold presets on BTC.**

> **This zip holds three groups of presets, in order of evidence.**
> 1. **`Loma_WF_BTC_M30_01` to `10`: the one result that passed the year-by-year test.** The method was set up on three years, traded on the next year without changes, and rolled forward. On M30 with one entry rule added (the Stochastic came from 80 / 20 and turned) it scored profit factor 1.22 in 2023, 1.39 in 2024, 1.87 in 2025. The 2026 months, kept back and checked once at the end, gave 1.26 on 267 trades. All four unseen years together: 1.46 on 753 trades (1.41 with stressed costs). These 10 presets are the setups picked by the same rule on 2024 – 13 November 2026, for the year ahead. Demo first.
> 2. **`Loma_BTC_M5_R01` to `R04`: unproven.** They passed the 2026 months (1.42) and lost on 2024 and 2023.
> 3. **`Loma_T15_BTC_*`: unproven.** The trailing-stop combinations that reached a profit factor of 1.3 on the 2026 months. None reached 1.3 on 2024 or 2023. Strategy Tester and demo only.

## The year-by-year result: presets `Loma_WF_BTC_M30_*`

**How it was tested.** Binance BTCUSDT one-minute prices from 2018 to 13 November 2026, in broker server time. For every year from 2021 to 2025, 12,000 setups per timeframe (M1 to H1) were scored on the three years before it, with each of 59 entry conditions added one at a time. The 10 best (one per direction, session and trend-filter family, each with a profit factor of at least 1.3 in all three years at normal and stressed costs, and costs under 1/8 of the risk) were then traded on that year unchanged. A timeframe-and-condition cell passes with a profit factor of 1.3 or more over its unseen years together, 1.1 or more with stressed costs, at least two years with 50 trades and no such year below 1.0. The 2026 months were not used to decide anything: they were run once at the end. Costs: a $10 spread, scaled with the price like every dollar distance of a setup, so a setup means the same in 2021 as today; stressed = one minute late, pessimistic trailing, $3 slippage and $2 commission per BTC, also scaled.

**What passed.** Of 472 cells, 2 passed, both on M30 with the Stochastic turn rule: the rule alone (these presets) and the rule with a liquidity sweep added (that one scored 1.09 on the 2026 months, so it is not shipped). None of the 24 random-half controls passed. The method without an extra condition passed on no timeframe (M30: 0.96 on 793 trades).

| Unseen year | Setups traded | Trades | Profit factor | Stressed |
|---|---|---|---|---|
| 2021 | none passed the three years before | – | – | – |
| 2022 | none passed the three years before | – | – | – |
| 2023 | 2 | 65 | 1.22 | 1.24 |
| 2024 | 5 | 170 | 1.39 | 1.36 |
| 2025 | 7 | 251 | 1.87 | 1.75 |
| **2021 – 2025 together** | | **486** | **1.60** | **1.54** |
| 2026 (to 13 Nov), checked once at the end | 10 | 267 | 1.26 | 1.24 |
| **All unseen years together** | | **753** | **1.46** | **1.41** |

- **The 2026 check is profitable but under 1.3 on its own** (1.26, +27.9R, 7 of 11 months positive). Resampling its weeks gives 0.84 to 1.93 in nine cases out of ten, with a 17% chance of a result below 1.0.
- **Over all four unseen years:** 30 of 46 months positive, largest drawdown 30.2R, 1.43 without the three largest wins; resampling the weeks gives 1.15 to 1.86 in nine cases out of ten. Buys 1.38 (338 trades), sells 1.53 (415). Average cost 0.02R per trade. With the spread fixed at $10 in every year instead of following the price: 1.44.
- **Only 3 of the 5 windows produced setups,** so the evidence rests on 2023 – 2026.
- **The same rule did not pass on the other timeframes** (M15 1.18, M10 1.09, M5 0.96 and lower). With 472 cells tested, part of a pass can be luck; the 2026 check is the part that was not chosen.
- **Not in the test: swap.** 12% of the trades were held over the server midnight (median holding time 3.8 hours); preset 06 has no time exit and held one trade for 30 days. Your broker's BTC swap is a cost the test does not have.

**The 10 presets** (picked on 2024 – 13 November 2026; these are calibration figures, not a forecast):

| Preset | Side | Session (server time) | Trend filter | MACD | Target | Trailing | 2024: PF (trades) | 2025: PF (trades) | 2026: PF (trades) |
|---|---|---|---|---|---|---|---|---|---|
| `01` | buy | all day | none | 12-26 | 3.0R | from 1.0R, 0.5R behind | 1.69 (22) | 2.50 (28) | 2.04 (26) |
| `02` | sell | all day | H1 EMA 200 | 8-17 | 1.0R | from 1.5R, 0.5R behind | 2.45 (27) | 1.67 (27) | 1.53 (22) |
| `03` | both | 07:00-20:00 | H4 EMA 50 | 10-22 | 2.0R | off | 1.94 (26) | 1.62 (27) | 1.57 (20) |
| `04` | both | 07:00-20:00 | H1 EMA 100 | 10-22 | 3.0R | from 1.0R, 1.0R behind | 2.90 (29) | 1.72 (31) | 1.51 (22) |
| `05` | sell | all day | none | 8-17 | 3.0R | from 1.0R, 1.0R behind | 1.66 (33) | 1.50 (25) | 2.13 (27) |
| `06` | both | 07:00-20:00 | none | 10-22 | 3.0R | off | 1.61 (43) | 1.66 (45) | 2.08 (44) |
| `07` | both | 12:00-20:00 | H4 EMA 20 | 10-22 | 3.0R | from 1.0R, 1.0R behind | 1.52 (22) | 3.20 (24) | 1.63 (20) |
| `08` | both | 12:00-20:00 | none | 10-22 | 3.0R | off | 1.95 (22) | 1.85 (28) | 2.26 (23) |
| `09` | both | 12:00-20:00 | H1 EMA 20 | 10-22 | 3.0R | off | 1.40 (22) | 2.35 (26) | 2.79 (21) |
| `10` | both | all day | H1 EMA 100 | 10-22 | 2.0R | off | 1.36 (29) | 1.66 (25) | 1.60 (23) |

**How to run them.** All 10 together on one **hedging** account: that is what was tested. They overlap: 175 of their 316 entry minutes in 2024 – 2026 were shared by two or more presets, and up to 9 positions were open at once. So each file sets **`RiskPercent=0.1`** (up to about 0.9% at risk at once); do not raise it to the 0.5 of the other presets. The stops are wide: median $688, 90% under $1,322, widest $3,311. With a 1-BTC contract and a 0.01 minimum lot, a trade is taken only if the balance is at least 10 times its stop in dollars at `RiskPercent=0.1` (`SkipIfBelowMinLot=true`): about $13,000 covers 90% of trades. At 0.1% each, the 10 together held up to about 4 times the balance in open positions: the account needs BTC leverage of at least 1:5, and 1:10 leaves room.

**Inputs these presets use (new in v1.35):** `UseStochTurnFilter=true` (the entry rule), `ScaleWithPrice=true` with `ReferencePrice=72408.79` (the stop buffer and minimum stop were calibrated at that price and follow it), `TrailMode=0` (the EA's own trailing).

**Re-picking.** The test picks the setups once a year from the three years before. These 10 are meant for about a year; then the selection should be run again on the newest data.

## The trailing presets `Loma_T15_BTC_*` (unproven)

These are the 11 combinations of timeframe and trailing system that reached a profit factor of 1.3 on at least 100 unseen trades in 16 May – 13 November 2026, out of 23 trailing systems tested on every timeframe (38 presets: every setup behind each combination). The setups were chosen on January 2025 – 15 May 2026 only. Then each combination was run on 2024 and 2023, before the calibration data: **none reached 1.3 there** and the group lost in 2023 everywhere except M10 EMA (1.02). With so many combinations, some reach 1.3 on one period by chance.

| Combination | Trailing (TrailMode) | Presets | Unseen 2026: PF (trades) | Stressed | 2024: PF (trades) | 2023: PF (trades) |
|---|---|---|---|---|---|---|
| M2 | Parabolic SAR (9) | 3 | 1.48 (109) | 1.27 | 0.80 (227) | 0.71 (204) |
| M2 | ATR at entry (1) | 3 | 2.14 (121) | 1.64 | 1.10 (214) | 0.60 (187) |
| M3 | candle lows / highs (6) | 3 | 1.44 (140) | 1.12 | 0.85 (271) | 0.87 (242) |
| M5 | candle lows / highs (6) | 3 | 1.89 (156) | 1.71 | 1.02 (306) | 0.92 (320) |
| M5 | SMA (8) | 6 | 1.51 (205) | 1.43 | 1.10 (462) | 0.71 (425) |
| M5 | profit lock (3) | 4 | 1.35 (214) | 1.14 | 0.77 (400) | 0.74 (397) |
| M5 | Bollinger band (10) | 3 | 1.37 (112) | 1.27 | 0.77 (267) | 0.65 (250) |
| M5 | higher-timeframe candle (11) | 4 | 1.71 (166) | 1.51 | 1.14 (321) | 0.70 (337) |
| M10 | EMA (7) | 2 | 1.95 (102) | 2.09 | 1.04 (156) | 1.02 (201) |
| M10 | stepped (4) | 3 | 1.36 (161) | 1.26 | 1.12 (310) | 0.79 (291) |
| M10 | swing pivots (12) | 4 | 1.56 (129) | 1.54 | 1.11 (283) | 0.72 (269) |

- Every preset's header gives its own figures for the calibration period, the 2026 months and 2024 and 2023; `BTC_TRAILING15_SUMMARY.csv` lists them all.
- The test is of each combination's setups together, not of the best of them by their 2026 result.
- They need v1.35 (`TrailMode`, `TrailParam`). Strategy Tester and demo only.

## The four M5 presets (unproven)

`Loma_BTC_M5_R01` to `R04`, from the re-calibration of November 2026. They were chosen on January 2025 – 15 May 2026 only and then run unchanged on 16 May – 13 November 2026: 133 trades, profit factor 1.42 (1.37 in the stress test). On the two years before the calibration data they lost: profit factor 0.79 in 2024 (276 trades) and 0.83 in 2023 (291 trades).

All four trade the M5 chart. Data: Binance BTCUSDT one-minute prices in broker server time, with an assumed $10 spread. "Picked on" is January 2025 – 15 May 2026. "Unseen" is 16 May – 13 November 2026. Stress = entry one minute late, pessimistic trailing, $3 slippage and $2 commission per BTC (per 1.0 lot). R = result in units of the trade's own risk.

| Preset | Direction | Session (server time) | Trend filter | Target | Trailing | Picked on: trades / PF | Unseen 2026: trades, PF, net | Stress PF | 2024: PF (trades) | 2023: PF (trades) |
|---|---|---|---|---|---|---|---|---|---|---|
| `R01` | both | 07:00-12:00 | none | previous hump | off | 77 / 1.99 | 31, 1.64, +8.1R | 1.74 | 0.76 (78) | 0.79 (74) |
| `R02` | sell | 07:00-20:00 | M15 EMA 200 | 1.5R | never active (would start at 1.5R, the target) | 102 / 1.54 | 38, 1.50, +8.9R | 1.38 | 1.17 (59) | 0.85 (83) |
| `R03` | both | 12:00-16:30 | H1 EMA 200 | 1.5R | from 1.0R, 1.0R behind | 85 / 1.76 | 28, 0.74, −3.3R | 0.79 | 0.73 (80) | 0.67 (59) |
| `R04` | sell | 12:00-20:00 | none | 1.5R | from 1.0R, 1.0R behind | 103 / 1.63 | 36, 1.79, +9.7R | 1.60 | 0.52 (59) | 0.96 (75) |
| **All four** | | | | | | | **133, 1.42, +23.3R** | **1.37** | **0.79 (276)** | **0.83 (291)** |

- **The test is of the four together.** Picking the best of them by their 2026 result would be hindsight. R03 lost in all three periods.
- **Mostly sells.** 113 of the 133 unseen trades were sells. BTC ended those months lower (about $79,000 to $68,000), after falling to $58,000 by July and rising to $87,000 in September. Sells in the four falling months made +12.2R of the +23.3R, sells in the three rising months +3.7R and the 20 buys +7.4R. In 2023 and 2024 BTC rose, and the same four presets lost. The spread is not the reason: with no spread at all they score 0.83 in 2024 and 0.94 in 2023.
- **Month by month in 2026:** six of the seven months were positive (September −2.1R). The largest drawdown was 5.7R.
- **How firm is 1.42?** It falls to 1.31 without the three largest wins and to 1.25 at a $20 spread. Extra round-trip costs of $20 per BTC lower it to 1.22, and $45 per BTC removes the gain (1.01). The stress test's 1.37 includes the one-minute-late entry, which happened to help in these months; with the extra costs alone it is 1.30. Resampling the weeks gives 1.03 to 1.96 in nine cases out of ten, and about a third of the resamples are below 1.3. Under four other ways of choosing the M5 setups the result is 1.43, 1.33, 1.31 and 1.17.
- **The other timeframes failed** with the EA's own trailing: M1 0.55, M2 1.22 (35 trades), M3 1.02, M10 1.07, M15 0.82, M30 1.08; H1 had no setup that passed in the calibration period.
- **With 23 trailing systems** instead of the EA's one, M5 again passes the 2026 months (1.48 on 377 trades), and the same setups scored 1.00 in 2024 and 0.69 in 2023. No other BTC timeframe passes. The EA cannot trade the other 22 systems, and nothing in these results is a reason to add them.
- **The presets overlap.** R02 shares entry minutes with R03 (7) and R01 (3), and R03 with R04 (1), so the 133 trades start on 122 different minutes. Positions of two presets were open together 39 times, 38 of them in the same direction, and up to four at once: 2% at risk at `RiskPercent=0.5`.
- The data is Binance spot. Your broker's BTCUSD CFD has its own prices, spread, commission, swaps and weekend behaviour.

## Correction: the first BTC zip is withdrawn

The first BTC zip held four other presets, `Loma_BTC01` to `Loma_BTC04`. **Delete them.** They were calibrated on a BTC price file whose clock was 2 hours (US winter) or 3 hours (US summer) ahead of broker time, so their trading hours, end-of-day times and trend filters were fitted to the wrong hours. The figures I gave for BTC with that zip came from the same file and are withdrawn too: the 1.05 out-of-sample profit factor, "no BTC timeframe passes", and the moving-average trailing result.

The BTC prices were rebuilt from the raw Binance files with one time conversion, and the calibration now checks the clock of every price series before it runs.

## What is in the zip

| File | What it is |
|---|---|
| `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` | The EA, v1.35 (the same file as in the gold zip). |
| `MQL5/Include/EVK/EVK.mqh` | Records trades in the Strategy Tester only (EA Validation Kit). The EA needs it to compile. |
| `MQL5/Presets/Loma_WF_BTC_M30_*.set` | The 10 presets of the year-by-year result. |
| `MQL5/Presets/Loma_BTC_M5_R01 … R04 *.set` | The four M5 presets from before (unproven). |
| `MQL5/Presets/Loma_T15_BTC_*.set` | The trailing presets (unproven). |
| `BTC_WF_M30_SUMMARY.csv` | The year-by-year presets with their calibration figures. |
| `BTC_PRESETS_SUMMARY.csv` | The four M5 presets: the calibration period, the unseen months of 2026, and 2024 and 2023. |
| `BTC_TRAILING15_SUMMARY.csv` | Every trailing preset with its figures. |
| `Loma_OOS_Review.html` | The full report, the same file as in the gold zip. Section 6 is the year-by-year test, section 5 the re-calibration. Open it in a browser. |

## Install

1. In MT5 choose **File > Open Data Folder**.
2. Copy the zip's `MQL5` folder over the data folder's `MQL5` folder.
3. In MetaEditor open `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` and press **F7** (compile).
4. Attach the EA to a BTCUSD chart (any timeframe: it reads its own). In **Inputs** click **Load** and pick a preset. The EA's built-in defaults are for gold; if they are left in place on BTC, the journal prints a warning.
5. Enable **Algo Trading**.

## New in v1.35

- **`TrailMode`** chooses the trailing system; `TrailStartR`, `TrailDistanceR` and the new **`TrailParam`** are read in its units. 0 = the EA's own (multiples of the risk, as before), 1 = ATR at entry, 2 = percent of price, 3 = profit lock, 4 = stepped, 5 = chandelier, 6 = candle lows / highs, 7 = EMA, 8 = SMA, 9 = Parabolic SAR, 10 = Bollinger band, 11 = higher-timeframe candle, 12 = swing pivots, 13 = hump structure. Every system except 0 and 4 moves the stop once per closed one-minute bar, as the backtest does; the stop only ever moves closer.
- **`UseStochTurnFilter`** (with `StochTurnBars`, `StochTurnHigh`, `StochTurnLow`): enter only when the Stochastic (7, 1, 7) of the trigger timeframe came from 80 (sells) or 20 (buys) within the last 5 bars and turned.
- **`ScaleWithPrice`** with **`ReferencePrice`**: the stop buffer, minimum and maximum stop follow the price, relative to the price they were calibrated at.
- With these inputs at their defaults v1.35 trades exactly like v1.34: the earlier presets work unchanged.
- v1.35 was checked in a C++ compile harness (the same diagnostics as v1.34) and in a simulated terminal that replays real one-minute prices: it took the same trades as the Python backtest on the shipped setups. It has not been compiled in MetaEditor: if the compiler reports anything, send me the log rather than editing the file.

## Settings that are specific to BTC

- **Points are 0.01 USD** with `AutoScalePoints=true`, whatever your broker's number of digits: for example R01's `SL_Buffer_Points=3500` is $35 and R03's `MinSL_Points=7000` is $70 (the other presets use $5 to $10 and $10 to $35). `MaxSpread_Points=3000`, in every BTC preset, lets trades open up to a $30 spread.
- **`MaxSlippage_Points=1000` ($10)** and **`TrailStep_Points=200` ($2):** the trailing stop moves in steps of at least $2.
- **Weekend close is off:** BTC trades through the weekend at most brokers.
- **Server time:** sessions and the end-of-day close are broker server time on a GMT+2 (winter) / GMT+3 (summer) clock, the clock of VT Markets and FTMO. Shift them if your broker's clock differs.
- **One account, several presets:** only on a **hedging** account. On a netting account all presets on one symbol share one position. The EA warns on a netting account and sends no entry while another position on the symbol is open.
- **Commission:** set `CommissionPerLot` to your round-trip commission per lot, in your account's currency (on a USC cent account, $0.60 is 60), so a stop-out costs `RiskPercent` including commission.
- **Account size (M5 presets):** the stops are wide: median $375, 90% under $750, widest $1,850 over the whole data. With a 1-BTC contract and a 0.01 minimum lot at `RiskPercent=0.5`, a trade is taken only if the balance is at least twice its stop in dollars: about $1,500 covers 90% of trades. Smaller balances skip the wide-stop trades.
- **Leverage (M5 presets):** the stops are small next to the price, so at `RiskPercent=0.5` a position is typically 1.3 times the balance (up to 3.3 times in the unseen months), and the four presets together held up to 5.7 times the balance. BTC leverage of about 1:10 or more is needed. With less, the EA cuts or skips trades for lack of free margin and says so in the journal, and the result will differ from the backtest.
- **News filter** is on in the presets but was not in the backtest. It does nothing in the Strategy Tester, so tester results equal `UseNewsFilter=false`.

## If you want to test it

- **Strategy Tester first:** "Every tick based on real ticks" on your broker's BTCUSD, deposit currency equal to your account's. In the tester, the Load dialog of the Inputs tab usually opens in `MQL5\Profiles\Tester`; browse to `MQL5\Presets` for these files. For the `Loma_WF` presets test 2023 to today, year by year, and compare profit before commission, commission and swap.
- **Then demo**, the `Loma_WF` presets together on a hedging account at `RiskPercent=0.1`. A tester run and a demo that match the figures above show that the EA trades its backtest; the 2026 check is the only evidence that the edge is real, and it was 1.26.

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

1. **Trend first:** a big MACD hump below zero (bearish) or above zero (bullish). "Big" = peak at least `BigHumpMultiplier` times the median of the last `BigHumpHistory` humps and at least `BigHumpMinBars` bars. R03 and R04 also need the Stochastic to reach `StochLow` / `StochHigh` during it (20/80 and 25/75). No big hump in force = no trades.
2. **Trend break:** an opposite hump as large as `TrendBreakRatio` times the big hump.
3. **Signal:** a small pullback hump, then the first bar with the MACD back across zero; only `MaxSignalsPerBigHump` signals per big hump.
4. **Stop** beyond the pullback hump's extreme plus `SL_Buffer_Points` (and the spread for sells). **Target:** the previous hump's extreme in R01, 1.5 times the risk in the others.
5. **Filters and exits:** higher-timeframe EMA filter, trading hours, spread limit, trailing in multiples of the risk, maximum holding time and end-of-day close, as set in each preset.

## What changed

**v1.35** (this zip)
- The trailing systems, the Stochastic turn filter and the price scaling of "New in v1.35" above.

**v1.34**
- **BTC presets:** $10 of slippage instead of $0.20, and a $2 trailing step instead of $0.10.
- **Trailing stop:** after a failed stop change it pauses for 5 seconds instead of retrying on every tick, and it does not try while Algo Trading is off. Its original risk (1R) is read from the opening deal, so a crash or a move to another terminal no longer shrinks the trailing distance.
- **Slippage setting** is rounded up, so BTC quotes with 0 or 1 digits no longer turn it into 0.
- **Netting accounts:** a warning, and no entry while another position on the symbol is open.
- **`MaxHoldMinutes`:** no early close when the one-minute history is not loaded yet.
- **New input `CommissionPerLot`** (0 = off), counted in the risk. `MaxLotSize` is rounded to the volume step; margin cuts are logged.
- **Checks:** `HTF_Timeframe=MN1` is rejected, a data stall prints a warning every 5 bars, and a gold preset loaded on BTC prints a warning.

**v1.33**
- Strategy Tester fix: in the non-visual tester, v1.32 never traded.
