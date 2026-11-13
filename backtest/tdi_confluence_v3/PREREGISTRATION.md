# Pre-registration: confirmation test of the frozen 15m rule at 98% confidence

Written 2026-11-13, **before any trading rule was simulated on, or any return computed from, the test data below.** The validation code (`validate.py`) was written and checked on the tuning data alone (`python3 validate.py selftest`).

*Corrected in Amendment 1 (section 8). The original sentence said the test data had not been loaded and existed as zip files only. That was no longer true when the file was committed: the zips had been converted to `.npz` and scanned for format, gaps and timestamps (`build_npz.py`, `data_quality.txt`). No indicator, signal or return was computed.*

The point of writing this down first: the rule, the data, the tests and the pass mark are fixed now, so the result cannot be bent afterwards by choosing whichever test, period or setting happens to look best.

## 1. What is being tested

**Claim:** the frozen rule below makes money per trade, after costs, on BTCUSDT, and does so because of its entry signal rather than by luck.

"Proven at 98%" means: if the rule had no edge at all, a result this good would turn up less than 2% of the time.

## 2. The frozen rule

Exactly the defaults of `TDI_Confluence_Strategy_v3.1.pine`, on a 15-minute chart:

| Input | Value |
|---|---|
| Pivot left / right strength | 5 / 5 |
| Min / max bars between swings | 5 / 60 |
| Day start | 13:00 UTC |
| TF and divergence toggles | defaults; toggles do not gate entries |
| Require 4th signal | off |
| TDI levels filter | on, buy ≤ 42, sell ≥ 58 |
| Stop | 5 × ATR(14) of the last closed 60m bar |
| Target | 2 × the stop distance |
| Trailing stop | off |

Simulation: `engine.py` as committed with this file. Entries fill at the next 15m bar's open. Stop and target are walked on real 1-minute bars. Commission 0.02% per side. No setting is changed after this point.

## 3. Data

All Binance spot 1-minute bars, UTC.

- **Primary test set (BTC, unseen):** BTCUSDT from its first bar (2017-08-17) to 2024-10-31 23:59 *(Amendment 1, section 8.2: trades are not opened in 2017-08 .. 2017-11, months with stale prices)*. None of it has been used so far. The series is cut at 2024-11-01, so nothing from the tuning period (2024-11-01 → 2026-11-12) enters. A position still open at the cut is dropped.
- **Replication set (six other coins, unseen):** ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, each from its first bar to 2024-10-31. The list is fixed here. None of these coins has been used so far.
- **Descriptive only:** the same six coins from 2024-11-01 to 2026-11-12. BTC over this window was used for tuning and the coins move with BTC, so this window is not clean evidence.
- **Exclusions:** none *(replaced by the data-quality rule of Amendment 1, section 8.2)*. Minutes the exchange did not publish stay missing.
- **Data quality, checked before the test without looking at any result** (`build_npz.py`, report in `data_quality.txt`):
  - no malformed price rows and no missing monthly files inside any coin's range;
  - missing minutes are 0.04% to 0.18% per coin, in 11 to 34 gaps; the largest is a 33.5-hour exchange outage on 2018-02-08/09, the rest are 10 hours or less;
  - about 15 days of BTC, ETH and BNB bars in two stretches between 2017-12-04 and 2018-02-10 are stamped 15 to 22 seconds off the minute. They are used as published; a bar is assigned to the 15-minute bar its start time falls in.

## 4. The verdict (primary test set only)

Statistic: average net return per trade, in basis points of the position's notional (1 bp = 0.01%), trades assigned to the month of their entry.

- **T1, profit:** resample whole calendar months with replacement 20,000 times and recompute the average. `p1` = share of resamples with an average ≤ 0. Resampling months instead of single trades keeps clustered trades together.
- **T2, skill against random timing:** 5,000 runs that place the same number of long and short entries on random 15m bars and use the same exits and costs. `p2` = (1 + number of runs whose average ≥ the real average) / 5,001.

**Decision rule** *(superseded by Amendment 1, section 8.4, before the test was run)*

| Outcome | Condition |
|---|---|
| **PROVEN at 98%** | `p1` < 0.02 **and** `p2` < 0.02, at 0.02% per side |
| additionally **COST-ROBUST** | `p1` < 0.02 at 0.05% per side as well |
| **NOT PROVEN** | anything else |

If the outcome is NOT PROVEN, the rule is not re-tuned on this data to rescue the claim. Any setting chosen after looking at this data would need new unseen data of its own.

## 5. Supporting analyses (reported, but they do not change the verdict)

