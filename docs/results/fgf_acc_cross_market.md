# "Reverse an old signal": BTC, ETH and gold side by side

Rule: when the last FlashGold filter signal is 9+ filter candles old, call
the OPPOSITE of its direction. Accuracy averages buys and sells (50% = coin
flip); in brackets the number of distinct signals and the 95% interval
re-sampled by signal. Whole period after a 5-day warm-up. Data: TradingView
5m exports, BTCUSD and ETHUSD 2026-05-25..10-17, OANDA XAUUSD 2026-03-22..10-16.

| Filter TF | Close 6 candles later: BTC / ETH / XAU | Close 12 candles later: BTC / ETH / XAU |
|---|---|---|
| 15m | 53.5% (242) / 53.1% (295) / 54.2% (306) | 55.1% (242) / 51.8% (293) / 55.1% (306) |
| 30m | 50.7% (137) / 54.1% (166) / 53.3% (145) | 50.7% (136) / 62.1% (166) / 52.9% (145) |
| 1H | 43.5% (86) / 45.2% (82) / 48.2% (75) | 44.9% (85) / 49.4% (82) / 51.7% (75) |
| 2H | 64.3% (42) / 60.2% (50) / 49.2% (36) | 72.2% (41) / 55.9% (49) / 56.9% (36) |
| 4H | 51.0% (19) / 65.1% (22) / 70.2% (17) | 52.6% (19) / 59.7% (22) / 62.7% (17) |

Pooled over the three markets:

| Filter TF | Close +6 | Close +12 |
|---|---|---|
| 15m | 53.5% (843 signals, 50.5 - 56.3%) | 53.9% (841 signals, 50.5 - 57.1%) |
| 1H | 45.4% (243 signals, 40.4 - 50.1%) | 48.3% (242 signals, 42.2 - 54.3%) |

What it says:
- **15m is the only row above 50% in all three markets**, by 3-5 points,
  with hundreds of signals each. Pooled, the interval just clears 50%.
- **1H points the other way** in all three (43-52%). A real "the burst ends
  the move" effect should not flip sign between 15m and 1H, so treat the
  15m edge as unproven.
- The big 2H / 4H numbers (60-72%) rest on 17-50 signals and disagree across
  markets: noise until shown otherwise.
- The 15m row was picked after seeing this table (5 timeframes x 2
  horizons), so it is a lead, not a result. The clean test is fresh data:
  the same rule, unchanged, on exports from after 2026-10-17.
