# reconcile_xpw23: stage 3 for XPW Orientation TDI v2.8 (S2 / S3 exits) + FGF [Update 1]

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Ground truth: `/home/user/master/xpw_orientation_tdi_v2.8_strategy_FGF.pine` at HEAD (`d28ba97`). Brief:
`$W/SPEC_xpw23.md`. Builds: `$W/xpw23_a.py`, `$W/xpw23_b.py` (their notes `xpw23_a_notes.md`,
`xpw23_b_notes.md`). Canonical module: `$W/xpw23.py`. Final notes: `$W/xpw23_notes.md`.

Nothing here was compiled or run in TradingView (there is none). "Agree" below means two Python
implementations written independently from the Pine give the same trades; it does not mean TradingView was
matched. The readings of TradingView that both builds share are listed in `xpw23_notes.md` section 4 and
in section 8 below.

---------------------------------------------------------------------------------------------------------

## 1. A against B

Tool: `$W/reconcile_xpw23_cmp.py PAIR TF [TF ...] [--seed N]`. Per chart, full windows:

- base: default inputs and filter off, each with `xpwInv` off / on x cost 'tv' / 'ours' / 'stress' (12 settings);
- grid: random settings drawn from the calibration grid of SPEC_xpw23.md section 9 (signal inputs `actDL` =
  `actDS`, `actInf`, `fgfOn`; exit inputs `xpwInv`, `slAtrMult`, `tpRMult`, `trailOn`, `trActAtr`, `trDistAtr`,
  `timeStop`, `maxOpen`; a random cost mode);
- extra: random settings OUTSIDE the grid, so that the code the grid never reaches is compared too: limit
  mode, `limitBars`, one-side modes, `oppCloses`, Points mode, other ATR lengths, stops and targets of 0, Risk
  sizing with odd steps and caps, `reverseAll`, "every rung", `lblRead` off, "enter opposite" and "exit only"
  rows.

Compared per setting: the `prepare` arrays; every trade column both builds have (the 25 columns of A; B has
six more of its own); the 54 summary fields both have; the bar-close equity curve. Bars, kinds, ids and
counts exactly; prices, quantities, P/L and equity to a relative 1e-9.

| run | charts | settings (base / grid / extra) | trades compared | settings that differ | trades that differ | log |
|---|---|---|---|---|---|---|
| round 0, seed 23, XAU | 240, 60, 15, 5, 1 | 384 (60 / 162 / 162) | 1,402,811 | 0 | 0 | `reconcile_xpw23_cmp_XAU.log` |
| round 0, seed 23, BTC | 240, 60, 15, 5, 1 | 384 (60 / 162 / 162) | 2,667,638 | 0 | 0 | `reconcile_xpw23_cmp_BTC.log` |
| second seed 7, XAU | 240, 60, 15, 5, 1 | 384 (60 / 162 / 162) | 1,301,176 | 0 | 0 | `reconcile_xpw23_cmp_r1_XAU.log` |
| second seed 7, BTC | 240, 60, 15, 5 | 336 (48 / 144 / 144) | 1,423,607 | 0 | 0 | `reconcile_xpw23_cmp_r1_BTC.log` |
| second seed 7, BTC | 1 | 48 (12 / 18 / 18) | 1,658,813 | 0 | 0 | `reconcile_xpw23_cmp_r1_BTC_1.log` |
| total | | 1,536 (240 / 648 / 648) | 8,454,045 | 0 | 0 | |

Per chart, trades compared (round 0 / second seed): XAU 240 34,580 / 22,074; XAU 60 85,407 / 76,935; XAU 15
257,554 / 225,282; XAU 5 492,726 / 370,891; XAU 1 532,544 / 605,994; BTC 240 47,526 / 42,012; BTC 60
132,354 / 199,445; BTC 15 381,415 / 524,009; BTC 5 864,123 / 658,141; BTC 1 1,242,220 / 1,658,813.

**The two builds agreed from the first comparison: no trade, no summary field and no equity bar differed in
any run, so no build had to be fixed and there was no disagreement to settle by reading the Pine.** The
round-0 logs are those of 24 Nov; neither build was edited after them (file dates 04:08 and 04:18, logs
04:33 and 04:35). The second seed was run on 26 Nov with the same two files.

### 1.1 What the compared settings reach

A comparison says nothing about a branch no setting enters. `reconcile_xpw23_cover.py` rebuilds the settings of
both seeds (charts 240, 60, 15, 5; 1,344 of the 1,536 settings; its trade totals equal those of the comparison
logs, so the settings are the same ones) and counts, on the canonical module, in how many settings each
counter is above zero (`reconcile_xpw23_cover.log`):

