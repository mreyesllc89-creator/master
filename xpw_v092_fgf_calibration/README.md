# XPW v0.9.2 + FlashGold EA input calibration

Calibration of `XPW_ShapeMap_v092_FGF_EA` inputs for XAUUSD and BTCUSD across
M1, M5, M15, M30, H1 and H4, produced 2026-11-06 from the
`XPW_v092_FGF_LATEST_20261105.zip` source handoff.

- `CALIBRATION_REPORT.md` - method, results, caveats.
- `presets/` - complete 157-input `.set` files for the combinations that were
  profitable in-sample, out-of-sample and under 2x trading costs. Live gates
  stay disabled (`EnableTrading=false`, `FenceAllowExecution=false`).
- `data/` - search summary, accepted presets table, and every evaluated
  candidate's metrics per symbol/timeframe.
- `tools/` - the Python/numba replica of the EA logic and the search scripts
  (see the report's "Reproduce" section).

These are backtest results from a Python port of the EA's decision logic on
Binance 1-minute history (PAXG as the gold proxy), not MT5 Strategy Tester or
broker results. Re-test in MT5 with real tick data before relying on any preset.
