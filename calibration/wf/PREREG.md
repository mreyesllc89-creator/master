# Pre-registration: BTC direction filter, longer history, native MT5 parent / child grid, purged walk-forward

Frozen **before** any 2020-2026 evaluation was run. The git commit that adds this file is the freeze point; the scripts
in this folder at that commit are the frozen procedure. Code checks ran only on a dry window (evaluation months
2018-07 .. 2019-12, outside every period below). If a bug fix is needed after the freeze, it is listed in the
results handoff with its reason; the candidates, folds, rules and decision rule below do not change.

Scope: BTC only (kept apart from any XAUUSD evidence). No Pine or MT5 default changes during this research.

## 1. Data
- Bitstamp BTC/USD 1-minute candles (public dataset, no gaps 2018-01-01 .. 2026-10-11). 2018-2019 = indicator warm-up
  (and the dry window). Evaluation months: 2020-01 .. 2026-10 (complete candles only).
- Clocks: **UTC** (primary); **broker server clock** = New York local time + 7h (UTC+2 winter / UTC+3 summer, US DST),
  secondary. The broker sample's clock was checked against Bitstamp before this freeze (5-minute return correlation
  0.96-0.995 in every month 2024-01 .. 2025-12 with this rule; a fixed UTC+2 or UTC+3 fails in half the year). That
  check reads prices only, no AUC.
- Broker BTCUSD.c M5 candles 2024-01-08 .. 2025-12-31 (supplied by Codex; private, kept outside the repository; only
  aggregate numbers are published): secondary, independent comparison, no selection.

## 2. What is scored
- **Permission** (the indicator's actual output): zone at each closed filter candle: +1 BUY ZONE (close > level + 0.25
  ATR of the signal candle), -1 SELL ZONE (close < level - band), 0 NO TRADE; level = the last FlashGold signal's
  entry price; signal inputs at their defaults (as the earlier `dir_auc.py`).
