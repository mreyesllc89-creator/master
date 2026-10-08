# FlashGold v5 EA presets

Spread-aware simulation of the EA logic: live bid/ask (BTC spread $12, gold $0.25),
stop widened by the spread at fill, partial closed on the bid/ask, breakeven at bar
close, slippage on stops ($3 BTC, $0.03 gold), gold commission $0.035/oz/side.
Every setting was scored under two intrabar fill models:

- **4-tick** (TradingView: open-high-low-close), and
- **pessimistic** (if the stop is inside the fill bar, the stop is hit first).

Only settings profitable under **both** are kept. Check on real data: gold 60m trades
replayed on the real 15m path (Oct 5-8) matched the 4-tick model for wide stops
(SL 50-80 pips) but **lost with tight stops** (10-20 pips: +711 model vs -105 real).

| Symbol | TF | Result | Preset |
|---|---|---|---|
| BTCUSD | 1h, 2h | no setting profitable under both models | - |
| BTCUSD | **4h** | win 24-33%, PF 1.04-1.52, 30 trades | `FlashGoldV5_BTCUSD_H4.set` |
| XAUUSD | 5m, 15m | no setting profitable under both models | - |
| XAUUSD | **30m** | win 21-37%, PF 1.12-2.42, 19 trades | `FlashGoldV5_XAUUSD_M30.set` |
| XAUUSD | **1h** | win 22%, PF 1.89 (both models, real 15m path confirms), 18 trades | `FlashGoldV5_XAUUSD_H1.set` |
| XAUUSD | 2h, 4h | no setting profitable under both models | - |

Data: MEXC BTCUSDT 60m Sep 6 - Oct 8 2026 (2h/4h resampled); OANDA XAUUSD 60m Sep 21 - Oct 8,
15m Oct 5-8, 5m Oct 7-8 (30m/2h/4h resampled). Small samples: confirm in the MT5 Strategy
Tester ("Every tick based on real ticks") and on demo before live trading.
