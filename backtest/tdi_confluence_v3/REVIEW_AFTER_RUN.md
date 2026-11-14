# Review after the run

After the confirmation test (`RESULTS.md`, Update 4: NOT PASSED), a second independent review tried to break the result. It also re-checked the write-up.

**Scope.** The review did not re-run the registered test and changed no registered file: `engine.py`, `validate.py`, `PREREGISTRATION.md`, `data_exclusions.json` and `data_manifest.sha256` are as they were at the run. Blinding no longer applied, so reviewers used the test data freely. They used it only to check the result, never to tune the rule.

**Reviewers:** five lenses. An adversarial verifier then checked every finding. "Real" meant the finding would change a result or the verdict, misstate a number, or leave out something a careful reader needs.

1. **Reproduce:** rebuild the data, the trades and the statistics from scratch.
2. **Signals:** compare an independent Pine emulator with the engine's signals.
3. **Statistics:** recompute everything with independent code, draw new nulls, try other statistics.
4. **Skeptic:** look for artifacts in the data and the simulation.
5. **Write-up:** `RESULTS.md`, `PREREGISTRATION.md` section 8, `AUDIT.md` and `validation_report.md`.

**Outcome: NOT PASSED stands.** The result reproduces exactly. Nothing found can turn any verdict test into a pass.

**Sources.** The reviewers' scripts were working files and are not committed, as in `AUDIT.md`. Every figure that `RESULTS.md` now cites and that is not already in a committed output is recomputed by `postrun_checks.py` (`postrun_checks_out.txt`).

## What was checked and held

### Reproduction
- **Data:**
  - `sha256sum -c data_manifest.sha256` passes for all 790 entries.
  - The data and code hashes in `validation.json` equal the files at the run's commit (a51780c), and no later commit touches the registered files.
  - `build_npz.py` rebuilds both BTC files byte for byte from the downloads.
- **Tuning data:**
  - The full BTC file equals the tuning file bit for bit on their overlap (1,068,480 bars).
  - On it the registered code reproduces the tuning result: the same 232 entries, +62.9 bp. One trade differs by 0.47 bp because the 60m ATR warms up on earlier history.
- **Committed outputs:**
  - A re-run of the registered code reproduces `trades_BTC_oos.csv` and `trades_alts.csv` byte for byte, and the BTC statistics in `validation.json` bit for bit.
  - `validation_report.md` regenerates byte for byte.
  - The crash log's result lines equal the final log's. The snapshots in 1c3db1b and 7c17617 are byte prefixes of the final log.
- **Independent simulator:**
  - Built from the raw Binance zips, with its own parser, 60m ATR, exclusion logic, 1-minute exit walk and commission. Only the signal flags came from the engine.
  - It rebuilt all 626 trades to within 0.0005 bp: 300 stops, 60 targets, 266 reversals, 0 gap fills.
  - No exit bar touched both the stop and the target, so the order of high and low inside a bar never decided a trade.
  - Pine's rounding of stop and target to ticks moves no trade by more than 0.014 bp and changes no exit. Only 6 of the 360 stop and target exits move by more than 0.01 bp.

### Signals
- **Six windows chosen for trouble:** the independent Pine emulator from the pre-run audit matched the engine on every 15m bar in each of them:
  - 2017-12 and 2018-01/02: off-grid timestamps and a 33-hour outage;
  - the 2020 COVID crash;
  - 2018-06/07: long gaps;
  - 2023: a gap over the 13:00 bar;
  - 2024-08/10.
- **The whole test period:** one bar differs, in an excluded month (a floating-point tie). The emulator's flags give the same 626 trades.
- **Other data:** the six other coins (0 differing bars in tradable months), the 11 signal-side neighbours and the tuning data all agree too.
- **Floating-point variants:**
  - other SMA and RSI forms, and exact-tie arithmetic, change 0 BTC signal bars;
  - a Wilder-form RMA changes 2 and no trade.
- **Amendment 1:** the off-grid fix is in effect. Without it, some trades in 2017-12 would differ and the average would be −33.6 bp.
- **The pivot tie rule** is the one thing this lens found. See below: the emulator shares the engine's rule, so their agreement could not catch it.

