# XAUUSD M1 Liquidity Zero-Cross Bearish (MT5 EA) v1.10

Short-only MQL5 Expert Advisor for XAUUSD on M1. *"No señal = no operación"*: no signal means no trade.

Files:
- `XAUUSD_M1_LiquidityZeroCross_Bearish.mq5` is the EA source. Copy it to `MQL5/Experts/` and compile it in MetaEditor.
- `XAUUSD_M1_LiquidityZeroCross_Bearish_FGF.mq5` is the same EA with the FlashGold Direction Filter (see below).
- `presets/*.set` are complete input presets (every input listed). Copy them to `MQL5/Presets/`, then load them from the EA's Inputs tab.

## Rule map

| Rule | Implementation | Type |
|---|---|---|
| R1 HTF bias | M15 (or M5) MACD(12,26,9) main < 0 **and** close < EMA(50) on the last closed HTF bar | Mechanical, `UseHTF_Filter` |
| R2 M1 trigger | MACD main at bar[2] ≥ 0 and at bar[1] < 0, checked once per new M1 bar on closed bars only, so it does not repaint | Mechanical |
| R3 Stochastic(7,1,7) | Main reached ≥ 80 within the last `Stoch_LookbackBars` bars and is now below its signal line or below 80 | Soft quality filter (`StochHardBlock` makes it hard) |
| R4 Liquidity | **SL:** the most recent liquidity candle (a bar that swept an older swing high and closed back below it). If there is none, the most recent swing high above price. Add `SL_Buffer_Points` plus the spread. **TP:** the nearest swing low below price that gives at least `MinRewardRisk`. If neither exists within `LiquidityLookbackBars`, the trade is skipped | Mechanical, simplified |
| R5 Risk | `RiskPercent` of equity, lot size from the SL distance (`OrderCalcProfit`), margin check, at most 1 position, `MaxSpread_Points`, trailing (server or hybrid) and an optional partial close | Mechanical |
| R6 Session/news | `TradingHoursStart`/`End` (default 12:00–16:30 GMT, the London/NY overlap), plus a ±30 min high-impact USD news filter using the MT5 calendar | Mechanical |
| Optional | RSI(12) < 50, manual SL/TP prices, HTF swing lows as extra TP candidates | Discretionary, default OFF |

## Notes
- Point inputs assume a 2-digit gold quote, where 1 point = 0.01 and 40 points = 4 pips. `AutoScalePoints` multiplies them by 10 on 3-digit feeds. They are fixed distances: gold rose from about $2,600 to $4,700 during the test data, so the same points mean less as price rises.
- Signals are evaluated once per trigger bar on closed bars. If indicator or higher-timeframe data is not up to date on the bar's first tick, the EA retries on the next tick instead of losing the signal.
- The trade plan (structure, SL, TP, lot) and the FlashGold permission are decided once per signal, as in the backtest. `MaxEntryDelaySeconds` limits how long after the bar opens an entry may happen. Requotes and timeouts are retried up to 3 times, with a check for an already-open position first.
- Hybrid trailing keeps the original broker SL as a catastrophe stop and closes at market when the virtual trailing level is hit. Partial close works on hedging and netting accounts.

## Known limitations
- Liquidity detection is simplified to fractal swings plus one sweep pattern. Hand-drawn "blue rectangle" zones, order blocks and equal-high/low clusters are not auto-detected. `DrawLiquidityZone()` is the hook for adding them.
- The economic calendar is unavailable in the Strategy Tester, so the news filter is bypassed there, and it was not part of the Python backtest.
- With `TradingHoursAreGMT=true` the tester converts server time to GMT with a fixed `TesterGMTOffsetHours`, which is wrong for half the year on brokers with daylight saving. The calibrated presets use server time instead.
- "Stochastic(7,1,7)" is mapped as %K=7, Slowing=1, %D=7. All three are inputs.
- The source code has not been compiled here because MetaEditor is not available. Compile it and run a visual backtest before going live.

## Calibration: what the backtest supports

v1.10 adds `TriggerTimeframe`, `TP_LookbackBars`, `TP_FallbackRR` and `MaxEntryDelaySeconds`. Their defaults keep the v1.00 behaviour.

The research (`research/`) replays the EA's rules in Python on FTMO XAUUSD M1 data from January 2025 to May 2026. That data is in **broker server time** (GMT+2 winter, GMT+3 summer, New York close), so every session window in the research and in the calibrated presets is server time (`TradingHoursAreGMT=false`). Spreads are a constant mean per hour of day, taken from the broker's measured hourly spreads.