- **T3, direction:** 5,000 runs that keep the real signal bars and shuffle the long/short labels.
- **Replication:** the frozen rule on the six coins before 2024-11-01. Pooled trades, month-block bootstrap as in T1; "replicates" if the pooled `p` < 0.02. Per-coin tables, each with 1,000 random-timing runs.
- **Sensitivity of T1:** week blocks instead of months, and a plain t-test.
- **Breakdowns on the primary set:** by year, long vs short, costs of 0 / 0.02 / 0.05 / 0.10% per side, worst drawdown.
- **Neighbours on the primary set:** pivot 3 / 4 / 6 / 8, swing 10–120, levels off / 38-62 / 45-55, day start 00:00 / 12:00 / 14:00, stop 3× ATR(60m), stop 8× ATR(60m) with target 3R, stop 5× ATR(240m). These show whether the rule sits on a plateau; they are not candidates for a new pick.
- **Data-snooping check on the tuning data** (`reality_check.py`, uses no test data): how good the best of ~100,000 tried settings looks when nothing has an edge.

## 6. Power *(corrected in Amendment 1, section 8.5)*

On the tuning data the rule made +62.9 bp per trade with a standard deviation of about 340 bp, at about 9 trades a month. The primary set has about 86 months, so roughly 800 trades are expected. With 800 trades the test detects a true edge of about 35 bp per trade or more 80% of the time. A real but smaller edge may fail the test; that would be reported as "not proven", not as "disproven".

## 7. Mechanics

- Random seed 20261113 for all resampling.
- `python3 validate.py run` is executed once. Its console output is saved as `validation_out.txt`, the numbers as `validation.json`, the trades as `trades_BTC_oos.csv` and `trades_alts.csv`.
- Any deviation from this protocol, including a bug found after the run, is listed in `RESULTS.md` together with the result before and after.

## 8. Amendment 1 (2026-11-13, after an independent audit, before the test was run)

**Who reviewed it.** Five reviewers audited the protocol and code: statistics, look-ahead, the simulation path, the reporting code and the data pipeline. A sixth review played the skeptic. Adversarial verifiers began checking the findings. A usage limit stopped that step after four verdicts, all on the statistics, and the remaining findings were fixed or answered directly.

A final review then checked the amended code and text, with three reviewers:
- the code path;
- the statistics;
- an end-to-end rehearsal of the strict run on synthetic data.

An adversarial verifier checked every defect that review claimed. `AUDIT.md` lists every finding of both rounds and what was done with it.

All reviewers worked under a blinding rule: they could run the strategy only on the tuning data or on synthetic data, and could read the unseen files only for timestamps, trading volume and byte-for-byte equality checks.

**What this amendment does.** Every change below either fixes a bug, adds a data-quality rule decided without any strategy result, or makes the verdict stricter. All of it was committed before `validate.py run` was executed. Sections 1–7 are kept above as originally written; where this section differs, this section applies.

### 8.1 Corrections to the record

- **Header:** corrected as noted there. During the audit, the data-pipeline reviewer compared the `.npz` files row by row with the source zips (equality only), and the leakage reviewer read timestamps only. No return was computed from unseen data.
- **Earlier use of the same market:** BTC/USD 2023-01 → 2026-10 (Bitstamp feed) was analysed earlier in this repository for a different indicator (`FlashGold_Direction_Filter_v1_2.pine`). That window overlaps 22 of the primary months. "Unseen" therefore means: not used for any choice made in `backtest/tdi_confluence_v3`. Nothing links that study to this rule's settings, and the design history of the user's v3.0 script is not known.
- **`data_quality.txt`:** it understates missing minutes by 3 for BTC, ETH and BNB. The correct counts are 8,562 / 8,563 / 8,143. The formula in `build_npz.py` is fixed; the `.npz` files are correct and unchanged.
- **Data pinned:** `data_manifest.sha256` (commit 4046ce7) holds the SHA-256 of all 782 source zips and the 8 `.npz` files. Every zip matches the `.CHECKSUM` file Binance publishes (782 of 782, `make_manifest.sh`).

### 8.2 Data-quality exclusion (new; decided from trading volume only)

Some months have many 1-minute bars with **zero traded volume**: no trade happened, so the price is stale.

