# Calibration — 2026-11-23

Walk-forward as in the Judge (6 m train / 3 m test, fees + funding + slippage). Timeframes: 1h, 4h. 56 combinations, 524 windows, 24357 out-of-sample trades. Every number below is computed by `tools/calibration.py`; none is an estimate.

## 1. Win rate: promised in-sample vs delivered out-of-sample

| Timeframe | OOS trades | Predicted win | Realised win | Brier | Brier of a constant forecast | Skill |
|---|---|---|---|---|---|---|
| 1h | 18695 | 40.1 % | 37.7 % | 0.2342 | 0.2349 | +0.003 |
| 4h | 5662 | 42.6 % | 39.0 % | 0.2399 | 0.2380 | -0.008 |
| all | 24357 | 40.7 % | 38.0 % | 0.2355 | 0.2356 | +0.001 |

Skill below zero means the train win rate predicts a trade's outcome worse than one constant number would.

| Predicted win rate | OOS trades | Mean predicted | Realised | Gap |
|---|---|---|---|---|
| 0.00–0.30 | 1661 | 25.4 % | 27.4 % | +2.0 pts |
| 0.30–0.35 | 1928 | 32.7 % | 30.8 % | -1.9 pts |
| 0.35–0.40 | 7024 | 37.9 % | 36.7 % | -1.1 pts |
| 0.40–0.45 | 8841 | 42.5 % | 40.0 % | -2.5 pts |
| 0.45–0.50 | 2893 | 47.0 % | 42.7 % | -4.3 pts |
| 0.50–0.60 | 1774 | 52.6 % | 43.4 % | -9.2 pts |
| 0.60–1.00 | 236 | 62.0 % | 39.8 % | -22.2 pts |

## 2. Shrinkage of the edge (average R per trade, windows with >= 10 test trades)

| Timeframe | Windows | Train avg R | Test avg R | Slope test~train | Correlation | Windows positive in test |
|---|---|---|---|---|---|---|
| 1h | 261 | +0.049 | -0.060 | -0.03 | -0.02 | 33.7 % |
| 4h | 178 | +0.070 | +0.007 | -0.04 | -0.02 | 42.7 % |
| all | 439 | +0.057 | -0.033 | -0.02 | -0.02 | 37.4 % |

A slope of 1 would mean the in-sample edge carries over in full; 0 means it carries no information.

## 3. Is any out-of-sample result distinguishable from luck?

Mean R per trade, 95 % interval and one-sided p from a bootstrap over calendar months (20000 resamples); Holm correction over the 47 combinations with >= 50 OOS trades.