### Statistics
- **Recomputed with independent code and scipy, all equal to `validation.json`:**
  - T1a, T1b and the 98% bounds;
  - all eight leave-one-year-out rows (T4);
  - the centred T2 and T3 p-values.
- **New null draws with a different random generator:**
  - T2 (10,000 runs): null mean +2.2 bp, centred p 0.893. The registered run had +2.0 bp, p 0.891.
  - T3 (2,400 runs): +6.8 bp, p 0.924. The registered run had +7.3 bp, p 0.927.
  - To pass T2 or T3, the rule would have needed a null mean below about −78 bp.
- **About 40 other statistics and cuts:**
  - medians, trimmed and winsorised means, Wilcoxon and sign tests;
  - Newey–West, calendar-quarter and calendar-year clusters;
  - compounded equity and R multiples;
  - without 2018, from 2021 on, longs only.

  The smallest p among them is 0.47.
- **Regimes:** the lag-1 autocorrelation of monthly totals is +0.07 (se 0.11), so there is no sign of them.
- **Other coins:** the pooled result and its monthly correlation with BTC (0.02) reproduce. Own random-timing nulls agree with `validation.json`.

### Artifacts (skeptic)
- **Outages and gaps:** 17 trades were open across a gap of more than 5 minutes and netted +756 bp. Without them the average is −29.9 bp. No ATR was inflated by more than 2% by a missing hour.
- **Fills:**
  - Every entry filled 1 minute after its signal bar.
  - No stop or target filled at a gapped open.
  - Stops fill at the stop price, although the minute that hit the stop traded a median 13.4 bp beyond it. That favours the rule.
- **Largest losses:**
  - The 10 worst trades are 88.5% of the net loss, and all are ordinary −1 R stop-outs on wide stops.
  - The worst trade (−2,279 bp, a short on 2020-03-16) has a correct ATR, no gap and no off-grid timestamp.
- **Stale and thin minutes:**
  - No signal, fill or exit minute had zero volume.
  - Only 3 trades hinged on an exact RSI tie.
- **Shorting and costs:** longs only −10.4 bp (p 0.61). With shorts dropped before Binance's margin launch (2019-07-11): −16.1 bp.
- **Amendment 1 helped the rule:**
  - Without the off-grid fix the average would be −33.6 bp.
  - Thresholds from 0.1% to 40% give 10 distinct sets of excluded months, and all 10 were tried. The registered set is the one every threshold from 0.23% to 3.8% gives, and it has the best average (−27.9 bp). The other nine give −28.9 to −34.5 bp, among them −31.1 bp with no exclusion. So the registered 1% rule is the most favourable choice.
- **All doubts at once:** dropping all 43 trades open to any of these doubts gives −33.1 bp (T1a p 0.90).

## Findings

