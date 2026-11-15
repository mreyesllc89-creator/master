# Loma EA v1.34 for BTCUSD: start here

`XAUUSD_Loma_TrendPullback.mq5` trades the "loma" (MACD hump) method in MetaTrader 5, buys and sells. The file name says XAUUSD, but the same EA runs on BTCUSD with these four presets. **Do not load them on gold, or the gold presets on BTC.**

> **Unproven: demo only.** The four presets are the M5 setups of a re-calibration that held part of the data back. They were chosen on January 2025 – 15 May 2026 only and then run unchanged on 16 May – 13 November 2026: 133 trades, profit factor 1.42 (1.37 in the stress test). With the EA's own trailing stop, M5 was the only one of eight BTC timeframes that passed. A second test on the two years before the calibration data failed: profit factor 0.79 in 2024 (276 trades) and 0.83 in 2023 (291 trades). One good period out of three is not an edge.

## Correction: the first BTC zip is withdrawn

The first BTC zip held four other presets, `Loma_BTC01` to `Loma_BTC04`. **Delete them.** They were calibrated on a BTC price file whose clock was 2 hours (US winter) or 3 hours (US summer) ahead of broker time, so their trading hours, end-of-day times and trend filters were fitted to the wrong hours. The figures I gave for BTC with that zip came from the same file and are withdrawn too: the 1.05 out-of-sample profit factor, "no BTC timeframe passes", and the moving-average trailing result.

The BTC prices were rebuilt from the raw Binance files with one time conversion, and the calibration now checks the clock of every price series before it runs.

## What is in the zip

| File | What it is |
|---|---|
| `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` | The EA, v1.34 (the same file as in the gold zip). |
| `MQL5/Include/EVK/EVK.mqh` | Records trades in the Strategy Tester only (EA Validation Kit). The EA needs it to compile. |
| `MQL5/Presets/Loma_BTC_M5_R01 … R04 *.set` | The four BTC presets (table below). Each has its own magic number. |
| `BTC_PRESETS_SUMMARY.csv` | The figures of the four presets: the calibration period, the unseen months of 2026, and 2024 and 2023. |
| `Loma_OOS_Review.html` | The full report, the same file as in the gold zip. Section 5 has the BTC tables. Open it in a browser. |

## Install

1. In MT5 choose **File > Open Data Folder**.
2. Copy the zip's `MQL5` folder over the data folder's `MQL5` folder.
3. In MetaEditor open `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` and press **F7** (compile).
4. Attach the EA to a BTCUSD chart (any timeframe: it reads its own, M5). In **Inputs** click **Load** and pick a `Loma_BTC_M5` preset. The EA's built-in defaults are for gold; if they are left in place on BTC, the journal prints a warning.
5. Enable **Algo Trading**.

v1.33 was compiled in MetaEditor (MT5 build 6302) with 0 errors and 0 warnings. v1.34, the file in this zip, adds the changes listed below. It was checked line by line and run through a compile harness and a simulated terminal, but it has not been compiled in MetaEditor yet. If the compiler reports anything, send me the log rather than editing the file.

## The four presets

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
- **How firm is 1.42?** It falls to 1.31 without the three largest wins and to 1.25 at a $20 spread. Extra round-trip costs of $20 per BTC lower it to 1.22, and $45 per BTC removes the gain (1.01). The stress test's 1.37 includes the one-minute-late entry, which happened to help in these months; with the extra costs alone it is 1.30. Resampling the weeks gives a range of 1.03 to 1.96. Under four other ways of choosing the M5 setups the result is 1.43, 1.33, 1.31 and 1.17.
- **The other timeframes failed** with the EA's own trailing: M1 0.55, M2 1.22 (35 trades), M3 1.02, M10 1.07, M15 0.82, M30 1.08; H1 had no setup that passed in the calibration period.
- **With 23 trailing systems** instead of the EA's one, M5 again passes the 2026 months (1.48 on 377 trades), and the same setups scored 1.00 in 2024 and 0.69 in 2023. No other BTC timeframe passes. The EA cannot trade the other 22 systems, and nothing in these results is a reason to add them.
- **The presets overlap.** R02 shares entry minutes with R03 (7) and R01 (3), and R03 with R04 (1), so the 133 trades start on 122 different minutes. Positions of two presets were open together 39 times, 38 of them in the same direction, and up to four at once: 2% at risk at `RiskPercent=0.5`.
- The data is Binance spot. Your broker's BTCUSD CFD has its own prices, spread, commission, swaps and weekend behaviour.

