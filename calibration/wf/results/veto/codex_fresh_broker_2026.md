# Fresh 2026 broker test of the frozen veto model (reported by the MT5 study; aggregate numbers only)

Run by Codex on broker BTCUSD.c BID M1 candles 2026-05-01 .. 2026-10-12 (232,098 candles): May-June warm-up,
**2026-07-01 .. 2026-10-12 exclusive test**. Frozen bank: commit `39c7248` (`veto_model_2026.json`, SHA-256
cacec7a2...; fitted on Bitstamp server-clock data with labels ending before 2026-01-01). Protocol frozen before any
outcome, with a data-availability amendment (native tick retention starts May 2026) also made before outcomes.
No refitting, no 2026 selection. Native candle parity: 999 M1 exact OHLC; sampled M5 / M15 / M30 exact; one H2
high differs by 0.08.

## Primary: M5, fixed H = 3 model (R2s), evaluated on next-5-minute labels (H = 1), clock-contiguous, n = 29,284

| rule | permission AUC | raw accuracy | coverage |
|---|---|---|---|
| P0 zone alone | 0.51013 | 51.04% | 83.90% |
| R2s zone + score agree | 0.51642 | 52.10% | 53.13% |

Paired 48-hour block bootstrap (1,000 repeats, 52 blocks, seed 20261015): AUC difference 95% CI [+0.0025, +0.0102];
accuracy difference [+0.0060, +0.0151]; coverage difference [-0.317, -0.298]. Continuous H = 3 score AUC on the same
labels 0.5227 (reported apart from the permission AUC). By quarter: 2026Q3 (46 blocks) accuracy +0.0096
[+0.0042, +0.0144]; 2026Q4 partial (6 blocks, 3,130 candles) +0.0191 [+0.0093, +0.0286].

## Independent recomputation (this repository's frozen `apply` path on the same broker M5 candles, observed-candle
sample, 2026-07-01 .. 2026-10-12)

| rule | n | calls | coverage | raw accuracy | AUC |
|---|---|---|---|---|---|
| P0 | 29,288 | 24,572 | 0.83898 | 0.51038 | 0.51011 |
| R2s | 29,288 | 15,560 | 0.53128 | 0.52108 | 0.51645 |

Identical to the author's observed-candle rows (n, calls, AUC, accuracy, coverage to 5 decimals). The 4-row
difference to the primary is the clock-contiguity filter. The hard-coded coefficient bank in the MQL5 source equals
the JSON exactly on all 9 models (max |diff| 0).

## Other timeframes and horizons (author's clock-contiguous pooled rows, R2s vs P0)

| TF | H = 1 acc diff [CI] | H = 3 | H = 10 | mean-H AUC diff [CI] |
|---|---|---|---|---|
| M5 | +0.0106 [+0.0060, +0.0151] | +0.0108 [+0.0047, +0.0168] | +0.0192 [+0.0114, +0.0270] | +0.0086 [+0.0037, +0.0134] |
| M15 | +0.0132 [+0.0045, +0.0220] | +0.0172 [+0.0066, +0.0279] | +0.0108 [-0.0066, +0.0278] | +0.0072 [-0.0008, +0.0157] |
| M30 | +0.0070 [-0.0036, +0.0168] | +0.0013 [-0.0104, +0.0133] | +0.0109 [-0.0125, +0.0322] | +0.0014 [-0.0079, +0.0107] |

M5 holds on every horizon; M15 holds at H = 1 and 3; M30 is positive but its CIs include 0 on 3.4 months of data.

## Comparison with the frozen Bitstamp runs (M5, R2s, raw accuracy gain over P0)

| window | H = 1 | mean of H = 1/3/10 | note |
|---|---|---|---|
| Bitstamp 2018-2019 (fresh, this repo) | +4.55 pts | +4.04 pts | about 1-2 pts of it is Bitstamp's last-trade bounce (HANDOFF section 11) |
| Bitstamp 2021-2022 | +1.89 pts | +1.91 pts | |
| Bitstamp 2026 Jan-Oct | +1.37 pts | +1.64 pts | |
| **Broker 2026 Jul-Oct (Codex, fully fresh)** | **+1.07 pts** | **+1.38 pts** | coverage 84% -> 53% |

The broker number is the honest size of the effect on this venue: about one extra correct call per hundred, at a
little over half the zone's coverage. Nothing here changes any Pine or MT5 default.
