# FlashGold v5: exits per timeframe (walk-forward)

Data: TradingView export CRYPTO:BTCUSD 5m, 5m candles. In-sample 2026-05-30 to 2026-08-22, out-of-sample 2026-08-22 to 2026-10-17 (never used to choose).
10 contracts, costs 0.02% per side + 500 ticks. Filter off, default signal.
Grid per timeframe: stop [0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0] ATR x target [1.0, 2.0, 3.0, 5.0] R x ['Fixed', 'Partial + runner'] x burst [0.5, 1.0] = 112 settings, scored worst case with costs.
Chosen = best plateau (median of the cell and its stop/target neighbours) among cells with >= 30 in-sample trades and both in-sample halves positive.

| Chart | Eligible / tried | Chosen | IS trades, net, PF | OOS worst+costs: trades, net, PF, max DD | OOS halves | OOS no costs (TV fills) | Verdict |
|---|---|---|---|---|---|---|---|
| 5m | 0 / 112 | - | - | - | - | - | **none passes in-sample** |
| 15m | 0 / 112 | - | - | - | - | - | **none passes in-sample** |
| 30m | 4 / 112 | SL 3 ATR, TP 2R, Partial + runner, burst 1 | 119, 116043, 1.30 | 76, 69872, 1.23, 76620 | 6756 / 63117 | 102376 | **holds** |
| 60m | 7 / 112 | SL 3 ATR, TP 3R, Partial + runner, burst 1 | 58, 114579, 1.42 | 41, -42368, 0.82, 108836 | -50592 / 8224 | -27727 | **fails** |
| 120m | 45 / 112 | SL 3 ATR, TP 5R, Partial + runner, burst 0.5 | 59, 103163, 1.35 | 32, -9504, 0.94, 38306 | 15370 / -24873 | 7 | **fails** |

**Verdict:** *holds* = out of sample, worst case with costs, net positive in both halves with >= 20 trades. *fails* = it does not. *none passes in-sample* = no setting was positive in both in-sample halves after costs.

How much data this is: about 140 days scored, so the out-of-sample part is only about 56 days of one market. A *holds* here means: keep testing it (new exports, other symbols, demo), not: trade it.

The full in-sample grid is in the `_insample_grid.csv` next to this report.
