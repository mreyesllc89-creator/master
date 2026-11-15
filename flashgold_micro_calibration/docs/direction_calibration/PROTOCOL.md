# Acceptance protocol for the direction calibration (binding)

Written after a statistics review and two cold-start reviews of the first drafts. Numbers marked (reviewer) are the reviewers' own calculations: check them
before leaning on them. "No change" and "unproven" are valid results. A failed gate stops the search, not the tools.

**Definitions.** Trading day = UTC calendar day. Alert episode = alert-candidate ticks less than 20 s apart merged (counts in BRIEF section 5; merge at 60 s
for inference). Gross per trade = side x (mid at exit minus mid at fill) / 0.01 points, before spread, slippage and commission; net = the engine's points. The
engine must log both mids (the prototype does not: add it). Frozen execution = presets/FlashGold_NativeReference_Calibrated_DISABLED.set plus sweep.REAL_FILLS
(150 ms delay, 10-point snap, stop-loss slip 1.5).

1. **Primary endpoint.** Net points per trading day from the full replay under the frozen execution. Trade floor: 50% of the frozen preset's trades over the
   whole period. The gain over the baseline must be positive for buys and for sells separately, and no input may treat them differently (buys beat sells in
   6 of 9 months, including March when gold fell 13%). Report every result without the best 5 days; the gain must keep its sign (the best 5 of the 158 days on
   which the preset traded make 96% of its net, 28 and 29 Jan 2026 alone 47%; without them it averages +0.4 points per trade, profit factor 1.006). Screening
   diagnostic only: gross move at +5/+10/+30 s per alert episode (first pass), divided by trailing volatility, with trading-day intervals.
2. **Anchors and placebos.** Anchor every outcome at the tick where the order would be sent (the hold-pass row), never at the arming tick: the entry hold needs
   +5 points over 1,100 ms and FlashGold is re-read at release. Use the alert-start tick as the candidate-independent event reference. Truncation test: cut the
   data after tick i; the features of row i must not change. The average of both sides is zero for gross moves and the unchosen side has no realistic fill: use
   sign-flipped outcomes and the unfiltered burst-follow at the same alert size as placebos. Net numbers come from engine trades only. Screen with full replays
   (0.3 to 2 s each). The prototype's forward kernel is validated for market entries only: use it only if a stop-order variant matches the engine and its Spearman
   correlation with the full-replay net per day over at least 50 random sets is at least 0.5.
3. **Data periods.** The nine months (Nov 2025 to Nov 2026) are burned: the calibrated preset was chosen with all of them in view after about 1,700 replays (about
   3,000 with the zero-delay searches). Use them for screening only; cut folds at weekend closes (the gap is over 6 h, longer than any hold); cluster by trading
   day. Untouched periods: earlier years from the Hugging Face dataset (May 2021 to Oct 2025: list its year=/month= trees first and report any missing month; own
   data root; half a year at a time because of 16 GB RAM) and June to September 2026 if the throttled Dukascopy download finishes (7 Sep to 8 Oct 2026 is where
   the fill model was fitted and the flow generator will be fitted: exclude it). Declare the earlier-year scaling before any outcome is read, from past data only:
   set MaxTrailingMultiplier per year so that alert episodes per trading day equal the nine-month rate, and MaxSpreadPoints = 0.93 x the year's median spread; also
   run the unscaled rule; accept on gross only; report tick rate, continuation-filter pass rate and spread median per year (ticks.py hard-codes the Dukascopy
   median spread 54.6, so rebuilt spreads differ by year). To check Hugging Face against the raw feed, download one March 2026 week of raw hourly files (about 120
   hours, throttled) and compare, or drop the check.
4. **Gates.** Gate 0, before the feed is used in any search: replay the frozen preset on two untouched half years, one with a long falling stretch (for example
   April to September 2022: check the price path first); both stay spent. If the pooled gross edge has a trading-day bootstrap 90% lower bound at or below zero, no
   acceptance is possible: report "unproven", deliver the tools and label any screening exploratory. Gate 1: the Spearman correlation of the metric between two
   disjoint halves of the nine months, over at least 200 random sets (inputs drawn within one grid step of the preset), must be at least 0.3 (the earlier joint grid
   gave 0.06 and 0.27); otherwise test at most 20 sets fixed in advance.