- **BTC:** 33%, 22%, 12% and 4% of the minutes in 2017-08 to 2017-11; 0.23% or less in every later month. Any threshold from 0.23% to 3.8% gives the same BTC exclusion.
- **The other coins:** excluded months:

  | Coin | Months excluded |
  |---|---|
  | ETH | 4 |
  | BNB | 8 |
  | SOL | 5 |
  | XRP | 4 |
  | DOGE | 18 |
  | ADA | 19 |

  Most are illiquid early months, but BNB 2018-08 → 2019-01 and XRP 2019-12 come later. Unlike BTC, these exclusions depend on the threshold, so the other-coins reading depends on it somewhat:

  | Threshold | BNB | XRP | ADA |
  |---|---|---|---|
  | 0.5% | 9 | 6 | 26 |
  | 1% | 8 | 4 | 19 |
  | 2% | 5 | 2 | 15 |

Stale stretches feed the 1-minute TDI artificial flat runs; one reviewer showed that its crossings and pivots there are decided by floating-point noise. They also make fills unrealistic.

**Rule:** a calendar month is excluded for a coin if more than **1%** of its 1-minute bars have zero volume.
- No trade is opened whose signal bar or fill falls in an excluded month. So a signal on the last 15m bar before such a month cannot fill at its first minute.
- A position already open when an excluded block begins is left to its stop or target; signals inside the block do not reverse it.
- Indicators still run through excluded months.
- For BTC, whose excluded block starts the series, neither of the first two cases can arise.

`data_exclusions.py` applies the rule using only the volume column; the result is `data_exclusions.json`. For BTC it excludes 2017-08 to 2017-11, leaving **83 months, 2017-12 → 2024-10**. The result without the exclusion is reported as a sensitivity.

### 8.3 Bug fixes

None of these changes the tuning-data result: `selftest` still gives 232 trades, +62.9 bp, t +2.82.

- **Off-grid timestamps (`engine.py`):** BTC, ETH and BNB bars from 2017-12-04 to 12-18 and 2018-02-09/10 are stamped 15–22 s after the minute. The 1-minute feed was then read one bar late on its 15m bar. A bar now closes at the end of the minute slot it starts in, as on TradingView. A `selftest` check shifts two weeks of tuning data by +14.789 s: the registered engine changed 12 signals and one trade; the fixed engine changes none.
- **Signal cache (`engine.py`):** keyed on a checksum of the whole dataset, not only its length and end points.
- **Zero stop distance (`validate.py`):** a stop distance of exactly 0 is no longer a valid entry, matching the Pine script's `slDist > 0`.
- **Reporting (`validate.py`):**
  - the maximum drawdown is counted from the starting equity;
  - no random-timing p-value is printed for a coin with fewer than 3 trades;
  - pooled rows leave out a trade-level t that would ignore the correlation between coins;
  - verdict lines print 6 decimals and the counts behind each p-value.
- **Found by the final review** (none can change the BTC verdict; they make the code match this text):
  - **Excluded-month boundary:** a signal on the last 15m bar before an excluded month could fill at 00:00 of that month. Now no entry is allowed whose signal bar or fill lies in an excluded month. A verifier showed BTC is unchanged (its block starts the series) and the dryrun output is bit-identical. A selftest check uses a real month-end signal.
  - **T4:** a year whose removal leaves too few trades or months for a p-value now counts as a fail. Before, it was skipped, and whether it was skipped depended on the year order. This is unreachable for BTC.
  - **Crash guards:** a null summary with no usable runs no longer crashes. Undefined p-values never pass.
  - **Strict start:** the run checks that git really confirms the registered files and `data_manifest.sha256` are committed and unchanged. Before, a git error read as "clean". It also checks that every test file is listed in the manifest.
  - **Output:** all result files are written together at the end, and the run writes its own console log.
  - **Reporting:** permutation p-values are labelled as reported only, the printed power line is labelled as one test alone, and the coin count is no longer hard-coded.

### 8.4 Verdict rule, replaced (stricter)

**Why the registered tests were replaced:**

- **T1** (month-block percentile bootstrap) passes up to 2.5% of no-edge histories even with independent months, and 4–11% when the rule's monthly results carry over from month to month or follow multi-month regimes. The amended verdict lowers these rates but, for regimes lasting about 6 months or more, not to 2% (table below).
- **T2**, compared on raw averages, passes about 2.5–4.5% of histories in which no entry rule can have skill. Random entries produce more, smaller trades than the rule, so their averages spread less than the rule's own average does. A verifier confirmed this and showed that comparing raw t-statistics, the first fix considered, is also miscalibrated.
  - **Adopted fix:** compare the rule's average with the null runs' average, using the rule's own clustered standard error. Centred at 0, the statistic is exactly T1a.
  - **T3 (sign-flip histories):** in sign-flip martingale histories built from the tuning data, where no rule can have skill, T3 passes about as often as T1a, about 2%.
  - **T2 (same histories):** T2 passes somewhat more often, about 2.4–3% against 1.9–2.2% for T1a. The rule enters against the preceding move, so within a month its trades tend to do well when random entries do badly (correlation about −0.15), and the rule's own standard error leaves this out.
  - **Effect on the verdict:** T1a and T3 must also pass, so the full verdict passes 0.4–0.8% of these histories. When a common positive mean lets T1a, T1b and T4 pass, T2 and T3 together pass about 1.3%.
