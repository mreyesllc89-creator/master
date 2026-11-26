# AMVI calibration on BTCUSDT (tools)

Calibration of `AMVI_FGF_Inverted_XAUUSD_15m.pine` (the closed-candle version) on the Binance
BTCUSDT perpetual, for chart timeframes 1m, 2m, 3m, 5m, 10m, 15m, 30m, 1h and 4h. The result
is in `REPORT.md`; the calibrated files are in `presets/`.

Nothing here runs on TradingView. Every number comes from a Python copy of the script.

## Layout

| Path | What it is |
|---|---|
| `REPORT.md` | findings, method, results per timeframe, caveats |
| `presets/` | one `.pine` file per timeframe: the script with other input defaults |
| `results/` | hold-out and plateau tests, final numbers and trade lists per timeframe |
| `tools/` | the Python copy of the script and the calibration steps |
| `data/` | 1-minute bars and funding (not in git; `tools/fetch_1m.py` rebuilds it) |

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
| `plateau.py` | are the neighbours of a candidate profitable too? Fixes the pick |
| `untouched_check.py` | do the candidates of the search window beat random settings on 2021-2023? |
| `trailing_study.py` | the same settings with and without a trailing stop, every activation and offset |
| `inputs_summary.py` | the search's settings grouped by one input's value (`results/INPUTS.md`) |
| `final_eval.py` | all numbers for one setting, including the untouched 2021-2023 period |
| `report.py` | verdict per timeframe, calibrated files, trade lists, tables |
| `charts.py` | equity curves of the picks |
| `make_pine.py` | writes a calibrated file: input defaults only, never the logic |
| `test_orders.py` | hand-computed order scenarios |
| `difftest.py`, `ref/` | the engine against two reference versions written independently from the Pine source |
| `test_fine.py` | the second-by-second order walk against walking every single second |
| `run_all.sh` | everything, in order |

## Conventions

- Decisions at the candle close, market fills at the next open (the script's closed-candle
  engine with Script executions = "On bar close").
- Stops, targets and trailing stops fill on the second-by-second trade prices: inside every
  minute in which an order could fill, the minute's one-second bars are walked (open, nearer
  extreme, other extreme, close). Minutes in which nothing can fill are skipped; the result is
  the same as walking every second (`test_fine.py`).
- A minute without a trade is not a bar (369 such minutes in the exchange's files, exchange
  outages), as on TradingView.
- Costs: 0.05 % commission per side, 1 tick slippage on market and stop fills, Binance funding
  (the crypto lab's rule). Stress: 0.10 % per side and 3 ticks.
- Results are in R: 1 R = Stop Loss x ATR at the signal = the amount risked per trade with the
  script's Risk % sizing.
- Search window 2023-11-01 to 2026-10-31 (36 months). The period 2021-01-01 to 2023-10-31 is
  not used by the search or the selection; each timeframe's pick is run on it once at the end.
- Seconds timeframes are not calibrated: there is no long seconds history to test them on.

## Rebuild

```bash
sh tools/run_all.sh
```
