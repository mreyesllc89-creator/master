# Acceptance protocol for the direction calibration (binding)

Written after a statistics review of the first draft of the task prompt. Numbers marked (reviewer) are the reviewer's own calculations from
`results/center_final_center_trades.csv` and `REPORT.md`; check them before leaning on them. "No change" is a valid result.

1. **Primary endpoint.** Net points per tradable day from the full replay under the frozen execution. Trade floor: 70% of the frozen preset's trades per week.
   Buys and sells must each gain, and no input may treat buys and sells differently (buys beat sells in 6 of 9 months, including March when gold fell 13%).
   Screening diagnostic only: gross mid move at +5/+10/+30 s, one row per alert episode (first pass), divided by trailing volatility, with trading-day
   intervals. Episode = alert-candidate ticks less than 20 s apart merged (counts in BRIEF section 5); merge at 60 s for inference.
2. **Anchors and placebos.** Anchor every outcome at the tick where the order would be sent (the hold-pass row), never at the arming tick: the entry hold
   needs +5 points over 1,100 ms and FlashGold is re-read at release, so a candidate would otherwise be scored on moves it has already waited for. Use the
   alert-start tick as the candidate-independent event reference. Run the truncation test (cut the data after tick i: the features of row i must not change).
   The average of both sides is identically zero for gross moves, and the unchosen side has no realistic fill: use sign-flipped outcomes and the unfiltered
   burst-follow at the same alert size as placebos. Net numbers come from engine trades only. The prototype's forward kernel is validated for market entries
   only: validate a stop-order variant against the engine before ranking on it, and report the Spearman correlation of the kernel (or offline) score with the
   full-replay net per day over at least 50 random sets; below 0.5, do not screen on the kernel.
3. **Data periods.** The nine months (Nov 2025 to Nov 2026) are burned: the calibrated preset was chosen with all of them in view after more than 1,200
   replays. Use them for screening only. Cut folds at weekend closes; embargo = 2 hours plus the longest hold; cluster by trading day. Untouched periods: earlier
   years from the Hugging Face dataset (May 2021 to Oct 2025; it ends May 2026; own data root; half a year at a time because of 16 GB RAM) and June to September
   2026 if the throttled Dukascopy download finishes (7 Sep to 8 Oct 2026 is the window the feed and the fill model were fitted on: exclude it). Declare the
   earlier-year scaling before any outcome is read: set `MaxTrailingMultiplier` per year so that alert episodes per trading day equal the nine-month rate (from
   past data only), and also run the unscaled rule; accept on gross only; report tick rate, continuation-filter pass rate and spread median per year
   (`ticks.py` hard-codes the Dukascopy median spread 54.6, so rebuilt spreads differ by year); replay one week present in both the Hugging Face and the raw files
   first. If June to September cannot be fetched, say so.
4. **Gates.** Gate 0, before any feed work: replay the frozen preset on untouched data, including one earlier year with falling gold (for example 2022); stop and
   report if its gross edge is not above zero by trading-day bootstrap. Gate 1: the Spearman correlation of the metric between two disjoint periods over at
   least 200 random sets near the preset must be at least 0.3 (the earlier joint grid gave 0.06 and 0.27); otherwise test at most 20 sets fixed in advance.
   Always report results without the best 5 days: the best 5 of 158 days make 96% of the calibrated preset's net (28 and 29 Jan 2026 alone about 47%); without
   them it averages +0.4 points per trade, profit factor 1.006.