- **No consistency check:** a pass could rest on one volatile year. Per-trade bp scales with the ATR stop, so volatile periods dominate the average.
- **Direction not tested:** T2 does not test whether the rule's long/short calls carry information, which section 1 claims.

**The verdict tests.** All are computed on the primary set (BTC, 83 months, 0.02% cost per side), with the average bp per trade as the statistic.

| Test | What it checks | Pass mark |
|---|---|---|
| **T1a** | Cluster-robust t-test, calendar months as clusters: e_g = month sum − mean × month count, se = √(G/(G−1) · Σe_g²) / N, one-sided Student t with G − 1 degrees of freedom (G = months with trades) | p < 0.02 |
| **T1b** | The same with consecutive 6-month blocks as clusters, counted from 2017-12 (December–May, June–November; 14 blocks, the last one 2024-06 → 2024-10) | p < 0.02 |
| **T2** | 10,000 runs with the same number of long and short entries on random valid 15m bars. Their average m₀ is compared with the rule's average using the rule's own month-clustered standard error: t = (mean − m₀) / se, one-sided, G − 1 degrees of freedom | p < 0.02 |
| **T3** | 10,000 runs on the rule's own signal bars with the long/short labels shuffled; their average is compared the same way as in T2. It tests the direction calls | p < 0.02 |
| **T4, consistency** | With each calendar year (2017 … 2024) removed in turn, the T1a p-value of the remaining trades. "2017" is a single month, 2017-12, so T4 in effect covers 2018–2024 | below 0.05 every time; a p-value that cannot be computed counts as a fail |

**Outcomes:**

| Outcome | Condition |
|---|---|
| **PASSED: edge significant at the 98% level** | T1a, T1b, T2 and T3 all pass, and T4 passes |
| additionally **"also under realistic execution"** | T1a and T1b also pass with 0.05% per side, stops hit inside a 1-minute bar filled at that bar's worst price (a bar that opens beyond the stop fills at its open), and a holding cost of 3 bp per day on both sides |
| **NOT PASSED** | anything else |

**What "significant at the 98% level" means here:**

- **Short memory.** If the rule's monthly results have short memory (carry-over from month to month up to about 0.5, or ±30 bp regimes lasting about 6 months), a rule with no edge passes about 1 time in 50 or less.
- **Longer regimes.** If the rule's own results follow longer regimes, a rule with no long-run edge passes more often: about 2.3% for ±50 bp regimes of about 6 months, 2.9% for carry-over 0.7, 5% for ±50 bp regimes of about 12 months, and 11% for 24 months.
  - Almost all of these passes come from histories in which the rule's good regime covered most of 2017-12 → 2024-10, so the rule really did earn in that period.
  - When the regime average over the period was not positive, the verdict passed at most 0.2% of the time.
  - The 25 tuning months show no persistence (lag-1 autocorrelation of monthly results −0.14, standard error about 0.2), but 25 months cannot rule such regimes out.
- **What a PASS shows.** The rule earned more than chance explains on BTC from 2017-12 to 2024-10. That it keeps earning outside that period also rests on the short-memory assumption.
- **No extra regime test.** The guards tried bring the 12-month-regime rate only to about 3.3–3.5% and cost about 9–15 points of power at 35 bp: T4 at 0.02, or a test with 12-month blocks.
- **What it does not mean.** It does not mean "98% sure the edge is real". That also depends on how likely an edge was before the test, and `reality_check_out.txt` shows the pick looks ordinary for a search of this size. The claim covers BTC from 2017-12 to 2024-10, not the future.

**Simulated pass rates in histories with no long-run edge.**
- **Setup:** 83 calendar months 2017-12 → 2024-10, about 9.2 trades a month, and the shape of the 232 real tuning trades.
- **Source:** `sim_regimes.py`, 40,000 histories per row, output in `sim_regimes_out.txt`. Monte Carlo error is ±0.05–0.15 points. The first three rows agree with `sim_final.py` (3,000 histories: 1.0%, 1.7%, 0.8%) within its Monte Carlo error.
- **T2 and T3** can only lower the verdict column.
- **Last column:** the original test as first registered, run on the same histories.

