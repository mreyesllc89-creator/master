# apex.py: the Update 1 option "Inverted direction" (apxInv)

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Ground truth: `/home/user/master/ApexForge_Flow_Resonance_Strategy_FGF.pine` at HEAD `d28ba97`
(Update 1); what changed: `git -C /home/user/master diff 6c59b9f d28ba97 -- ApexForge_Flow_Resonance_Strategy_FGF.pine`.
Brief: `$W/INV_BT_SPEC.md`. Nothing was written inside `/home/user/master` (`git status` clean).

## Files

| file | what |
|---|---|
| `$W/apex.py` | the replica, with the option (sha256 `030a9c92...`, 1058 lines) |
| `$W/pre_inv_backup/apex.py` | the module before the change (sha256 `0c192da3...`, 982 lines) |
| `$W/pre_inv_backup/baseline_sweep_ah_tests_apex.log` | `sweep_ah_tests.py apex` before the change (8 PASS) |
| `$W/inv_tests_apex.py` | the tests R1-R4 (+ R5-R8 extra, + R9-R11 and 12 more R8 mutants added by the sceptic review); log `$W/inv_tests_apex.log` (15 PASS, 0 FAIL, 107 s; about 4 minutes when the 20 R8 mutants have to be compiled first) |
| `$W/run_inv_apex.py` | the runner; outputs `$W/out/inv_apex_BTC_60.json`, `$W/out/inv_apex_XAU_240.json` (logs `$W/out/inv_apex_BTC_60.log`, `$W/out/inv_apex_XAU_240.log`) |
| `$W/inv_apex_existing_tests.log` | `sweep_ah_tests.py apex` after the change (8 PASS, same result lines as the baseline) |
| `$W/inv_apex_existing_verify.log` | `verify_trail_apex.py regress`, `compare BTC_60 20`, `compare XAU_240 20`, `apex.py` self-check after the change (all pass) |
| `$W/inv_apex_mut/apex_m1.py` .. `apex_m20.py` | deliberately WRONG copies of apex.py written by test R8 (each starts with a comment saying so); never import them |
| `$W/sceptic_apex/` | the sceptic review's sandbox (see "Sceptic review" below): its own reference `sref.py`, its checks and logs, 32 more deliberately wrong copies in `mutants/`, the runner's output for all 14 cells in `out_runner/`, and `backup_before_sceptic/` (the test file, notes and log as the implementer left them) |

## What changed in apex.py

Only the script step of the broker kernel and the parameter plumbing. `prepare()`, the signals,
the filter gate, the per-bar stop / target arrays, the exit walk `_walk`, the fills, the sizing,
the costs and the summary formulas are untouched.

1. Parameters: `apxInv=False` (the Pine input) and the replica alias `inv=None` in `DEFAULTS`
   (lines 128, 135); an explicit `inv` wins over `apxInv`, like `blkClose` over `apxBlkClose`
   (line 202). `inv` is an exit-side parameter: `EXIT_KEYS` (148), `_EXIT_ALIASES['apxInv']`
   (150), `_check_exit` (174). So `apex.run(pair, tf, {'apxInv': True})`, `prepare(...,
   {'inv': True})` (default of `simulate`) and `simulate(S, {'inv': True})` all work, and one
   `prepare()` serves both directions.
2. Kernel `_broker(..., want_curves, inv=False, want_state=False)` (line 462). Steps 1-3 (fills
   at the open, exits along the path / sub-bars, equity) are byte-identical to the previous
   version and work on REAL sides. Step 4, the script (lines 655-718), now reads
   `posn = -pos if inv else pos` and `side_b = -1 if inv else 1` and sends each order on
   `side_b` / `-side_b` (table below). With `inv` False the step reduces to the previous
   statements (codes 1 / -1 / 2 / -2, Exit Long from the BUY block), so nothing changes.
3. `want_state=True` (tests only; `simulate` always passes False) appends the final script /
   exit-order state to `stats` (`STATE_KEYS`, line 144): the real position, the two exit
   orders (on, stop, limit, trail ticks) and the four `apxTrPts* / apxTrOfs*` vars. `stats`
   keeps its 4 values otherwise.