| Strategy | Symbol | TF | OOS trades | Predicted win | Realised win | Avg R | 95 % interval | p | p (Holm) | Alive |
|---|---|---|---|---|---|---|---|---|---|---|
| btc_leads | ETHUSDT | 4h | 261 | 43.8 % | 41.8 % | +0.303 | +0.045 to +0.603 | 0.0095 | 0.4488 | no |
| taker_exhaustion | ETHUSDT | 4h | 591 | 48.1 % | 44.7 % | +0.067 | -0.028 to +0.165 | 0.0814 | 1.0000 | no |
| oi_flush_continuation | ETHUSDT | 1h | 430 | 36.3 % | 33.3 % | +0.101 | -0.091 to +0.340 | 0.1638 | 1.0000 | no |
| crowded_unwind | SOLUSDT | 4h | 120 | 33.6 % | 37.5 % | +0.082 | -0.201 to +0.450 | 0.3129 | 1.0000 | no |
| funding_time_premium | SOLUSDT | 1h | 127 | 49.8 % | 51.2 % | +0.022 | -0.084 to +0.101 | 0.3294 | 1.0000 | no |
| crowded_unwind | ETHUSDT | 4h | 83 | 29.5 % | 32.5 % | +0.068 | -0.254 to +0.511 | 0.3525 | 1.0000 | no |
| oi_flush_reversal | SOLUSDT | 4h | 200 | 40.4 % | 34.5 % | +0.042 | -0.165 to +0.271 | 0.3582 | 1.0000 | no |
| taker_exhaustion | BTCUSDT | 4h | 704 | 45.5 % | 40.8 % | +0.017 | -0.075 to +0.111 | 0.3593 | 1.0000 | no |
| donchian_trend | ETHUSDT | 1h | 273 | 28.3 % | 27.5 % | +0.040 | -0.178 to +0.314 | 0.3873 | 1.0000 | no |
| btc_leads | SOLUSDT | 4h | 355 | 41.4 % | 38.9 % | +0.015 | -0.150 to +0.209 | 0.4438 | 1.0000 | no |
| btc_leads | ETHUSDT | 1h | 518 | 39.8 % | 39.4 % | +0.002 | -0.132 to +0.146 | 0.4975 | 1.0000 | no |
| asia_open_fade | ETHUSDT | 1h | 181 | 46.3 % | 45.3 % | -0.012 | -0.142 to +0.149 | 0.5750 | 1.0000 | no |
| oi_flush_continuation | BTCUSDT | 1h | 711 | 32.8 % | 31.5 % | -0.011 | -0.086 to +0.086 | 0.6096 | 1.0000 | no |
| weekend_fade | SOLUSDT | 4h | 172 | 52.5 % | 50.0 % | -0.023 | -0.173 to +0.141 | 0.6195 | 1.0000 | no |
| asia_open_fade | ETHUSDT | 4h | 205 | 44.6 % | 44.4 % | -0.032 | -0.242 to +0.232 | 0.6255 | 1.0000 | no |
| crowded_unwind | ETHUSDT | 1h | 293 | 31.9 % | 32.4 % | -0.056 | -0.260 to +0.218 | 0.6950 | 1.0000 | no |
| asia_open_fade | BTCUSDT | 4h | 197 | 43.6 % | 43.1 % | -0.054 | -0.245 to +0.200 | 0.7035 | 1.0000 | no |
| asia_open_fade | SOLUSDT | 1h | 173 | 42.1 % | 39.3 % | -0.040 | -0.170 to +0.107 | 0.7137 | 1.0000 | no |
| taker_exhaustion | SOLUSDT | 4h | 673 | 45.7 % | 42.1 % | -0.025 | -0.103 to +0.073 | 0.7206 | 1.0000 | no |
| weekend_fade | ETHUSDT | 4h | 107 | 46.9 % | 42.1 % | -0.057 | -0.241 to +0.113 | 0.7367 | 1.0000 | no |
| oi_flush_continuation | SOLUSDT | 4h | 392 | 39.7 % | 32.9 % | -0.046 | -0.174 to +0.100 | 0.7385 | 1.0000 | no |
| donchian_trend | SOLUSDT | 1h | 253 | 25.8 % | 21.3 % | -0.092 | -0.325 to +0.202 | 0.7469 | 1.0000 | no |
| oi_flush_reversal | BTCUSDT | 4h | 187 | 33.0 % | 27.8 % | -0.106 | -0.373 to +0.264 | 0.7601 | 1.0000 | no |
| session_open_drift | ETHUSDT | 1h | 1372 | 44.1 % | 41.5 % | -0.024 | -0.080 to +0.035 | 0.7897 | 1.0000 | no |
| asia_open_fade | SOLUSDT | 4h | 222 | 47.3 % | 42.8 % | -0.069 | -0.207 to +0.087 | 0.8010 | 1.0000 | no |
| weekend_fade | BTCUSDT | 4h | 109 | 44.0 % | 45.0 % | -0.074 | -0.239 to +0.098 | 0.8035 | 1.0000 | no |
| oi_flush_reversal | ETHUSDT | 1h | 532 | 39.7 % | 35.9 % | -0.064 | -0.196 to +0.083 | 0.8084 | 1.0000 | no |
| asia_open_fade | BTCUSDT | 1h | 193 | 48.1 % | 42.0 % | -0.073 | -0.213 to +0.087 | 0.8236 | 1.0000 | no |
| session_open_drift | SOLUSDT | 1h | 1358 | 44.2 % | 42.6 % | -0.036 | -0.092 to +0.024 | 0.8777 | 1.0000 | no |
| donchian_trend | BTCUSDT | 1h | 307 | 24.6 % | 19.2 % | -0.181 | -0.420 to +0.117 | 0.8942 | 1.0000 | no |
| oi_flush_continuation | ETHUSDT | 4h | 335 | 35.1 % | 31.6 % | -0.110 | -0.249 to +0.068 | 0.9000 | 1.0000 | no |
| btc_leads | SOLUSDT | 1h | 435 | 42.2 % | 38.4 % | -0.082 | -0.191 to +0.033 | 0.9241 | 1.0000 | no |
| weekend_fade | BTCUSDT | 1h | 289 | 44.1 % | 42.2 % | -0.098 | -0.217 to +0.039 | 0.9248 | 1.0000 | no |
| oi_flush_reversal | SOLUSDT | 1h | 372 | 39.0 % | 34.7 % | -0.118 | -0.255 to +0.041 | 0.9304 | 1.0000 | no |
| crowded_unwind | BTCUSDT | 1h | 101 | 27.1 % | 28.7 % | -0.203 | -0.463 to +0.063 | 0.9342 | 1.0000 | no |
| oi_flush_reversal | BTCUSDT | 1h | 434 | 37.4 % | 33.4 % | -0.140 | -0.294 to +0.043 | 0.9359 | 1.0000 | no |
| oi_flush_continuation | BTCUSDT | 4h | 360 | 33.8 % | 27.5 % | -0.151 | -0.291 to +0.047 | 0.9415 | 1.0000 | no |
| oi_flush_reversal | ETHUSDT | 4h | 194 | 41.3 % | 32.5 % | -0.170 | -0.349 to +0.047 | 0.9422 | 1.0000 | no |
| oi_flush_continuation | SOLUSDT | 1h | 741 | 37.2 % | 32.5 % | -0.104 | -0.188 to -0.007 | 0.9811 | 1.0000 | no |
| weekend_fade | ETHUSDT | 1h | 310 | 46.3 % | 40.0 % | -0.141 | -0.257 to -0.015 | 0.9844 | 1.0000 | no |
| funding_time_premium | SOLUSDT | 4h | 167 | 44.7 % | 47.9 % | -0.067 | -0.152 to -0.015 | 0.9930 | 1.0000 | no |
| taker_exhaustion | SOLUSDT | 1h | 2235 | 43.2 % | 41.0 % | -0.069 | -0.114 to -0.018 | 0.9964 | 1.0000 | no |
| crowded_unwind | SOLUSDT | 1h | 443 | 33.5 % | 30.5 % | -0.182 | -0.289 to -0.059 | 0.9980 | 1.0000 | no |
| session_open_drift | BTCUSDT | 1h | 1347 | 42.6 % | 41.6 % | -0.103 | -0.172 to -0.032 | 0.9984 | 1.0000 | no |
| weekend_fade | SOLUSDT | 1h | 353 | 48.2 % | 38.8 % | -0.200 | -0.318 to -0.073 | 0.9988 | 1.0000 | no |
| taker_exhaustion | ETHUSDT | 1h | 2212 | 40.7 % | 39.4 % | -0.104 | -0.160 to -0.048 | 0.9999 | 1.0000 | no |
| taker_exhaustion | BTCUSDT | 1h | 2612 | 38.7 % | 36.6 % | -0.124 | -0.169 to -0.078 | 1.0000 | 1.0000 | no |
| range_breakout | SOLUSDT | 1h | 26 | 20.9 % | 19.2 % | +0.737 | n/a (< 50 trades) | n/a | n/a | no |
| funding_time_premium | BTCUSDT | 4h | 1 | 31.0 % | 100.0 % | +0.475 | n/a (< 50 trades) | n/a | n/a | no |
| funding_time_premium | BTCUSDT | 1h | 1 | 34.5 % | 100.0 % | +0.406 | n/a (< 50 trades) | n/a | n/a | no |
| funding_reset | SOLUSDT | 1h | 3 | 12.1 % | 33.3 % | +0.305 | n/a (< 50 trades) | n/a | n/a | no |
| range_breakout | ETHUSDT | 1h | 11 | 23.7 % | 36.4 % | +0.285 | n/a (< 50 trades) | n/a | n/a | no |
| funding_time_premium | ETHUSDT | 1h | 17 | 60.0 % | 41.2 % | +0.098 | n/a (< 50 trades) | n/a | n/a | no |
| funding_time_premium | ETHUSDT | 4h | 18 | 47.3 % | 38.9 % | -0.157 | n/a (< 50 trades) | n/a | n/a | no |
| range_breakout | BTCUSDT | 1h | 32 | 15.8 % | 21.9 % | -0.327 | n/a (< 50 trades) | n/a | n/a | no |
| donchian_trend | BTCUSDT | 4h | 9 | 6.7 % | 11.1 % | -0.567 | n/a (< 50 trades) | n/a | n/a | no |

**Result: 0 of 56 combinations survive the correction.**
