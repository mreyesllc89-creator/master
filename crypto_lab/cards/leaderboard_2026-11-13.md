# Judge — 2026-11-13 (first pass, run manually; corrected rerun)

Gauntlet: every library strategy × BTC/ETH/SOL × 1h and 5m; taker fee 0.05 %/side, funding, 1 tick slippage, 0.5 % risk, 5x cap;
rolling walk-forward (6 m train / 3 m test, 11 test windows May-2024 → Nov-2026); only out-of-sample trades are shown.
Stressed = double fees + 3 ticks. Scores 1-5 on profit / drawdown / trades / losing streak / regimes (0 = fewer than 50 OOS trades).

**Leak found and fixed before judging:** hourly OI / long-short rows were stamped at the start of their hour while holding data from
its end, so on 5-minute bars every OI-based strategy saw ~55 minutes into the future. Before the fix the 5m OI strategies showed
+45 % to +134 % OOS; after the fix every 5m strategy is negative. The fix is in `tools/fetch_binance.py` (rows now stamped at hour end).

## Leaderboard (all 67 strategy/symbol/timeframe combinations)

| Strategy | Symbol | TF | OOS trades | Return | PF | Max DD | Losing streak | Avg R | Stressed return | Score |
|---|---|---|---|---|---|---|---|---|---|---|
| oi_flush_continuation | ETHUSDT | 1h | 430 | +25.7 % | 1.18 | 11.5 % | 13 | +0.101 | +10.7 % | 17 |
| funding_time_premium | SOLUSDT | 1h | 127 | +1.3 % | 1.07 | 2.4 % | 5 | +0.022 | -4.0 % | 16 |
| asia_open_fade | ETHUSDT | 1h | 181 | -1.2 % | 0.97 | 7.9 % | 6 | -0.012 | -7.8 % | 14 |
| asia_open_fade | BTCUSDT | 1h | 193 | -7.4 % | 0.85 | 9.9 % | 6 | -0.073 | -18.5 % | 14 |
| donchian_trend | ETHUSDT | 1h | 273 | +3.1 % | 1.03 | 9.3 % | 13 | +0.040 | -2.4 % | 13 |
| btc_leads | ETHUSDT | 1h | 518 | +0.1 % | 1.00 | 16.6 % | 13 | +0.002 | -17.4 % | 13 |
| asia_open_fade | SOLUSDT | 1h | 173 | -3.9 % | 0.90 | 9.5 % | 12 | -0.040 | -9.0 % | 13 |
| oi_flush_continuation | BTCUSDT | 1h | 711 | -6.1 % | 0.97 | 21.2 % | 15 | -0.011 | -39.3 % | 12 |
| crowded_unwind | ETHUSDT | 1h | 293 | -8.9 % | 0.91 | 21.0 % | 7 | -0.056 | -18.6 % | 12 |
| weekend_fade | BTCUSDT | 1h | 289 | -14.7 % | 0.80 | 18.3 % | 9 | -0.098 | -26.6 % | 12 |
| btc_leads | SOLUSDT | 1h | 435 | -19.4 % | 0.84 | 25.0 % | 10 | -0.082 | -30.9 % | 12 |
| weekend_fade | ETHUSDT | 1h | 310 | -21.9 % | 0.75 | 24.4 % | 10 | -0.141 | -31.2 % | 12 |
| session_open_drift | SOLUSDT | 1h | 1358 | -26.2 % | 0.92 | 42.8 % | 11 | -0.036 | -63.7 % | 12 |
| weekend_fade | SOLUSDT | 5m | 1287 | -86.0 % | 0.80 | 93.7 % | 12 | -0.167 | -137.0 % | 12 |
| funding_reset | SOLUSDT | 5m | 53 | -1.1 % | 0.95 | 10.5 % | 13 | -0.016 | -5.1 % | 11 |
| oi_flush_reversal | ETHUSDT | 1h | 532 | -19.2 % | 0.89 | 27.2 % | 9 | -0.064 | -37.3 % | 11 |
| session_open_drift | ETHUSDT | 1h | 1372 | -21.8 % | 0.94 | 30.6 % | 10 | -0.024 | -72.2 % | 11 |
| oi_flush_reversal | SOLUSDT | 1h | 372 | -21.9 % | 0.80 | 26.0 % | 10 | -0.118 | -31.5 % | 11 |
| asia_open_fade | SOLUSDT | 5m | 297 | -27.4 % | 0.68 | 28.4 % | 9 | -0.190 | -62.1 % | 11 |
| crowded_unwind | SOLUSDT | 1h | 443 | -40.1 % | 0.72 | 41.3 % | 10 | -0.182 | -51.8 % | 11 |
| range_breakout | ETHUSDT | 5m | 631 | -59.6 % | 0.72 | 66.0 % | 10 | -0.196 | -111.4 % | 11 |
| session_open_drift | BTCUSDT | 1h | 1347 | -64.8 % | 0.79 | 75.7 % | 11 | -0.103 | -114.3 % | 11 |
| taker_exhaustion | SOLUSDT | 1h | 2235 | -70.9 % | 0.85 | 71.6 % | 11 | -0.069 | -125.1 % | 11 |
| donchian_trend | SOLUSDT | 1h | 253 | -14.6 % | 0.84 | 24.8 % | 20 | -0.092 | -19.0 % | 10 |
| funding_time_premium | SOLUSDT | 5m | 124 | -18.1 % | 0.37 | 19.3 % | 12 | -0.328 | -32.6 % | 10 |
| oi_flush_reversal | BTCUSDT | 1h | 434 | -28.6 % | 0.80 | 34.7 % | 16 | -0.140 | -47.7 % | 10 |
| asia_open_fade | ETHUSDT | 5m | 274 | -32.9 % | 0.62 | 36.9 % | 12 | -0.251 | -72.4 % | 10 |
| weekend_fade | SOLUSDT | 1h | 353 | -35.1 % | 0.66 | 37.5 % | 12 | -0.200 | -43.6 % | 10 |
| oi_flush_continuation | SOLUSDT | 1h | 741 | -38.8 % | 0.80 | 46.9 % | 14 | -0.104 | -56.0 % | 10 |
| btc_leads | ETHUSDT | 5m | 346 | -39.5 % | 0.61 | 39.5 % | 9 | -0.250 | -57.6 % | 10 |
| oi_flush_continuation | ETHUSDT | 5m | 505 | -52.0 % | 0.55 | 52.9 % | 17 | -0.250 | -77.0 % | 10 |
| btc_leads | SOLUSDT | 5m | 509 | -63.0 % | 0.57 | 66.1 % | 15 | -0.280 | -82.6 % | 10 |
| crowded_unwind | ETHUSDT | 5m | 489 | -63.9 % | 0.59 | 64.2 % | 14 | -0.307 | -93.2 % | 10 |
| donchian_trend | SOLUSDT | 5m | 1777 | -88.4 % | 0.85 | 92.3 % | 29 | -0.097 | -138.7 % | 10 |
| donchian_trend | ETHUSDT | 5m | 2289 | -93.3 % | 0.90 | 102.2 % | 23 | -0.063 | -173.6 % | 10 |
| range_breakout | SOLUSDT | 5m | 960 | -96.9 % | 0.75 | 98.1 % | 14 | -0.207 | -164.4 % | 10 |
| taker_exhaustion | ETHUSDT | 5m | 3958 | -123.4 % | 0.49 | 123.5 % | 17 | -0.404 | -45.7 % | 10 |
| taker_exhaustion | BTCUSDT | 1h | 2612 | -138.4 % | 0.73 | 138.3 % | 13 | -0.124 | -197.2 % | 10 |
| session_open_drift | ETHUSDT | 5m | 1309 | -140.6 % | 0.51 | 140.5 % | 13 | -0.341 | -169.4 % | 10 |
| session_open_drift | SOLUSDT | 5m | 1362 | -154.2 % | 0.53 | 153.8 % | 15 | -0.313 | -193.0 % | 10 |
| weekend_fade | ETHUSDT | 5m | 1563 | -158.3 % | 0.64 | 164.0 % | 18 | -0.317 | -187.6 % | 10 |
| taker_exhaustion | SOLUSDT | 5m | 4394 | -167.5 % | 0.70 | 164.4 % | 18 | -0.245 | -99.0 % | 10 |
| crowded_unwind | BTCUSDT | 1h | 101 | -10.1 % | 0.72 | 16.6 % | 16 | -0.203 | -13.9 % | 9 |
| crowded_unwind | BTCUSDT | 5m | 96 | -16.6 % | 0.52 | 18.0 % | 12 | -0.392 | -26.0 % | 9 |
| oi_flush_reversal | BTCUSDT | 5m | 149 | -25.4 % | 0.41 | 25.4 % | 9 | -0.361 | -39.7 % | 9 |
| donchian_trend | BTCUSDT | 1h | 307 | -31.5 % | 0.76 | 35.2 % | 17 | -0.181 | -41.8 % | 9 |
| oi_flush_continuation | SOLUSDT | 5m | 324 | -38.2 % | 0.51 | 38.2 % | 13 | -0.253 | -55.9 % | 9 |
| oi_flush_reversal | ETHUSDT | 5m | 321 | -40.9 % | 0.58 | 47.7 % | 15 | -0.287 | -63.9 % | 9 |
| crowded_unwind | SOLUSDT | 5m | 363 | -45.5 % | 0.62 | 46.0 % | 13 | -0.273 | -67.4 % | 9 |
| oi_flush_continuation | BTCUSDT | 5m | 365 | -47.3 % | 0.54 | 47.0 % | 14 | -0.283 | -79.6 % | 9 |
| taker_exhaustion | BTCUSDT | 5m | 4122 | -89.6 % | 0.39 | 89.7 % | 24 | -0.639 | -14.1 % | 9 |
| taker_exhaustion | ETHUSDT | 1h | 2212 | -99.1 % | 0.77 | 106.6 % | 32 | -0.104 | -148.1 % | 9 |
| range_breakout | BTCUSDT | 5m | 609 | -114.5 % | 0.53 | 115.0 % | 19 | -0.490 | -174.1 % | 9 |
| donchian_trend | BTCUSDT | 5m | 1994 | -151.7 % | 0.73 | 152.2 % | 28 | -0.206 | -185.1 % | 9 |
| session_open_drift | BTCUSDT | 5m | 1319 | -164.7 % | 0.37 | 164.8 % | 20 | -0.540 | -152.6 % | 9 |
| weekend_fade | BTCUSDT | 5m | 1607 | -172.8 % | 0.53 | 171.6 % | 20 | -0.544 | -162.4 % | 9 |
| oi_flush_reversal | SOLUSDT | 5m | 296 | -47.4 % | 0.45 | 48.4 % | 22 | -0.352 | -64.3 % | 8 |
| asia_open_fade | BTCUSDT | 5m | 279 | -59.8 % | 0.38 | 61.1 % | 20 | -0.534 | -107.2 % | 8 |
| range_breakout | SOLUSDT | 1h | 26 | +8.9 % | 1.81 | 7.0 % | 10 | +0.737 | +7.4 % | 0 |
| range_breakout | ETHUSDT | 1h | 11 | +1.4 % | 1.39 | 1.9 % | 3 | +0.285 | +0.8 % | 0 |
| funding_time_premium | ETHUSDT | 1h | 17 | +0.8 % | 1.27 | 2.1 % | 5 | +0.098 | -0.5 % | 0 |
| funding_reset | SOLUSDT | 1h | 3 | +0.4 % | 1.43 | 0.5 % | 2 | +0.305 | +0.3 % | 0 |
| funding_time_premium | BTCUSDT | 1h | 1 | +0.2 % | 99.00 | 0.0 % | 0 | +0.406 | +0.1 % | 0 |
| funding_reset | ETHUSDT | 5m | 4 | +0.0 % | 1.02 | 0.9 % | 3 | +0.189 | -0.3 % | 0 |
| funding_time_premium | BTCUSDT | 5m | 1 | -0.2 % | 0.00 | 0.0 % | 1 | -0.568 | -0.5 % | 0 |
| funding_time_premium | ETHUSDT | 5m | 15 | -4.6 % | 0.10 | 4.9 % | 6 | -0.676 | -7.9 % | 0 |
| range_breakout | BTCUSDT | 1h | 32 | -4.9 % | 0.62 | 7.4 % | 10 | -0.327 | -7.0 % | 0 |