4. Summary: one new top-level key `inv` (line 977). `params` / `exit_params` keep their keys (the
   saved JSONs are compared on those dicts). `long` / `short` and the trade list's `dir` are
   REAL sides; `raw_long` / `raw_short` / `blocked_long` / `blocked_short` stay the SIGNAL's
   side (the Pine's FGD rows do not change with the option).
5. Docstring: a section INVERTED DIRECTION.

## How each line of the Update 1 diff maps to the replica

Pine line numbers are those of the file at HEAD.

| Pine (Update 1) | replica (`apex.py`) |
|---|---|
| header blocks `UPDATE 1`, WHAT THE FILTER GATES / NEVER GATES / BLOCKED SIGNAL / CHART / ALERTS / TRAILING / FILTER OFF additions | text; the behaviour they describe is checked by tests R2c, R3, R5 |
| 149 `strategy("... [Update 1]", ...)`: title only; qty 1 % of equity, commission 0.04 % unchanged | nothing (cost mode `'tv'`, sizing unchanged) |
| 159-163 tooltips of apxBlkClose / apxTrailOn / apxUseTarget | nothing (text) |
| 752 `apxInv = input.bool(false, ...)`, last input | `DEFAULTS['apxInv'] = False`, alias `inv`; exit param `inv` |
| 800-803 `apxGoLong / apxGoShort / apxBlkLong / apxBlkShort` (unchanged: the gate stays in the normal frame) | `go_l, go_s, bk_l, bk_s` from `sig_l, sig_s, buy_ok, sell_ok` (unchanged, lines 656-661) |
| 814 `apxPosN = apxInv ? -strategy.position_size : strategy.position_size` | `posn = -pos if inv else pos` (665-670) |
| 815-816 `apxIdBuy / apxIdSell` ("Apex Short" / "Apex Long" when inverted) | `side_b` = real side of the trade a BUY signal opens (+1, inverted -1); an entry id is its real side: order codes `side_b` / `-side_b` |
| 817-818 `apxExBuy / apxExSell` | which exit-order slot the block writes: `xl_*` = "Exit Long", `xs_*` = "Exit Short"; inverted, the BUY block writes `xs_*`, the SELL block `xl_*` |
| 822-823 `if apxBlkClose and apxBlkShort and apxPosN > 0: strategy.close(apxIdBuy)` | 671-672: `if blk_close and bk_s and posn > 0: pend = 2 * side_b` (close of that real side) |
| 824-825 `if apxBlkClose and apxBlkLong and apxPosN < 0: strategy.close(apxIdSell)` | 673-674: `pend = -2 * side_b` |
| 839 `strategy.entry(apxIdBuy, apxInv ? strategy.short : strategy.long)` | 675-676: `pend = side_b`, qty = 1 % x equity / close (unchanged) |
| 840-842 `if apxPosN <= 0`: `apxTrPtsL / apxTrOfsL` fixed (per SIGNAL kind) | 677-683: `if posn <= 0: trp_l, tro_l = ...` (same formulas) |
| 844 `if apxGoLong or (bullResonance and apxPosN > 0)` | 684: `if go_l or (sl_k and posn > 0)` |
| 845-846 `stopPrice`, `targetPrice` (unchanged) | `stp_l[k]`, `lim_l[k]` from `prepare()` (unchanged) |
| 849-850 `apxStopBuy = apxInv ? 2.0 * close - stopPrice : stopPrice`, same for the target | 687-688: `xs_s = 2.0 * c[k] - stp_l[k]`, `xs_l = 2.0 * c[k] - lim_l[k]` (the same float expression); not inverted: `xl_s = stp_l[k]`, `xl_l = lim_l[k]` |
| 851 `strategy.exit(apxExBuy, apxIdBuy, stop, limit = apxTrailOn and not apxUseTarget ? na : apxTgtBuy, trail_points=apxTrPtsL, trail_offset=apxTrOfsL)` | 685-696: the slot gets `on`, stop, limit, `trp_l`, `tro_l`; "no target" = `simulate` passes a NaN limit array, and `2.0 * c - NaN` stays NaN (no limit) |
| 853-865 the SELL block, mirrored | 697-718 |
| 875-883 `apxMarkBuy ...` plotshape series, 895-896 alertcondition, 903-910 alert() texts | not modelled: display / alerts only, no order depends on them |
| 913-918 FGD plots (unchanged, the signal's side) | `raw_long / raw_short / blocked_long / blocked_short` (unchanged) |

## Interpretations

1. **The inverted script is the normal script on a mirrored broker.** Under the option the
   Pine changes only (a) the id and direction of each order, (b) the sign of the position it
   reads, (c) the two bracket prices. TradingView's rules used by the replica (fill at the next
   open in placement order, pyramiding 0, an opposite entry reverses, `strategy.close(id)`
   closes that id's trade, `strategy.exit(id, from_entry)` belongs to that entry, an exit
   whose trade closed is cancelled) do not distinguish long from short, so no broker rule
   had to be re-interpreted. This is checked, not assumed: test R2b shows the inverted run
   equals the unchanged normal kernel fed with relabelled inputs, bit for bit.
2. `apxPosN` uses only the sign of `strategy.position_size` (as every test of it in the Pine).
3. The bracket is mirrored about the close of the bar where `strategy.exit` is called: the
   signal bar, or the bar of a later same-kind signal (re-send), each time with that bar's
   `close`, `stopPrice` and `targetPrice`. The mirror is about the signal CLOSE, not the fill:
   after an opening gap the real distances from the fill differ from the normal trade's by
   the gap, as in the Pine.
4. Float arithmetic: `2.0 * close - x` is evaluated as written (one exact doubling, one
   rounded subtraction), like Pine's doubles. The replica's older control `reverse` +
   `reverseStops='mirror'` builds its levels from the distance: the stop `close + (close - S)`
   is bit-equal to `2*close - S` (the inner difference is exact; checked on every bar of
   BTC 1 / 5 / 15 and XAU 5), but its target `close - (close - S)*rr` is not always bit-equal
   to the Pine's `2*close - targetPrice`, which mirrors the already rounded
   `targetPrice = close + (close - S)*rr` (BTC 5: 239 of 4,960 BUY-signal targets differ in
   the last bit). Test R2a: 8 exit prices of 281,038 differ, all `tp`, by at most 7.3e-12.
   (Corrected by the sceptic review: the earlier text blamed the stop formula.)
5. Trailing: ticks stay per SIGNAL kind (`apxTrPtsL` for BUY signals) and are passed to the
   exit of the trade really open; the broker trails on the real side (a short trails down).
   The earlier assumption stands unchanged: a re-sent exit changes stop / limit from the next
   bar and keeps the trailing state and distances (TradingView cannot be checked here).
6. `reverse` (replica-only: swaps the signals BEFORE the gate) is left as it was and composes
   with `inv` (flip AFTER the gate). Filter off: `inv` gives the same trades as `reverse` +
   `reverseStops='mirror'`. Filter on they differ: `reverse` gates a bear signal with
   `fgfBuyOk`, `inv` with `fgfSellOk` (BTC 60: 67 vs 75 trades).
7. "script" cost = apex cost `'tv'` (0.04 % of the order value per fill); "ours" = apex cost
   `'ours'`. Both unchanged and side-independent.
8. Bull and bear resonance never occur on the same bar (one needs close > open, the other
   close < open; test R2b counts 0 such bars in the 14 cells), so the order of the BUY and SELL
   blocks never matters on data. The kernel keeps the Pine's statement order anyway, and R3
   checks it with forced double signals.

## Not reproduced

- BUY / SELL labels, gray "blocked" marks, highlights, `strategy.close` comments, alert() and
  alertcondition() texts (Pine lines 823 / 825 comments, 875-883, 895-896, 903-910): display
  only. If needed they follow from the arrays: `apxMarkBuy = inv ? go_s : go_l` etc.
- No TradingView run exists in this workspace: like the rest of the replica, the option is
  verified against the Pine text, not against a Strategy Tester export. The Pine was not
  compiled either (UPDATES.md says so).
- Nothing else of the Update 1 diff is left out.

## Tests (`python3 -I inv_tests_apex.py`, real output in `$W/inv_tests_apex.log`)

`summary: 15 PASS, 0 FAIL (107s)` (after the sceptic review; before it: 12 PASS, 69 s).

| test | what | result |
|---|---|---|
| R1a | option off (absent / `apxInv` False / `inv` False in turn): 14 cells x every variant x cost of `out/apex_<PAIR>_<TF>.json`, every saved field; saved trade lists | PASS: 182 summaries, 70 trade lists / 143,964 rows, exact |
| R1b | option off: 40 random rows of each `out/swah_apex_*.parquet` (20 tv + 20 mag), 33 columns | PASS: 560 rows, exact |
| R1c | edited module vs `pre_inv_backup/apex.py`, random settings (filter, reverse, pivotTies, trailing, 3 costs, tv / mag): prepared arrays, all 15 broker outputs, every old summary field | PASS: 54 runs, 94,790 trades, bit for bit |
| R2a | filter off: `inv` == `reverse` + `reverseStops='mirror'` trade by trade (14 cells x 6 settings, tv and mag), and == the SAVED `rev_off_mir` summaries | PASS: 84 runs, 281,038 trades; 8 exit prices differ in the last bits (max 7.28e-12) |
| R2b | `inv` == the unchanged normal kernel on relabelled inputs (signals swapped, gates moved with them, brackets `2.0*close - x`), filter off AND on | PASS: 112 runs, 283,963 trades, every output bit-identical; 0 bars with both signals |
| R2c | header statements on the trade lists: side against the signal, gate of the SIGNAL's side, every allowed signal trades, blocked-opposite close on the mirrored position, sl / tp at the mirrored bracket of the last same-kind signal | PASS: 72 runs; inverted: 71,126 trades, 2,097 level exits + 10 at a gapping open, 19,832 blocked closes, 896 re-sent brackets |
| R3 | single decisions through the real kernel (3 flat bars, final state read with `want_state`): 611 sampled bars x p in {-1,0,+1} x 16 (bull, bear, buyOk, sellOk) x blkClose x 3 exit settings: option on from p == mirror of option off from -p; both == a literal Pine transcription | PASS: 175,968 decisions, 0 failures; 351,936 kernel-vs-transcription comparisons |
| R4 | option on: mag on chart "1" == tv (BTC 1, XAU 1); mag with fake sub-bars == tv (BTC / XAU 60, 240) | PASS: 52 settings, 0 failures (BTC 1: 176,742 trades, 36,486 trail exits) |
| R5 | engine == `pine_ref` (the Pine at HEAD in the REAL frame, string ids), trade by trade, option on (66 runs) and off (19), tv and mag (19), 3 costs, random filter / trailing / blkClose | PASS: 85 runs, 11,277 trades (option on: 4,406 long, 4,446 short; sl 1,159, tp 136, trail 2,067, reverse 4,290, blocked_close 1,173, end 27) |
| R6 | speed vs the pre-change kernel, best of 9 | PASS: BTC 1 tv, no trail 0.0230 s -> 0.0231 s (off), 0.0233 s (on); with trail 0.0197 s -> 0.0195 s (off), 0.0229 s (on); BTC 60 mag 0.0048 s -> 0.0048 s (off), 0.0066 s (on). Option off = the old speed; option on simulates other trades (BTC 60 mag x1.39 = its exposure 0.270 / 0.194), not a slower kernel |
| R7 | the runner's JSON files: keys, == saved by-timeframe results, == saved sweep rows (tv and mag), inverted/off == rev_mirror/off, recomputation, internal counts | PASS: 2 files x 32 runs |
| R8 | 20 mutants of apex.py through reduced R2b / R3 / R5 / R9 / R10 / R11: m1-m8 (implementer: real position instead of apxPosN, bracket not mirrored, wrong id, entry not flipped, wrong trailing ticks) and m9-m20 (sceptic: gate of the other side = flip before the gate, apxPosN not mirrored at all, bracket mirrored about the fill / distances from the fill, stop and target swapping roles, blocked closes on the normal ids, SELL entry not flipped, trade list reporting the normal side, trail points / offset swapped, three parameter-plumbing mistakes) | PASS: every mutant caught by every check listed for it (m1-m10, m13-m17 by R2b, R3 and R5; m11 / m12 by R2b, R5 and R10, not by R3 whose probes are flat; m18-m20 only by R9); the unmutated module passes all six |
| R9 (sceptic) | the option's two names: Pine `apxInv` and alias `inv` through `run()` / `prepare()` / `simulate()`: 8 ways of switching it on give the same inverted run, 7 ways of leaving it off the normal run, an explicit `inv` wins over `apxInv`, `simulate()` wins over `prepare()`, misspelt names are refused (BTC 60, XAU 240, XAU 60 x filter on / off) | PASS: 102 forms. Before this test nothing exercised `apxInv=True` (only `inv=True`): a module that ignored the Pine name passed R1-R8 |
| R10 (sceptic) | single decisions with a 0.3 % opening gap after the signal candle (4-bar probes on every signal candle of BTC 60 / XAU 240 / XAU 60, from flat, from the other kind's trade and from its own): the exit order is exactly `2.0*close - stopPrice` / `2.0*close - targetPrice` of the SIGNAL close; a move that reaches that stop but not the one mirrored about the fill ends the trade at that price, a move that only passes the fill-mirrored level does not; kernel == Pine transcription; option off keeps the candle's own bracket | PASS: 1,914 gap decisions (957 stopped at the close-mirrored level, 957 correctly not stopped) |
| R11 (sceptic) | the header's side restriction: `fgfAllowBuy` off blocks every BUY signal: the normal run holds only real shorts, the inverted run only real LONGS (the BUY orders), each from an allowed SELL signal; blocked BUY signals close that trade, no reversal; `fgfAllowSell` off mirrored (6 cells) | PASS: 24 runs, 2,390 trades, 1,820 blocked closes |

How R3 isolates one decision: bar 0 (flat price) carries an optional setup signal with no
stop / target, whose order fills at bar 1's open; bar 1 (flat, at the sampled bar's close)
carries the decision under test with the sampled bar's stop / target; bar 2 (flat, same
price) lets the orders fill and is the last bar. The same inputs run with the option on reach
real position p, with it off -p (asserted on the position curve). "Mirror" = trades on the
other side with the same bars, prices, sizes and P/L; "Exit Long" <-> "Exit Short" with
stop = 2*close - stop and limit = 2*close - limit; the same trailing ticks per signal kind.
32,994 of the 175,968 decisions give the same output on and off without mirroring (no order
and no bracket); the test is not vacuous on the other 142,974.

