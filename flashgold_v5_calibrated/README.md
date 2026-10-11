# FlashGold v5: one calibrated strategy per export

Thirteen copies of the FlashGold v5 Strategy MTF template, each with the best cell of the
September 2026 exit sweep (`calibration/results/fg/sweep_*.csv`, branch
`claude/confident-einstein-uzfabw`) written in as the input defaults. Load each file on the
symbol and chart timeframe in its name; no inputs need changing.

Ranking: at least 30 trades, same-bar fraction at most 0.5, score = min(PF, PF first half,
PF second half), tie-break win rate. Every file is the best of 5,120 cells on days to months of
data, so treat the profit factor as an upper bound. The sweep's own picks for live use were
XAUUSD 60m, SPX500 15m and BTCUSD 60m.

| File | Trades | Win | PF | Note |
|---|---|---|---|---|
| FlashGold_v5_XAUUSD_5m.pine | 37 | 76% | 1.23 | thin edge, not recommended |
| FlashGold_v5_XAUUSD_10m.pine | 70 | 36% | 1.29 | thin edge, not recommended |
| FlashGold_v5_XAUUSD_15m.pine | 43 | 67% | 2.15 | |
| FlashGold_v5_XAUUSD_30m.pine | 31 | 55% | 2.61 | |
| FlashGold_v5_XAUUSD_60m.pine | 88 | 72% | 1.95 | |
| FlashGold_v5_BTCUSD_5m.pine | 40 | 65% | 1.77 | swept on MEXC BTCUSDT, 10% of grid positive |
| FlashGold_v5_BTCUSD_15m.pine | 30 | 80% | 2.24 | |
| FlashGold_v5_BTCUSD_30m.pine | 37 | 73% | 2.30 | |
| FlashGold_v5_BTCUSD_60m.pine | 31 | 52% | 2.57 | |
| FlashGold_v5_SPX500_1m.pine | 42 | 62% | 2.23 | |
| FlashGold_v5_SPX500_15m.pine | 46 | 83% | 1.95 | |
| FlashGold_v5_SPX500_30m.pine | 51 | 78% | 2.71 | |
| FlashGold_v5_SPX500_60m.pine | 36 | 89% | 4.96 | few trades, PF not to be trusted |

Cost headers are per symbol (VT Markets): gold 0.13 USD per oz and 5 ticks, SPX 0.25 points and
10 ticks (placeholder), BTC 10.5 USD and 500 ticks. For Bitget BTCUSDT switch the header to
percent commission 0.06 per side as in `flashgold_v5_strategy_btcusdt_10m.pine` on branch
`claude/epic-faraday-deqlp1`.

`results/` holds the top 10 cells per export (Markdown, CSV, Excel).