## Verdict: NO CHAMPION TONIGHT

Only one of 67 combinations is positive out-of-sample after costs with enough trades: **oi_flush_continuation on ETHUSDT 1h**
(430 trades, +25.7 %, PF 1.18, 11.5 % max DD, +10.7 % under stressed costs). It fails the final check:

- Not consistent across assets: the same rule loses on BTCUSDT (−6.1 %) and SOLUSDT (−38.8 %). One symbol out of three is the signature of luck, not mechanism.
- Not alive on the newest data: quarterly net R = 2024Q2 −9.1, Q3 +6.9, Q4 +7.9, 2025Q1 +34.0, Q2 +30.7, Q3 −4.1, Q4 +3.1, **2026Q1 −12.3, Q2 −12.6**, Q3 +2.0 (5 trades), Q4 −2.8. Six of eleven quarters positive, but the whole profit sits in 2025 H1; the last three full quarters lose.
- Losing streak 13 and a 33 % win rate with 1.5 ATR stops: fine for the mechanism, but the 2026 drawdown would already have triggered a review.
- Future leakage: inputs are OI (hour-end stamped, shifted one bar) and price; no leak remains after the fix. This one passes.

Closest miss / watch list (not challengers — nothing else is positive): `funding_time_premium SOLUSDT 1h` (+1.3 %, 127 trades, negative under stress),
`donchian_trend ETHUSDT 1h` (+3.1 %, negative under stress). Everything on 5 m loses after costs — 5-minute bars are not viable for these
mechanisms at retail fees; the lab should spend its 5 m budget on cost-light ideas (fewer trades, wider stops) or drop 5 m.