| Scenario | Verdict (T1a + T1b + T4) | Registered T1 |
|---|---|---|
| Common month effect, as in the tuning data | 0.9% | 2.2% |
| Month effect carried over, autocorrelation 0.5 | 1.75% | 4.6% |
| Volatility profile by year | 0.8% | 2.1% |
| Month effect carried over, autocorrelation 0.7 | 2.9% | 7.5% |
| Regimes ±30 bp, about 6 months | 1.4% | 3.6% |
| Regimes ±50 bp, about 6 months | 2.3% | 6.0% |
| Regimes ±30 bp, about 12 months | 2.7% | 5.8% |
| Regimes ±50 bp, about 12 months | 5.2% | 10.7% |
| Regimes ±50 bp, about 24 months | 10.8% | 17.9% |

Most of the gain over the registered T1 comes from requiring T1a, T1b and T4 together. T1a alone passes about 2.0%, 4.3%, 1.8% and 10.2% in the first three rows and the ±50 bp, 12-month row.

**Still reported, but not part of the verdict:**

- the registered bootstrap p, and the permutation p-values of T2 and T3 on raw averages and on t-statistics;
- the results in **R**, i.e. return ÷ stop distance, which is what a trader who sizes by risk earns;
- 98% one-sided bounds on the average;
- month boundaries shifted by 0–29 days;
- shorts dropped before 2019-09-13, when Binance listed its BTCUSDT perpetual (shorting on Binance itself was limited before that);
- costs of 0 / 0.05 / 0.10% per side;
- the result without the stale-price exclusion;
- by-year and long/short tables, and the worst drawdown.

**Pre-set readings, fixed now:**

- **Neighbours:** the 14 neighbour settings of section 5 count as a **plateau** if at least 9 have a positive average, and as an **isolated peak** otherwise.
- **Other coins** (surviving large caps chosen in 2026; same calendar period as the BTC test, so not independent confirmation): **consistent with an edge** if their pooled clean trades pass T1a and T1b, using calendar months across all coins as clusters, which absorbs their common moves. Otherwise the reading is **BTC-only or no edge**. The correlation of monthly results between BTC and the other coins is reported.

### 8.5 Power, corrected

Share of histories in which T1a, T1b and T4 all pass, from `sim_final.py` (same setup, 3,000 histories per row, seed 1, output in `sim_final_out.txt`):

| True edge per trade | 20 bp | 35 bp | 45 bp | 62.9 bp |
|---|---|---|---|---|
| Constant in bp | 16% | 50% | 76% | 98% |
| Scaled with each year's volatility (constant in R) | 15% | 48% | 72% | 96% |

If 2017–2022 trades were about 1.3–2× larger in bp than tuning trades while the edge stayed constant in bp, power at 35 bp falls to about 24%.

The table counts T1a, T1b and T4 only; requiring T2 and T3 as well costs about 1–2 more points. The month effect is set to 60 bp. That matches the tuning data's clustering averaged over month boundaries (shifted 0–29 days); the calendar months alone suggest about 90 bp. At 90 bp, power is about 38% at 35 bp and 62% at 45 bp. The tuning data cannot tell these two settings apart.

**How to read a NOT PASSED:** it means "not shown", not "disproven". The run prints a 98% upper bound so the reader can see which edge sizes the data rules out.

### 8.6 Mechanics

`python3 validate.py run` refuses to start if any of these holds:

- git cannot confirm that `engine.py`, `validate.py`, `PREREGISTRATION.md`, `data_exclusions.json` and `data_manifest.sha256` are committed and unchanged;
- a result file already exists (`validation.json`, `trades_BTC_oos.csv`, `trades_alts.csv` or `validation_out.txt`);
- the BTC or any of the six other-coin `.npz` files is not listed in `data_manifest.sha256`, or any listed `.npz` differs from it.

**Records:**
- `validation.json` records the git commit, the SHA-256 of code and data, and the Python, numpy, pandas and numba versions.
- The run writes its own console log, `validation_out.txt`, which it creates and never overwrites. All other result files are written together at the end.
- The run is deterministic for a fixed environment.

**If the run stops with an error before it finishes:**
1. The partial console log is renamed `validation_out_crash1.txt` and committed as it is.
2. The bug is fixed and listed in `RESULTS.md`.
3. The run is started again.

The verdict lines of the partial log and of the new run are both reported. If they differ, both are shown and the difference is explained.
