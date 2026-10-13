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
  level, 20-candle return). **Broker test (section 10, pre-registered): it transfers on M5, M15 and M30**, not on H1 or
  slower; most of its edge is short-term mean reversion that one contrarian input already captures on M5 and M30.
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
turning it into a permission needs its own threshold and coverage; section 10 does that and tests it on the broker. The preserved exploratory feature run
(`dir_feat_auc.py`, 2023 / 2024-25H1 / 2025H2-26 split; `../direction/auc/feat_auc_summary.csv`, all 8 timeframes) agrees: the best-by-validation feature
score reaches 0.526-0.535 on M5-H1, 0.528 H2, 0.532 H4, 0.504 H8 and 0.543 D1 on 2025H2-26, vs 0.50-0.52 for the zone
(inspected period; exploratory only; the gradient-boosted models fit train far better than test).

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
- Logistic-score broker test: `PREREG_G2_BROKER.md`, `wf_g2_broker.py`, `g2_tables.py`; `results/g2_broker/`
  (`g2_broker_eval.csv`, `g2_broker_reading.csv`, `g2_broker_weights.json`, `g2_tables.md`, `g2_parity_check.csv`,
  `exploratory_after_freeze/` with the verification and stress-test tables and scripts).

## 10. Broker transfer of the logistic score (pre-registered addendum, `PREREG_G2_BROKER.md`, frozen at `5c9009d`)

**Design.** G2 (section 5) was fitted on Bitstamp candles re-stamped to the broker clock, using only labels that end
before each broker half-year (models for 2024H2, 2025H1, 2025H2), then applied with **frozen coefficients,
standardisation and thresholds** to BTCUSD.c candles, as a fixed MQL5 port would. On identical candles it is compared
with the filter's zone (P0, native default). **G2P** turns G2 into a permission at the zone's coverage (BUY above the
training 58.5% score quantile, SELL below 41.5%, NO TRADE between). Paired block bootstrap, 500 repeats, blocks of
max(48 h, 4 x the 10-candle label span). Reviewed before the freeze (fixes listed in the addendum). The first real
run computed but could not save (missing output folder) and printed nothing; it was re-run unchanged.

**Result (broker candles, pooled 2024H2-2025H2, mean of H = 1/3/10; pre-registered reading rule):**

| TF | Zone (P0) AUC | G2 AUC | G2 - P0 AUC [95% CI] | P0 raw acc | G2P raw acc | G2P - P0 acc [95% CI] | Coverage P0 -> G2P | Verdict |
|---|---|---|---|---|---|---|---|---|
| **M5** | 0.5091 | 0.5237 | +0.0146 [+0.0111, +0.0184] | 0.5094 | 0.5185 | +0.0091 [+0.0057, +0.0130] | 0.836 -> 0.840 | **transfers** |
| **M15** | 0.5085 | 0.5277 | +0.0192 [+0.0131, +0.0249] | 0.5087 | 0.5221 | +0.0134 [+0.0071, +0.0189] | 0.835 -> 0.839 | **transfers** |
| **M30** | 0.5061 | 0.5281 | +0.0220 [+0.0142, +0.0304] | 0.5065 | 0.5241 | +0.0176 [+0.0097, +0.0262] | 0.825 -> 0.841 | **transfers** |
| H1 | 0.5139 | 0.5269 | +0.0131 [-0.0012, +0.0267] | 0.5145 | 0.5257 | +0.0112 [-0.0022, +0.0240] | 0.830 -> 0.834 | no (both CIs include 0) |
| H2 | 0.5183 | 0.5276 | +0.0093 [-0.0068, +0.0270] | 0.5189 | 0.5239 | +0.0050 [-0.0102, +0.0203] | 0.838 -> 0.827 | no; flagged 2024H2 |
| H4 | 0.5141 | 0.5174 | +0.0033 [-0.0235, +0.0303] | 0.5154 | 0.5155 | +0.0001 [-0.0231, +0.0251] | 0.838 -> 0.834 | no; flagged 2024H2, 2025H1 |
| H8 | 0.5081 | 0.5006 | -0.0074 [-0.0402, +0.0325] | 0.5094 | 0.5046 | -0.0048 [-0.0338, +0.0320] | 0.854 -> 0.816 | no; flagged all 3 |
| D1 | 0.5151 | 0.5060 | -0.0090 [-0.1425, +0.1182] | 0.5226 | 0.4961 | -0.0266 [-0.1312, +0.0810] | 0.830 -> 0.812 | no; flagged all 3 |

