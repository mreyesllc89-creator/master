# TDI Confluence Strategy: stop-mode backtest (v3.0 → v3.1)

> **Latest: Update 4, the pre-registered confirmation test, did not pass.**
> - **The test:** the frozen 15m pick was tested once, at 98% confidence, on seven years of BTC history it had never seen (2017-12 → 2024-10).
> - **The result:** it lost 27.9 bp per trade over 626 trades, every test failed by a wide margin, and 13 of the 14 neighbouring settings lost too.
> - **What it means:** none of the results below show an edge that holds on unseen data. See [Update 4](#update-4-the-pre-registered-confirmation-test-not-passed) and the revised [Recommendation](#recommendation).

**Data:** Binance BTCUSDT, 1-minute bars, 2026-04-01 → 2026-10-31 (308,160 bars). Tick size 0.01, so 100 ticks = $1.
**Costs:** 0.02% commission per side unless stated. Sizing: 1% of equity per trade, as in the script.
**Units:** "bp" is the average trade result in basis points of the position's notional value, after commission. It does not depend on position size: at 1% of equity, +50 bp per trade is +0.005% of the account per trade, and it scales linearly with size.

> **Correction:** the first version of this file, from the first push of this branch, was wrong. The engine's timestamps were in milliseconds while the multi-timeframe mapping assumed nanoseconds, so the 5m, 15m, 30m and 1h TDI and divergence states never reached the chart. That is fixed now, with a regression test in `test_mtf.py`, and every number below comes from the fixed engine.

## v3.0 as written (200/400 ticks, trail 150/50)
| Chart | Trades | Win %, no fees | Profit factor, no fees | bp/trade, no fees | bp/trade, 0.02%/side |
|---|---|---|---|---|---|
| 1m | 468 | 52 | 0.95 | −0.1 | −4.1 |
| 5m | 292 | 49 | 0.91 | −0.4 | −4.4 |
| 15m | 203 | 53 | 1.07 | +0.5 | −3.5 |

Without fees it roughly breaks even, and with fees it loses. A 200-tick stop is $2 on BTC, so every trade is a coin flip that then pays the commission.

## What changed in v3.1 (`TDI_Confluence_Strategy_v3.1.pine`)
- **Stop Mode** input: `ATR` (default), `Percent` or `Ticks`. TP is set as a multiple of the stop distance (R). Trailing activation and offset are fractions of the stop distance.
- **ATR:** `ta.atr(14)` on the chart, or on 15m or 60m using the last **closed** higher-timeframe bar (`[1]` + `lookahead_on`), so it doesn't repaint.
- **Frozen distances:** the stop distance is fixed at the signal bar. The exit is attached on the entry bar, so the position is protected **from the fill bar**. In v3.0 the stop was only placed one bar after the fill.
- **Conflicting signals:** bars that signal both long and short are skipped.
- **New option "TF/Divergence toggles also gate entries"**, off by default. Off keeps v3.0 behaviour, where entries use every timeframe's raw state and ignore the toggles.
- **Commission:** set to 0.02% in `strategy()` so the TradingView report includes costs.
- **Signal logic:** unchanged.

## Method
- **Stage A:** 8,064 input combinations reduce to 1,544 distinct signal sets, of which 1,015 have at least 60 signals. Inputs varied: chart 1/5/15m, pivot strength 3/5/8, swing bars 5–60 or 10–120, day start 00:00 or 13:00, divergence toggles, TF toggles with and without gating, 4th-signal filter, TDI levels off / 38-62 / 30-70 / 45-55.
- **Stage B:** every distinct signal set was run against 468 exit settings, **475,020 backtests** in total:
  - **Ticks:** 200–80,000 ticks × TP 1/2/3R × trail on/off. Each run twice: exits active from the fill bar, and v3.0's one-bar-late placement.
  - **ATR:** ATR on the chart, 15m or 60m × multiple 0.5–12 × TP 1–3R × 3 trail settings.
  - **Percent:** 0.1–2% × TP 1–3R × 3 trail settings.
- **Walk-forward:** each test month (Jul, Aug, Sep, Oct) is traded with the setting that scored best on all earlier months. The concatenated test trades estimate how each mode performs on unseen data.
- **Audit:** the engine was checked by two rounds of independent reviewers against Pine and TradingView semantics, with each claim verified adversarially. Fixed: the MTF time units, the trailing stop at the bar open, the RSI rounding form, reversal sizing, the higher-TF ATR `[1]` alignment (regression-tested), and the conflicting-signal bars.

## Which stop mode works best: ATR
**Across all 1,015 signal sets** (combinations with at least 100 trades, all 7 months):

| Mode | Share of combinations profitable | Median bp | 90th percentile bp |
|---|---|---|---|
| Ticks | 14% | −3.4 | +1.0 |
| **ATR** | **31%** | −2.1 | **+9.2** |
| Percent | 33% | −1.9 | +7.3 |

**Walk-forward**, choosing each month's setting by the t-stat on earlier months:

| Mode | Out-of-sample trades | bp/trade | Positive test months |
|---|---|---|---|
| Ticks | 33 | +7.5 | 3/4 |
| **ATR** | 61 | +3.9 | **4/4** |
| Percent | 36 | −4.1 | 2/4 |

Choosing by in-sample average instead gave ATR +46.9 bp (33 trades, 3/4 months), ticks +37.3 bp (3/4) and percent +15.6 bp (2/4). No mode reaches statistical significance in walk-forward, because there are too few out-of-sample trades. ATR is the only mode that was positive in every test month.

**Where the profitable ATR settings sit:** median bp across all signal sets, with TP 2R:

| Stop distance | chart ATR | 15m ATR | **60m ATR** |
|---|---|---|---|
| 1× | −2.5 | −1.9 | −2.0 |
| 2× | −2.8 | −2.2 | +0.8 |
| 3× | −3.0 | −1.2 | +4.4 |
| **5×** | −1.2 | +2.0 | **+10.9** |
| 8× | +0.5 | +7.2 | +9.2 |
| 12× | +2.5 | +7.6 | +9.8 |

Tight stops lose under every mode. Profit appears once the stop sits beyond the 1-hour noise, at roughly 3× ATR(60m) or more, which is about 1.5–3% on BTC. The percent mode shows the same pattern: 1.5–2% stops are positive and anything under 0.75% is negative. ATR beats percent because the distance adapts to volatility. Trailing helps tight stops a little and adds nothing at 5× ATR(60m), so it is off by default.

## Finalists: stress test
All rows use 5m or 15m charts, all 7 months, and 0.02% per side. The random-entry check places the same number of long and short signals at random times with the same exits, 300 times.

| Setup | Trades | Win % | bp | t | Profit factor | Long / short bp | bp at 0% / 0.05% fees | Months positive | Random entries beat it |
|---|---|---|---|---|---|---|---|---|---|
| **B: v3.1 defaults on a 5m chart** (5× ATR(60m), TP 2R, day start 00:00) | 144 | 56 | +13.6 | 0.8 | 1.18 | +16.5 / +10.5 | +17.6 / +7.6 | 5/7 | 14% |
| A′: same, day start 13:00 | 133 | 62 | +55.9 | 2.9 | 1.89 | +66.3 / +46.0 | +59.9 / +49.9 | 6/7 | <0.3% |
| A: day start 13:00, 8× chart ATR, TP 2R | 153 | 59 | +53.3 | 3.8 | 2.12 | +55.3 / +51.6 | +57.3 / +47.3 | 7/7 | <0.3% |
| C: v3.1 defaults on a 15m chart | 113 | 62 | +38.1 | 1.6 | 1.48 | +32.9 / +43.5 | +42.1 / +32.1 | 5/7 | 1% |
| D: 15m scalp, 0.5× ATR, TP 3R, trail | 154 | 66 | +6.8 | 3.8 | 2.31 | +6.4 / +7.1 | +10.8 / **+0.8** | 6/7 | <0.3% |
| v3.0 ticks 200/400, protected | 292 | 0 | −3.8 | — | 0 | — | +0.2 / −9.8 | 0/7 | — |

**Neighbourhood check** for the 60m ATR on the 5m defaults, bp per trade:
- **Day start 00:00:** every stop from 3× to 8× and every TP from 1.5R to 3R is positive, from +5 to +24.
- **Day start 13:00:** the same grid ranges from +28 to +62.

So it is a broad plateau, not a single lucky point.

**Day-start hour (5m chart, 5× ATR(60m), TP 2R, all 24 hours):** all 24 hours are profitable, averaging +22 bp. On a 15m chart, 20 of 24 are profitable, averaging +19 bp. 13:00 UTC is the best on 5m, at +56 bp with t = 2.9. Other hours mostly fall between +4 and +41 bp with t ≈ 0.2–2.2. The **ATR stop is the robust part. 13:00 is probably a lucky pick**, so I originally kept 00:00; the default is now 13:00 at the user's request (see the update below). Full table: `dayhour_out.txt`.

**Avoid D:** its edge is about 7 bp per trade before costs above 0.02%, and it disappears at 0.05% per side.

## Update 4: the pre-registered confirmation test, NOT PASSED

**Verdict: NOT PASSED. The edge is not significant at the 98% level.** On seven years of BTC history it had never seen, the frozen 15m pick of Update 3 lost money: **−27.9 bp per trade** after 0.02% fees, over 626 trades from 2017-12 to 2024-10. Every test failed by a wide margin.

### What was tested

- **Protocol:**
  - `PREREGISTRATION.md` (commit 76bebb8) fixed the rule, the data, the tests and the pass mark before any of the test data was simulated.
  - Amendment 1 (section 8) fixed the bugs found by two blinded audit rounds (`AUDIT.md`) and made the verdict stricter. It was committed as 54bcff4 before the run.
  - `validate.py run` was then executed. Its outputs are `validation_out.txt`, `validation.json`, `trades_BTC_oos.csv` and `trades_alts.csv`. All tables are in `validation_report.md`, generated by `report_validation.py`.
- **Rule:** exactly the v3.1 defaults on a 15m chart:
  - pivot 5/5, swing 5–60, day start 13:00 UTC, TDI levels 42/58;
  - stop 5× ATR(14) of the last closed 60m bar, target 2R, no trail;
  - 0.02% per side, with exits walked on 1-minute bars.
- **Data:** Binance BTCUSDT 2017-12 → 2024-10 (83 months), none of it used for any choice in this folder. 2017-08 → 2017-11 was excluded in advance for stale prices, decided from trading volume only.
- **Pass mark:** T1a, T1b, T2 and T3 all at p < 0.02, and T4 below 0.05 with any single year removed. If monthly results have short memory, a rule with no edge passes this about 1 time in 50 or less (Amendment 1, 8.4).

### Result

| Test | p | Pass mark | Result |
|---|---|---|---|
| T1a: profit, month-clustered t-test | 0.875 | < 0.02 | fail |
| T1b: profit, 6-month-block t-test | 0.811 | < 0.02 | fail |
| T2: beats random entry timing | 0.891 | < 0.02 | fail |
| T3: long/short calls carry information | 0.927 | < 0.02 | fail |
| T4: consistent without any single year (worst p) | 0.941 | < 0.05 | fail |
| Realistic execution: T1a / T1b | 0.983 / 0.946 | < 0.02 | fail |

**98% one-sided bounds on the true average** (month-clustered): **above −78.1 bp, and below +22.3 bp per trade.** Each bound holds at 98% on its own, so the range −78.1 to +22.3 is a 96% interval. The upper bound is the one that matters: it shows which edge sizes the data rule out.

- **No better than chance entries:**
  - Random entry timing averaged +2.0 bp per trade over 10,000 runs.
  - The rule's own signal bars with shuffled long/short labels averaged +7.3 bp.
  - The rule averaged −27.9 bp, below both. The gap is not significant: tested the other way, for worse than chance, the month-clustered p-values are 0.11 and 0.07.
  - So the entries showed no skill. The data do not show that they were worse than chance.
- **Costs only make it worse:** −23.9 bp before fees, −52.9 bp under realistic execution (0.05% per side, stops at the bar's worst price, 3 bp/day holding cost).
- **Mostly one bad year, but no edge without it either:**
  - 2018 lost heavily, at −224 bp per trade with a median trade of −369 bp. Its −17,034 bp is 98% of the whole period's −17,459 bp.
  - Without 2018 the average is −0.8 bp (p 0.51). That is break-even, not an edge. So the size of the loss rests on 2018, but the missing edge does not.
  - 38 of 83 months and 11 of 29 quarters were positive.
  - Without its 10 worst trades the average is −3.3 bp, still not positive. These descriptive figures come from `trades_BTC_oos.csv`.
- **Every view agrees:**
  - In R (return ÷ stop distance): −0.076 R per trade.
  - Longs −10.4 bp, shorts −44.5 bp.
  - Dropping shorts before Binance listed its perpetual (2019-09-13): −17.2 bp.
  - Without the stale-price exclusion: −31.1 bp.
  - Shifting the month boundaries by 0–29 days: month-clustered p between 0.86 and 0.89.
- **Risk:** worst trade −2,279 bp, a short on 2020-03-16 stopped in the COVID-crash rebound. Worst drawdown 26,672 bp of one position's notional.

| Cost per side | Trades | Win % | Avg bp/trade | Profit factor | Month-clustered t / p |
|---|---|---|---|---|---|
| 0.00% | 626 | 46 | −23.9 | 0.90 | −0.99 / 0.838 |
| **0.02%** | 626 | 46 | **−27.9** | 0.88 | −1.16 / 0.875 |
| 0.05% | 626 | 46 | −33.9 | 0.86 | −1.41 / 0.919 |
| 0.10% | 626 | 45 | −43.9 | 0.82 | −1.83 / 0.964 |
| Realistic execution | 626 | 46 | −52.9 | 0.79 | −2.16 / 0.983 |

| Year | Trades | Win % | Avg bp/trade | Total bp | Without this year: avg bp / p |
|---|---|---|---|---|---|
| 2017 (Dec only) | 12 | 50 | +46.5 | +559 | −29.3 / 0.883 |
| 2018 | 76 | 32 | −224.1 | −17,034 | −0.8 / 0.514 |
| 2019 | 79 | 44 | +21.9 | +1,730 | −35.1 / 0.907 |
| 2020 | 75 | 48 | −45.2 | −3,391 | −25.5 / 0.831 |
| 2021 | 107 | 51 | +9.5 | +1,012 | −35.6 / 0.908 |
| 2022 | 100 | 54 | +40.5 | +4,047 | −40.9 / 0.941 |
| 2023 | 85 | 36 | −49.1 | −4,178 | −24.5 / 0.815 |
| 2024 (to Oct) | 92 | 49 | −2.2 | −204 | −32.3 / 0.882 |

### Neighbours and other coins

These readings were fixed before the run.

- **Neighbours:**
  - Only 1 of the 14 neighbouring settings has a positive average: pivot 3, +4.3 bp, p 0.42.
  - The other 13 lose between −15.6 and −48.2 bp per trade. Among them are the earlier 15m default with the levels filter off (−20.7 bp over 1,109 trades) and day start 00:00 (−29.5 bp).
  - Pre-set reading: **isolated peak**. More plainly, no setting near the pick works on this data.
- **Other coins** (ETH, BNB, SOL, XRP, DOGE, ADA, same period):
  - Pooled −9.8 bp per trade over 3,084 trades (month-clustered p 0.73).
  - 3 of 6 coins positive, none significant (best: XRP +49.8 bp, p 0.08).
  - Pre-set reading: **BTC-only or no edge**. Their monthly results are uncorrelated with BTC's (0.02).
- **After 2024-11** (the BTC tuning window; descriptive only): the other coins pooled +22.8 bp (p 0.11). This fits a rule that did better in 2024–26 than before, i.e. a tuning result specific to that period.

### Deviations from the protocol

- **First run interrupted:**
  - The first `validate.py run` started at 23:36 UTC from commit 54bcff4. A container restart at about 23:40 UTC killed it during the null distributions.
  - There was no code error, and no result file had been written.
  - As pre-registered (8.6), its partial log is kept unchanged as `validation_out_crash1.txt`, and the run was started again at 23:41 UTC.
  - The new run started from commit a51780c, which only renamed that log; the code and data hashes were identical. It reproduced the partial log's result lines exactly. Nothing was fixed in between.
- **Log snapshots** were committed while each run was in progress:
  - 6602d44 holds the first run's log, committed before the restart. It is identical to `validation_out_crash1.txt`.
  - 1c3db1b and 7c17617 hold the new run's log part-way through.
  - The final log is in 04a8f78.
- **Nothing else deviated.** No setting was changed after the data was seen.

### What this means

- **The tuning result did not hold up.** The rule made +62.9 bp per trade in the tuning period, but its true average over 2017-12 → 2024-10 was below +22.3 bp at 98% confidence.
  - That excludes both the tuning figure and edges of 35–45 bp. The estimate is also negative, so the data argue against an edge of that size, not just fail to show one.
  - This comes from the bound, not from the test's power. Amendment 1 (8.5) gave a 35–45 bp edge only about a 50–76% chance of passing. On this data's wider spread, an edge of about 71 bp (T1a) or 96 bp (T1b) would have been needed to pass each test alone 80% of the time.
  - The exclusion of 35–45 bp edges leans on 2018: without 2018 the upper bound is +44.1 bp. The tuning figure is excluded either way.
- **This is what Update 3 warned of:** a sharp peak at pivot 5, no benefit from walk-forward optimisation, and a t-statistic within what chance produces across this many settings. The reality check (`reality_check_out.txt`) said the same.
- **No re-tuning.** As pre-registered, the rule is not re-tuned on this data. Pivot 3's +4.3 bp is not a new candidate: any setting chosen after seeing this data would need new unseen data of its own.

## Update 3: input optimisation for the 15m chart on two years

Scripts: `opt15.py` (first sweep), `opt15_final.py` (finalists on 1-minute bars), `opt15m.py` (re-run with exits on 1-minute bars), `opt15_wf.py` (walk-forward and marginals), `opt15_pick.py` (stress test of the pick). Outputs are the matching `*_out.txt` files. Costs 0.02% per side.

### The first sweep's winner was a simulation artifact
The first sweep (2,176,515 backtests, exits judged from 15m bars) ranked one family on top: stop 1× ATR(15m) with a trail activating at 0.5R and trailing by 0.25R. It showed +9.7 bp per trade, 70% wins, t = 6.5. Re-simulating the same trades with exits walked on real 1-minute bars gives **+1.4 bp** (t = 1.3), and a loss at 0.04% fees or more. A 15m bar only gives open, high, low and close, and the simulator, like TradingView without Bar Magnifier, has to assume the order of the high and low. Tight trailing stops exploit that assumption. Wide stops without a trail give identical results under both methods.

An independent audit of the 1-minute exit method found no defects.

### Re-run with exits on 1-minute bars (129,360 backtests)
539 distinct signal sets (pivot 3/4/5/6/8, swing 5–60 or 10–120, 13 day-start hours, TDI levels off/35-65/38-62/42-58/45-55/30-70) × 240 exits (ATR on chart/60m/240m × 1–12, percent 0.5–3, TP 1–4R, trail off or two trail settings).

- **Most settings lose:** 33% of combinations are profitable after fees; the median is −3.1 bp per trade.
- **The best results are no better than chance would produce:** 0.86% of combinations have t > 2 and 0.019% have t > 3. With no edge at all, roughly 2.3% and 0.13% would.
- **Last year's winners don't repeat:** rank correlation between year 1 and year 2 is −0.10. Of the settings profitable in year 1, 25% were profitable in year 2, against a 27% base rate.
- **Walk-forward optimisation adds nothing:** re-optimising on all prior data every 3 months and trading the next 3 months made −0.1 bp per trade over 231 trades. The top 1% of settings by training t-stat averaged between −10.6 and +6.4 bp in the following quarter.

### What is consistent
Median bp per trade across all exits:

| Pivot strength | All | Year 1 | Year 2 | Share profitable |
|---|---|---|---|---|
| 3 | −5.3 | −3.5 | −8.5 | 18% |
| 4 | −2.7 | +5.7 | −14.8 | 31% |
| **5** | **+2.1** | −1.0 | +5.8 | **64%** |
| 6 | −1.2 | +2.2 | −4.8 | 41% |
| 8 | −9.2 | −6.0 | −10.3 | 5% |

- **Stop width:** only wide stops have a positive median (5× ATR(240m) +2.2, 12× ATR(60m) +1.3). Every stop of 3× ATR or tighter, and every percent stop up to 2%, has a negative median.
- **TDI levels filter:** with pivot 5 and a wide stop, levels 42/58 or 45/55 are positive in both years at almost every day-start hour; with levels off, year 1 is near zero.
- **Day start:** 12:00–14:00 UTC is best, and other hours are weaker but mostly still positive with the levels filter on.
- **Trailing:** no benefit once exits are simulated on 1-minute bars.

### The pick: levels filter on at 42/58, everything else as before
Pivot 5/5, swing 5–60, day start 13:00, stop 5× ATR(60m), TP 2R, no trail, TDI levels on at 42/58. Exits on 1-minute bars.

| Setup | Trades | Win % | bp/trade | t | PF | Year 1 / Year 2 bp | Long / short bp | At 0.05% / 0.10% fees | Random entries beat it |
|---|---|---|---|---|---|---|---|---|---|
| Previous default (levels off) | 370 | 55 | +26.4 | 1.7 | 1.26 | 0.0 / +52.5 | +29.1 / +23.6 | +20.4 / +10.4 | 2.5% |
| **Pick: levels 42/58** | 232 | 59 | **+62.9** | 2.8 | 1.56 | +41.0 / +86.8 | +89.0 / +37.7 | +56.9 / +46.9 | 0 of 200 |
| Levels 42/58, 8× ATR(60m), TP 3R | 201 | 65 | +71.7 | 2.4 | 1.55 | +61.8 / +83.1 | +83.4 / +59.8 | +65.7 / +55.7 | 0 of 200 |
| Levels 42/58, 5× ATR(240m), TP 2R | 189 | 66 | +67.1 | 2.2 | 1.51 | +66.5 / +67.7 | +83.6 / +50.0 | +61.1 / +51.1 | 0.5% |
| Levels 45/55 | 258 | 56 | +45.4 | 2.2 | 1.39 | +22.6 / +70.4 | +66.5 / +25.2 | +39.4 / +29.4 | 0 of 200 |

For the pick: 6 of 9 quarters and 17 of 25 months were positive. The worst quarter was 2025 Q1 at −3,153 bp in total, the worst single trade −752 bp, and the worst drawdown 3,487 bp (35% of one position's notional; 0.35% of the account at 1% sizing). About 9–10 trades a month.

### Why this is still not a proven edge
Changing one input of the pick (all / year 1 / year 2 bp per trade):

| Change | All | Year 1 | Year 2 |
|---|---|---|---|
| Pivot 3 | −7.7 | +12.0 | −31.5 |
| Pivot 4 | +8.9 | +21.4 | −7.7 |
| **Pivot 5 (pick)** | +62.9 | +41.0 | +86.8 |
| Pivot 6 | −1.2 | +26.4 | −30.3 |
| Pivot 8 | −6.1 | −26.2 | +16.1 |
| Swing 10–120 | +31.4 | −15.2 | +80.3 |
| Levels 38/62 | +51.6 | +0.5 | +110.2 |
| Day start 00:00 | +24.0 | +0.7 | +51.1 |
| Day start 12:00 | +61.8 | +25.4 | +98.2 |
| Day start 14:00 | +46.0 | +13.0 | +82.2 |

- **It only works at pivot strength 5.** Pivot 4 and 6 are near zero. A real edge usually degrades gradually around its best setting; a single sharp peak is typical of a fitted result.
- **The pick was chosen using the full two years**, so there is no unseen data left to test it on. The t of 2.8 is the best of many settings tried and is within what chance produces across this many combinations.
- **The systematic walk-forward found no benefit from optimising at all.**

Expect materially less than +63 bp per trade going forward. Forward-test on a 15m chart with Bar Magnifier on before using real money.

## Update 2: two-year backtest (Nov 2024 → Nov 12 2026)

Data: 1,068,480 one-minute bars, no gaps. The settings were chosen on April–October 2026, so **November 2024 – March 2026 (17 months) is data nothing was tuned on**. Script `hist2y.py`, full output `hist2y_out.txt`. v3.1 defaults: stop 5× ATR(60m), TP 2R, no trail, 0.02% per side.

| Chart, day start | All 2 years: trades / bp / t / PF | Unseen 17 months: trades / bp / PF | Tuned Apr–Oct 2026: bp |
|---|---|---|---|
| 1m, 13:00 | 574 / +8.2 / 0.8 / 1.09 | 399 / +3.4 / 1.03 | +23.2 |
| **5m, 13:00** | 468 / +7.6 / 0.6 / 1.08 | 331 / **−11.8** / 0.90 | +58.8 |
| 5m, 00:00 | 512 / +4.2 / 0.4 / 1.04 | 361 / +2.8 / 1.03 | +13.1 |
| **15m, 13:00** | 370 / +26.4 / 1.7 / 1.26 | 263 / **+22.4** / 1.20 | +41.3 |
| 15m, 00:00 | 393 / +27.0 / 1.8 / 1.27 | 278 / +22.6 / 1.21 | +36.0 |

(The Apr–Oct figures differ slightly from earlier sections because indicators now warm up on prior history.)

**What the longer history shows**
- **The 5m result did not hold.** The +55 bp per trade on the 5m chart with a 13:00 day start was specific to Apr–Oct 2026. On the 17 unseen months the same settings lost 11.8 bp per trade, on both longs (−13.4) and shorts (−10.0). Over two years the 5m chart is about break-even after fees, with a worst drawdown of 91% of one position's notional, and random entries beat it 18% of the time.
- **The 13:00 day start was a lucky pick.** Over two years no hour stands out on the 5m chart: results range from −9 to +10 bp, and only 4 of 24 hours are positive on the unseen months.
- **The 15m chart is the part that held up.** It made +22 bp per trade on the unseen months and +26 bp over two years, with both longs (+29) and shorts (+24) positive. 23 of 24 day-start hours are positive on the unseen months, so it does not depend on the hour. Random entries beat it 1.5% of the time, and it keeps +20 bp at 0.05% fees.
- **It is still not statistically proven.** t = 1.7 over two years, 15 of 25 months positive, and the worst drawdown is 47% of one position's notional (0.47% of the account at 1% sizing).
- **Pivot strength 8 loses everywhere** (−26 bp over two years on 5m). Gating entries by the TF toggles, which looked best on 2026, lost heavily on unseen data (−55 bp). TDI levels 38/62 was the only 5m variant positive on unseen data (+12 bp, 194 trades).
- **Tick stops still lose:** v3.0-style 200/400 ticks made −3.9 bp per trade over 951 trades.
- **Stop width on 5m:** no ATR or percent setting produced more than about +6 bp on unseen data.

**Takeaway:** run v3.1 on a **15m chart**. The day-start hour matters little there; 13:00 and 00:00 perform the same. Treat it as a small, unproven edge.

## Update: day start 13:00 UTC is now the default

At your request, v3.1 now defaults to a 13:00 UTC day start. Re-test of the full defaults (5× ATR(60m) stop, TP 2R, no trail, 0.02% per side), from `day13.py`; full output in `day13_out.txt`.

**April–October (the period the settings were chosen on):**

| Chart | Trades | Win % | bp/trade | t | Profit factor | Random entries beat it |
|---|---|---|---|---|---|---|
| 1m | 167 | 59 | +22.4 | 1.5 | 1.35 | 1% |
| **5m** | 134 | 62 | **+55.5** | 2.9 | 1.89 | <0.3% |
| 15m | 102 | 60 | +37.0 | 1.5 | 1.45 | 5% |

On the 5m chart (including the November trades below): longs +62.5 bp, shorts +40.2 bp; 6 of 7 full months positive (May was −543 bp in total); +45 bp per trade at 0.05% fees; worst drawdown about 12% of the position's notional.

**November 1–12 (new data, not used to choose anything):**

| Chart | Trades | Won | bp/trade |
|---|---|---|---|
| 1m | 6 | 3 | −94.6 |
| 5m | 3 | 1 | −146.8 |
| 15m | 4 | 0 | −97.4 |

The first unseen stretch lost on every chart. Three to six trades is far too few to judge the strategy, and one losing trade at this stop size costs about 150–250 bp, so a start like this is within normal variation. It is still the only truly out-of-sample evidence so far, and it is negative. The 00:00 day start also lost on 1m and 5m in the same window.

**How sensitive the 5m result is to other inputs** (all data, default exits):

| Change from default | Trades | bp/trade |
|---|---|---|
| none | 137 | +51.1 |
| Stop 3× to 8× ATR(60m), TP 1R to 3R | 131–166 | +21 to +62 |
| Stop 2× ATR(60m) | 179–194 | 0 to +23 |
| Trailing on (1R / 0.5R) | 144 | +50.2 |
| Divergence toggles (any) | 137 | +51.1 (no effect on entries) |
| TDI levels 45/55 | 101 | +43.4 |
| TDI levels 38/62 | 80 | +34.1 |
| Toggles gate entries, no 1m | 68 | +67.5 |
| Swing bars 10–120 | 97 | +28.0 |
| **Pivot strength 3** | 142 | **+7.8** |
| **Pivot strength 8** | 93 | **−23.3** |
| Require 4th signal | 3 | too few trades |

The stop and target settings are robust. The result depends heavily on pivot strength staying at 5: 3 is roughly break-even and 8 loses. Together with 13:00 being the single best of 24 hours, that means the +55 bp figure is probably optimistic; expect less going forward.

## Recommendation

*Revised after Update 4; the earlier advice to use the 5m defaults is withdrawn.*

- **Don't trade this strategy with real money as if it had an edge.**
  - The only rigorous out-of-sample test failed decisively: the frozen 15m pick on seven unseen years of BTC.
  - None of its 14 neighbours worked either, including the earlier 15m default with the levels filter off.
  - The 5m and 1m charts never showed a lasting edge on the two-year data (Update 2), and were not tested on 2017–2024.
- **What remains useful from v3.1 is mechanics, not edge:**
  - the position protected from the fill bar;
  - conflicting bars skipped;
  - commission in the strategy properties.

  These make the script behave correctly. They do not make the TDI confluence signal profitable.
- **ATR stops are a better design, not a proven gain.** They scale with volatility and did better than tick stops in most comparisons here, but not all: in the first study's walk-forward, ticks made +7.5 bp per trade against +3.9 bp for ATR.
- **If you want to keep working on it:**
  - treat each new idea as a new hypothesis and fix it before looking;
  - test it on data it has never seen, for example a forward test on live data from 2026-11-13 on, or another market;
  - use the same kind of pre-registered test.

  Expect most ideas to fail: the reality check shows how often the best of a large search looks good by chance.
- **Don't use tick-based stops on BTC.** A fixed distance does not scale with price or volatility. v3.0's 200 ticks is only $2 on BTC, inside the noise, and it lost after fees in every test here.
- **Caveats:**
  - Binance data, while TradingView may chart a different BTC feed;
  - the Python engine reproduces TradingView's broker emulator closely, but not tick-for-tick;
  - 0.02% per side is a low cost assumption, and realistic retail costs make every result above worse.

## Reproduce
```bash
./fetch_data.sh        # Binance BTCUSDT 1m into ./data (Nov 2024 - Oct 2026 + Nov 1-12 2026)
python3 test_mtf.py    # MTF / ATR alignment regression tests
python3 sweep3.py      # stages A+B, ~5 min on 4 cores
python3 wf31.py        # mode comparison + walk-forward + plateaus
python3 finalists.py   # stress tests
python3 dayhour.py     # day-start hour sweep
python3 day13.py       # 13:00 default re-test incl. November
python3 hist2y.py      # two-year backtest (needs the full download)
python3 opt15.py && python3 opt15_wf.py opt15      # 15m sweep, exits on 15m bars (~15 min)
python3 opt15_final.py                             # finalists with exits on 1m bars
python3 opt15m.py && python3 opt15_wf.py opt15m    # 15m sweep, exits on 1m bars (~20 min)
python3 opt15_pick.py                              # stress test of the pick
# confirmation test (Update 4): protocol in PREREGISTRATION.md, audit in AUDIT.md
./fetch_full.sh && python3 build_npz.py            # Binance 1m history 2017-2026 for 7 coins (~1.6 GB)
python3 build_npz.py --insample                    # the tuning data (BTC Nov 2024 - Nov 12 2026, from ./fetch_data.sh) as one file; the steps below need it
sha256sum -c data_manifest.sha256                  # data must match the pinned hashes (7 coins + the tuning data)
python3 validate.py selftest && python3 validate.py dryrun   # checks on the tuning data only
python3 validate.py run                            # the one-shot test; refuses changed code/data and existing outputs (move the committed ones away to reproduce)
python3 report_validation.py > validation_report.md
python3 sim_final.py 3000 1 && python3 sim_regimes.py      # false-positive rate and power simulations
```
`v31_top_results.csv` lists the top 3,000 combinations, by t-stat, that have at least 100 trades.
