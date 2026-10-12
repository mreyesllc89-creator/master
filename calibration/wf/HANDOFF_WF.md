# BTC direction filter: longer history, native MT5 parent / child grid, purged walk-forward (handoff)

**BTC only** (Bitstamp BTC/USD 1-minute, 2018-2026; broker BTCUSD.c M5 2024-2025 as an independent check). Keep apart
from any XAUUSD evidence. **No Pine or MT5 default was changed.** Design frozen in `PREREG.md` at commit `1aeba54`
before any 2020-2026 evaluation; every post-freeze change is listed in section 7.

## 1. Answer

| Filter TF | Frozen rule (R2, section 7 of PREREG) | Setting it names (trained 2020-01 .. 2025-06) | Read-across |
|---|---|---|---|
| **M5** | suggest change (for broker check) | parent M5; zones M15 / H1 / H2; min aligned 1 | Better than the native default in **every** view: fresh, inspected, exploratory 2025H2-26, both clocks, both read modes, endpoint-purged, broker 2024H2 / 2025H1 / 2025H2 (out-of-sample fold picks too). Small: about +0.005 AUC and +0.005 raw accuracy at 1.8 points less coverage. Broker CIs include 0. |
| **H1** | suggest change (for broker check) | parent H1; zones H2 / H8 / H12; min aligned 1 | Strong in 2021-2025H1 (+0.009 / +0.013 AUC), but **worse than the default after mid-2025**: Bitstamp 2025H2-26 -0.004, broker 2025H2 -0.0075, Bitstamp server clock 2025H2 -0.004; server-clock fresh effect only +0.0026 (CI includes 0). Fails a deployment guard that needs recent out-of-sample gains. |
| M15, M30, H2, H4, H8, D1 | keep default | - | M15 / M30 / H4 point estimates positive but CIs include 0 (H4 also negative on the server clock); H2, H8, D1: R2 keeps the default. |

- The permission (BUY ZONE / SELL ZONE / NO TRADE) is a weak directional signal on BTC: walk-forward AUC 0.50-0.52 for every
  timeframe and setting; nothing reaches 0.53 out of sample.