- M5, M15 and M30 meet all three pre-registered conditions and are positive in every half-year (no flagged period).
  Coverage is near-equal: G2P minus P0 = +0.004 / +0.004 / +0.016.
- On the same broker candles the edge is at least as large as on Bitstamp server-clock candles (G2 - P0, pooled:
  M5 0.0146 vs 0.0124, M15 0.0192 vs 0.0187, M30 0.0220 vs 0.0194). The Bitstamp edge was not a last-trade
  artefact: on M5 the broker gain grows with the horizon (+0.008 at H = 1, +0.021 at H = 10).
- Per period, every M5-M30 point estimate is positive, but some accuracy CIs include 0 (M5 2025H1 +0.0033
  [-0.0028, +0.0095]; M15 2025H1 +0.0052 [-0.0058, +0.0157]; M30 2024H2 +0.0093 [-0.0038, +0.0223]).
- Full tables (per period, broker vs Bitstamp, per horizon): `results/g2_broker/g2_tables.md`; model file with
  coefficients, training mean / sd and thresholds: `results/g2_broker/g2_broker_weights.json`.

**Independent verification** (after the run; `results/g2_broker/exploratory_after_freeze/`):
- Recompute from the exported model with separate code (sklearn AUC, own labels): 384 / 384 numbers match (largest
  difference 5e-6, CSV rounding); all 27 training sets, means, sds and thresholds reproduce; every training label ends
  at or before its period start; an sklearn refit reproduces the coefficients to 3e-6. Limitation: the features were
  built with the same `features()` code, so a shared feature bug would not show.
- *Exploratory stress tests (done after the frozen run; they cannot upgrade or downgrade a verdict):* with 7-day and
  28-day blocks the M5-M30 CIs stay above 0 (AUC lower bounds 0.011 / 0.013 / 0.015); G2 - P0 AUC is positive in
  18 / 18 / 17 of 18 months; the edge holds in both low- and high-volatility halves. H1's longer-block CIs exclude 0,
  but H1 stays a fail under the frozen rule.

**What G2 is, and what it is not.**
- G2 is a short-horizon **contrarian / mean-reversion score, not a refinement of the zone**. Its rank correlation with
  the zone is about 0.38-0.40; G2P opposes the zone on 21-23% of its calls. On those candles the zone is right only
  0.48-0.49 of the time, and flipping them gives 56-69% of G2P's accuracy gain; the rest comes from dropping about 17%
  of zone calls that were coin flips.
- One input carries most of it. Fading the TDI fast-line level of the filter's own timeframe (RSI(14) + SMA(2), high
  = sell) alone reaches AUC 0.5223 / 0.5228 / 0.5248 on M5 / M15 / M30, i.e. **91% / 74% / 85% of the G2 - P0 gap**.
  G2's lead over it: M5 +0.0013 [-0.0003, +0.0030], M15 +0.0050 [+0.0014, +0.0085], M30 +0.0033 [-0.0033, +0.0094]
  (7-day blocks). So G2 clearly adds to it only on M15. That single input was identified on broker data after the
  run (exploratory), although its sign matches the Bitstamp-trained coefficients.
- At H1 the whole edge rests on one input (last signal side); 20-candle reversal alone matches G2 there.

**Caveats.** Effects are small (AUC about 0.52-0.53, raw accuracy about 0.52); direction sign only, no spread or
costs, nothing here shows it is tradable. This tests a move to another venue and clock more than a new period: G2 was
chosen after Bitstamp walk-forward results that cover the same calendar months, and the broker months were already used
for zone work. The pooled AUC ranks scores of three period models together (within 0.0007 of the per-period average).
No Pine or MT5 default was changed.

## 11. Option 2 (score veto): frozen fresh-window test, independent verification, fresh broker test, MQL5 module

