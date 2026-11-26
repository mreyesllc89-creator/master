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
| `bars.py` | timeframes built from the 1-minute bars the way TradingView builds them |
| `pineta.py` | Pine built-ins (`ta.rma`, `ta.atr`, `ta.rsi`, `ta.stdev`, ...) bar for bar |
| `amvi_engine.py` | the script: AMVI trigger, FlashGold filter zone, order simulation |
| `space.py` | the search space: every input that changes a trade |
| `sweep.py` | random search, one chart timeframe at a time |
| `holdout.py` | does the best of one part of the window work on another part? |
| `plateau.py` | are the neighbours of a candidate profitable too? |
| `final_eval.py` | all numbers for one setting, including the untouched 2021-2023 period |
| `report.py` | verdict per timeframe, calibrated files, trade lists, tables |
| `make_pine.py` | writes a calibrated file: input defaults only, never the logic |
| `test_orders.py` | hand-computed order scenarios |
| `difftest.py`, `ref/` | the engine against two reference versions written independently from the Pine source |
| `run_all.sh` | everything, in order |

## Conventions

- Decisions at the candle close, market fills at the next open (the script's closed-candle
  engine with Script executions = "On bar close").
- Stops, targets and trailing stops fill on the 1-minute bars inside each chart candle, each
  walked open, nearer extreme, other extreme, close.
- Costs: 0.05 % commission per side, 1 tick slippage on market and stop fills, Binance funding
  (the crypto lab's rule). Stress: 0.10 % per side and 3 ticks.
- Results are in R: 1 R = Stop Loss x ATR at the signal = the amount risked per trade with the
  script's Risk % sizing.
- Search window 2023-11-01 to 2026-11-25. The period 2021-01-01 to 2023-10-31 is not used by
  the search or the selection; each timeframe's pick is run on it once at the end.
- Seconds timeframes are not calibrated: there is no long seconds history to test them on.

## Rebuild

```bash
sh tools/run_all.sh
```