Existing tests after the change: `python3 -I sweep_ah_tests.py apex`: 8 PASS, 0 FAIL, every
result line equal to the pre-change baseline once timings are stripped (grid timing 0.0369 s
per setting vs 0.0370 s before). `verify_trail_apex.py regress`: 20/20; `compare BTC_60 20`:
80 runs equal, 9,405 trades; `compare XAU_240 20`: 80 runs equal, 548 trades. Note: the
existing `test_apex_R7` forks 3 sweep workers for about 7 s (its own design).

R5's reference re-uses `verify_trail_apex.walk` (the independent exit walk along a bar path
written for the trailing verification) and `build_sub`; its script step and order book are
new, written from the Pine at HEAD with the real ids. It is by the same author as the kernel
change, so it is a second derivation, not an independent party.

## Sceptic review (independent check of the option, its tests and its runner)

Done after the implementation, by a reviewer who did not write it. `apex.py` and
`run_inv_apex.py` were NOT changed (sha256 `030a9c92...` / `85744752...` as above): no defect
was found in them. Changed: `inv_tests_apex.py` (three tests and twelve mutants added, one
docstring corrected) and this file (interpretation 4, the test table, this section). All of
the review's own material is in `$W/sceptic_apex/`; nothing was written in `/home/user/master`
or in `out/`.

