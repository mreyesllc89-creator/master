# Loma EA v1.34 for XAUUSD: start here

`XAUUSD_Loma_TrendPullback.mq5` trades the "loma" (MACD hump) method on gold in MetaTrader 5, buys and sells. This zip holds the EA and the six gold presets with a backtest profit factor of 1.3 or more under stress, in both 2025 and 2026.

> **Do not trade these presets with real money.** They were fitted to January 2025 – May 2026. On the months after that, which they never saw, all six lost money. On VT Markets real ticks (MT5 Strategy Tester, 1 June – 6 November 2026), the six together had a profit factor of 0.74 before commission on 247 trades. Five of the six lost and the sixth (Top02) broke even. Dukascopy prices agree. The EA itself works: it takes the same trades as the backtest. The edge did not last. Open `Loma_OOS_Review.html` for the full test.

## What is in the zip

| File | What it is |
|---|---|
| `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` | The EA, v1.34 (the same file runs on gold and on BTCUSD). |
| `MQL5/Include/EVK/EVK.mqh` | Records trades in the Strategy Tester only (EA Validation Kit). The EA needs it to compile. |
| `MQL5/Presets/Loma_Top01 … Top07 *.set` | The six gold presets (table below). Each has its own magic number. |
| `GOLD_PRESETS_SUMMARY.csv` | Backtest and out-of-sample figures of the six presets. |
| `Loma_OOS_Review.html` | The out-of-sample report: VT Markets run, Dukascopy cross-check, walk-forward test. Open it in a browser. |

## Install

1. In MT5 choose **File > Open Data Folder**.
2. Copy the zip's `MQL5` folder over the data folder's `MQL5` folder. This adds files and replaces nothing else.
3. In MetaEditor open `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` and press **F7** (compile).
4. Attach the EA to an XAUUSD chart (any timeframe: it reads its own). In **Inputs** click **Load** and pick a preset.
5. Enable **Algo Trading**.

v1.33 was compiled in MetaEditor (MT5 build 6302) with 0 errors and 0 warnings. v1.34 adds the small changes listed below. If the compiler reports anything, send me the log rather than editing the file.

## The six presets

Backtest: FTMO one-minute data, January 2025 – 15 May 2026, the period the presets were chosen on. Out of sample: 1 June – 6 November 2026, never used for calibration. "PF" is the profit factor.

| Preset | Chart | Direction | Session (server time) | Trend filter | Backtest trades / PF | 2026 PF (in sample) | VT trades, Jun – Nov 6 | VT PF before / after commission | Dukascopy PF |
|---|---|---|---|---|---|---|---|---|---|
| `Loma_Top01` | M10 | both | 07:00-20:00 | H1 EMA 20 | 129 / 2.09 | 1.72 | 32 | 0.46 / 0.28 | 0.55 |
| `Loma_Top02` | M3 | sell | all day | none | 143 / 1.98 | 2.07 | 48 | 1.04 / 0.31 | 0.99 |
| `Loma_Top03` | M2 | sell | 12:00-20:00 | H1 EMA 20 | 117 / 2.03 | 1.46 | 44 | 0.77 / 0.27 | 0.68 |
| `Loma_Top04` | M5 | both | 07:00-12:00 | H1 EMA 50 | 124 / 1.82 | 1.40 | 42 | 0.58 / 0.19 | 0.56 |
| `Loma_Top05` | M10 | buy | all day | M30 EMA 20 | 141 / 1.96 | 1.47 | 49 | 0.87 / 0.42 | 0.84 |
| `Loma_Top07` | M5 | buy | all day | H1 EMA 50 | 135 / 2.17 | 1.84 | 32 | 0.72 / 0.26 | 0.64 |

- The VT Markets figures come from Codex's MT5 run with 100% real ticks. VT charged about $6 per lot round trip, which may be a cent-account setting; the before-commission column does not depend on it.
- Dukascopy is a third price source, separate from FTMO (calibration) and VT. It found 220 of the 247 VT trades.
- A walk-forward test (recalibrating every few months on recent data) did not rescue the method: only one of five schedules passed, and only on four windows that include the 2025–26 gold rally.

## If you still want to test it

- **Strategy Tester:** model "Every tick based on real ticks", your broker's XAUUSD, deposit currency equal to your account's (USC for a cent account). Test January 2025 – May 2026 and June 2026 – today **separately**, and compare profit before commission, commission and swap.
- **Demo only.** Top02 and Top05 were the least bad out of sample. Expect break-even minus costs at best.
- **Server time:** session, weekend and end-of-day times are broker server time, calibrated on a GMT+2 (winter) / GMT+3 (summer) clock. VT Markets matches. Shift them if your broker's clock differs.
- **One account, several presets:** only on a **hedging** account. On a netting account all presets on one symbol share a single position, so one preset's trade changes another's. v1.34 prints a warning when it starts on a netting account.
- **News filter** (`UseNewsFilter`) is on in the presets but was not in the backtest. It does nothing in the Strategy Tester.

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

1. **Trend first:** a big MACD hump below zero (bearish) or above zero (bullish). "Big" = peak at least `BigHumpMultiplier` times the median of the last `BigHumpHistory` humps, at least `BigHumpMinBars` bars, and the Stochastic reached `StochLow` / `StochHigh` if `RequireStochLevel` is on. No big hump in force = lineal market = no trades.
2. **Trend break:** an opposite hump as large as `TrendBreakRatio` times the big hump.
3. **Signal:** a small pullback hump (at least `PullbackMinBars` bars, at most `PullbackMaxRatio` times the big hump), then the first bar with the MACD back across zero. Only `MaxSignalsPerBigHump` signals per big hump, and none after `TrendMaxBars` bars.
4. **Stop:** beyond the pullback hump's extreme, plus `SL_Buffer_Points` and (for sells) the spread. **Target:** `TP_RR` times the risk in the presets.
5. **Filters and exits:** higher-timeframe EMA filter, trading hours, spread limit, trailing in multiples of the risk, maximum holding time, end-of-day close and Friday close, as set in each preset.

## What changed

**v1.34** (this zip)
- A failed trailing-stop change, for example while the market is closed at the daily open, is retried at most every few seconds instead of on every tick. The MT5 test printed 295 such failures.
- A warning is printed at start on a netting account, where several presets on one symbol cannot be kept apart.

**v1.33**
- Strategy Tester fix: the EA now asks for an indicator value before checking that the indicator is ready. In the non-visual tester, v1.32 never traded.

**v1.31 and v1.32** added `SkipBigPullback`, the Friday close (`CloseBeforeWeekend`), `MaxHoldMinutes` and the end-of-day close (`CloseAtEndOfDay`).

## What you see on the chart

- **Status panel:** trend state (BEARISH / BULLISH / LINEAL), the big hump's size, signals used, the current hump, the session and the last reason a signal was skipped.
- **Labels** on big humps, **arrows** on signals, and the stop and target lines of the last trade.