5. **Family and multiple testing.** Log every configuration evaluated by any route, append-only, and deduplicate by a hash of the signal list: the distinct signal
   lists are the family; only full-replay configurations enter the test. Compute the minimum detectable effect first (mean gain per changed order, iid trades,
   one-sided, Bonferroni, 80% power, ignoring day clustering and pair variance; one trade has SD 205 points; with 800 changed orders about 18 points uncorrected, 34
   at 1,000 configurations and 41 at 100,000; with 2,000 changed orders 11, 22 and 26; reviewer). Test: the maximum over configurations of the trading-day t of net
   (candidate minus baseline); 5,000 draws, each flipping the sign of every trading day's total, one flip vector shared by all configurations; adjusted p = share
   of draws at or above the observed maximum. Accept only if adjusted p < 0.05. Then freeze at most 5 candidates (with their grid neighbours, so that one opening
   covers the plateau) and open each untouched period once (acceptance uses periods other than Gate 0's: June to September 2026 and at least two more earlier half
   years), logging it in results/direction/oos_once.json; a later edit relabels that period as seen. A candidate passes only with the same sign in every untouched
   period, for buys and sells separately, and a pooled trading-day block 90% lower bound above zero. Findings already seen in REPORT.md section 10 (its four rows
   FG_InpBandAtr 1, FG_InpEntryDistAtr 1, InpCPMinTickRate60 2 and 0, and the best values of its one-at-a-time table, for example MaxSpreadPoints 12 and
   MicroBreakLookbackSeconds 60) are hypotheses for untouched data, not results.
6. **Stress**, one at a time: delay 0 / 150 / 400 ms (nearly inert under StopOnly; keep 150 in searches), commission 0 / 3 / 7 points, stop-loss slip 1.0 / 1.5 / 2.0,
   strict fills, spread x0.7 and x1.3 with MaxTrailingMultiplier and MaxSpreadPoints rescaled (450 / median spread; 0.93 x median), stop distance 35 / 50 / 70.
   Pass: at least 80% of cells positive and none below minus half the gain. Regimes and stress cells share one price path: they test robustness, not independence.
7. **Order flow.** Calibrate direction with flow off first (the frozen preset has UseOrderFlow false); flow is a robustness panel. MinFlowImbalance,
   FlowComponentScore, MinScoreEdge and WeakFlowMarket* stay shipped (the generator's magnitudes cannot identify the 5.0 threshold; WeakFlowMarket* is dead under
   StopOnly). Regimes: off (the same as always neutral); always agree; calibrated random at 1 s updates (finalists once more at 250 ms and 4 s) as an ensemble of 5
   parameter sets inside the 95% intervals of the fit targets, with component correlation 0 and 0.5; lead (the vote sign hits the next 30 s move 65% of the time:
   report only) and anti-lead (45%). With the live logs, first measure that hit rate on ALL logged decision rows (skips included) with a trading-day bootstrap, and
   use it. Candidate and baseline share every seed; screen with 3 seeds, confirm with 20 new ones; the interval for a gain comes from resampling trading days, not
   from the seed SD. A regime where the baseline has fewer than 300 trades is reported, not voted on.
8. **Fitting the generator (simulated method of moments).** Fit on the shipped preset with UseOrderFlow true (the account's inputs made the real trades). Fit
   targets: buy-market FA/FD/none 74/12/14; the market route at 74% of trades; P(next market trade has the same label) 0.685 (random-order null 0.661, SD 0.006, z
   about 4; scan persistence none / weak / strong). Check, do not fit: sell-market 86/14/0, FLXQ 4/24/72, EXHL 28/18/54, and trades per day (the replay's price layer
   differs and the hours with ticks on disk are the busiest; 117 a day is 2,584 trades over 22 days). First check the price layer alone on the two feed-off runs (207
   trades, 7 to 8 Sep and 28 to 30 Sep, server time; 32 are replay-usable: download the hours). Fit on 7 to 22 Sep, test on 23 Sep to 8 Oct (server time is UTC+3).
   The Dukascopy ticks of 7 Sep to 5 Oct are missing on disk (about 375 hours, about 1 hour throttled).
9. **End game.** Deliver the centre of the best plateau; the *_TESTER_OPT.set ranges are that plateau, and the MT5 checklist states the minimum detectable effect.
   The independent reviewer is a fresh subagent or session (otherwise write "self-review, not independent"), given the repo at the freeze commit, the frozen candidate
   list and the access log, not PROGRESS.md or results; it reruns the truncation test, the anchor check and the results without the best 5 days. Run the whole search
   once on within-day shuffled outcomes (it must accept nothing) and once with a planted effect of the minimum detectable size (report the recovery rate).
