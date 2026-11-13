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

## Run 2 (2026-11-13)

`run2_20261113/` holds a second, wider calibration: every entry style and trade
direction searched separately (about 207,000 combinations), stricter acceptance,
and a check on 12 days of data published after run 1.

- `run2_20261113/CALIBRATION_REPORT.md` - results, what changed, caveats.
- `run2_20261113/TOP20.md` and `top20/` - ten gold and ten BTC presets across timeframes.
- `run2_20261113/presets/` - up to three presets per symbol and timeframe.
- `run2_20261113/data/` - tables, including how the run-1 presets did on the unseen days.
