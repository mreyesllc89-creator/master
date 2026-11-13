# Pre-registration: confirmation test of the frozen 15m rule at 98% confidence

Written 2026-11-13, **before any of the test data below was loaded, plotted or simulated**. The downloads exist as zip files only. The validation code (`validate.py`) was written and checked on the tuning data alone (`python3 validate.py selftest`).

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

- **Primary test set (BTC, unseen):** BTCUSDT from its first bar (2017-08-17) to 2024-10-31 23:59. None of it has been used so far. The series is cut at 2024-11-01, so nothing from the tuning period (2024-11-01 → 2026-11-12) enters. A position still open at the cut is dropped.
- **Replication set (six other coins, unseen):** ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, each from its first bar to 2024-10-31. The list is fixed here. None of these coins has been used so far.
- **Descriptive only:** the same six coins from 2024-11-01 to 2026-11-12. BTC over this window was used for tuning and the coins move with BTC, so this window is not clean evidence.
- **Exclusions:** none. Minutes the exchange did not publish stay missing.
- **Data quality, checked before the test without looking at any result** (`build_npz.py`, report in `data_quality.txt`):
  - no malformed price rows and no missing monthly files inside any coin's range;
  - missing minutes are 0.04% to 0.18% per coin, in 11 to 34 gaps; the largest is a 33.5-hour exchange outage on 2018-02-08/09, the rest are 10 hours or less;
  - about 15 days of BTC, ETH and BNB bars in two stretches between 2017-12-04 and 2018-02-10 are stamped 15 to 22 seconds off the minute. They are used as published; a bar is assigned to the 15-minute bar its start time falls in.

## 4. The verdict (primary test set only)

Statistic: average net return per trade, in basis points of the position's notional (1 bp = 0.01%), trades assigned to the month of their entry.

- **T1, profit:** resample whole calendar months with replacement 20,000 times and recompute the average. `p1` = share of resamples with an average ≤ 0. Resampling months instead of single trades keeps clustered trades together.
- **T2, skill against random timing:** 5,000 runs that place the same number of long and short entries on random 15m bars and use the same exits and costs. `p2` = (1 + number of runs whose average ≥ the real average) / 5,001.

**Decision rule**

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

## 6. Power

On the tuning data the rule made +62.9 bp per trade with a standard deviation of about 340 bp, at about 9 trades a month. The primary set has about 86 months, so roughly 800 trades are expected. With 800 trades the test detects a true edge of about 35 bp per trade or more 80% of the time. A real but smaller edge may fail the test; that would be reported as "not proven", not as "disproven".

## 7. Mechanics

- Random seed 20261113 for all resampling.
- `python3 validate.py run` is executed once. Its console output is saved as `validation_out.txt`, the numbers as `validation.json`, the trades as `trades_BTC_oos.csv` and `trades_alts.csv`.
- Any deviation from this protocol, including a bug found after the run, is listed in `RESULTS.md` together with the result before and after.