- **In-sample headline.** A search of 126,360 setups across 13 trigger/bias pairs picked an **M3 trigger with an H1 bias, 12:00-16:30 server time** (`presets/XLZC_Bearish_M3_H1_NY.set`): 77 trades, PF 2.48 (2.15 / 2.80 / 2.56 in 2025 H1 / 2025 H2 / 2026). All 17 months were used to choose it, so this figure is in-sample. When a trailing stop is set and touched within the same M1 bar the order is unknown; the pessimistic assumption gives PF 1.82.
- **Walk-forward (choose on 2025, test on 2026).** Picking single setups does not carry over: the top 10 by 2025 results had a median 2026 PF of 0.67, worse than the 51% base rate of profitable setups. Picking the timeframe pair does: the best two pairs on 2025 alone were M2/H1 and M3/H1, and both stayed profitable in 2026 (median PF 1.27 and 2.30 across their setups). The supported conclusion is "M2/M3 trigger with an H1 bias", not the exact parameter values. The M3/H1 preset itself ranked 91st of 86,241 on 2025 alone and made PF 2.56 on 30 trades in 2026.
- **M2/H1 preset** (`presets/XLZC_Bearish_M2_H1_NY.set`). Chosen with 2025 data only, as the most stable M2/H1 setup (median of the setup and its neighbouring settings, at least 30 trades per half-year): M2 trigger, H1 bias, 12:00-16:30 server time, swing strength 4, lookback 15, fixed 1.5R target when no liquidity pool qualifies, trailing on. 186 trades, PF 1.55, +19.9R, max drawdown 4.9R; PF 1.51 / 1.56 in 2025 and **1.61 on 43 trades in 2026, which the choice never saw**. It leans on trailing: counting every same-bar trailing touch as a stop gives PF 1.05. The FlashGold filter lowers it (PF 1.44, 2026 PF 1.11), so there is no FGF variant.
- **Sensitivity.** Trailing is essential (PF 1.35 without it). A 07:00-20:00 window drops PF to about 1.2. A spread 50% wider than FTMO's exceeds the 60-point cap, so the EA would not trade at all.

## Trailing stop calibration

`research/trailing_sweep.py` tested every trailing start (0 to 800 gold points) against every distance (25 to 600) plus trailing off, 81 combinations, on the four calibrated presets. Each combination ran under four assumptions about what happens inside a one-minute bar after a new trailing level is set:
- `next`: no same-bar hit;
- `close`: a hit when the bar closes beyond the level;
- `worst`: a hit when the bar's high reaches it;
- `random`: the low comes first in a seeded half of the bars.

The EA's points are gold points × √(trigger minutes) × instrument scale. Results, where PF is the range across the four assumptions:

| Preset | Trailing off | Current 150/100 | Best tight setting on 2025 | Decision |
|---|---|---|---|---|
| Gold M2/H1 | PF 1.25 | PF 1.05–1.55; 2026 1.21–1.61 | 300/25: PF 1.41–1.62 | **Keep 150/100.** The tight setting looked better in 2025 but was not better in 2026. |
| Gold M3/H1 | PF 1.35 | PF 1.82–2.48; 2026 2.12–2.56 | 150/25: PF 1.94–2.54 | **Keep 150/100.** No confirmed improvement in 2026. |
| BTC M3/H1 | PF 0.89 | PF 0.99–1.52; 2026 0.82–1.21 | 150/25: PF 1.39–1.58; 2026 1.19–1.37 | **Changed to 150/25** (8470/1412 points). Better than 150/100 on 2026 data in a paired bootstrap. |
| BTC M3/M30 | PF 1.15 | PF 0.96–1.45 | 0/25 failed in 2026 (0.49–0.97) | **Experimental.** No trailing setting chosen on 2025 held up. |

What this shows:
- **Trailing matters.** It is on in every preset because it beats trailing off in all four presets, in both 2025 and 2026.
- **Tight distances can't be judged on one-minute bars.** Below a typical one-minute range, which includes every 25-point setting, the result depends on the order of prices inside the bar. None of the four assumptions bounds what real ticks do.
- **Settle it in MT5.** Optimize the two trailing inputs in the Strategy Tester with *Every tick based on real ticks* and EVK, then run `python -m evk analyze`. Use these ranges, which cover the same gold-point grid:

| Preset | `TrailingStart_Points` start / step / stop | `TrailingDistance_Points` start / step / stop |
|---|---|---|
| Gold M2/H1 | 0 / 71 / 1131 | 35 / 35 / 849 |
| Gold M3/H1 | 0 / 87 / 1386 | 43 / 43 / 1039 |
| BTC M3/H1 or M3/M30 | 0 / 2823 / 45172 | 1412 / 1412 / 33879 |

## BTCUSD

The same research was run on BTCUSD (Binance BTCUSDT one-minute data, Jan 2025 to May 2026, converted to the same server clock). All point distances were scaled by 32.6, the ratio of BTC's typical one-minute range to gold's ($41 vs $1.26). The spread is an assumption, because no broker spread data was available.

- **At a 20 USD spread there is no edge.** Every pair family's median PF is below 1. Setups chosen on 2025 lost money in 2026 (M3/M30 PF 0.72, M3/H1 PF 0.82).
- **Costs decide it.** At 10 USD the M3 families have a median PF around 1.06-1.10; at 5 USD, 1.13-1.18. The trend-filter pairs M3/M30 and M3/H1 were the top two on 2025 and stayed profitable in 2026.
- **Low-cost presets.** Chosen on 2025 only with a 5 USD spread:
  - `presets/XLZC_Bearish_BTCUSD_M3_M30.set`: 117 trades, PF 1.45; 2026 PF 1.31 on 38 trades.
  - `presets/XLZC_Bearish_BTCUSD_M3_H1.set`: 102 trades, PF 1.52; 2026 PF 1.21 on 32 trades.
  - Both use `MaxSpread_Points=1000` (10 USD), so they stand aside when the spread is wider.
  - Both depend on trailing: the worst-case fill assumption gives PF about 0.96-0.99.
- `AutoScalePoints` now also handles BTC quotes with 1 or 0 decimals; the inputs are always 0.01 USD steps.

This is a Python replica of the EA, not the MT5 Strategy Tester. Confirm the result in MT5 with real ticks before trading it live. The calibration report in `research/results/calibration_report.html` has the details.

## Two versions: without and with the FlashGold Direction Filter

- `XAUUSD_M1_LiquidityZeroCross_Bearish.mq5` has no direction filter.
- `XAUUSD_M1_LiquidityZeroCross_Bearish_FGF.mq5` is the same EA with the FlashGold Direction Filter v1.2. A short opens only while the indicator's buffer 2 ("sell allowed") is 1: price below the FlashGold level and outside the ATR no-trade band, with the permission window open. It is checked once per signal.

The FGF file defines `XLZC_WITH_FGF` and includes the base file, so both versions share every rule and fix. Keep both files in `MQL5/Experts/` and compile the one you want. The indicator package is in `FlashGold_Direction_Filter_v1_2_Gold_M1/`: copy its `MQL5/Indicators` and `MQL5/Include/FlashGold` folders into your MT5 data folder.

FGF inputs:
- `UseFGF_Filter` turns the filter on or off.
- `FGF_IndicatorName` is the indicator's path under `MQL5/Indicators`.
- `FGF_CalcTimeframe` is the chart timeframe the indicator runs on. The default is the trigger timeframe.
- `FGF_Shift` picks the bar to read: 0 is the live permission, 1 is the last closed bar.
- `FGF_BlockIfUnavailable` blocks trading until the indicator has data.
- `FGF_PassInputs` sends the `FGF_*` indicator settings below it (filter and parent timeframe, level, window, check mode, band, against, hold, burst, any-combo, zones, alignment) to the indicator. Off by default, which runs the indicator's own defaults.

**What the FlashGold backtest shows** (Python port of the indicator, audited against its MQL5 core):
- On the M3/H1 preset, the default filter keeps 28 of 77 trades and raises PF from 2.48 to 3.18, but total profit falls from +20.8R to +8.7R.
- Across about 10,000 EA setups on all 13 timeframe pairs, the default filter left the median PF unchanged (0.92) and raised it in only 54% of setups. It helped on M3 triggers (PF up in 59-85% of M3 setups) and hurt on M1 triggers and M2/H1.
- Only the "until next signal" permission window keeps a useful number of trades. The minutes and candles windows let almost nothing through on a live feed.
- Filter settings chosen on 2025 kept beating the unfiltered EA in 2026 on M3/H1, but not on M2/H1.

The FGF preset is `presets/XLZC_Bearish_M3_H1_NY_FGF.set`. Run both versions in the MT5 Strategy Tester to compare them on your broker.