| | XAU seed 23 | BTC seed 23 | XAU seed 7 | BTC seed 7 |
|---|---|---|---|---|
| settings | 336 | 336 | 336 | 336 |
| with `xpwInv` on / limit mode / a one-side mode | 159 / 75 / 75 | 179 / 99 / 79 | 161 / 84 / 70 | 154 / 95 / 65 |
| Points mode / Risk sizing / time stop on | 57 / 48 / 165 | 62 / 62 / 183 | 42 / 60 / 167 | 45 / 54 / 165 |
| cost 'ours' / 'stress' | 111 / 121 | 106 / 131 | 113 / 120 | 95 / 104 |
| trail off / no stop / no target | 114 / 23 / 76 | 137 / 26 / 80 | 91 / 23 / 72 | 111 / 28 / 87 |
| filter on / `reverseAll` / "every rung" | 120 / 12 / 60 | 168 / 42 / 42 | 222 / 42 / 54 | 198 / 48 / 72 |
| an "exit only" row / an "enter opposite" row | 198 / 72 | 120 / 90 | 108 / 84 | 156 / 66 |
| Risk + inverted + limit together | 19 | 17 | 24 | 14 |
| equity at or below zero at some bar | 0 | 124 | 0 | 97 |
| settings with exits `sl` / `tp` / `trail` | 293 / 209 / 172 | 283 / 224 / 152 | 283 / 224 / 196 | 286 / 230 / 163 |
| settings with exits `time` / `close_all` / `reverse` / `end` | 144 / 203 / 215 / 208 | 147 / 140 / 204 / 105 | 141 / 170 / 207 / 200 | 139 / 192 / 214 / 100 |
| labels skipped for room / for a quantity of 0 | 167 / 5 | 179 / 33 | 164 / 10 | 183 / 26 |
| a reversal bar that placed more than `room` | 116 | 131 | 116 | 134 |
| pending entries placed / filled at the placement close | 70 / 60 | 92 / 87 | 80 / 67 | 88 / 86 |
| pending entries cancelled as stale / as against | 68 / 45 | 91 / 62 | 76 / 52 | 87 / 66 |
| ghosts in the pending list / orders still pending at the end | 63 / 24 | 87 / 7 | 73 / 32 | 84 / 5 |
| zero-length trades (entry and exit on one bar) | 79 | 92 | 85 | 87 |

Every exit kind, both fill modes, both directions of the option, the one-side modes, both exit units, both
sizing modes, the pending-list corner cases (fill at the placement close, stale, against, ghost) and the
negative-equity case are entered in many settings of every run (the fewest: a quantity that rounds to 0, in
5 to 33 settings per run).

### 1.2 Differences between the builds that are not disagreements

| item | A | B | effect |
|---|---|---|---|
| order of the time-stop closes at one close | newest first (the Pine loop) | oldest first | none: same price, same kinds, same cost total |
| where passes (c) and (f) sit in the code | in the Pine's order | before the close fills | none: `strategy.cancel` is not a fill and (f) only matches trades open at script time; `room` is taken between the two in both |
| intrabar walker | `_walk(open, extreme 1, extreme 2, close, start segment, start point)` | a buffer of path points with an "is an open" flag | none |
| extra summary fields | `reverse_bars`, `reverse_over_room` | `labels_long`, `labels_short`, `both_cancel_bars`, `pend_cancel_stale`, `pend_cancel_against` | the canonical module has all of them |
| extra trade columns | none | `sl_ticks`, `tp_ticks`, `trail_points`, `trail_offset`, `pend_fill`, `fill_at_close` | the canonical module has `sl_ticks` and `fill_at_close` |
| a display input given to `simulate` | raises (it is a `prepare` key) | accepted and ignored | API only; the canonical module raises |
| integer inputs | must be whole numbers | integer-valued floats accepted | the same thing |

Readings each builder made on its own and both made the same way (window end: `exposure`, `max_open`,
`max_expo`, `margin_bars` before the `end` closes, the equity curve after; `eq_before`; `halves_rule` from the
inputs; `fifo_exits` as a prefix maximum of `2 * exit_bar + closefill`; the filter-off shortcut in
`prepare`): replica conventions, listed in `xpw23_notes.md` section 4. None touches a fill.

### 1.3 Because nothing differed: what was done to look for readings both share

Agreement of two builds that worked from the same brief can hide a misreading the brief gave to both. So:

1. **The Pine, read again in stage 3.** Lines 1622-1799 were read against `xpw23.py` statement by
   statement (table in `xpw23_notes.md` section 3): the pre-filter gate, the market / limit forms of
   `closeL` / `closeS`, the distances, `entryQty` and its order of operations, the cancel pass with the
   pre-filter flags, the time stop, `room` between the two list passes, `placeEntry`, the filled pass, the
   FGD funnel, and the seven Update 1 expressions. No difference from the brief and none from the kernel.