**Design** (`PREREG_VETO.md`, frozen at `196d771`): keep the filter's zone only where the logistic score permission
agrees ("R2"); never reverses the zone. Primary window Bitstamp 2018-2019, never evaluated before by any rule here,
models trained on candles from 2015-01-01 whose labels end before each half-year starts (the 2018H2-2019H2 models
therefore include the earlier fresh half-years; no model sees its own half-year or later); secondary 2021-2022 and 2026; baselines: the
zone alone (P0), the one-model variant R2s (H = 3 model for every use; the version to port), a distance-only veto of
the same size (DV), the score alone (G2P).

**Frozen result** (`results/veto/`, pre-registered reading rule met on all three timeframes):

| TF | window | P0 raw acc / cov | R2 raw acc / cov | R2 - P0 acc [95% CI] | R2 - P0 AUC [95% CI] |
|---|---|---|---|---|---|
| M5 | fresh 2018-19 | 0.5230 / 0.851 | 0.5662 / 0.461 | +0.0432 [+0.0407, +0.0456] | +0.0243 [+0.0225, +0.0260] |
| M15 | fresh 2018-19 | 0.5205 / 0.844 | 0.5615 / 0.478 | +0.0411 [+0.0374, +0.0444] | +0.0242 [+0.0213, +0.0267] |
| M30 | fresh 2018-19 | 0.5153 / 0.845 | 0.5550 / 0.452 | +0.0396 [+0.0347, +0.0445] | +0.0231 [+0.0187, +0.0271] |
| M5 | 2021-22 | 0.5155 / 0.847 | 0.5374 / 0.510 | +0.0220 [+0.0201, +0.0239] | +0.0133 [+0.0118, +0.0148] |
| M5 | 2026 Jan-Oct | 0.5105 / 0.846 | 0.5283 / 0.521 | +0.0177 [+0.0152, +0.0206] | +0.0115 [+0.0094, +0.0138] |