| # | Lens | Finding | Kind | Verdict | Disposition |
|---|---|---|---|---|---|
| 1 | signals | `engine.py` gives a pivot tie to the older bar, TradingView to the newer one. The emulator shares the engine's rule, so their agreement could not catch it | defect, low | **real**; verdict unchanged | Caveat in `RESULTS.md` with the effect (`postrun_checks.py` §5). `engine.py` is left unchanged, so the committed results stay reproducible. The change for future work is below |
| 2 | signals | On the other coins, 0–6 entry bars per coin are decided by floating-point ties (none on BTC) | suggestion | not material: pooled −9.8 → −11.0 bp, p 0.75 | No change |
| 3 | reproduce | `trades_BTC_oos.csv` has only entry time, side and return | suggestion | not material: with the price data, each row fixes its exit | No change. A future pre-registered run should also write exit time, exit kind and stop distance |
| 4 | skeptic | The signals hinge on tiny price differences. 1 bp of random noise on every 1-minute price changes about 28% of the trades; the average ranges from −43.5 to −11.7 bp over 18 runs. With 5 bp, it ranges from −70.4 to +11.8 bp over 30 runs. The best T1a p is 0.32 | suggestion | not material: all runs lie inside the 96% interval, and none passes | Recorded here only. Expect a different trade list on any other price feed, but not a different verdict. The same 1 bp noise lowers the tuning figure from +62.9 to +44 bp on average |
| 5 | write-up | Reproduce: the first-study scripts read all of `./data`, which now holds two years. They give different numbers, and `wf31.py` crashes | defect, medium | **real** | The Reproduce block now sets the other months aside for those five scripts |
| 6 | write-up | The Pine script's header still said "use a 15m chart" and called the defaults the most robust setting | defect, medium | **real** | Header comment rewritten with the test result. Inputs unchanged: they define the frozen rule |
| 7 | write-up | "Mostly one bad year" holds in bp only. In R, 2018 is 47% of the loss and 2023 another 36% | suggestion, medium | **real**: two bad years, not "almost every year" as first claimed | Bullet added to Update 4 (`postrun_checks.py` §2) |
| 8 | write-up | The exclusion of 35–45 bp edges also depends on month clusters. With T1b's 6-month blocks the bound is +41.7 bp | defect, low | **real** | Reworded in "What this means" (`postrun_checks.py` §3) |
| 9 | write-up | First-study conclusions (stop width, plateau, "the ATR stop is the robust part") were not marked as overtaken by unseen data | defect, low | **real** | Notes added in the first study, from `hist2y_out.txt` and `validation_report.md` |
| 10 | write-up | The other coins after 2024-11 were read as support for a rule specific to 2024–26. The rise is not significant (p 0.09), mostly DOGE, and flat in R | defect, low | **real** | Bullet rewritten (`postrun_checks.py` §4) |
| 11 | write-up | A caveat stated agreement with TradingView's broker emulator that was never measured | suggestion | **real** | Caveat reworded. A comparison with the Strategy Tester was added to the next steps |
| 12 | write-up | Reproduce left out `reality_check.py` | suggestion | **real** | Line added, with a note that the `*_out.txt` files are console output and that `sim_regimes.py` needs scipy |
| 13 | write-up | The week-block and plain t-test checks registered in section 5 were not reported. Amendment 1 had dropped them from the printout without saying so | suggestion | **real** | Added to `RESULTS.md` and `validation_report.md` from `validation.json`: p 0.8895; t −1.21, p 0.8863 |
| 14 | write-up | The file-level Data line described only the first study | suggestion | **real** | Rewritten |
| 15 | write-up | Update 2's 15m takeaway reads as current advice | defect | not real: the callout, Update 4 and the Recommendation withdraw it | A one-line pointer to Update 4 added anyway, also after Update 3's closing advice |
| 16 | write-up | The Recommendation's note withdraws only the 5m advice | defect | not real: the 15m advice was never in that section, and its first bullet withdraws both 15m settings | No change |
| 17 | write-up | Update 3 ends with a positive expectation | defect | not real: "materially less than +63 bp" was borne out | Pointer line (as #15) |
| 18 | write-up | The day-start update calls November the only out-of-sample evidence | defect | not real: a dated entry in a newest-first log | No change |
| 19 | write-up | Realistic execution costs more than the largest edge the bound allows | suggestion | not real: true only with month clusters; with 6-month blocks the realistic bound is +17 bp | No change |
| 20 | write-up | Amendment 1 was committed in three steps | defect | not real: its text and code are in 54bcff4, on top of the manifest (4046ce7) and the exclusion list (29a0e73) | No change |
| 21 | write-up | The pre-run documents give no pointer to the outcome | suggestion | not real: `PREREGISTRATION.md` sections 7 and 8.6 name the outputs | No change. `PREREGISTRATION.md` and `AUDIT.md` stay as committed before the run |

**Found while verifying:**
- **Update 2's day-start counts were wrong when first written.** Per `hist2y_out.txt`, the unseen months had 22 of 24 positive hours on 15m, not 23 (21:00 was −0.2 bp, 22:00 −17.8 bp). On 5m they had 3 of 24, not 4. Both are corrected.
- **A broken pointer:** the first study's "(see the update below)" no longer pointed at the day-start update once newer updates were added above it. It is now a link.
- **This review's own text:** a final independent check found 8 small inaccuracies in it, none of which changes a result. They were:
  - the neighbour count;
  - a rounded null mean;
  - the coverage of the threshold sweep;
  - the description of the tie evidence, where one example was a re-implementation's prediction and not TradingView output;
  - the tick-rounding sentence;
  - two over-short phrasings.

  All are corrected. The prediction was replaced by a TradingView export.

## The pivot tie rule

The strategy finds RSI pivots with `ta.pivotlow(osc, 5, 5)` and `ta.pivothigh(osc, 5, 5)`. Sometimes a pivot candidate has the same RSI value as a bar beside it, usually because two 1-minute closes are equal.

**TradingView's rule** is asymmetric:
- an equal bar on the left does not disqualify the candidate;
- an equal bar on the right does.

So the newer of two equal bars becomes the pivot. `engine._pivots` does the reverse, so the older bar wins.

**Evidence:** TradingView output published with two independent Pine re-implementations.
- **PineTS:**
  - `tests/namespaces/ta/tie-handling.test.ts` holds TradingView's output for a 28-bar repeating series under four calls, `pivothigh` and `pivotlow` at (1,1) and (2,2). That is 112 cells, with ties on the left and on the right. TradingView's rule gets every cell right, and the engine's rule gets 10 of the 112 wrong.
  - Its CHANGELOG (0.10.0, 2026-09-25) gives the BINANCE:BTCUSDT 60m example below.
- **PyneCore:** two TradingView exports (`pivot.csv`, in the repository since 2025-04-06, and `pivot_zero_strength.csv`) each contain one bar where a tie decides the pivot. In both, TradingView gives no pivot and the engine's rule gives one.

Two ties with TradingView's own output, from `postrun_checks_out.txt`:

| BINANCE:BTCUSDT highs | Call | TradingView | `engine.py` |
|---|---|---|---|
| 60m, quoted in PineTS's CHANGELOG: 80107.99, 80028.01, 80107.99, 79989.13, 79865.89 | `pivothigh(2, 2)`, last bar | 80107.99 | na |
| 30m, 2025-01-05 05:30 → 09:00, from PyneCore's `pivot_zero_strength.csv`: 98500.00, 98393.94, 98500.00, 98464.84, 98355.83, 98268.78, 97941.97, 97943.02 | `pivothigh(high, 0, 5)` at 08:00 / 09:00 | na / 98500.00 | 98500.00 / 98500.00 |

In the first case the tie is on the candidate's left, and TradingView keeps the pivot. In the second it is on the right: TradingView rejects the older 98500.00 and reports the newer one at 09:00, while `engine.py` reports a pivot at both bars.

**Effect** (`postrun_checks.py` §5, the engine with only the tie rule swapped):

| Data | `engine.py` | TradingView's tie rule |
|---|---|---|
| BTC test, 2017-12 → 2024-10 | 626 trades, −27.9 bp; T1a p 0.875, T1b p 0.811, worst T4 p 0.941; bounds −78.1 / +22.3 | 625 trades, −27.6 bp; T1a p 0.872, T1b p 0.808, worst T4 p 0.939; bounds −77.9 / +22.7 |
| BTC tuning data | 232 trades, +62.9 bp | 234 trades, +58.2 bp |
| Other coins, pooled | 3,084 trades, −9.8 bp, p 0.728 | 3,092 trades, −9.1 bp, p 0.711 |

- **BTC test:** 4 of the 1,032 tradable signal bars change, and 1 trade disappears and 1 changes.
- **T2 and T3:** with 2,000 null draws under each rule, the reviewer's verifier found 0.892 / 0.926 with TradingView's rule against 0.892 / 0.929 with the engine's.
- **Other coins:** 2–14% of each coin's trades change, for example SOL +31.8 → +24.4 bp and ADA +35.9 → +42.9 bp.

**Why `engine.py` was not changed:**
- It is a registered file. Changing it would make every committed result irreproducible from this commit.
- The one-shot test cannot be re-run anyway.
- The verdict is the same under either rule.

**The change for future work:** in `engine._pivots`, swap the strictness of the two sides:

```python
            if k < c:                       # left side: an equal bar does not disqualify
                if not v <= w: isl = False
                if not v >= w: ish = False
            else:                           # right side: an equal bar disqualifies
                if not v < w: isl = False
                if not v > w: ish = False
```

Add the two cases above as a regression test. The tuning-data results in `RESULTS.md` would then need to be recomputed.