- The **graded logistic score** (not the indicator's output) reaches AUC 0.53-0.545 on M5-H1 in every period, but it is
  mostly a contrarian / mean-reversion score (largest weights negative: FDF trend, last signal side, distance from the
  level, 20-candle return) and has not been tested on broker candles.
- The winning family is stable even though the exact pick is not: on M5-H1 every fold pick keeps parent = filter TF,
  **drops the filter-TF child zone, uses 2-3 higher children and needs only 1 aligned**. The exact children vary
  (R1 bootstrap pick frequency 0.23-0.51).

## 2. Definitions (kept distinct)
- **AUC**: ROC-AUC of the 3-valued zone vs sign(close[t+H] - close[t]), ties in the score counted half; ties in the label dropped and counted. Mean of H = 1, 3, 10 filter candles.
- **Raw accuracy** (`acc`): share right among BUY ZONE and SELL ZONE candles. **Coverage**: share of candles with a zone.
- **Balanced precision** (`bal_precision`, the PREREG's "balanced accuracy"; frozen rule (c) uses it): mean of P(up | BUY ZONE) and P(down | SELL ZONE).
- **Balanced recall** (`bal_recall`, the MT5 study's balanced_accuracy): mean of P(BUY | up) and P(SELL | down) on candles with a zone.
- Reads (primary = the MT5 port): parent closed by the filter candle's close; higher child zones closed by the filter candle's open; equal / lower children closed by its close. W1 opens Sunday 00:00 (matches the broker's native W1).

## 3. Results (primary: UTC, MT5 reads, all labels)

Generated tables: `results/handoff_tables.md` (decision, raw accuracy / coverage, per-group AUC with 95% CIs and
label counts, server-clock and closed_prev sensitivities, graded scores, broker). Key rows:

| TF | Period | Native default AUC [95% CI] | R2 AUC [95% CI] | R2 - default AUC [95% CI] | Raw acc default -> R2 | R2 - default acc [95% CI] | Coverage default -> R2 |
|---|---|---|---|---|---|---|---|
| M5 | fresh 2021-22 | 0.5151 [0.5130, 0.5172] | 0.5201 [0.5178, 0.5224] | +0.0049 [+0.0026, +0.0074] | 0.5155 -> 0.5206 | +0.0051 [+0.0028, +0.0076] | 0.847 -> 0.830 |
| M5 | inspected 2023-25H1 | 0.5138 | 0.5161 | +0.0023 [+0.0002, +0.0045] | 0.5141 -> 0.5166 | +0.0024 | 0.853 -> 0.835 |
| M5 | exploratory 2025H2-26 | 0.5093 | 0.5124 | +0.0031 [-0.0005, +0.0066] | 0.5095 -> 0.5128 | +0.0033 | 0.845 -> 0.824 |
| H1 | fresh 2021-22 | 0.5083 [0.5008, 0.5157] | 0.5175 [0.5104, 0.5254] | +0.0093 [+0.0019, +0.0169] | 0.5086 -> 0.5182 | +0.0096 [+0.0019, +0.0174] | 0.836 -> 0.822 |
| H1 | inspected 2023-25H1 | 0.5071 | 0.5202 | +0.0131 [+0.0063, +0.0202] | 0.5073 -> 0.5211 | +0.0138 | 0.853 -> 0.832 |
| H1 | exploratory 2025H2-26 | 0.4995 | 0.4954 | -0.0040 [-0.0136, +0.0068] | 0.4996 -> 0.4955 | -0.0041 | 0.825 -> 0.807 |

Label counts (H = 10, fresh): M5 105,897 up / 103,870 down; H1 8,671 / 8,836 (all counts per H and group in
`wf_pooled_permission.csv`). Confidence intervals: paired calendar-month block bootstrap over the pooled test months
(2,000 repeats). Grid rank stability (train vs test Spearman per fold, `wf_grid_rank_stability.csv`): positive through
2025H1 on M5-H1, then near zero or negative in 2025H2-2026 on H1 (-0.07, -0.51, -0.38).

## 4. Broker comparison (BTCUSD.c M5, aggregate numbers only; the raw file is not in the repository)
- **Clock**: broker server time = New York + 7h (UTC+2 winter / UTC+3 summer, US DST dates): 5-minute return
  correlation with Bitstamp 0.955-0.995 in every month 2024-01 .. 2025-12; fixed UTC+2 or UTC+3 fails half the year
  (`broker_clock.csv`). Median |price difference| 0.01-0.1%.
- **Engine parity with the MT5 study (2025H2, mean of H = 1/3/10)**: H2 default AUC 0.51546, acc 0.51593, coverage
  0.82184; H2 candidate (parent H2, zones H8/H12/D1, min 1) 0.52126 / 0.52163 / 0.82278; H1 default 0.51571; H1
  candidate (parent H2, zones M30/H1/D1, min 2) 0.51646 - **identical to the MT5 study's figures to 5 decimals**.
- **Same setting, different data**: broker vs Bitstamp zones agree on 77-85% of M5 candles, 84-89% M15, 87-89% M30,
  89-94% H1, 91-99% H2 and above (`broker_zone_agreement.csv`). Low timeframes depend on the data source.
- **Frozen picks on broker candles** (paired 48-hour block CIs, 500 repeats). The final picks were trained on
  2020-01 .. 2025-06, so 2024H2 and 2025H1 are **inside their selection window**; the walk-forward fold pick for each
  period (chosen without it) is the out-of-sample comparison:

| TF | Period | Setting (sample) | Broker AUC diff vs default [CI] | Broker raw acc diff [CI] | Coverage diff |
|---|---|---|---|---|---|
| M5 | 2024H2 | fold pick M10/M30/H1 min 1 (out-of-sample) | +0.0017 [-0.0026, +0.0062] | +0.0017 [-0.0028, +0.0062] | -0.020 |
| M5 | 2025H1 | fold pick M10/M15/H1 min 1 (out-of-sample) | +0.0003 [-0.0037, +0.0047] | +0.0003 [-0.0037, +0.0048] | -0.021 |
| M5 | 2025H2 | final pick M15/H1/H2 min 1 (out-of-sample) | +0.0036 [-0.0022, +0.0088] | +0.0038 [-0.0022, +0.0092] | -0.022 |
| H1 | 2025H1 | fold pick H2/H8/H12 min 1 (out-of-sample) | +0.0095 [-0.0060, +0.0273] | +0.0098 [-0.0063, +0.0280] | -0.009 |
| H1 | 2025H2 | final pick H2/H8/H12 min 1 (out-of-sample) | -0.0075 [-0.0230, +0.0078] | -0.0076 [-0.0246, +0.0084] | -0.019 |
| H2 | 2025H2 | MT5 study candidate H8/H12/D1 min 1 | +0.0058 [-0.0224, +0.0318] | +0.0057 [-0.0236, +0.0330] | +0.001 |

## 5. Graded scores (reported apart from the permission)
Walk-forward, same folds, native-default zones (`wf_graded_pooled.csv`; logistic weights per fold in `results/graded_weights/`):

| TF | P0 permission AUC fresh / inspected / expl. | G1 distance (close - level) / ATR | G2 logistic [CI, fresh] |
|---|---|---|---|
| M5 | 0.515 / 0.514 / 0.509 | 0.508 / 0.509 / 0.506 | 0.542 [0.537, 0.547] / 0.534 / 0.528 |
| M15 | 0.517 / 0.518 / 0.512 | 0.510 / 0.512 / 0.506 | 0.544 [0.538, 0.550] / 0.543 / 0.534 |
| M30 | 0.518 / 0.520 / 0.511 | 0.510 / 0.510 / 0.508 | 0.545 [0.538, 0.554] / 0.546 / 0.530 |
| H1 | 0.508 / 0.507 / 0.500 | 0.499 / 0.495 / 0.492 | 0.544 [0.535, 0.554] / 0.543 / 0.524 |
| H2 | 0.513 / 0.515 / 0.513 | 0.504 / 0.504 / 0.511 | 0.536 [0.520, 0.551] / 0.536 / 0.519 |
| H4-D1 | 0.50-0.52 | 0.48-0.52 | 0.48-0.52 (overfits: few candles) |

The logistic score's edge is largest at H = 1 and comes mainly from fading the FDF trend, the last signal side, the
distance from the level and the 20-candle move. It is a different rule from the zone (it often disagrees with it);
turning it into a permission needs its own threshold, coverage and broker test. The preserved exploratory feature run
(`dir_feat_auc.py`, 2023 / 2024-25H1 / 2025H2-26 split; `../direction/auc/feat_auc_summary.csv`; M5, M15, M30, H1 and D1 finished, H2-H8 still running at this commit) agrees: best-by-validation
feature scores 0.526-0.543 on 2025H2-26 vs 0.50-0.52 for the zone (inspected period; exploratory only).

## 6. Codex's audit points
1. **Tick-exact edges** (bug fix 1): the frozen code compared close with level +- band; the indicator rounds the edges
   outward to 0.01 and needs the close beyond the rounded edge by more than half a tick. Size (baselines and final picks): at most 56 of 712,827 M5
   candles (0.008%) change zone, at most 10 of 237,609 M15, 4 on M30, 3 on H1, 1 on H2, none on H4 and above
   (`tickfix_count.csv`). All runs were repeated with the fix. No final pick changed; one M15 fold pick changed (near-tie),
   moving M15's inspected AUC by +0.0013; every other pooled number moved by < 0.0001 (`tickfix_effect_pooled.csv`;
   pre-fix outputs in `results/pre_tickfix_v0/`).
2. **Balanced metrics**: renamed and both reported (section 2). The frozen rule (c) is unchanged (balanced precision).
3. **Raw accuracy at comparable coverage**: paired CIs for the accuracy difference and the coverage difference are in
   `wf_pooled_permission.csv` / `wf_decision.csv` / `broker_eval.csv`. For M5 and H1 the AUC and raw-accuracy
   differences move together; coverage falls 1.5-2.3 points.
4. **Fresh labels reaching 2023**: per timeframe exactly H candles of 2022-12 (1, 3, 10 for H = 1, 3, 10) have their
   endpoint in January 2023. Endpoint-purged sensitivity (labels must end inside the test block): M5 fresh diff +0.0049
   (CI low +0.0026), H1 +0.0095 (CI low +0.0022); no conclusion changes. The graded-score table keeps those few labels.
5. **W1 anchor**: Sunday 00:00, matching the broker's native W1 (Codex's CopyRates check).

## 7. Changes after the freeze (complete)
- Bug fix 1 (tick-exact edges), above; every run repeated.
- Reporting only: balanced recall; raw-accuracy difference CIs; coverage difference; endpoint-purged variant; fresh-label
  overlap counts; broker comparison: in-sample flags, walk-forward fold picks per period, accuracy CIs; `bal_acc` renamed
  `bal_precision` in published CSVs; an always-empty column removed.
- Unchanged: candidates, folds, purge, R1 / R2, decision rule, horizons, seeds, the primary read.
- An adversarial code review (two reviewers, one skeptic per finding) found no leakage or selection error; its two
  confirmed points (broker in-sample overlap, broker metric naming / accuracy CI) are fixed above.

## 8. Caveats
- One asset; Bitstamp last-trade prices; effects of 0.002-0.013 AUC, the size of the CIs on broker data.
- 2023-2025H1 was inspected by the earlier study and 2025H2-2026 by its final test (exploratory here); only 2021-2022 is
  fresh evidence. The earlier study's fallback rule saw its test results.
- 6,640 settings per run; R1 overfits more than R2 at H2-D1. The exact pick moves between folds (family stable).
- H1's result depends on the clock (UTC vs server time shifts H8 / H12 / D1 boundaries) and reversed after mid-2025.
- Broker sample: 2 years, 3 half-years; 2024H2 and 2025H1 are inside the final picks' selection window.

## 9. Files (`calibration/wf/`)
- `PREREG.md` (frozen design), `frozen_candidates.csv` (6,640 settings).
- Scripts: `prep_long.py`, `wf_common.py`, `wf_grid.py`, `wf_select.py`, `wf_graded.py`, `wf_broker.py`, `wf_report.py`,
  `wf_tables.py`, `tickfix_count.py`, `run_all.sh` (diff against `1aeba54` shows the post-freeze changes).
- `results/`: `wf_decision.csv`, `wf_pooled_permission.csv` (every TF x clock x read x group x labels x method, per H
  and mean, CIs, label counts), `wf_folds_permission.csv` (every fold's picks and test metrics), `wf_final_picks.csv`,
  `wf_grid_rank_stability.csv`, `wf_graded_pooled.csv`, `wf_graded_folds.csv`, `broker_eval.csv`,
  `broker_zone_agreement.csv`, `broker_clock.csv`, `broker_clock_best.csv`, `tickfix_count.csv`,
  `tickfix_effect_pooled.csv`, `handoff_tables.md`, `pre_tickfix_v0/`.
