# Pre-registration: option 2, the score veto on the filter's zone

Frozen before the real run (the commit adding this file is the freeze point; the script is `wf_veto.py` at that
commit). Code checks ran only on a dry window, 2017H2, which is not evaluated below. BTC only. No Pine or MT5 default
changes.

## Why this test
After the broker test of the logistic score (`PREREG_G2_BROKER.md`), an exploratory look at the same broker months
(2024H2-2025H2) suggested a rule that keeps the filter's own direction: trade the zone only where the score agrees.
That look used data already seen, so this test checks the rule on data where neither the rule nor the score was ever
evaluated.

## The rule (R2)
BUY is allowed only if the zone is BUY ZONE **and** the score permission G2P is BUY; SELL only if the zone is SELL ZONE
**and** G2P is SELL; otherwise NO TRADE. It never reverses the zone. G2 is the logistic score of `wf_g2_broker.py`
(same features, L2 = 1, 30 Newton steps, standardised on training rows, one model per horizon H). G2P = BUY above the
training 58.5% score quantile, SELL below the 41.5% quantile.

Compared on identical candles (rows with every feature defined):
- **P0** the zone alone (native default; the baseline).
- **R2s** R2 with one model for every horizon (the H = 3 model): the simpler version to port.
- **DV** a simple baseline veto: the zone where |close - level| / ATR >= k, with k set on training rows so DV covers
  as many training candles as R2. It asks whether the score adds anything over the zone's own strength.
- **G2P** the score as its own permission (reference).

## Data and periods
Bitstamp BTC/USD 1-minute data from 2014-01-01 (UTC); complete candles; filter timeframes M5, M15, M30 (the rule) and
H1 (reported only). Labels sign(close[t+H] - close[t]), H = 1, 3, 10, ties dropped, labels end inside the period.
- **Primary, fresh: 2018H1, 2018H2, 2019H1, 2019H2** and the four pooled. Models trained on candles from 2015-01-01
  whose labels end before each half-year starts (2014 = warm-up). Neither G2 nor the rule was ever evaluated on
  2014-2019 (only a 2018-2019 dry check of zone counts on H4 / D1 code).
- **Secondary (rule never evaluated there, but G2's AUC was): 2021H1-2022H2 pooled, and 2026-01 .. 2026-10.**
  Models trained from 2020-01-01, labels ending before each period.
- 2014-2016 Bitstamp minutes are thin (24-33% of minutes without a trade, against 3-4% in 2018-2019), so the fresh
  test trains on lower-quality data: a harder test, not an easier one.

## Metrics
Per H and mean of H: raw accuracy (share right among BUY / SELL calls), ROC-AUC of the -1 / 0 / +1 output (ties half),
coverage, balanced precision, balanced recall, label and call counts. Paired block bootstrap (500 repeats, blocks of
max(48 h, 4 x the 10-candle label span), shared across H and rules) for the accuracies, AUCs and the differences
R2 - P0, R2s - P0, DV - P0, G2P - P0, and R2 - DV.

## Reading rule (computed by the script, `veto_reading_real.csv`)
For each of M5, M15 and M30, **option 2 holds** if, on the fresh 2018-2019 pooled candles, (1) the R2 - P0 raw-accuracy
difference has a 95% CI above 0 **and** (2) the R2 - P0 AUC difference has a 95% CI above 0. Coverage is reported, not
tested: the rule is meant to block about half of the zone's calls. A timeframe is **flagged** when any fresh half-year
has a negative accuracy or AUC point difference. Secondary periods and R2s / DV / G2P are reported next to it and do not
change the verdict. H1 is reported only.

## For the MT5 study
The script also writes `veto_model_2026.json`: the models (per timeframe and H: features, coefficients, training mean
/ sd, G2P thresholds, DV threshold) fitted on Bitstamp re-stamped to the broker server clock (New York + 7h),
2020-01-01 .. labels ending before 2026-01-01, and the rule text. `python wf_veto.py apply <broker_csv> <start> <end>
veto_model_2026.json` scores new broker candles with these frozen models (no fitting) and writes the same metrics:
the fully fresh test on 2026 broker data.

## Pre-freeze review
An independent review (two reviewers, one skeptic per finding) ran on the draft. Fixed before this freeze: the run
argument now fails closed (only `real`, `dry`, `apply`); `apply` keeps the broker's first candle and refuses a window
that starts before it or before 2026-01-01; the R2 - DV AUC difference and its CI are now computed as listed above.

## Known limits before running
- One asset. 2018-2019 is a different market regime from 2024-2026 (that is part of the point of the test).
- The coverage drop is the rule's purpose; raw accuracy can rise when calls are removed, which is why the AUC condition
  and the DV baseline (an equally large, simple veto) are reported.