1. **The Update 1 diff, line by line** against the kernel's script step (lines 655-718):
   every changed code line has its counterpart (the table above is right): `apxPosN` ->
   `posn`, the four ids -> `side_b` and the exit slot written, the two `strategy.close` ->
   codes `2*side_b` / `-2*side_b`, the two entries -> `side_b` / `-side_b` with unchanged
   sizing, the four bracket prices -> `2.0*c[k] - x`, the trailing ticks per signal kind. The
   remaining diff lines are comments, labels, plotshape series and alert texts.
2. **A second reference**, `sceptic_apex/sref.py`: my own transcription of the Pine at HEAD in
   the real frame (string ids, an order book, my own stop / limit walk; the trailing walk is the
   older independent `verify_trail_apex.walk`). `check_ref.py`: all 16 runs of
   `out/inv_apex_BTC_60.json` and `out/inv_apex_XAU_240.json` reproduced (17 summary fields
   each, trade lists exact); option on, all 14 cells x filter off / on, tv: 84,094 trades
   equal; mag (12 cells, cost ours): 13,213 trades equal; 48 trailing settings on 6 cells, tv
   and mag: 13,813 trades (7,338 trail exits) equal. `fuzz.py`: 4,000 random synthetic
   sequences (7,716 bars with BOTH signals, gaps, brackets on the wrong side, trailing in
   40 %), option on and off: 8,000 runs, 55,756 trades, 0 differences. One side of the filter
   off (`fgfAllowBuy` / `fgfAllowSell`), 4 cells: kernel == reference, and the sides are the
   header's (Allow buys off + inverted = only real longs).