2. **The reuse of `xpw.py`, proved again** with `sha256sum` on the three line ranges of the two Pine files
   and a `grep` of the names the shared block takes from outside it (`xpw23_notes.md` section 1). The
   fusion and Update 1 diffs (`git show 6c59b9f:` against the unfused original and against HEAD) contain
   exactly the expressions the brief lists.
3. **A third, unrelated implementation.** Where this file and the trailing-TP file place the same orders
   (filter off, Signal tick, exits in ticks = `trail_points` / `trail_offset` with or without `loss`, no
   target, no time stop, "Both", 20 entries) the canonical module must equal the verified replica of the
   OTHER Pine file, which other agents built twice, reconciled and audited: `engine.py` on path 'tv' and
   `sweep_core._run_mag` on path 'mag'. Test section `engine`: BTC 60, XAU 60, BTC 15, XAU 240, BTC 240,
   XAU 15, two signal settings, normal and inverted, five tick settings, both paths: 240 runs, 850,858
   trades, sides, rows, label index, prices and exit kinds all equal. This covers the market-mode script
   logic, the reversal rule, the trail and the stop loss, and their Bar Magnifier walk. It does not cover
   the take profit, the time stop and the S3 sizing (only this file has them), nor limit mode (the
   trailing-TP replica has none). Those rest on the two builds, the slow references and the unit tests.
4. **Three slow references**, each a transcription of the Pine with real order objects: A's
   (`xpw23_a_ref.py`: 1,032 settings, 1,124,363 trades against its kernel, and the ORIGINAL unfused script
   with the filter off), B's (`xpw23_b_ref.py`: 288 comparisons) and the stage 3 one for both paths
   (`xpw23_magref.py`, section 4).
5. **Mutation check** (section 5): the tests fail when one line of the kernel is changed.

What this does not remove: the readings of TradingView's broker (T1-T16), which every implementation here
takes from the same brief. They are assumptions, not findings.

---------------------------------------------------------------------------------------------------------

## 2. The canonical module `$W/xpw23.py`

Build A, plus:

- path 'mag' (section 3): `_step1` takes a range of sub-bars; path 'tv' is the same code with the chart bar
  as its only sub-bar. A was chosen because its walker already took a start segment and a start point, so
  the sub-bar loop is the same function called once per sub-bar; B's point buffer would have had to grow to
  4 x 240 points per bar;
- B's fields `labels_long`, `labels_short`, `both_cancel_bars`, `pend_cancel_stale`, `pend_cancel_against`
  and trade columns `sl_ticks`, `fill_at_close`;
- `summary` reports `path` and `cost`;
- `sub_bars` / `get_sub` / `fake_sub` (the 1-minute sub-bars, checked against the chart bars) and
  `free_caches()` (memory on the 1-minute charts).

With `path='tv'` it gives A's results on every case of the tests (and so B's): test section `abc`.

---------------------------------------------------------------------------------------------------------

## 3. Path 'mag'