## Settings that are specific to BTC

- **Points are 0.01 USD** with `AutoScalePoints=true`, whatever your broker's number of digits: `SL_Buffer_Points=3500` is $35, `MinSL_Points=7000` is $70, `MaxSpread_Points=3000` lets trades open up to a $30 spread.
- **`MaxSlippage_Points=1000` ($10)** and **`TrailStep_Points=200` ($2):** the trailing stop moves in steps of at least $2.
- **Weekend close is off:** BTC trades through the weekend at most brokers.
- **Server time:** sessions and the end-of-day close are broker server time on a GMT+2 (winter) / GMT+3 (summer) clock, the clock of VT Markets and FTMO. Shift them if your broker's clock differs.
- **One account, several presets:** only on a **hedging** account. On a netting account all presets on one symbol share one position. v1.34 warns on a netting account and sends no entry while another position on the symbol is open.
- **Commission:** set `CommissionPerLot` to your round-trip commission per lot, in your account's currency (on a USC cent account, $0.60 is 60), so a stop-out costs `RiskPercent` including commission.
- **Account size:** the stops are wide: median $375, 90% under $750, widest $1,850 over the whole data. With a 1-BTC contract and a 0.01 minimum lot at `RiskPercent=0.5`, a trade is taken only if the balance is at least twice its stop in dollars: about $1,500 covers 90% of trades. Smaller balances skip the wide-stop trades.
- **Leverage:** the stops are small next to the price, so at `RiskPercent=0.5` a position is typically 1.3 times the balance (up to 3.3 times in the unseen months), and the four presets together held up to 5.7 times the balance. BTC leverage of about 1:10 or more is needed. With less, the EA cuts or skips trades for lack of free margin and says so in the journal, and the result will differ from the backtest.
- **News filter** is on in the presets but was not in the backtest. It does nothing in the Strategy Tester, so tester results equal `UseNewsFilter=false`.

## If you want to test it

- **Strategy Tester first:** "Every tick based on real ticks" on your broker's BTCUSD, deposit currency equal to your account's. Test January 2025 – 15 May 2026 and 16 May 2026 – today separately, and compare profit before commission, commission and swap. If your broker has BTC history for 2023 and 2024, test those years too: that is where the backtest lost.
- **Then demo**, all four presets together on a hedging account, for a few months. Do not put real money on them before the tester and the demo agree with the 2026 figures above.

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

**v1.34** (this zip)
- **BTC presets:** $10 of slippage instead of $0.20, and a $2 trailing step instead of $0.10.
- **Trailing stop:** after a failed stop change it pauses for 5 seconds instead of retrying on every tick, and it does not try while Algo Trading is off. Its original risk (1R) is read from the opening deal, so a crash or a move to another terminal no longer shrinks the trailing distance.
- **Slippage setting** is rounded up, so BTC quotes with 0 or 1 digits no longer turn it into 0.
- **Netting accounts:** a warning, and no entry while another position on the symbol is open.
- **`MaxHoldMinutes`:** no early close when the one-minute history is not loaded yet.
- **New input `CommissionPerLot`** (0 = off), counted in the risk. `MaxLotSize` is rounded to the volume step; margin cuts are logged.
- **Checks:** `HTF_Timeframe=MN1` is rejected, a data stall prints a warning every 5 bars, and a gold preset loaded on BTC prints a warning.

**v1.33**
- Strategy Tester fix: in the non-visual tester, v1.32 never traded.
