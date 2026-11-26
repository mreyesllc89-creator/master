# AMVI calibration on BTCUSDT (tools)

Calibration of `AMVI_FGF_Inverted_XAUUSD_15m.pine` (the closed-candle version) on the Binance
BTCUSDT perpetual, for chart timeframes 1m, 2m, 3m, 5m, 10m, 15m, 30m, 1h and 4h. The result
is in `REPORT.md`; the calibrated files are in `presets/`.

Nothing here runs on TradingView. Every number comes from a Python copy of the script.

## Layout

| Path | What it is |
|---|---|
| `REPORT.md` | findings, method, results per timeframe, caveats |
| `presets/` | a `.pine` file for every timeframe whose pick holds up on the untouched period: the script with other input defaults |
| `results/` | hold-out and plateau tests, final numbers and trade lists per timeframe; `results/checks/` holds the logs of the engine checks |
| `REPORT_src.md`, `REPORT_tables.md` | the hand-written text and the generated tables that `tools/assemble_report.py` joins into `REPORT.md` |
| `tools/` | the Python copy of the script and the calibration steps |
| `data/` | 1-minute bars, funding and one-second bars (not in git; step 1 of `tools/run_all.sh` rebuilds it: `fetch_1m.py`, the funding call, `fetch_1s.py`) |

## Tools

| File | Step |
|---|---|
| `fetch_1m.py` | Binance USDT-M 1-minute bars from the public archive |
| `fetch_1s.py` | one-second bars built from the archive's trade-by-trade files |
| `bars.py` | timeframes built from the 1-minute bars the way TradingView builds them |
| `pineta.py` | Pine built-ins (`ta.rma`, `ta.atr`, `ta.rsi`, `ta.stdev`, ...) bar for bar |
| `amvi_engine.py` | the script: AMVI trigger, FlashGold filter zone, order simulation |
| `space.py` | the search space: every input that changes a trade |
| `sweep.py` | random search, one chart timeframe at a time |
| `holdout.py` | does the best of one part of the window work on another part? |
| `plateau.py` | are the neighbours of a candidate profitable too (a screen against fragility)? Fixes the pick |
| `untouched_check.py` | do the candidates of the search window beat random settings on 2021-2023? |
| `trailing_study.py` | the same settings with and without a trailing stop, every activation and offset |
| `inputs_summary.py` | the search's settings grouped by one input's value (`results/INPUTS.md`) |
| `direction_by_filter.py` | the two trade directions by filter timeframe, with a luck test (`results/direction_by_filter.txt`) |
| `luck.py` | the same counts in no-skill worlds: what luck alone would produce |
| `convergence.py` | the picks with orders walked on chart candles, 1-minute, 15s, 5s and 1s bars |
| `final_eval.py` | all numbers for one setting, including the untouched 2021-2023 period |
| `report.py` | verdict per timeframe, calibrated files (PAPER-TRADE and better), trade lists, tables |
| `charts.py` | equity curves of the picks; trade direction and cost per timeframe |
| `assemble_report.py` | `REPORT.md` = the hand-written `REPORT_src.md` with the generated tables put in |
| `make_pine.py` | writes a calibrated file: input defaults only, never the logic |
| `check_outputs.py` | the trade lists and the calibrated files checked against the records and the shipped script |
| `replicate_picks.py` | the picked settings against the reference versions: signals bar for bar, the filter zone against a literal copy of the filter, orders trade for trade |
| `test_orders.py` | hand-computed order scenarios |
| `difftest.py`, `ref/` | the engine against two reference versions written independently from the Pine source: `ref_signals.py` (signal side only) and `ref_orders.py` (order side only, given the engine's signals); `ref_filter.py` is a statement-by-statement copy of the filter |
| `test_lookahead.py` | prices after a time T replaced by another path: nothing the engine shows for candles closed by T may change |
| `test_fine.py` | the second-by-second order walk against walking every single second |
| `seconds_coverage.py` | how completely the one-second bars cover the 1-minute bars |
| `tester_view.py` | what TradingView's tester will show differently from a file's trade list: exits on chart candles, the Deep Backtesting check (period against date range), and entries at the start of an ordinary chart for every plan size, with and without the filter's earlier history |
| `run_all.sh` | everything, in order |

## Conventions

- Decisions at the candle close, market fills at the next open (the script's closed-candle
  engine with Script executions = "On bar close").
- Stops, targets and trailing stops fill on the second-by-second trade prices: inside every
  minute in which an order could fill, the minute's one-second bars are walked (open, nearer
  extreme, other extreme, close). Minutes in which nothing can fill are skipped; the result is
  the same as walking every second (`test_fine.py`).
- An empty row of the exchange's 1-minute file is not a bar. There are 367 of them from 2021-01
  to 2026-10; in 192 (all between 2023-11 and 2025) the trade-by-trade files do show a trade,
  so TradingView may have a candle there (`results/checks/seconds_coverage.txt`).
- In 27 minutes the one-second prices contradict the exchange's own 1-minute bar (off-market
  prints); the 1-minute bar is used there.
- Costs: 0.05 % commission per side, 1 tick slippage on market and stop fills, Binance funding
  (the crypto lab's rule). Stress: 0.10 % per side and 3 ticks.
- Results are in R: 1 R = Stop Loss x ATR at the signal = the amount risked per trade with the
  script's Risk % sizing.
- Search window 2023-11-01 to 2026-10-31 (36 months). The period 2021-01-01 to 2023-10-31 is
  not used by the search or the selection; each timeframe's pick is run on it once at the end.
- Seconds timeframes (1s to 45s) are not calibrated: the engine builds its indicators from
  1-minute bars; the one-second bars only fill the orders.
- Verdicts, from best to worst: RECOMMENDED, USABLE, PAPER-TRADE, NOT RECOMMENDED, DO NOT
  TRADE (`tools/report.py`; `REPORT.md` section 3). A file is written for PAPER-TRADE and
  better and carries its verdict in its title.

## Rebuild

```bash
sh tools/run_all.sh
```
