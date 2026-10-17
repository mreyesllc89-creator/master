# FlashGold v5, 30m, Points exits SL 5000 / trail 4500 + 1000 / TP 50000 (BTCUSD)

On BTCUSD (tick 0.01): stop $50, trail starts after $45 profit, trails $10
behind, target $500. Burst 1, filter off, 10 contracts, 0.02% per side +
5 ticks. The 30m chart is replayed on its 15m or 5m candles (intrabar path).

| Period | Intrabar path | TradingView fills | Worst case | Pessimistic (trail exits at activation, +$35) |
|---|---|---|---|---|
| 2025-08-06..2026-05-24 | 15m | 834 tr, +357,295, PF 1.78 | 834 tr, +322,790, PF 1.69 | -378,563, PF 0.02 |
| 2026-05-30..10-17 | 15m | 415 tr, +52,737, PF 1.25 | 413 tr, +38,086, PF 1.18 | -153,446, PF 0.08 |
| 2026-05-30..10-17 | **5m** | 420 tr, **+2,895**, PF 1.02 | 419 tr, **-3,744**, PF 0.98 | -140,695, PF 0.09 |

**Same trades, finer data, profit gone:** on the same recent period the
result falls from +38k / +53k (15m path) to about zero (5m path). A $10
trail is ~3% of a 30m candle's range ($310 median ATR); the backtest's
profit comes from guessing where inside the candle the trail was hit, and
the finer the data, the less of it survives. Costs alone are ~$32 per BTC
per round trip at $80k, close to the $35-50 distances. On tick data or
live it is expected to be negative. Your BTCUSD header found the same for
these exits on 60m (+219k in TradingView, +27k worst case, about -12k with
fees).

Compare the ATR exit (SL 2-3 ATR, ~$600-900), which held on the same ten
unseen months: docs/results/fg_30m_fixed_setting_checks.md.
