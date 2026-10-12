# Pre-registration addendum: broker transfer of the G2 logistic score

Frozen before the broker evaluation of G2 runs (the commit adding this file is the freeze point; the script is
`wf_g2_broker.py` at that commit). Code checks ran only on (a) a parity test against `wf_graded.py` on UTC Bitstamp
(fold 2025H1: identical AUCs to 5 decimals for all 8 timeframes x 3 horizons) and (b) a dry window inside the broker
warm-up, 2024-03 .. 2024-06, which is not evaluated below. BTC only. No Pine or MT5 default changes.

## Question
Does the G2 logistic graded score, fitted on Bitstamp and applied with **frozen coefficients** to the broker's
BTCUSD.c candles (as a fixed MQL5 port would), keep its AUC and raw-accuracy advantage over the filter's zone?

## Model (unchanged from `wf_graded.py`)
- Features at the close of filter candle t (native-default zones, MT5 reads): zone, (close - level) / ATR_signal,
  last signal side, returns over 1 / 5 / 20 candles in ATR, ATR / SMA100(ATR), log bars since the signal, zone x vol,
  distance x vol, FDF trend, TDI fast-line level and slope of each native-default child zone.
- L2 logistic regression (L2 = 1, 30 Newton steps), standardised on the training rows; one model per horizon.
- **Training**: Bitstamp candles re-stamped to the broker server clock (New York + 7h), from 2020-01-01, every
  label ending before the evaluated period starts. One model per period: 2024H2 (labels end before 2024-07-01),
  2025H1 (before 2025-01-01), 2025H2 (before 2025-07-01). Every evaluated period is out of sample in time.
- **G2P** (G2 as a permission at the zone's coverage): BUY if the score is above the 58.5% quantile of the training
  scores, SELL if below the 41.5% quantile, NO TRADE between (target coverage 0.83, set on training rows only).

## Evaluation
- Periods 2024H2, 2025H1, 2025H2 and the three pooled; broker candles (primary) and Bitstamp server-clock candles
  (comparison). The broker series is warmed up with Bitstamp server-clock 5-minute candles before its first candle
  (2024-01-08), so slow indicators (the W1 RSI read by D1) are seeded as a terminal with full history would seed them;
  nothing before 2024-07 is evaluated; identical candles for every score (rows with every feature defined); labels sign(close[t+H] -
  close[t]), H = 1, 3, 10, ties dropped, labels must end inside the period.
- Scores on the same candles: P0 = the filter's zone (native default), G2, G2P.
- Metrics: AUC (ties half) per H and mean; raw accuracy, balanced precision, balanced recall, coverage for P0 / G2P;
  paired block bootstrap (500 repeats, blocks shared across H and scores) for the mean-H AUCs, raw accuracies and
  the differences G2 - P0, G2P - P0. Block length = max(48 hours, 4 x the longest label span of 10 candles): 48 h
  for M5 .. H1 (as the MT5 study), 80 h H2, 160 h H4, 320 h H8, 960 h D1.

## Reading rule (descriptive; nothing is deployed from it)
For a filter timeframe, "G2 transfers to the broker" if, on **broker candles pooled over 2024H2-2025H2**: (1) the
G2 - P0 mean-AUC difference has a 95% CI above 0, (2) the G2P - P0 raw-accuracy difference has a 95% CI above 0, and
(3) G2P coverage is within 0.10 of P0's. A timeframe is **flagged** when, in any of the three broker periods, the
G2 - P0 mean-AUC point difference or the G2P - P0 raw-accuracy point difference is negative. The script computes the
verdict and the flag (`g2_broker_reading_real.csv`); Bitstamp server-clock rows are a comparison, not part of the rule. H4, H8 and D1 are reported but expected to be noisy (few candles, and G2
overfit there on Bitstamp).

## Outputs
`g2_broker_eval_real.csv` (per timeframe x period x source x H / mean x score), `g2_broker_reading_real.csv`,
`g2_broker_weights_real.json` (per model: features, coefficients, the training mean / sd used for standardisation,
G2P thresholds; score = b0 + sum w_i (x_i - mu_i) / sd_i). Aggregate numbers only.

## Pre-freeze review
An independent review (three reviewers, one skeptic per finding) ran on the draft. Fixed before this freeze: bootstrap
blocks too short for H4 .. D1; under-seeded W1 RSI on the broker's short history; an empty trailing block; the flag
definition; the exported model lacked the standardisation; the parity check now also reads the repository copy of the
walk-forward graded results.

## Caveats known before running
- G2's feature set was fixed earlier in this research, and its Bitstamp walk-forward results (including the inspected
  2023-2026 periods) are why it is tested now; the broker candles of 2024H2-2025H2 have been used for P0 and other
  settings already, but never for G2 (except the dry window above).
- Bitstamp last-trade prices may carry bid-ask bounce that broker quotes do not; H = 1 is the most exposed.