- **Graded scores** (reported apart, not the indicator's output): G1 = (close - level) / ATR of the signal candle,
  clipped to +-5; G2 = L2 logistic regression on fixed features (zone, G1, last signal side, returns over 1/5/20
  candles in ATR, ATR / SMA100(ATR), log bars since the signal, zone x vol, G1 x vol, FDF trend, TDI fast-line level
  and slope of each native-default child zone), refitted per fold on the purged training window.
- **Label**: sign(close[t+H] - close[t]), H = 1, 3, 10 filter candles (identical horizons for every setting and
  baseline); ties dropped and counted.
- **Higher-timeframe reads (primary = the MT5 port's)**: parent = last parent bar closed by the filter candle's close;
  higher child zones = last child bar closed by the filter candle's open; equal / lower child zones = closed by the
  close. Secondary: `closed_prev` (parent also from the bar closed by the filter candle's open; the earlier calibration).

## 3. Candidates (`frozen_candidates.csv`, 6,640 rows)
- Filter timeframes M5, M15, M30, H1, H2, H4, H8, D1.
- Native MT5 intervals that are whole multiples of the filter timeframe, ratio 1..24 (M5: M5 M10 M15 M20 M30 H1 H2;
  M15: M15 M30 H1 H2 H3 H4 H6; M30: M30 H1 H2 H3 H4 H6 H8 H12; H1: H1 H2 H3 H4 H6 H8 H12 D1; H2: H2 H4 H6 H8 H12 D1;
  H4: H4 H8 H12 D1; H8: H8 D1 W1; D1: D1 W1). W1 = Sunday 00:00 of the data clock.
- Grid: parent in that list x every child-zone set of size 1..3 from that list x minimum aligned 1..size, plus zones off.
- Baselines (identical horizons): **native default** = parent = filter TF, children x1/x2/x4 snapped to the nearest
  native multiple (M5: M5/M10/M20, M15: M15/M30/H1, M30: M30/H1/H2, H1: H1/H2/H4, H2: H2/H4/H8, H4: H4/H8/H12,
  H8: H8/D1, D1: D1/W1), min aligned 2 = **the reference**; the earlier study's default x1/x2/x4 with TradingView
  intervals (16H, 32H = D1, 2D, 4D where not native); the literal input default (parent H1, zones H1/H2/H4, min 2);
  zones off.

## 4. Purged walk-forward
- Test blocks: half-years 2021H1 .. 2026H2 (2026H2 = 2026-07 .. 2026-10-10). Training: expanding, 2020-01 up to the
  block start; **purge**: in the last training month only candles whose label ends inside that month are kept (no
  training label reaches into the test block). Indicator state is causal, so no embargo is needed.
- Groups: **fresh 2021-2022** (never inspected; primary evidence), **inspected 2023 .. 2025H1** (train / validation of
  the earlier study), **inspected final 2025H2 .. 2026** (the earlier final test, already inspected by the earlier
  fallback rule -> exploratory only).

## 5. Selection rules (applied inside every fold on its training window only)
- Training metric: mean over H = 1, 3, 10 of the permission AUC of the pooled training counts (ties half).
- **R1 greedy**: highest training metric on the grid (ties: fewer zones, lower parent, lower minimum).
- **R2 conservative (primary)**: highest training metric among grid settings that (a) beat the native default's
  training metric in at least 2/3 of the training half-years, (b) have a paired calendar-month block-bootstrap
  (500 repeats) 5th percentile of the training difference vs the native default above 0, and (c) have a training
  metric above 0.5; if none qualifies, the native default.

## 6. Reporting
- Per fold and pooled per group: AUC per H and mean, accuracy (share right among BUY / SELL zone candles), balanced
  accuracy (mean of P(up | BUY) and P(down | SELL)), up rate, coverage, label counts (up, down, ties dropped),
  BUY / SELL / NO TRADE counts; train vs test rank correlation of the grid per fold.
- Confidence: paired calendar-month block bootstrap over the pooled test months (2,000 repeats) for the mean AUC, the
  difference vs the native default and the balanced accuracy; R1 pick frequency over 500 training bootstraps.
- Graded scores: AUC per fold and pooled, month block bootstrap (500 repeats).

## 7. Decision rule (per filter timeframe)
Suggest a default change only if **all** hold for procedure R2: (a) fresh 2021-2022 pooled mean-AUC difference vs
the native default has a 95% CI above 0; (b) the difference on inspected 2023 .. 2025H1 is >= 0; (c) R2's fresh
balanced accuracy >= the native default's; (d) the server-clock run's fresh difference is > 0. The setting to suggest
is then R2 applied to training 2020-01 .. 2025-06 (purged). The 2025H2 .. 2026 numbers are never used for a choice.
Otherwise: keep the default. Any change is a suggestion for Codex's broker check, not an edit of Pine / MT5 defaults.

## 8. Secondary analyses (no choices)
- Server-clock run of the whole procedure; `closed_prev` read run.
- Broker comparison (`wf_broker.py`): baselines, the R1 / R2 final picks and Codex's two reported candidates
  (H2: parent H2, zones H8/H12/D1, min 1; H1: parent H2, zones M30/H1/D1, min 2) on broker candles and on Bitstamp
  re-stamped to the server clock, 2024H2 / 2025H1 / 2025H2, labels purged at each period end, paired 48-hour block
  bootstrap (500 repeats, blocks shared across H); zone agreement between the two sources (engine / data parity).
- The feature-score run started before this freeze (`dir_feat_auc.py`, 2023 / 2024-25H1 / 2025H2-2026 split) is
  preserved and reported as exploratory: its test period was already inspected.

## 9. Files
`wf_common.py` (definitions), `wf_grid.py` (counts), `wf_select.py` (walk-forward, rules, bootstrap),
`wf_graded.py` (graded scores), `wf_broker.py` (broker comparison), `prep_long.py` (data), `frozen_candidates.csv`.
Run from `calibration/` (they import `fgrun.py` / `fgengine.py`).
