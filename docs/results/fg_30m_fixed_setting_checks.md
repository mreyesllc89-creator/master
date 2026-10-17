# FlashGold v5, 30m, partial + runner, burst 1: fixed-setting checks

The 30m setting was chosen by `tools/fg_sweep` on BTCUSD 2026-05-30..08-22
and held out of sample 2026-08-22..10-17. Below it is run UNCHANGED on data
it was not chosen on. Worst-case fills, 0.02% commission per side + slippage,
10 contracts, filter off. Engine: tools/fgf_ab/fg5.py.

| Data (never used to choose) | Setting | Trades | Net | PF | Max DD | Halves |
|---|---|---|---|---|---|---|
| BTCUSD 15m export, 2025-08-06..2026-05-24, 5 ticks | SL 2 ATR / TP 3R | 437 | +376,357 | 1.19 | 132,154 | +213,326 / +163,031 |
| same, $5 slippage | SL 2 ATR / TP 3R | 437 | +338,968 | 1.17 | 143,119 | +190,634 / +148,334 |
| same, 5 ticks | SL 3 ATR / TP 2R | 393 | +461,254 | 1.22 | 175,245 | +137,431 / +323,823 |
| same, $5 slippage | SL 3 ATR / TP 2R | 392 | +432,875 | 1.21 | 176,913 | +124,323 / +308,552 |
| ETHUSD 5m export, 2026-05-30..10-17, 5 ticks | SL 2 ATR / TP 3R | 198 | -1,264 | 0.95 | 5,004 | -2,724 / +1,460 |
| same | SL 3 ATR / TP 2R | 175 | +7,146 | 1.28 | 4,226 | -518 / +7,664 |
| OANDA XAUUSD 5m export, 2026-03-27..10-16, 5 ticks | SL 2 ATR / TP 3R | 203 | -4,585 | 0.88 | 6,562 | -3,850 / -735 |
| same | SL 3 ATR / TP 2R | 183 | -883 | 0.98 | 6,336 | -2,253 / +1,370 |

- **BTC: holds** on ten earlier months, both settings, both slippage levels,
  both halves positive (~400 trades). The drawdown (130-180k on ~$1M
  notional) is large next to PF 1.2: size accordingly.
- **ETH: not shown** (one setting slightly negative, the other negative in
  its first half). **Gold: fails** - but 0.02% of notional (~$0.87 per oz per
  side) is harsher than a typical gold spread; re-run with the broker's
  real cost before ruling it out.
- The BTC 15m export gives the 30m chart only two intrabar points per
  candle (15m candles); with 2-3 ATR stops that matters little.

## Signal parity with TradingView (30m build settings)

FlashGold v5 indicator export, CRYPTO:BTCUSD 30m, 2026-08-04..10-17 (3,525
candles, burst 1.0): the Python engine gives the same BUY / SELL on 100% of
candles after warm-up (143 buys, 124 sells, all matched) and the same entry
prices (largest difference 0.00000001). A 300-candle 15m export (3 days)
agrees on 99% of candles; the misses are on the first candles, before ATR /
RSI and the x4 zone have enough history.