## Strategy card — oi_flush_continuation ETHUSDT 1h (nominated for WATCH only)

- **Idea:** when open interest falls > 4 % over 12 hours while price is down, short for 48 bars (2 days) with a 1.5 ATR stop (walk-forward picked oi_drop 0.04 / hold 48 in 8 of 11 windows, hold 12 in the last three).
- **Why the edge should exist / who pays:** liquidation cascades continue until OI stabilises; the liquidated leveraged longs pay.
- **Entry / exit / stop:** on the 1h close, if OI(t−1h)/OI(t−13h) − 1 < −0.04 and close(t)/close(t−12h) < 1 → short at the next open; exit after 48 bars or at the stop (entry + 1.5 × ATR14); mirror for longs when price is up during the flush.
- **Size:** 0.5 % of equity / stop distance, capped at 5x.
- **Results before / after costs:** gross ≈ +40 % est. (fees+funding+slippage took ≈ 14 pts; estimate, from the stressed run delta); after costs +25.7 %, PF 1.18, avg +0.10 R; stressed +10.7 %, PF 1.07.
- **Walk-forward:** 11 windows, 430 OOS trades; worst month 2024-06 −$711 (−7 %).
- **Longest losing streak:** 13.
- **Condition that kills it:** V-shaped reversals after a flush (2026 H1 pattern) and low-leverage regimes where OI drops without forced selling.
- **First warning sign it is dying:** two consecutive negative quarters — already observed (2026Q1, Q2).
- **WHY THIS COULD FAIL:** it only works on one of three symbols, its profit is concentrated in two quarters of 2025, and the most recent year is negative; the mechanism is real but the 4 %/12 h threshold is a fit to ETH's 2025 liquidation profile.

## Questions for the owner

1. Drop 5 m from the nightly gauntlet (all 34 combinations lose after costs) and spend the time on 1h/4h and cost-light ideas? Default if no answer: keep 5 m but only for ideas with < 10 trades/month.
2. Keep the ETH OI-flush rule on the watch list (paper-logged by the dry-run bot, no orders) so we see whether 2026 H2 revives it? Default: yes, watch only.