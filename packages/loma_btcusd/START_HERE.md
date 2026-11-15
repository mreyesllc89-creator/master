# Loma EA v1.34 for BTCUSD: start here

`XAUUSD_Loma_TrendPullback.mq5` trades the "loma" (MACD hump) method in MetaTrader 5, buys and sells. The file name says XAUUSD, but the same EA runs on BTCUSD with these four presets. **Do not load them on gold, or the gold presets on BTC.**

> **No reliable edge: demo only.** The presets were fitted to January 2025 – 15 May 2026 (Binance BTCUSDT one-minute data). From 16 May to 13 November 2026, which they never saw, the four together broke even: 193 trades, profit factor 1.05 with a $10 spread and 1.00 with a $20 spread. BTC01 and BTC04 lost. BTC02 made money but broke even under the stress costs. BTC03 stayed modestly positive under stress (PF 1.19).

## What is in the zip

| File | What it is |
|---|---|
| `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` | The EA, v1.34 (the same file as in the gold zip). |
| `MQL5/Include/EVK/EVK.mqh` | Records trades in the Strategy Tester only (EA Validation Kit). The EA needs it to compile. |
| `MQL5/Presets/Loma_BTC01 … BTC04 *.set` | The four BTC presets (table below). Each has its own magic number. |
| `BTC_PRESETS_SUMMARY.csv` | Backtest and out-of-sample figures of the four presets. Columns up to `stress_2026` are the backtest (January 2025 – 15 May 2026; the `_2026` columns are its 2026 part, in sample). The `oos_` columns are 16 May – 13 November 2026. |
| `Loma_OOS_Review.html` | The full report, the same file as in the gold zip. Section 5 has the re-calibration tables for BTC. Open it in a browser. |

## Install

1. In MT5 choose **File > Open Data Folder**.
2. Copy the zip's `MQL5` folder over the data folder's `MQL5` folder.
3. In MetaEditor open `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` and press **F7** (compile).
4. Attach the EA to a BTCUSD chart (any timeframe). In **Inputs** click **Load** and pick a `Loma_BTC` preset. The EA's built-in defaults are for gold; if they are left in place on BTC, the journal prints a warning.
5. Enable **Algo Trading**.

v1.33 was compiled in MetaEditor (MT5 build 6302) with 0 errors and 0 warnings. v1.34, the file in this zip, adds the changes listed below. It was checked line by line and run through a compile harness and a simulated terminal, but it has not been compiled in MetaEditor yet. If the compiler reports anything, send me the log rather than editing the file.

## The four presets

Backtest: Binance BTCUSDT one-minute data with an assumed $10 spread, January 2025 – 15 May 2026. Out of sample: 16 May – 13 November 2026, same source, never used for calibration. Stress = entry one minute late, pessimistic trailing, $3 slippage and $2 commission per trade. R = result in units of the trade's own risk.

| Preset | Chart | Direction | Session (server time) | Trend filter | Trailing | Backtest trades / PF | Out of sample: trades, PF, net | Stress PF | PF at $20 spread |
|---|---|---|---|---|---|---|---|---|---|
| `Loma_BTC01` | M3 | both | 07:00-12:00 | M15 EMA 20 | from 1.5R, 0.5R behind | 136 / 2.22 | 56, 0.86, −4.9R | 0.79 | 0.78 |
| `Loma_BTC02` | M5 | both | 12:00-16:30 | H4 EMA 50 | from 0.5R, 0.3R behind | 129 / 2.22 | 41, 1.79, +7.9R | 1.04 | 1.61 |
| `Loma_BTC03` | M10 | sell | 07:00-20:00 | none | from 0.5R, 1.0R behind | 124 / 2.21 | 51, 1.24, +4.9R | 1.19 | 1.22 |
| `Loma_BTC04` | M10 | sell | 07:00-20:00 | M30 EMA 50 | off | 132 / 1.72 | 45, 0.90, −3.0R | 0.82 | 0.90 |