Definition: `xpw23_notes.md` section 5 (SWEEP_AH_SPEC.md section 2 applied to this script: exit orders AND
the pending limit / stop entries walk the 1-minute sub-bars in time order, each sub-bar with its own path
and open test, the trailing state carrying over; the script, market orders, `close_all`, the time stop and
the placement-close attempt of a new pending entry stay on the chart bar's close).

How it was checked:

| check | what | result |
|---|---|---|
| sub-bars | every chart bar of the 14 cells equals its sub-bars (first open, highest high, lowest low, last close); equal to the verified `hrd.sub_bars` on XAU 240 and BTC 60 | 16 PASS |
| chart "1" | 'mag' == 'tv' bit for bit (trades, summary, equity curve), BTC and XAU, filter on and off, 7 settings each incl. limit mode, inverted, Risk; one sub-bar per chart bar | 8 PASS, 784,924 trades |
| fake sub-bars | one sub-bar per chart bar (the chart bar itself): 'mag' == 'tv' bit for bit, 7 cells x 27 settings | 7 PASS, 634,918 trades |
| hand-made minutes | known answers where the minutes must change the result: the trail arms and stops inside the bar instead of the target; a stop / a target / a pending limit jumped over between two minutes fills at the next minute's open; the trail ratchets across minutes; a pending entry filled in one minute and stopped in a later one; inverted stop entry; T6 stays on the chart close; the path tie inside a minute | in the unit section (24 PASS) |
| slow reference | `xpw23_magref.py` (pure Python, real prices, Pine-like order book, its own inverse mapping of minutes to chart bars): 'tv' and 'mag' on 33 random settings (grid and extra) over two 2-month windows on 8 cells | 9 PASS, 17,196 trades; the two paths differ from each other on 24 of the 33 settings; all seven exit kinds occur |
| third implementation | `sweep_core._run_mag` (the verified Bar Magnifier kernel of the trailing-TP replica), section 1.3 item 3 | 7 PASS; 850,858 trades on the two paths together |
| hand traces | `reconcile_xpw23_trace.py` -> `reconcile_xpw23_trace.log`: 8 trades of BTC 60 (normal and inverted) whose exit differs between the paths, the chart bar and its minutes printed, the exit re-derived by a walker written for the trace | 8 PASS |

Two of the traces, as an example of WHY the two paths differ (BTC 60, default inputs, filter on):

- `S109479-1`, short from 97,650.00, trail arming at 96,842.73 with offset 605.45. Chart path of the next
  hours: the bar of row 109484 goes high first and ends at 97,084, below the trailing stop 97,201.45 that its
  low 96,596 set, so the trade lives on and leaves on the next bar at 96,244.45 (+140.55). The minutes of
  row 109484: armed at minute 38, best 96,596 at minute 41, and minute 44 trades up through 97,201.45: out
  at 97,201.45 (+44.85). The chart path let the trail "ride" through a rebound that really stopped it.
- `L109829-1`, long, trailing stop 97,604.48 in force. Chart path: filled at the stop. Minutes: minute 54
  opens at 97,600.00, already below the stop: filled at the open (the jump rule).

---------------------------------------------------------------------------------------------------------

## 4. Tests: `$W/tests_xpw23.py` -> `$W/tests_xpw23.log`

`python3 -I tests_xpw23.py [section ...]`; exit code 1 on any FAIL. Final run: **168 PASS, 0 FAIL, 290 s.**

| section | PASS | what |
|---|---|---|
| unit | 24 | hand-made bars: the four worked checks of SPEC section 5 on both paths; hand-made minutes (above); `entryQty` order of operations (round down, then cap; rounds to 0 = nothing placed; Risk; Risk without a stop); a level touched exactly fills (target, stop, pending limit); the path tie in each of the three places a path is chosen |
| sub | 16 | the sub-bars of the 14 cells |
| fake | 7 | 'mag' with one fake sub-bar per chart bar == 'tv' |
| ref | 9 | both paths against `xpw23_magref.py`, 33 random settings, 2-month windows, 8 cells |
| engine | 7 | both paths against `engine.py` / `sweep_core._run_mag` (section 1.3 item 3) |
| money | 15 | every money field recomputed from the trade list and the bars alone: per-fill costs in the three cost modes, `pnl`, `final_equity`, `net_pct`, `pf`, `win_pct`, the fair halves (additive and compound), the equity curve, `half1_pct` / `half2_pct`, the two drawdowns, `exposure`, `max_open`, `max_expo`, `margin_bars`, exit counts, `R` sums, `fifo_exits` by brute force; 5 cells x filter on / off x 16 settings on both paths. Risk quantities against a direct evaluation of `entryQty()` on the equity rebuilt from the trade list |
| inv | 60 | the Pine header's statements on Update 1, 6 cells x 10 checks. VS REVERSE: filter off + Signal tick + default rows: `xpwInv` alone == `reverseAll` alone trade for trade and both on == both off (both paths, incl. Risk, costs, one-side); the FGD counts keep the label side; "(inv)" comments, real-side id letters; with the filter on, and in limit mode, the two options differ; both options on with the filter on: every LONG label is a real buy taken where the SELL zone allows it (the entries equal the labels gated by the opposite permission), in limit mode by a buy stop at the candle's HIGH. FRAME: the inverted run takes the same entries on the other side when room never binds; with every S2 exit off it is the exact mirror of the normal run with the other one-side mode (72 cases per cell). ONE SIDE: Long only + inverted = only real buys, from SHORT labels. CLOSES: an "exit only" row closes the side its label is against with the option off, the side it points to with it on |
| timing | 4 | one `simulate` on BTC 5 / 60 / 240 and XAU 15, both paths (worst 0.024 s) |
| abc, mag1, timing, memory | 10 + 8 + 4 + 4 | in four child processes: A == B == canonical on 400 settings (2,545,847 trades; BTC and XAU, charts 240, 60, 15, 5, 1); chart "1": 'mag' == 'tv'; timing on chart "1" (BTC: worst `simulate` 0.145 s, first `prepare` 11.3 s; limits 1 s and 120 s); peak memory of each child (0.95, 1.51, 1.90, 2.85 GB; limit 3 GB) |

---------------------------------------------------------------------------------------------------------

## 5. The tests can fail: `$W/xpw23_s3_mut/make_mutants.py` -> `$W/xpw23_s3_mutants.log`

Each mutant is a sandbox copy of `xpw23.py` with one line changed; sections `unit` and `ref` are run on it.

| mutant | change | result |
|---|---|---|
| m1 | no open test on the later sub-bars of an exit | killed (8 FAIL) |
| m2 | a pending entry jumped over at a later sub-bar's open fills at its own price | killed (7) |
| m3 | the armed-trail shortcut ignores a new best price | killed (7) |
| m4 | no fill at the placement close (T6) | killed (5) |
| m5 | the exit of a trade filled inside the bar is not walked on the later sub-bars | killed (5) |
| m6 | an inverted pending entry opens the normal side | killed (the kernel's own invariant raises) |
| m7 | sub-bar path of an open trade: high first on a tie | killed (2) |
| m8 | the trailing stop wins over the stop loss only when strictly higher, exit at the stop loss | killed (10) |
| m9 | time stop one bar late | killed (9) |
| m10 | `room` ignores the pending list | killed (5) |
| m11 | sub-bar path of a pending entry: high first on a tie | killed (1) |
| m12 | sub-bar path after an intrabar fill: high first on a tie | killed (1) |
| m13 | "Trade direction" is not swapped under Inverted direction | killed (2) |
| m14 | the closes read the real position, not the mirrored one | killed (the kernel's own invariant raises) |
| m15 | market mode: a blocked entry signal still closes the other side | killed (8) |
| m16 | a target must be exceeded, not touched | killed (2) |
| m17 | the entry cost is not charged | killed (8) |
| m18 | `entryQty`: the cap is applied before the rounding | killed (1) |
| m19 | a pending limit must be exceeded, not touched | killed (6) |
| m20 | a stop must be exceeded, not touched | killed (1) |

**20 of 20 killed.**

How the list got here. The first run had 10 mutants (m1-m10) and one survived: m7, the path tie (`<` to
`<=` where a sub-bar's path is chosen). A second run with 20 mutants left one alive again: m18, the order
of rounding and cap in `entryQty`. Both are real departures from the brief / the Pine that the random
2-month runs of section `ref` happen not to meet (an exact tie that matters to a trade; a cap that is not a
multiple of the step). Unit tests with exact answers were added for each (the tie in all three places
where a path is chosen; a level touched exactly; the `entryQty` order), and the final run above kills all
20. The earlier logs are in `xpw23_s3_old/`.

---------------------------------------------------------------------------------------------------------

## 6. By timeframe: `$W/run_inv_xpw23.py PAIR TF [TF ...]` -> `$W/out/inv_xpw23_<PAIR>_<TF>.json`

As INV_BT_SPEC.md item 3: default inputs, full windows, direction {normal, inverted} x filter {off, on} x
path {tv, mag} x cost {script, ours}; `runs['<direction>/<filter>/<path>/<cost>']` = the full summary;
`reference['reversed/...']` = "Reverse every label" on; `checks`. All 14 cells were run with the final module
(`run_inv_xpw23_XAU.log`, `run_inv_xpw23_BTC.log`); the 14 files are identical to those of the first run of
24 Nov apart from the timing fields. Built-in checks, all true in the 14 files: chart "1": every 'mag' run
equals its 'tv' run; filter off: inverted == reversed trade for trade on both paths and both costs; filter
on: inverted differs from reversed.

"script" cost = the script's own Properties = no commission and no slippage. Money: 10,000 account, a fixed
0.1 unit per entry, no margin model. net % = money earned in % of 10,000 (0.1 ounce of gold is about 130
USD, hence the small gold figures); net R = sum of P/L in units of each trade's own stop distance (3 ATR).
`$W/inv_tables_xpw23.md` has this table and the 16 runs of every cell.

| pair | TF | filter | trades | TV normal: net % / PF / win % / net R | TV inverted: net % / PF / win % / net R | 1m + costs normal: net % / PF / net R / max DD % | 1m + costs inverted: net % / PF / net R / max DD % |
|---|---|---|---|---|---|---|---|
| BTC | 1 | off | 63358 | +477.88 / 1.203 / 65.7 / +4077.7 | +364.21 / 1.150 / 65.0 / +3296.9 | -1800.66 / 0.472 / -23256.0 / 1801.38 | -1914.31 / 0.455 / -24036.8 / 1911.55 |
| BTC | 1 | on | 22169 | +178.34 / 1.191 / 69.5 / +1473.6 | +227.12 / 1.252 / 70.2 / +1781.3 | -618.39 / 0.512 / -8157.7 / 619.28 | -569.60 / 0.538 / -7849.9 / 567.38 |
| BTC | 5 | off | 23789 | +384.03 / 1.186 / 67.5 / +1038.1 | +199.73 / 1.092 / 65.3 / +716.2 | -559.63 / 0.765 / -2222.0 / 533.70 | -761.01 / 0.695 / -2562.5 / 764.20 |
| BTC | 5 | on | 8831 | +110.01 / 1.114 / 72.6 / +368.0 | +160.86 / 1.176 / 73.5 / +431.2 | -245.84 / 0.769 / -858.6 / 236.84 | -199.48 / 0.802 / -799.7 / 203.73 |
| BTC | 15 | off | 11644 | +316.51 / 1.186 / 66.7 / +405.7 | +158.70 / 1.089 / 63.1 / +294.9 | -187.78 / 0.898 / -435.1 / 187.82 | -368.43 / 0.811 / -592.4 / 370.00 |
| BTC | 15 | on | 4728 | +56.55 / 1.061 / 72.9 / +114.9 | +172.96 / 1.200 / 71.8 / +217.1 | -160.22 / 0.836 / -252.6 / 158.56 | -62.81 / 0.931 / -171.4 / 73.68 |
| BTC | 30 | off | 6945 | +254.65 / 1.172 / 66.9 / +190.6 | +216.73 / 1.144 / 62.7 / +220.3 | -87.50 / 0.944 / -177.6 / 94.55 | -147.42 / 0.908 / -164.6 / 143.62 |
| BTC | 30 | on | 2943 | +134.18 / 1.180 / 74.4 / +119.5 | +137.37 / 1.177 / 69.6 / +130.3 | -14.65 / 0.981 / -41.1 / 43.49 | -40.40 / 0.950 / -59.3 / 85.24 |
| BTC | 60 | off | 3886 | +63.28 / 1.049 / 66.0 / +44.3 | +242.33 / 1.204 / 64.5 / +165.1 | -158.38 / 0.883 / -109.5 / 148.80 | -46.82 / 0.962 / -33.2 / 77.05 |
| BTC | 60 | on | 1807 | +47.87 / 1.067 / 72.6 / +32.2 | +189.10 / 1.291 / 70.2 / +126.1 | -68.79 / 0.907 / -46.8 / 87.79 | +31.11 / 1.046 / +21.2 / 74.74 |
| BTC | 120 | off | 1826 | +48.89 / 1.051 / 67.4 / +4.8 | +226.15 / 1.271 / 67.3 / +109.7 | -99.45 / 0.899 / -62.4 / 112.32 | +62.84 / 1.073 / +32.3 / 70.46 |
| BTC | 120 | on | 849 | +19.94 / 1.040 / 69.0 / -9.3 | +134.92 / 1.322 / 72.2 / +70.7 | -47.10 / 0.908 / -38.4 / 72.06 | +57.52 / 1.135 / +32.7 / 30.59 |
| BTC | 240 | off | 1094 | -41.69 / 0.949 / 64.4 / -8.0 | +160.95 / 1.234 / 63.8 / +47.7 | -137.30 / 0.834 / -41.5 / 143.73 | +46.86 / 1.067 / +14.7 / 85.12 |
| BTC | 240 | on | 486 | -62.02 / 0.856 / 67.5 / -16.3 | +75.18 / 1.216 / 68.3 / +27.3 | -98.27 / 0.775 / -29.2 / 122.00 | +25.29 / 1.071 / +12.1 / 27.67 |
| XAU | 1 | off | 29828 | +0.544 / 1.101 / 66.8 / +664.8 | +0.663 / 1.123 / 67.5 / +1004.5 | -8.404 / 0.190 / -13244.8 / 8.404 | -8.285 / 0.197 / -12905.0 / 8.287 |
| XAU | 1 | on | 10795 | +0.111 / 1.047 / 72.5 / +168.5 | +0.378 / 1.174 / 74.5 / +515.6 | -3.127 / 0.218 / -4906.6 / 3.129 | -2.860 / 0.237 / -4559.5 / 2.861 |
| XAU | 5 | off | 11022 | +0.366 / 1.081 / 66.6 / +232.0 | +0.541 / 1.123 / 64.3 / +281.2 | -3.163 / 0.462 / -1841.7 / 3.174 | -3.009 / 0.484 / -1805.9 / 3.020 |
| XAU | 5 | on | 4268 | +0.176 / 1.082 / 74.1 / +117.7 | +0.337 / 1.161 / 73.7 / +137.2 | -1.228 / 0.520 / -696.7 / 1.238 | -1.062 / 0.575 / -677.5 / 1.089 |
| XAU | 15 | off | 5399 | +0.271 / 1.070 / 66.5 / +74.1 | +0.215 / 1.054 / 62.1 / +87.7 | -1.627 / 0.633 / -510.3 / 1.667 | -1.703 / 0.632 / -506.4 / 1.731 |
| XAU | 15 | on | 2213 | +0.133 / 1.068 / 73.8 / +58.1 | +0.062 / 1.030 / 69.8 / +4.5 | -0.673 / 0.683 / -188.9 / 0.717 | -0.768 / 0.660 / -248.1 / 0.801 |
| XAU | 30 | off | 3117 | +0.252 / 1.078 / 65.9 / +55.7 | +0.118 / 1.036 / 61.2 / +26.8 | -0.903 / 0.745 / -186.9 / 0.949 | -1.007 / 0.723 / -208.6 / 1.008 |
| XAU | 30 | on | 1312 | +0.133 / 1.082 / 73.4 / +47.6 | +0.055 / 1.032 / 67.8 / -1.5 | -0.352 / 0.796 / -52.2 / 0.460 | -0.453 / 0.755 / -106.4 / 0.480 |
| XAU | 60 | off | 1782 | +0.014 / 1.005 / 66.4 / +0.2 | +0.386 / 1.152 / 64.4 / +55.6 | -0.775 / 0.744 / -113.3 / 0.970 | -0.458 / 0.833 / -65.2 / 0.518 |
| XAU | 60 | on | 811 | +0.097 / 1.067 / 73.7 / +21.0 | +0.129 / 1.090 / 67.6 / +14.8 | -0.253 / 0.834 / -31.1 / 0.410 | -0.288 / 0.809 / -44.9 / 0.308 |
| XAU | 120 | off | 855 | +0.218 / 1.117 / 72.2 / +23.6 | +0.159 / 1.083 / 67.7 / +20.8 | -0.220 / 0.887 / -21.5 / 0.478 | -0.316 / 0.841 / -29.0 / 0.414 |
| XAU | 120 | on | 398 | +0.199 / 1.223 / 76.1 / +21.7 | -0.071 / 0.930 / 69.1 / -6.6 | -0.005 / 0.994 / +1.0 / 0.238 | -0.277 / 0.739 / -28.3 / 0.333 |
| XAU | 240 | off | 544 | +0.399 / 1.265 / 70.8 / +29.7 | -0.182 / 0.901 / 62.1 / -10.6 | +0.079 / 1.051 / +6.8 / 0.359 | -0.497 / 0.738 / -32.9 / 0.589 |
| XAU | 240 | on | 247 | +0.225 / 1.301 / 75.7 / +16.1 | -0.226 / 0.769 / 61.9 / -15.1 | +0.073 / 1.095 / +5.2 / 0.182 | -0.361 / 0.641 / -24.5 / 0.384 |

Sanity checks on these numbers:

- **Trade counts.** The four runs of a row have the same trades count: with "Max open entries" 20 the room
  never binds (`skipped_room` 0 in all 224 runs) and the quantity is fixed, so every label the gate lets
  through is placed in all of them; only the exits differ. Per year: BTC 60 1,944 (filter off) / 904 (on),
  XAU 60 1,221 / 556; per bar the two markets give the same density (0.22 trades per 60-minute bar, filter
  off). A bar carries at most two labels (chart rung + READ HERE).
- **TradingView view against 1-minute fills.** In every cell above 1 minute, both directions, filter on and
  off, the 'tv' path is better than the 'mag' path at equal costs (BTC by 19 to 149 points of net %, gold by
  0.06 to 0.31). The reason is one mechanism, visible in the exit counts: on the minutes fewer trades reach
  the target and more leave by the trail (BTC 60, filter off, normal: sl 650 -> 648, tp 222 -> 166, trail
  1,677 -> 1,759, reverse 1,335 -> 1,311). The chart-bar path lets the 0.75 ATR trail arm at the bar's far
  extreme and survive the bar; the minutes show the pullback that stops it first (first trace of section
  3). It flatters both directions, which is why normal AND inverted are positive in most TradingView
  columns. The Pine header says the same of its own "TV path" figures.
- **Costs.** BTC 60, filter off, normal, 'tv': the 3,886 trades pay 14,004.80 USD with our costs (3.60 USD per
  round trip of 0.1 BTC), 140.05 % of the account, and that is exactly the distance between the 'script'
  (+63.28 %) and the 'ours' (-76.77 %) runs.
- **Chart "1".** 'mag' == 'tv' exactly; 63,358 (BTC) and 29,828 (gold) trades with the filter off: with costs
  the 1-minute charts lose the account many times over (the Pine header: "a fee machine").
- **Win rate 61 to 76 % with a profit factor of 0.77 to 1.32** in the 56 TradingView-view runs: the shape of
  a 0.75 ATR trail against a 3 ATR stop (many small wins, fewer full losses).
- **Margin.** `margin_bars` is 0 in all 112 gold runs. On BTC the position value is above the equity on 519
  to 325,807 bars per run (1,778 to 13,983 in the 'tv' / 'script' / normal runs), and in 31 of the 112 BTC runs
  the equity is at or below zero at some bar (max DD above 100 %, in all seven BTC charts): see section 8,
  item 1.
- **Not a calibration.** These are the script defaults. With 1-minute fills and our costs the default
  setting is positive in 7 of the 56 rows x directions: BTC 60 inverted with the filter on, BTC 120 and 240
  inverted (filter off and on), XAU 240 normal (filter off and on); positive in both fair halves in 4 (BTC
  120 inverted off / on, BTC 240 inverted off with a first half of +0.96 %, XAU 240 normal on with 137 / 110
  trades). Nothing here says any of them is defensible: that is the calibration's job.

---------------------------------------------------------------------------------------------------------

## 7. Files of stage 3

| file | what |
|---|---|
| `xpw23.py` | canonical module |
| `xpw23_notes.md` | final interpretations and limits |
| `reconcile_xpw23.md` | this file |
| `reconcile_xpw23_cmp.py`, `reconcile_xpw23_cmp_<PAIR>.log`, `reconcile_xpw23_cmp_r1_*.log` | A against B (also `--mods a,c` / `b,c`) |
| `reconcile_xpw23_cover.py`, `reconcile_xpw23_cover.log` | which branches the compared settings reach |
| `xpw23_magref.py` | slow pure-Python reference for both paths |
| `reconcile_xpw23_trace.py`, `reconcile_xpw23_trace.log` | hand traces of the 'mag' path |
| `tests_xpw23.py`, `tests_xpw23.log` | tests |
| `xpw23_s3_mut/make_mutants.py`, `xpw23_s3_mutants.log` | mutation check |
| `run_inv_xpw23.py`, `run_inv_xpw23_<PAIR>.log`, `out/inv_xpw23_<PAIR>_<TF>.json` | runner, 14 cells |
| `inv_tables_xpw23.py`, `inv_tables_xpw23.md` | tables |
| `xpw23_s3_old/` | superseded logs of this stage (first test runs, first runner logs and JSON files, first mutation run) |

Memory: every process of the tests and the runner stays under 3 GB (largest: the BTC "1" child of the
tests, 2.85 GB; the runner on BTC "1", 2.80 GB). The round-0 comparison of 24 Nov ran all five BTC charts in
one process and peaked at 3.36 GB, above the limit; the tool now releases its caches on chart "1" (the BTC
"1" comparison of the second seed: 2.65 GB).

---------------------------------------------------------------------------------------------------------

## 8. Open issues for the audit (stage 4)

1. **Margin (T11).** The replica has none. With TradingView's default 100 % margin this script on BTC would
   be cut by margin calls: 0.1 BTC per entry on a 10,000 account, up to 20 stacked. The BTC rows of the
   "TradingView view" are what TradingView shows only with the margin set to 0 % (or a much larger
   account); read them as money per 0.1 BTC entry. Gold is not affected (0 margin bars).
2. **FIFO (T10).** Per-entry pairing. Net profit and the equity curve do not depend on it with the default
   inputs; profit factor, win rate and the fair halves' attribution do (`fifo_exits` 30 to 2,695 rows in the
   14 x 2 default runs of the normal direction on path 'tv').
3. **Several entries on a reversal bar (T8).** First reverses, the others add. 0 to 8 % of the reversal
   bars carry two entries (at most 3 % of the trades of a default run, six cells counted).
4. **A pending entry filling at its placement close (T6).** Limit mode only (not the default). The Pine
   header's sentence says it cannot happen; `process_orders_on_close` as documented says it does when the
   close is the label price.
5. **Levels not rounded to the tick (T12)**; ATR-mode tick distances are fractional.
6. **Bar Magnifier** uses 1-minute bars for every chart; TradingView picks its own lower timeframe.
7. **TradingView's order limit.** Outside Deep Backtesting the Strategy Tester keeps a limited number of
   orders (9,000 as we remember its documentation; not checked here). The 1-, 5- and 15-minute cells have up
   to 63,358 trades.
8. **Shared code.** Signals and filter come from `xpw.py` and `fgf.py` in every implementation, by design
   (their Pine is byte-identical to the Pine they were verified against). A defect there would be shared.
9. Not implemented: `agreeOn` true, the seconds rungs, anything live-only.