3. **Mutation tests** (`sceptic_apex/mut.py`, logs `mut_run1.log`, `mut_run2.log`): 32 wrong
   copies of apex.py in `sceptic_apex/mutants/`, each run through the suite's full R1c, R2a,
   R2b, R2c, R3, R4, R5 (R1a / R1b too for the option-off and plumbing ones). Caught by the
   suite as the implementer left it: 28 (gate of the wrong side in three variants, position
   not mirrored, bracket about the fill in three variants, blocked close on the wrong trade in
   three variants, trade list / summary reporting the normal side, trailing distances swapped
   in three variants, the SELL-side twins of m1-m8, stop and target swapping roles, bracket on
   the wrong exit id, the other block's bracket, `simulate()` not passing the option, four
   option-off mutants). Found:
   - three parameter-plumbing mutants were caught by NOTHING (the Pine name `apxInv` ignored
     by `run()` / `prepare()`; `simulate()` refusing `apxInv`; `apxInv` winning over an
     explicit `inv`): no test ever passed `apxInv=True`. Added test R9; all three are now
     caught (and are R8's m18-m20).
   - the bracket-about-the-fill mutants were caught by R2a / R2b / R2c / R5 but not by R3,
     whose probes are flat (fill == close). Added test R10 (gap probes).
   - one mutant is equivalent, not a gap: `close - (x - close)` instead of `2.0*close - x`
     gives the same double on every bar (1.4 M bars checked; the inner difference is exact).
   - added test R11 for the header's side-restriction statement, which nothing checked
     directly.
4. **Option off = the saved results** (`check_off_runner.py`, part 3; my own loops, not the
   suite's): all 7 cells of both pairs: 26 saved by-timeframe summaries per cell (every
   variant x cost, option absent and `apxInv=False`) and the saved trade lists exact; the
   saved sweep: every trail-off row and 24 random trail-on rows per path, 40 tv + 40 mag rows
   per cell x 33 columns exact. The pre-existing tests were re-run after the review
   (`sweep_ah_tests.py apex_R1..R4`: 5 PASS; `verify_trail_apex.py regress` 20/20, `compare
   BTC_60 20` 80 runs equal).
5. **The runner** (part 4): 12 random entries of the two JSON files recomputed with
   `apex.run` and Pine-named parameters: identical; each run's `costs` rebuilt from its own
   trade list with the spec's words (script: 0.04 % of the fill value per side; ours: XAU
   $0.30 x ounces per round trip, BTC 0.02 % per side + $0.20 x coins per round trip) and
   `final_equity` = 1,000,000 + gross - costs: equal; windows, default inputs and direction
   flags of all 64 stored runs checked; the reference runs are the existing ones (rev_literal
   == the saved `rev_off` / `rev_on` of `out/apex_*.json` and the `rev` rows of the saved
   sweep, tv and mag; rev_mirror == the saved `rev_off_mir` / `rev_on_mir`). The runner was
   also run for all 14 cells into `sceptic_apex/out_runner/` (10 s in all; BTC 60 and
   XAU 240 identical to the files in `out/`), and the suite's R7 passes on those 14 files
   (`r7_all.py`), so the orchestrator's run of the other 12 cells should pass R7 as well.
