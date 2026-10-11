# FlashGold v5 BTC builds for MEXC: percent commission, MEXC slippage, 0.1 % equity risk

The four BTC exports were re-swept with MEXC USDT-M perpetual costs instead of the VT Markets
header: taker 0.02 % of traded value per side, $1 spread, $2 slippage per side
(`flashgold_backtest_mexc.py`, the September backtester with a percent-commission term).
Same 5,120-cell grid per timeframe, same ranking (at least 30 trades, same-bar fraction at most
0.5, score = min(PF, PF first half, PF second half), tie-break win rate).

Each script carries its best cell as the input defaults and:

- `commission_type = strategy.commission.percent, commission_value = 0.02` (per side)
- `slippage = 20` ticks per side (MEXC BTCUSDT.P mintick 0.1, so $2)
- Sizing: `Quantity = Risk %`, `riskPct = 0.1` (0.1 % of equity per trade, qty = equity x 0.1 % / stop distance), max 2 BTC, step 0.001
- Spread input 10 pts ($1); the Points-mode defaults assume mintick 0.1

Load each on MEXC:BTCUSDT.P at the chart timeframe in the file name.

| File | Zones | Signal | Dist ATR | Hold | SL ATR | TP R | Trail | Close opp | Trades | Win | Net per BTC | PF | PF h1 / h2 | Max DD | Grid positive |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FlashGold_v5_MEXC_BTCUSDT_5m.pine | chart only | burst 0.5 | 0.25 | 3 | 1.5 | 3.0 | on | off | 44 | 57% | +1,289 | 1.48 | 1.45 / 1.52 | 726 | 20% |
| FlashGold_v5_MEXC_BTCUSDT_15m.pine | chart, 2x, 4x, 8x (3 aligned) | burst 0.5 | 0.25 | 0 | 3.0 | 3.0 | on | on | 52 | 83% | +6,279 | 2.54 | 2.55 / 2.53 | 1,535 | 56% |
| FlashGold_v5_MEXC_BTCUSDT_30m.pine | chart, 2x, 4x (2 aligned) | any combo | 0.1 | 3 | 3.0 | 0.5 | on | on | 30 | 80% | +4,802 | 2.65 | 2.68 / 2.64 | 1,032 | 58% |
| FlashGold_v5_MEXC_BTCUSDT_60m.pine | chart, 2x, 4x, 8x (3 aligned) | burst 0.25 | 0.1 | 0 | 3.0 | 2.0 | off | off | 32 | 50% | +15,258 | 2.53 | 2.80 / 2.37 | 3,214 | 71% |

Net is per 1 BTC fixed, as swept; with 0.1 % risk sizing on 100k the position is about 0.03 to
0.1 BTC, so scale the net accordingly. PF and win rate do not depend on size. Data: 15m to 60m are
CRYPTO:BTCUSD exports of 1 to 4 weeks, 5m is MEXC:BTCUSDT 7.8 days. Treat every PF as an upper
bound. 5m stays weak: only 20 % of the grid is positive at MEXC costs.

`results/` holds the full MEXC sweep per timeframe and the top 10 per timeframe.