5. **Family and multiple testing.** Log every configuration evaluated by any route (kernel, re-score, signal-only, replay) append-only, and deduplicate by a hash of
   the signal list: the distinct signal lists are the family. Compute the minimum detectable effect first (one trade has SD 204 points; with 800 changed orders
   the detectable gain is about 18 points uncorrected, 34 at 1,000 configurations, 41 at 100,000; with 2,000 changed orders 11, 22 and 26; 80% power; reviewer).
   Test: the maximum over configurations of the trading-day t of (candidate minus baseline); 5,000 draws, each flipping the sign of every trading day's total, one
   flip vector shared by all configurations; adjusted p = share of draws at or above the observed maximum; report the gain minus the mean permuted maximum.
   Accept a candidate only if adjusted p < 0.05; then freeze at most 5 candidates and open each untouched period once, logging it in
   `results/direction/oos_once.json`; a later edit relabels that period as seen. A candidate passes only with the same sign in every untouched period and for buys
   and sells separately, and a pooled trading-day block 90% lower bound above zero. Findings already seen in `REPORT.md` section 10 (`FG_InpBandAtr` 1,
   `FG_InpEntryDistAtr` 1, `MicroBreakLookbackSeconds` 60, `InpCPMinTickRate60` 0 to 2) are hypotheses to test on untouched data, not results.
6. **Stress** (one at a time, not crossed): delay 0 / 150 / 400 ms (nearly inert under StopOnly; keep 150 in searches), commission 0 / 3 / 7 points, stop-loss slip
   1.0 / 1.5 / 2.0, strict fills, spread x0.7 and x1.3 with `MaxTrailingMultiplier` and `MaxSpreadPoints` rescaled, stop distance 35 / 50 / 70, pending expiry
   3 / 5 / 8 s. Pass: at least 80% of cells positive and none below minus half the gain. Regimes and stress cells share one price path: they test robustness,
   not independence.
7. **Order flow.** Calibrate direction with flow off first (the frozen preset has `UseOrderFlow` false); flow is a robustness panel. `MinFlowImbalance`,
   `FlowComponentScore`, `MinScoreEdge` and `WeakFlowMarket*` stay shipped (the generator's magnitudes cannot identify the 5.0 threshold; `WeakFlowMarket*` is dead
   under StopOnly). Regimes: off (the same as always neutral); always agree; calibrated random at update periods 250 ms, 1 s and 4 s, as an ensemble of parameter
   sets inside the 95% intervals of all targets, with component correlation 0 and 0.5; lead and anti-lead defined by the hit rate of the vote sign on the next 30 s
   move (65, 55 and 45%); lead is reported, never voted on. With the live logs, first measure that hit rate on ALL logged decision rows (skips included) with a
   trading-day bootstrap, and use it. Candidate and baseline share every seed; confirm with 20 new seeds; the interval for a gain comes from resampling trading
   days, not from the seed SD. A regime where the baseline has fewer than 300 trades is reported, not voted on.
8. **Fitting the feed generator (simulated method of moments).** Fit under the shipped preset with `UseOrderFlow` true (the account's inputs made the real
   trades), to the real label ratios only: buy-market FA/FD/none 74/12/14 and the market route at 74% of trades; P(next market trade has the same label) 0.685
   (2.4 standard errors above chance: scan persistence as none / weak / strong). Check, do not fit: sell-market 86/14/0, FLXQ 4/24/72, EXHL 28/18/54 (labels
   there are relative to the burst side the EA fades). Do not fit trades per day (the replay's price layer differs from the live one, and the hours with ticks on
   disk are the busiest; 117 a day is 2,584 trades over 22 days). First check the price layer alone on the two feed-off runs (207 trades, 7 to 8 Sep and 28 to 30
   Sep, server time; only 32 have ticks on disk: download the hours). Fit on 7 to 22 Sep, test on 23 Sep to 8 Oct. Server time is UTC+3.
9. **End game.** Deliver the centre of the best plateau (the mean of the untouched metric over plus and minus one grid step); the `*_TESTER_OPT.set` ranges are
   that plateau, and the MT5 checklist states the minimum detectable effect. Give the independent reviewer only the frozen candidate list and the access log, and
   have them run: the truncation test, the anchor check, results without the best 5 days, a one-hour time-shift placebo and a within-day outcome shuffle. Run the
   whole search once on within-day shuffled outcomes (false-accept rate at most 5%) and once with a planted +10 point effect (report the recovery rate).
