# FlashGold Direction Filter: accuracy search

`acc.py` searches for readings of the filter that call direction more often
right than 50%, and checks them on data they were not chosen on.

```
python -I tools/fgf_acc/acc.py CRYPTO_BTCUSD_5.csv --out acc_report.md
```

It rebuilds the filter on 15m, 30m, 1H, 2H and 4H from a 5m export and, at
every filter candle close, scores 8 readings (zone, signal direction, signal
reversed, zone with / against the signal, TDI parent, ...) x 11 conditions
(distance from the level, signal age, volatility) x 5 outcomes (close 1 / 3 /
6 / 12 candles later, 1 ATR reached first) = 2,200 candidates on the first
60% of the data, and reports the 15 most accurate on the last 40%.

Accuracy averages buys and sells (50% = coin flip). A candidate *holds* only
if its out-of-sample 95% interval, re-sampled by whole signals, stays above
50% with at least 20 different signals behind it: calls made under one
signal overlap and move together, so they are not independent.
