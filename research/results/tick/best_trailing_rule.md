# Best trailing per timeframe: the rule

Written on 18 November 2026, before the full tick replay was run (a test run of BTC's M10 and M15 cells had been
seen while the replay tool was being built). It decides which trailing system goes into the zip for each timeframe.

**What is compared.** The tick replay (`research/tick_replay.py`) re-runs, tick by tick and with the EA's own
execution rules, the setups that the re-calibration (`hump_tf_recal.py`, `hump_trail2.py`) picked for each
timeframe (M1 to H1) and each of the EA's 14 trailing systems (TrailMode 0 to 13), on gold (Dukascopy ticks) and BTC
(Binance one-second prices). The setups were picked on 1 January 2025 to 15 May 2026 only.

**The rule.**
1. For each symbol and timeframe, the candidates are the EA's trailing systems with at least one setup picked on that
   timeframe. A timeframe without picks (none passed the calibration) gets no preset.
2. Score: the profit factor of a system's setups together in the unseen months, 16 May to 13 November 2026, in the
   tick replay at VT costs (model `vt`: gold = Dukascopy's mid price with VT's 0.15 spread, scaled by Dukascopy's own
   spread so its spikes stay, plus $0.60 commission per ounce; BTC = mid price with a $10 spread).
3. Eligible: at least 100 trades in those months, the study's minimum. Where no system of a timeframe reaches 100,
   those with at least 30 trades are eligible and the result is marked thin. Under 30 everywhere: no preset.
4. Best: the highest profit factor; equal profit factors go to the higher net result in R.
5. The check: the same setups on the earlier data, which was used neither to pick the setups nor to choose the
   system: gold 15 July to 31 December 2024, BTC 2023 (from 15 January) and 2024, tick replay at VT costs. A choice
   "held" only if its profit factor is at least 1.3 in every earlier period.
6. The choice is made on the 2026 months, so the chosen system's 2026 profit factor is the score it was chosen by,
   not a test, and the highest of up to 14 systems is biased upward. Stressed costs (one minute late, slippage, more
   commission) are reported next to it.
7. Presets: one per setup of the chosen system. Where a setup's target equals its minimum reward (TP_RR =
   MinRewardRisk with a fixed target), the preset sets MinRewardRisk = TP_RR - 0.05 so the EA takes every such signal,
   as the earlier presets do; the tick figures must come from a replay with that same setting.
8. Nothing here is proven. The presets are for the Strategy Tester and demo accounts.

**Note added after an independent check (18 November 2026).** For BTC the timing above does not protect the
choice: a test run of the replay with every BTC setup on January 2025 – November 2026, the 2026 months included, had
already been computed with a per-cell summary before this rule was committed (only its M10 and M15 rows had been
looked at), and its 2026 figures give the same six BTC choices. An earlier replay of four BTC combinations (M2 ATR at entry, the
later M2 choice; M5 risk multiples; M5 SMA; M10 stepped) also had their 2026 results before the rule. For gold no 2026 replay result existed before the
rule; a test run of July – October 2024, part of the check period, did. The rule is the study's own (100 trades,
highest profit factor), so there was little room to tune it, but for BTC it should be read as chosen with the
results available.