6. **Sanity of BTC 60 and XAU 240** (`sanity.py`: every signal accounted for). BTC 60, filter
   on: 40 allowed BUY and 50 allowed SELL signals in both directions. Normal: 36 longs (4 BUY
   signals ignored because their long was still open) + 40 shorts (10 ignored) = 76.
   Inverted: 36 shorts from the BUY signals (4 ignored) + 39 longs from the SELL signals (11
   ignored) = 75. So the long / short split IS swapped by signal kind (36 BUY-kind trades
   both ways; 40 vs 39 SELL-kind); the one trade of difference is a SELL signal that found
   its (longer-lived) inverted trade still open. Every inverted trade is on the side opposite
   to its signal, opened by a signal its own zone allows, filled at the next open; reversals
   and blocked closes equal the signal counts that cause them (12 blocked closes in both: 8
   blocked BUY + 4 blocked SELL signals met the other kind's trade). Exits: normal sl 43 / tp
   8 / reverse 13 / blocked 12; inverted sl 44 / tp 8 / reverse 11 / blocked 12. Filter off:
   131 vs 122 trades for the same reason (19 + 32 ignored signals normal, 21 + 39 inverted).
   XAU 240, filter on: 1 allowed BUY and 1 allowed SELL signal; normal short 1253.881 ->
   stop 1277.638 after 13 bars and long 1246.449 -> stop 1220.355 after 11; inverted long
   1253.881 -> mirrored stop 1230.086 after 106 bars (bar low 1225.851) and short 1246.449 ->
   mirrored stop 1272.509 after 136 bars (bar high 1274.302). Equal stop distances from the
   signal close on equal sizes: that is why both nets print -0.0415 % (they differ in the 6th
   decimal). Two trades: this cell says nothing about the option. The five hand traces above
   were reproduced with my reference (`traces.py`).

### All 14 cells (sandbox run of the same runner; cost script unless said; net % of the initial capital)

| cell | filter | normal trades | normal net % | normal PF | normal L / S | inverted trades | inverted net % | inverted PF | inverted L / S | mag net % normal / inverted | cost ours net % normal / inverted |
|---|---|---:|---:|---:|---|---:|---:|---:|---|---|---|
| BTC 1 | off | 34602 | -23.9990 | 0.437 | 17302 / 17300 | 34542 | -24.3407 | 0.375 | 17281 / 17261 | -23.9990 / -24.3407 | -12.7874 / -13.2003 |
| BTC 1 | on | 17221 | -12.9712 | 0.452 | 8836 / 8385 | 17197 | -12.7358 | 0.402 | 8373 / 8824 | -12.9712 / -12.7358 | -6.8024 / -6.5592 |
| BTC 5 | off | 4955 | -3.7091 | 0.718 | 2482 / 2473 | 4855 | -3.4758 | 0.719 | 2434 / 2421 | -3.7097 / -3.4759 | -1.7927 / -1.5940 |
| BTC 5 | on | 3076 | -2.9602 | 0.660 | 1555 / 1521 | 3020 | -1.6142 | 0.792 | 1494 / 1526 | -2.9608 / -1.6143 | -1.7657 / -0.4254 |
| BTC 15 | off | 1180 | -0.4702 | 0.917 | 573 / 607 | 1116 | -0.6437 | 0.881 | 572 / 544 | -0.4708 / -0.6438 | -0.0020 / -0.2017 |
| BTC 15 | on | 861 | -0.5646 | 0.868 | 418 / 443 | 823 | -0.4253 | 0.897 | 420 / 403 | -0.5652 / -0.4254 | -0.2235 / -0.0988 |
| BTC 30 | off | 359 | +0.5853 | 1.230 | 174 / 185 | 347 | -0.8420 | 0.728 | 173 / 174 | +0.5851 / -0.8421 | +0.7289 / -0.7051 |
| BTC 30 | on | 274 | +0.0504 | 1.024 | 134 / 140 | 261 | -0.4715 | 0.793 | 126 / 135 | +0.0504 / -0.4716 | +0.1596 / -0.3681 |
| BTC 60 | off | 131 | -0.2171 | 0.864 | 60 / 71 | 122 | -0.2053 | 0.863 | 64 / 58 | -0.2169 / -0.2054 | -0.1650 / -0.1569 |
| BTC 60 | on | 76 | -0.2716 | 0.723 | 36 / 40 | 75 | -0.1524 | 0.833 | 39 / 36 | -0.2714 / -0.1525 | -0.2414 / -0.1227 |
| BTC 120 | off | 52 | -0.3297 | 0.592 | 25 / 27 | 49 | -0.2039 | 0.751 | 25 / 24 | -0.3297 / -0.2039 | -0.3090 / -0.1844 |
| BTC 120 | on | 26 | -0.2999 | 0.352 | 9 / 17 | 26 | -0.0234 | 0.946 | 17 / 9 | -0.2999 / -0.0234 | -0.2895 / -0.0131 |
| BTC 240 | off | 31 | +0.0036 | 1.007 | 14 / 17 | 31 | -0.0951 | 0.859 | 16 / 15 | +0.0036 / -0.0951 | +0.0160 / -0.0828 |
| BTC 240 | on | 10 | -0.1184 | 0.481 | 3 / 7 | 10 | +0.1204 | 1.891 | 7 / 3 | -0.1184 / +0.1204 | -0.1144 / +0.1244 |
| XAU 1 | off | 3651 | -3.1979 | 0.280 | 1826 / 1825 | 3651 | -2.5577 | 0.301 | 1825 / 1826 | -3.1979 / -2.5577 | -1.1787 / -0.5252 |
| XAU 1 | on | 2164 | -1.9940 | 0.289 | 1035 / 1129 | 2164 | -1.4372 | 0.353 | 1129 / 1035 | -1.9940 / -1.4372 | -0.7872 / -0.2235 |
| XAU 5 | off | 875 | -0.7583 | 0.540 | 437 / 438 | 873 | -0.6143 | 0.576 | 436 / 437 | -0.7583 / -0.6143 | -0.2666 / -0.1229 |
| XAU 5 | on | 606 | -0.4097 | 0.619 | 290 / 316 | 604 | -0.5599 | 0.484 | 314 / 290 | -0.4097 / -0.5599 | -0.0680 / -0.2198 |
| XAU 15 | off | 290 | -0.3318 | 0.645 | 144 / 146 | 281 | -0.1306 | 0.827 | 139 / 142 | -0.3318 / -0.1306 | -0.1684 / +0.0280 |
| XAU 15 | on | 229 | -0.3029 | 0.604 | 114 / 115 | 223 | -0.0718 | 0.874 | 110 / 113 | -0.3029 / -0.0718 | -0.1738 / +0.0542 |
| XAU 30 | off | 194 | -0.2726 | 0.630 | 98 / 96 | 188 | -0.0593 | 0.899 | 93 / 95 | -0.2726 / -0.0593 | -0.1631 / +0.0471 |
| XAU 30 | on | 138 | -0.1616 | 0.687 | 71 / 67 | 137 | -0.0687 | 0.850 | 66 / 71 | -0.1616 / -0.0687 | -0.0837 / +0.0087 |
| XAU 60 | off | 74 | -0.0390 | 0.901 | 37 / 37 | 70 | -0.1716 | 0.601 | 35 / 35 | -0.0390 / -0.1716 | +0.0028 / -0.1321 |
| XAU 60 | on | 40 | -0.1034 | 0.557 | 18 / 22 | 39 | -0.0645 | 0.698 | 21 / 18 | -0.1034 / -0.0645 | -0.0808 / -0.0424 |
| XAU 120 | off | 37 | -0.1531 | 0.443 | 15 / 22 | 34 | +0.0486 | 1.213 | 17 / 17 | -0.1531 / +0.0486 | -0.1322 / +0.0679 |
| XAU 120 | on | 17 | -0.0350 | 0.663 | 8 / 9 | 17 | +0.0329 | 1.276 | 8 / 9 | -0.0350 / +0.0329 | -0.0254 / +0.0425 |
| XAU 240 | off | 10 | -0.1057 | 0.094 | 4 / 6 | 10 | -0.0628 | 0.336 | 6 / 4 | -0.1057 / -0.0628 | -0.1000 / -0.0571 |
| XAU 240 | on | 2 | -0.0415 | 0.000 | 1 / 1 | 2 | -0.0415 | 0.000 | 1 / 1 | -0.0415 / -0.0415 | -0.0404 / -0.0404 |

Not checked here, as before: TradingView itself (no Strategy Tester export exists in this
workspace; the Pine was not compiled). The replica is verified against the Pine text.

## Runner

    python3 -I run_inv_apex.py PAIR TF [TF ...] [--trades]

Writes `$W/out/inv_apex_<PAIR>_<TF>.json`: `runs["<direction>/<filter>/<path>/<cost>"]`
(direction normal / inverted, filter off / on, path tv / mag, cost script / ours: 16 full
summaries) and `reference["<labels>/<filter>/<path>/<cost>"]` (labels rev_literal = the
replica's `reverse`, rev_mirror = `reverse` + `reverseStops='mirror'`: 16 more), plus `_meta`.
Chart "1": mag is run with the real sub-bar table and equals tv. About 1 s per cell, 4 s for
BTC 1. Deterministic: a second run reproduces both files (seconds apart).

### BTC 60 (17,518 bars; signals: 79 BUY, 103 SELL; filter on blocks 39 BUY, 53 SELL)

| cost | path | filter | direction | trades | net % | PF | win % | max DD % | long / short | h1r % (n) | h2r % (n) | avg bars | exposure | exits |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|---|---:|---:|---|
| script | tv | off | normal | 131 | -0.2171 | 0.864 | 35.9 | 0.5304 | 60 / 71 | -0.1255 (72) | -0.0917 (59) | 51.6 | 0.386 | sl 72, tp 16, reverse 43 |
| script | tv | off | inverted | 122 | -0.2053 | 0.863 | 35.2 | 0.5282 | 64 / 58 | +0.1292 (60) | -0.3341 (62) | 62.9 | 0.438 | sl 72, tp 15, reverse 35 |
| script | tv | on | normal | 76 | -0.2716 | 0.723 | 32.9 | 0.3286 | 36 / 40 | -0.2070 (39) | -0.0647 (37) | 44.7 | 0.194 | sl 43, tp 8, reverse 13, blocked_close 12 |
| script | tv | on | inverted | 75 | -0.1524 | 0.833 | 34.7 | 0.4228 | 39 / 36 | +0.0549 (36) | -0.2072 (39) | 63.0 | 0.270 | sl 44, tp 8, reverse 11, blocked_close 12 |
| script | mag | off | normal | 131 | -0.2169 | 0.864 | 35.9 | 0.5304 | 60 / 71 | -0.1253 (72) | -0.0917 (59) | 51.6 | 0.386 | sl 72, tp 16, reverse 43 |
| script | mag | off | inverted | 122 | -0.2054 | 0.863 | 35.2 | 0.5282 | 64 / 58 | +0.1292 (60) | -0.3342 (62) | 62.9 | 0.438 | sl 72, tp 15, reverse 35 |
| script | mag | on | normal | 76 | -0.2714 | 0.723 | 32.9 | 0.3285 | 36 / 40 | -0.2068 (39) | -0.0647 (37) | 44.7 | 0.194 | sl 43, tp 8, reverse 13, blocked_close 12 |
| script | mag | on | inverted | 75 | -0.1525 | 0.833 | 34.7 | 0.4228 | 39 / 36 | +0.0549 (36) | -0.2072 (39) | 63.0 | 0.270 | sl 44, tp 8, reverse 11, blocked_close 12 |
| ours | tv | off | normal | 131 | -0.1650 | 0.894 | 35.9 | 0.5015 | 60 / 71 | -0.0968 (72) | -0.0683 (59) | 51.6 | 0.386 | sl 72, tp 16, reverse 43 |
| ours | tv | off | inverted | 122 | -0.1569 | 0.893 | 35.2 | 0.4932 | 64 / 58 | +0.1532 (60) | -0.3096 (62) | 62.9 | 0.438 | sl 72, tp 15, reverse 35 |
| ours | tv | on | normal | 76 | -0.2414 | 0.749 | 32.9 | 0.3105 | 36 / 40 | -0.1914 (39) | -0.0500 (37) | 44.7 | 0.194 | sl 43, tp 8, reverse 13, blocked_close 12 |
| ours | tv | on | inverted | 75 | -0.1227 | 0.863 | 34.7 | 0.3951 | 39 / 36 | +0.0692 (36) | -0.1918 (39) | 63.0 | 0.270 | sl 44, tp 8, reverse 11, blocked_close 12 |
| ours | mag | off | normal | 131 | -0.1649 | 0.895 | 35.9 | 0.5015 | 60 / 71 | -0.0966 (72) | -0.0683 (59) | 51.6 | 0.386 | sl 72, tp 16, reverse 43 |
| ours | mag | off | inverted | 122 | -0.1569 | 0.893 | 35.2 | 0.4932 | 64 / 58 | +0.1532 (60) | -0.3097 (62) | 62.9 | 0.438 | sl 72, tp 15, reverse 35 |
| ours | mag | on | normal | 76 | -0.2412 | 0.749 | 32.9 | 0.3103 | 36 / 40 | -0.1913 (39) | -0.0500 (37) | 44.7 | 0.194 | sl 43, tp 8, reverse 13, blocked_close 12 |
| ours | mag | on | inverted | 75 | -0.1227 | 0.863 | 34.7 | 0.3951 | 39 / 36 | +0.0692 (36) | -0.1918 (39) | 63.0 | 0.270 | sl 44, tp 8, reverse 11, blocked_close 12 |

Reference, reversed labels, cost script (tv / mag): filter off rev_literal 107 trades
-0.4149 % / -0.4156 %, rev_mirror 122 trades -0.2053 % / -0.2054 % (= inverted); filter on
rev_literal 59 trades -0.3281 % / -0.3281 %, rev_mirror 67 trades -0.2725 % / -0.2725 %.

### XAU 240 (2,246 bars; signals: 5 BUY, 6 SELL; filter on blocks 4 BUY, 5 SELL)

| cost | path | filter | direction | trades | net % | PF | win % | max DD % | long / short | h1r % (n) | h2r % (n) | avg bars | exposure | exits |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|---|---:|---:|---|
| script | tv | off | normal | 10 | -0.1057 | 0.094 | 20.0 | 0.1106 | 4 / 6 | -0.0480 (3) | -0.0577 (7) | 61.8 | 0.276 | sl 5, reverse 4, end 1 |
| script | tv | off | inverted | 10 | -0.0628 | 0.336 | 30.0 | 0.1203 | 6 / 4 | -0.0478 (3) | -0.0150 (7) | 73.6 | 0.328 | sl 5, reverse 4, end 1 |
| script | tv | on | normal | 2 | -0.0415 | 0.000 | 0.0 | 0.0441 | 1 / 1 | -0.0415 (2) | +0.0000 (0) | 12.0 | 0.011 | sl 2 |
| script | tv | on | inverted | 2 | -0.0415 | 0.000 | 0.0 | 0.0721 | 1 / 1 | -0.0415 (2) | +0.0000 (0) | 121.0 | 0.108 | sl 2 |
| script | mag | off | normal | 10 | -0.1057 | 0.094 | 20.0 | 0.1106 | 4 / 6 | -0.0480 (3) | -0.0577 (7) | 61.8 | 0.276 | sl 5, reverse 4, end 1 |
| script | mag | off | inverted | 10 | -0.0628 | 0.336 | 30.0 | 0.1203 | 6 / 4 | -0.0478 (3) | -0.0150 (7) | 73.6 | 0.328 | sl 5, reverse 4, end 1 |
| script | mag | on | normal | 2 | -0.0415 | 0.000 | 0.0 | 0.0441 | 1 / 1 | -0.0415 (2) | +0.0000 (0) | 12.0 | 0.011 | sl 2 |
| script | mag | on | inverted | 2 | -0.0415 | 0.000 | 0.0 | 0.0721 | 1 / 1 | -0.0415 (2) | +0.0000 (0) | 121.0 | 0.108 | sl 2 |
| ours | tv | off | normal | 10 | -0.1000 | 0.108 | 20.0 | 0.1060 | 4 / 6 | -0.0463 (3) | -0.0537 (7) | 61.8 | 0.276 | sl 5, reverse 4, end 1 |
| ours | tv | off | inverted | 10 | -0.0571 | 0.370 | 30.0 | 0.1181 | 6 / 4 | -0.0461 (3) | -0.0110 (7) | 73.6 | 0.328 | sl 5, reverse 4, end 1 |
| ours | tv | on | normal | 2 | -0.0404 | 0.000 | 0.0 | 0.0433 | 1 / 1 | -0.0404 (2) | +0.0000 (0) | 12.0 | 0.011 | sl 2 |
| ours | tv | on | inverted | 2 | -0.0404 | 0.000 | 0.0 | 0.0713 | 1 / 1 | -0.0404 (2) | +0.0000 (0) | 121.0 | 0.108 | sl 2 |
| ours | mag | off | normal | 10 | -0.1000 | 0.108 | 20.0 | 0.1060 | 4 / 6 | -0.0463 (3) | -0.0537 (7) | 61.8 | 0.276 | sl 5, reverse 4, end 1 |
| ours | mag | off | inverted | 10 | -0.0571 | 0.370 | 30.0 | 0.1181 | 6 / 4 | -0.0461 (3) | -0.0110 (7) | 73.6 | 0.328 | sl 5, reverse 4, end 1 |
| ours | mag | on | normal | 2 | -0.0404 | 0.000 | 0.0 | 0.0433 | 1 / 1 | -0.0404 (2) | +0.0000 (0) | 12.0 | 0.011 | sl 2 |
| ours | mag | on | inverted | 2 | -0.0404 | 0.000 | 0.0 | 0.0713 | 1 / 1 | -0.0404 (2) | +0.0000 (0) | 121.0 | 0.108 | sl 2 |

Reference, reversed labels, cost script (tv = mag here): filter off rev_literal 9 trades
-0.0872 %, rev_mirror 10 trades -0.0628 % (= inverted); filter on rev_literal 6 trades
-0.0562 %, rev_mirror 6 trades -0.0504 %.

Reading notes:
- Net % is of the initial capital with the script's sizing (1 % of equity per entry), so the
  figures are small by construction.
- XAU 240, filter on: 2 trades in both directions and both are stopped out in both. Normal:
  short 1253.881 -> stop 1277.638, long 1246.449 -> stop 1220.355 (-0.041477 %). Inverted: long
  1253.881 -> mirrored stop 1230.086 (hit 106 bars later), short 1246.449 -> mirrored stop
  1272.509 (-0.041482 %). The two nets agree to 4 decimals because each loss is the same stop
  distance on the same size; they are not the same number. With 2 trades (10 with the filter
  off) this cell says nothing about the option.
- On XAU 240 the mag path gives exactly the tv results (no exit depends on the order inside a
  240-minute bar here); on BTC 60 it moves net % in the 4th decimal.
- Inverted is not minus normal: entries coincide only while both runs are flat or reversing
  at the same bar; the mirrored exits end trades at other times, after which a same-kind
  signal is ignored in one run and opens a trade in the other (BTC 60 off: 131 vs 122 trades).

## Hand traces (BTC 60, filter on, option on, cost script; from the trade list)

Signal times are the signal bar's close (UTC); a fill "at the next open" is at that same time.

- SELL signal 2024-11-18 12:00, close 90272, in the SELL zone. Normal bracket: stop 92621.234,
  target 83224.298. Inverted: real LONG at the next open 90285; stop 2c-S = 87922.766,
  target 2c-T = 97319.702; exit `tp` at 97319.70248 on 2024-11-21 04:00 (bar high 97699).
- BUY signal 2024-11-24 19:00, close 96607, in the BUY zone. Normal: stop 95975.821, target
  98500.536. Inverted: real SHORT at 96563; stop 97238.179, target 94713.464; exit `sl` at
  97238.17856 three bars later (bar high 98091).
- Re-send: BUY signal 2025-02-11 22:00 opens a real SHORT at 96370 (stop 99257.649). A later
  allowed BUY signal (2025-02-18 10:00, close 95758) moves the stop to 97501.427; a BLOCKED BUY
  signal (2025-02-18 22:00, close 95001) moves it to 95987.427 (target 92041.719): "also when
  blocked". Exit `sl` at 95987.42704 on 2025-02-19 10:00.
- Blocked-opposite close: SELL signal 2025-05-21 18:00 opens a real LONG at 106671. On
  the bar closing 2025-05-25 23:00 a BUY signal appears outside the BUY zone (blocked):
  `apxBlkLong and apxPosN < 0` -> `strategy.close("Apex Long")`, filled at the next open
  109219 (`blocked_close`).
- Reversal: the real SHORT of the BUY signal of 2025-03-26 21:00 (87300) is reversed by the
  allowed SELL signal of 2025-03-31 20:00: exit `reverse` at the next open 82409, and a real
  LONG opens there.