- **BTC02's gain is thin.** With all the stress costs together (late entry, pessimistic trailing, $3 slippage and $2 commission) its profit factor falls from 1.79 to 1.04, and to 0.86 at a $20 spread. Its tight trailing stop (0.3R behind price) is something one-minute bars cannot judge; only a Strategy Tester run on real ticks can.
- **BTC03 is the only one that stayed positive under stress**, and most of its gain came in June 2026 (+9.7R). Without June it lost.
- **BTC03 and BTC04 are both M10 sells in the same session** and share many trades: run one of them.
- The data is Binance spot. Your broker's BTCUSD CFD has its own prices, spread, commission, swaps and weekend behaviour.
- **Re-calibration per timeframe (15 November 2026):** every timeframe from M1 to H1 was re-calibrated on January 2025 – 15 May 2026 with eleven kinds of trailing stop, and the best 10 setups of each were run on 16 May – 13 November 2026. No BTC timeframe holds a profit factor of 1.3 on at least 100 unseen trades: M5 is the closest at 1.20 (1.10 under stress). Moving-average trailing looked good in 2026 (1.35 on 401 trades) but scored 1.04 on 2024 and 0.80 on 2023, so it is not counted as an edge. The full tables are in the repository: `research/reports/loma_oos_review.html`, section 5.

## Settings that are specific to BTC

- **Points are 0.01 USD** with `AutoScalePoints=true`, whatever your broker's number of digits: `SL_Buffer_Points=5000` is $50, `MinSL_Points=1000` is $10, `MaxSpread_Points=3000` lets trades open up to a $30 spread.
- **`MaxSlippage_Points=1000` ($10)** in v1.34. It was 20 ($0.20), which a broker with instant execution would reject on almost every BTC order. Brokers with market execution ignore it.
- **`TrailStep_Points=200` ($2)** in v1.34: the trailing stop moves in steps of at least $2. It was $0.10, which would send a stop change on almost every BTC tick.
- **Weekend close is off:** BTC trades through the weekend at most brokers.
- **Server time:** sessions and the end-of-day close are broker server time on a GMT+2 (winter) / GMT+3 (summer) clock. Shift them if your broker's clock differs.
- **One account, several presets:** only on a **hedging** account. On a netting account all presets on one symbol share one position. v1.34 warns on a netting account and sends no entry while another position on the symbol is open.
- **Commission:** set `CommissionPerLot` to your round-trip commission per lot, in your account's currency (on a USC cent account, $0.60 is 60), so a stop-out costs `RiskPercent` including commission.
- **Account size:** the stops are wide (median $300–460, 90% under $580–810, widest about $2,230). With a 1-BTC contract and a 0.01 minimum lot at `RiskPercent=0.5`, a trade is taken only if the balance is at least twice its stop in dollars: about $2,000 covers 90% of trades. Smaller balances skip the wide-stop trades.
- **News filter** is on in the presets but was not in the backtest. It does nothing in the Strategy Tester, so tester results equal `UseNewsFilter=false`.

## If you still want to test it

- **Strategy Tester:** "Every tick based on real ticks" on your broker's BTCUSD, deposit currency equal to your account's. Test January 2025 – 15 May 2026 and 16 May 2026 – today separately, and compare profit before commission, commission and swap.
- **Demo only** until a real-tick test and a few months of demo agree. BTC03 is the one to try first.

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

1. **Trend first:** a big MACD hump below zero (bearish) or above zero (bullish), with the Stochastic reaching `StochLow` / `StochHigh` during it (20/80; 15/85 in BTC04). No big hump in force = no trades.
2. **Trend break:** an opposite hump as large as `TrendBreakRatio` times the big hump.
3. **Signal:** a small pullback hump, then the first bar with the MACD back across zero; only `MaxSignalsPerBigHump` signals per big hump.
4. **Stop** beyond the pullback hump's extreme plus `SL_Buffer_Points` (and the spread for sells); **target** `TP_RR` times the risk.
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