Every fresh half-year positive; DV (same number of calls, zone's own strength) is **worse** than the zone everywhere
(-0.03 in 2018-19), so the gain is the score's, not a side effect of calling less.

**Why 2018-2019 is larger than every later window.** Bitstamp 2018-19 minute prints carry a Roll-implied bid-ask
bounce of about 7 bp (1-lag return autocorrelation -0.08 at 1m); a "bounce oracle" that only exploits that reaches
55.5% accuracy at H = 1 there, against 51.2% in 2021-22 and 50.0% on Bitstamp 2026 (Roll spread 0; bid-quote
broker candles carry no last-trade bounce by construction).

**Independent judge's verdict** (recompute, regime and leakage material; `wf/verify_veto/`): numerically correct
(every frozen M5 / M15 / M30 value reproduced, max |diff| 5e-6; dry-window truncation shows no look-ahead; apply-path
JSON round trip exact). Of the M5 +4.3 pts: stale prints at most 0.1 pt; Bitstamp's last-trade bounce about 1-1.5 pt
(1-2 pt of the +5.0 at H = 1), measured by re-labelling the frozen calls with a centred mid-price proxy and netting
the proxy's lag bias with the bounce-free 2026 window as placebo; about 0.2 pt of the M30 +4.0. The de-bounced
2018-19 gains, about +3 (M5) / +3.8 (M30), are a genuine but era-specific mean-reversion regime: a de-bounced
"fade the last candle" veto gains +2.4 (2018-19) -> +1.5 (2021-22) -> +0.8 (2026) over the zone; all 24 fresh
months positive; the monthly gain tracks the sign-reversal rate (Spearman 0.81). The 2018-19 models also weight the
last return about 4x more than the shipped 2026 bank, so that window tests the rule, not the shipped coefficients;
the fresh broker test below is the only test of the shipped bank. Sizes on bounce-free data: +1 to +2 pts.

**Fresh broker test** (run by the MT5 study on BTCUSD.c, 2026-07-01 .. 2026-10-12, protocol frozen before outcomes;
`results/veto/codex_fresh_broker_2026.md`): M5, fixed H = 3 model, next-5-minute labels, n = 29,284: raw accuracy
51.04% -> 52.10% [+0.60, +1.51 pts], permission AUC 0.5101 -> 0.5164 [+0.0025, +0.0102], coverage 83.9% -> 53.1%;
positive in both quarters. **Independently recomputed here** with the frozen `apply` path on the same candles:
identical to 5 decimals (n, calls, AUC, accuracy, coverage). The hard-coded coefficient bank in the MQL5 source
equals the frozen JSON exactly on all 9 models. Honest effect size for deployment discussions: **about one extra
correct call per hundred, at a little over half the zone's coverage.**

**MQL5 module** (`BTCUSD_Score_Veto_MT5.mq5`, separate optional indicator, SHA-256 `d50e2f0e...`, EnableVeto = false
by default, no order API, original indicator / binary / defaults unchanged and hash-verified by its author):
independent adversarial source review (three reviewers, one skeptic per finding; final source SHA-256
`d50e2f0e...`): **no numerical or causality defect; two low robustness findings, four claims refuted.**
- Confirmed (low): global feed and model state survive `OnInit` re-entry, so changing `ModelTimeframe` (or the
  symbol) in the properties dialog splices the previous timeframe's bars in front of the new feed; and after a rebuild
  that extends the retained history anchor, historical buffers on a chart whose period differs from `ModelTimeframe`
  are not recomputed (`OnCalculate` resumes from `prev_calculated`). Both affect **displayed history and the
  retrospective statistics only**; the live permission resyncs. One fix covers both: free the feed, arm and veto
  arrays and reset `ready` / `built_time` / `built_closed` / `retry_at` in `OnInit`, and force a full buffer pass when
  the anchor moves. Recommended before any live use; not a parity issue.
- Refuted: buffer 2 = `EMPTY_VALUE` on unscored or expired candles (the declared MQL5 "no value", `PLOT_EMPTY_VALUE`
  set); `EnableVeto = false` publishing 0 (documented; the README tells an EA to check `EnableVeto` and `ModelReady`);
  gap expiry only on the forming slot (correct on a same-period chart); a flat-close TDI rounding difference on x2 /
  x4 children (no realistic effect).
- Checked by me: the 11-line diff from the first upload is exactly the retry clamp, enum validation and the removed
  stale buffer comment; the README's 13-buffer map matches `OnInit`; the coefficient bank equals the JSON on all 9
  models; an independent run of the research `apply` path on the same broker candles reproduces the author's M5
  metrics to 5 decimals.
- Still outstanding, by design: a live `iCustom` chart smoke test (the isolated terminal has no broker clock).

**Not done, by design**: no Pine or MT5 default changed; no live iCustom chart smoke (isolated terminal without a
broker clock; stated limitation); the Pine-side veto is a pending user choice.

## 12. The fractal direction score (W1 down to M5): frozen test (`PREREG_FRACTAL.md`, frozen at `8e53ab5`)

**Question.** Does reading the direction state of every higher timeframe (FDF structure trend and TDI fast line at
M5, M15, H1, H4, D1 and W1, W1 = TradingView's Monday week) forecast the next 5-minute direction better than the
zone alone, and better than the local option-2 veto that reads only M5 / M10 / M20? Fitted frozen logistic weights
(FR), its permission (FRP), the veto FRV = zone kept where FRP agrees, and a no-fitting "count the aligned
timeframes" baseline (CNT / CNTV), all on identical candles.

**Frozen verdict: the stack works only because it contains the local reading; it does not beat the local veto.**

| window (M5, H = 1) | zone acc / cov | option-2 veto R2s acc / cov | fractal veto FRV acc / cov | FRV - zone | FRV - R2s [95% CI] |
|---|---|---|---|---|---|
| fresh 2018-19 | 0.5155 / 0.851 | 0.5610 / 0.460 | 0.5559 / 0.407 | +0.0404 | **-0.0051 [-0.0070, -0.0028]** |
| 2021-22 | 0.5163 / 0.847 | 0.5352 / 0.538 | 0.5368 / 0.477 | +0.0205 | +0.0016 [-0.0003, +0.0036] |
| 2026 Jan-Oct | 0.5087 / 0.846 | 0.5224 / 0.540 | 0.5225 / 0.501 | +0.0139 | +0.0001 [-0.0026, +0.0028] |

Pre-registered conditions: (1) FRV beats the zone, met; (2) FRV beats R2s at comparable coverage, **not met**
(worse in all four fresh half-years, three with the CI below zero); (3) FRP's permission AUC beats the option-2
permission's, **not met** (-0.013 [-0.015, -0.011]). As continuous scores, FR's AUC (0.557) is 0.014 [0.013, 0.016]
below the option-2 score's (0.571) on the fresh window. Horizon convention: the option-2 baselines use the fixed
H = 3 model at every horizon (as ported), FR a model per horizon; this favours FR. (The section 11 veto table reports
the mean of H with per-horizon R2, so its zone row reads 0.5230 for the same window; this table is H = 1.)

**Where the weight went** (standardised |w|, fresh H = 1 models): M5 0.32, M15 0.11, W1 0.06, H1 0.04, H4 0.03,
D1 0.02; the three alignment summaries 0.05. The two largest inputs are the M5 TDI level and direction, both
negative (contrarian), i.e. the same reading the option-2 veto already uses. The higher timeframes carry small
positive (trend-following) weights with stable signs.

**The alignment count is wrong-way at 5 minutes.** CNT (net number of timeframes pointing up) has AUC 0.48 in every
window, and the count veto CNTV is below the zone: when the whole stack points one way, the next five minutes lean
very slightly the other way.

**Independent verification** (`wf/verify_fractal/`): every pooled fresh H = 1 quantity for P0, R2s, G2P, FRP, FRV
and the three differences reproduces with separate code to < 5e-6; sklearn refits equal the frozen weights to 5e-6;
every training label ends before its half-year; a truncation test at two cuts shows all 21 inputs and the zone are
identical on truncated and full data (no look-ahead); a Sunday-week control does not reproduce the CSV, so the
published numbers use TradingView's Monday weeks as designed. Post-hoc checks by the judge, not pre-registered:
**adding all fifteen higher-timeframe inputs to the option-2 veto's own inputs changes the 5-minute AUC by +0.0003
[+0.0000, +0.0008] and the veto's accuracy by +0.0001 [-0.0010, +0.0012]**; the H1-and-above readings alone forecast
the next 5 minutes with AUC 0.508, M15-and-above 0.517, the three M5 readings alone 0.556, all 21 inputs 0.557. So the
frozen design shows a stack-only score does not beat the local veto; the nested check shows the higher timeframes add
nothing measurable to it at 5 minutes. The pre-registered drop-one-timeframe ablation and the longer-horizon look
(where the stack starts to pay) are reported in `results/fractal/ablation.csv` (exploratory). Code note, no effect on
results: higher-TF direction columns carry an int64 fill in 1,440 warm-up rows that the level column's NaN mask
removes; cast before `take` in any future version.

**Where each reading pays** (`results/fractal/ablation.csv`, `fractal_ablation.py`; exploratory, point AUCs, no
CIs; fresh 2018-19 walk-forward; labels at longer horizons overlap heavily, so the 1-day column rests on far fewer
independent observations than its n suggests):

| inputs | 5 min | 15 min | 50 min | 1 h | 4 h | 1 day |
|---|---|---|---|---|---|---|
| all 21 (W1 .. M5) | 0.557 | 0.563 | 0.575 | 0.577 | 0.563 | 0.523 |
| local only (M5 + M15) | 0.556 | 0.562 | 0.573 | 0.574 | 0.559 | **0.482** |
| M5 only | 0.556 | 0.560 | 0.572 | 0.573 | 0.552 | 0.491 |
| M15 and above | 0.552 | 0.558 | 0.571 | 0.572 | 0.562 | 0.523 |
| **stack only (H1, H4, D1, W1 + depth)** | **0.508** | 0.519 | 0.539 | 0.542 | 0.540 | **0.523** |
| drop-one at 5 min: M5 / M15 / H1 / H4 / D1 / W1 | loss 0.0046 / 0.0012 / 0.0002 / 0.0001 / 0.0000 / -0.0001 | | | | | |

Reading: at 5 minutes the forecast is the local contrarian reading and the big timeframes add nothing (dropping W1
changes the AUC by 0.0001). The higher stack's own AUC rises with the horizon (0.508 at 5 min, 0.54 at 1-4 h) and
at one day it carries all the information there is (0.523) while the local reading has turned wrong-way (0.482).
So "read from the biggest chart down" is the right idea for a 1-hour-to-1-day direction and the wrong one for the
next five minutes; a per-horizon switch (local below about 1 h, stack above about 4 h) would be the natural design
if a longer-horizon filter is ever wanted, and would need its own frozen test.

**Consequence for Pine.** Under the pre-registered rule no fractal veto is added to the Pine filter. The 2026
coefficients are kept for the record (`results/fractal/fractal_model_2026.json`), not for use. The one veto that
earned a place remains option 2 (section 11), whose Pine integration is the user's pending choice.

## 13. Option 2 in the Pine filter: optional "Score veto", off by default

The user's choice after sections 11-12: the full option-2 veto goes into `flashgold_direction_filter.pine` as a switch
in the new input group "Score veto", **off by default** (with it off every gate, plot, label and status-box text is what
v1.2 produced; two new Data Window plots and the new input group are the only additions). With it on, a BUY ZONE
allows buys only while the frozen score says UP and a SELL ZONE allows sells only while it says DOWN; it never allows
what the zones forbid.

- **Model**: the H = 3 entry of `results/veto/veto_model_2026.json` for the filter timeframe, hard-coded in the script
  (`fgvModelW / Mu / Sd / Qlo / Qhi`, one array per timeframe: 5m, 15m, 30m, 1H). On any other filter timeframe the
  veto is not applied, the zones decide alone and the status box says "NOT APPLIED".
- **Inputs**: the 17 of `VETO_PORT_CONTRACT.md` section 2, computed in `fgvScore()` inside the filter-timeframe
  `request.security` call at each candle's close, from the filter's own state: the zone with the v1.2 tick-exact edges
  and the filter's band / level inputs, `dist`, `side`, `r1 / r5 / r20`, `vol`, `age`, `zone_vol`, `dist_vol`, the FDF
  structure direction (`fgvFdf()`, the strategy's state machine without the divergence and Hurst parts), the TDI fast
  line's level and slope on the filter timeframe (same candle) and on 2 x / 4 x it (two nested `request.security`
  calls with `lookahead_on` and `[1]`, the `map_prev_on` read; the script now makes 16 `request.security` calls).
  Division and clipping follow the calibration's numpy semantics (`fgvDiv`); a candle with any undefined input is not
  scored and, with the veto on, allows nothing (the contract's fail-closed rule).
- **Timing**: the score, its answer and the ready flag travel in the same tuple as the arm and are picked by the same
  rule (`fgfSel`: latest filter candle closed by the clock, the one before it, or the previous bar's pick), so the
  permission of candle t applies from t's close to the next close, as the zone does and as the research labelled it.
- **Calibration guard**: the status box lists any input that differs from the calibrated settings (band 0.25, level =
  Entry price, lasts until next signal, against on, parent = filter TF, child zones 1-3 at 1 / 2 / 4 x, min aligned 2,
  v1.2 signal defaults). It is a warning, not a lock.
- **Known deviation**: the 30m and 1H models were fitted with 2H / 4H child bars on the broker's clock (UTC+2 / +3);
  TradingView's start at 00:00 UTC. `results/veto/pine_parity/aggregates_2026_utc.csv` applies the frozen model to UTC
  bars for 2026: within 0.3 pt of the clock-matched run on every timeframe (no CIs; 2026 is an inspected window).
- **Parity check for the user**: `veto_pine_parity.py` writes `results/veto/pine_parity/parity_<TF>.csv` (last 3,000
  candles, every input, the score, the answer, the zone and the veto permission on Bitstamp UTC bars) and the README
  there says how to compare them with the Data Window plots `FGV in 1 .. 17` / `FGV score` / `FGV answer` (switch
  "Score inputs in the Data Window"). The script could not be compiled here (no TradingView); it was syntax-checked
  with pynescript and reviewed against the Python definitions; the row-level check on TradingView is the user's.
- **Evidence on the switch itself**: header section "SCORE VETO" of the filter repeats the frozen numbers (fresh
  2018-2019, 2021-2022, 2026, the broker 2026 test) with the bounce caveat; the gain is +1 to +2 points of next-candle
  accuracy out of sample at about 45-55 % of the candles allowed instead of 84 %.
