# EURUSD and US500: what counts as a result (fixed before their results were seen)

Written and committed on 15 November 2026 while the EURUSD and US500 runs of `research/hump_wf.py` (protocol 2)
were still running, before any of their walk-forward or 2026 figures existed. The engine, data, costs and pass
rule are in the docstring of `hump_wf.py`; this file adds the decision on top of the pass rule, using what the
independent audit of the gold and BTC runs taught (`research/results/wf/chance_check.json`).

A timeframe-and-condition cell counts as a result only if all four hold:

1. **The pass rule** (as for gold and BTC): over the unseen years 2016 – 2025 together, profit factor 1.3 or
   more on 100 or more trades, 1.1 or more with stressed costs, at least two unseen years with 50 trades, and
   none of those years below 1.0.
2. **Once per signal.** The same rule holds with the trades collapsed to distinct signals (entry time and side;
   the mean R of the picks that took each): PF 1.3 or more on 100 or more signals, 1.1 or more stressed, at least
   two years with 50 signals, none of them below 1.0.
3. **Not chance.** In the no-skill reshuffle of the audit (`research/audit_wf/nulls.py`: every year's results
   swapped among setups of similar activity, 25 runs or more), the cell passes in fewer than 5% of the runs, and
   the symbol's number of passing cells is above the 95th percentile of the reshuffle's. Nested conditions count
   as one (xlzc_both inside xlzc_stoch).
4. **The final check.** The 2026 months (to 13 November), run only for cells that meet 1 – 3: profit factor 1.3
   or more = confirmed; 1.0 to 1.3 = not confirmed; under 1.0 = failed.

Only a confirmed cell gets presets. If no cell is confirmed on either symbol, the answer is that nothing passed.

Also reported, without changing the decision: for US500, the test years 2022 – 2025 alone (their calibration
lies after April 2018, when the Dukascopy feed became a full 23-hour market); the base method per timeframe; the
best cells that failed, with the reason.
