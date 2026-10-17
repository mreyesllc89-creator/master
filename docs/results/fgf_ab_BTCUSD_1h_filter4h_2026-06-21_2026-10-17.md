# FlashGold Direction Filter: off vs on

Data: TradingView export CRYPTO:BTCUSD 1H, 60m chart, 2818 bars; scored 2026-06-24 17:00 to 2026-10-17 02:00 UTC (after 3 warm-up days), halves split at 2026-08-20 21:30.
Strategy: FlashGold v5 (BTCUSD FGF build) input defaults, exits Pips, 10 contracts. Filter: 240m, band 0.25 ATR, against on. Costs: 0.02% per side + 5 ticks slippage per side.

| Fills | Costs | Filter | Trades | Net | Net/trade | PF | Win | Max DD | H1 net | H2 net | Signals blocked |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TradingView | no costs | off | 321 | 218046 | 679.3 | 4.53 | 33% | 5370 | 56283 | 161763 | - |
| TradingView | no costs | on | 207 | 177098 | 855.5 | 5.36 | 32% | 5124 | 42988 | 134110 | 199 |
| TradingView | with costs | off | 321 | 125453 | 390.8 | 1.99 | 14% | 15435 | 14226 | 111227 | - |
| TradingView | with costs | on | 207 | 117438 | 567.3 | 2.42 | 14% | 17442 | 15856 | 101581 | 199 |
| worst case | no costs | off | 321 | 211205 | 658.0 | 4.22 | 29% | 7147 | 50304 | 160902 | - |
| worst case | no costs | on | 207 | 174850 | 844.7 | 5.12 | 29% | 5574 | 41458 | 133392 | 198 |
| worst case | with costs | off | 321 | 118698 | 369.8 | 1.89 | 13% | 17982 | 7989 | 110709 | - |
| worst case | with costs | on | 207 | 115190 | 556.5 | 2.34 | 13% | 18432 | 14327 | 100863 | 198 |

## Filter on minus filter off (net)

| Fills | Costs | All | H1 | H2 |
|---|---|---|---|---|
| TradingView | no costs | -40948 | -13295 | -27653 |
| TradingView | with costs | -8015 | +1631 | -9646 |
| worst case | no costs | -36355 | -8845 | -27510 |
| worst case | with costs | -3508 | +6338 | -9846 |

## Filter on vs 50 random filters keeping the same share of signals (62%)

Beats = the share of random filters whose net the real filter beats.

| Fills | Costs | Filter on: all / H1 / H2 | Random median: all / H1 / H2 | Beats: all / H1 / H2 |
|---|---|---|---|---|
| TradingView | no costs | 177098 / 42988 / 134110 | 157247 / 41744 / 114065 | 86% / 54% / 82% |
| TradingView | with costs | 117438 / 15856 / 101581 | 92499 / 12815 / 78363 | 88% / 60% / 86% |
| worst case | no costs | 174850 / 41458 / 133392 | 152666 / 38548 / 112818 | 90% / 62% / 82% |
| worst case | with costs | 115190 / 14327 / 100863 | 88145 / 9172 / 78099 | 90% / 66% / 86% |

**Read it this way:** the filter earns its place only if, in the worst-case, with-costs row, it beats at least 90% of the random filters on the whole period AND in each half. Beating "filter off" is not enough: any filter that trades less pays less in costs.

**Verdict:** NOT SHOWN (worst case, with costs: beats 66% of random filters in its weakest of all / H1 / H2).

Fills: "TradingView" walks each bar open -> nearer extreme -> other extreme -> close and fills stops at their price (plus slippage); "worst case" moves price against an open position first inside every bar. This is a replica on OHLC bars, not TradingView itself: expect the trade counts to differ a little from the Strategy Tester.
