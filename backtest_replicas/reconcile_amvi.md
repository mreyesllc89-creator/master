# reconcile_amvi: stage 3 for AMVI Full MTF Strategy + FGF [Update 1] (key `amvi`)

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Ground truth: `/home/user/master/AMVI_Full_MTF_Strategy_FGF.pine` at HEAD (`Lnnn` = its lines); unfused original
`/home/user/master/AMVI_Full_MTF_Strategy.pine` (`Onnn`). Brief: `$W/SPEC_amvi.md`. The two stage-2 builds as
delivered are kept in `$W/reconcile_amvi_orig/` (with their SHA-256); `$W/amvi_a.py` is build A after the one fix
below, `$W/amvi_b.py` is build B unchanged, `$W/amvi.py` is the canonical module (B + the 'mag' path).

## Result

- Written independently from the Pine and the brief, the two builds gave **the same trades in every case of
  round 0**: 640 cases on 10 cells (BTC and XAU, charts 1, 5, 15, 60, 240, full windows), 419,901 trades,
  every column of `trades()` and every field of `summary()`. The largest relative difference of a float column
  was 6.4e-11 (a P/L close to zero: B subtracts the sum of a trade's two costs, A subtracts them one by one).
- One difference was found outside the full windows (D1, a summary field on a window whose mid-point is the last
  bar). B follows SPEC_amvi section 12; A was fixed.
- No place was found where both builds follow the brief and the Pine does something else (section "Shared
  readings" below lists what was checked against the Pine, line by line).
- After the fix: **round 1, all 14 cells (charts 1, 5, 15, 30, 60, 120, 240), 952 cases, 513,859 trades, 0
  differences** between A, B and the canonical module; the canonical module equals B bit for bit on path 'tv'
  in every case (`tests_amvi.py` T1 repeats it on the 10 cells).

## What was compared (`$W/reconcile_amvi_cmp.py PAIR TF --mods a,b[,c] --nrand 8 --extra --edge`)

Per cell (full window unless said):

| group | cases | content |
|---|---|---|
| fixed | 18 | filter {on = the fused file, off = the unfused original's defaults (dirSource 'orig', "Trend (EMA)" 50, "Both", reverse on)} x `inv` {off, on} x cost {tv, ours, stress}; the literal fused file with `fgfOn` False (both directions: no trade); `revClose` 'closes' (filter on / off); `ltfRule` 'last' (both directions) |
| random | 8 (112 over the 14 cells, 80 over the 10 cells of round 0) | settings drawn from the calibration grid of SPEC_amvi section 14: `highVolThreshold` {50, 60, 70, 80}, `minConfluence` {1, 2, 3}, `tfSet` {'all', 'ge'} (charts 1, 120, 240: 'all'), `dirSource` / `dirMode`, `fgfTf` {"15", "60", "240"} with the parent and the three zones moved with it ("240" builds the 480 and 960 bars), `fgfBandAtr` {0, 0.25, 0.75}, `fgfLvMode`, `inv`, `slMult` {1, 1.5, 2.5}, `exitStyle` {tp3, tp1.5, none, trail with the cell's trailing pair}, `useVolExit`; each with a random cost mode and `revClose` |
| extra | 38 | SPEC_amvi section 13's list: periods 7 / 100 / 20 (filter on and off), `noRepaint` off (and with `ltfRule` 'last', which it must ignore), `ltfRule` 'last' with Donchian, one timeframe only with confluence 1, no timeframe at all, the five seconds toggles off, (60, 1), (65, 4), trailing (tp 0; inverted with cost 'tv'; with stop and target; tight 0.5 / 0.25; activation 0 = the 1-tick minimum), `slMult` 0, `tpMult` 0, no bracket, trail only, `maxBars` 5 / 3 / 2 with 'void' and 'closes', collapse off with and without a time stop, the original's `allowReverse` off, "Long Only" with `inv`, "Short Only" with Donchian 10, EMA 20 with no reverse and `inv`, `useDateRange` (the middle half of the window), `fgfCheck` "Candle open", `fgfAllowSell` off with `inv`, `fgfAllowBuy` off, `fgfLast` "Candles", `fgfTf` "" (the chart; on chart "1" "5" instead), other weights with `exitAtrLen` 7 and `lowVolThreshold` 40, stress + inv + trail, the inputs of `/home/user/master/AMVI_by_timeframe/AMVI_FGF_XAUUSD_15m.pine` |
| edge | 3 (XAU 5) | two months in the middle of the pair's window (default; loose trigger + original Candle + inv + trail + `maxBars` 4 + 'closes'; loose trigger + filter, cost ours); on XAU a window that ends over a weekend (the mid-window bar is the last bar, a trade open at the end), both directions |

Every column of `trades()` (floats to a relative 1e-9, everything else exactly) and every field of `summary()`.
Coverage of round 1 (sum over the cases): 235,679 'sl', 102,655 'tp', 36,949 'trail', 27,350 'reverse', 58,152
'vol', 52,809 'time', 222 'end' exits; 66 cases with a close_all placed in the same run as a reversal
(`rev_close_same_run`, 978 such runs), both `revClose` readings.

Logs: round 0 `$W/reconcile_amvi_r0_<PAIR>_<TF>.log` (A and B as delivered, groups fixed / random / extra),
round 1 `$W/reconcile_amvi_r1_<PAIR>_<TF>.log` (A fixed, B and the canonical; all four groups; charts 30 and 120
added). Scripts: `$W/reconcile_amvi_r0.sh`, `$W/reconcile_amvi_r1.sh`.

| cell | round 0: cases / differ / trades | round 1: cases / differ / trades |
|---|---|---|
| BTC 1 | 64 / 0 / 112,767 | 67 / 0 / 115,203 |
| BTC 5 | 64 / 0 / 104,375 | 67 / 0 / 106,021 |
| BTC 15 | 64 / 0 / 57,745 | 67 / 0 / 58,797 |
| BTC 30 | | 67 / 0 / 42,353 |
| BTC 60 | 64 / 0 / 22,358 | 67 / 0 / 22,750 |
| BTC 120 | | 67 / 0 / 18,746 |
| BTC 240 | 64 / 0 / 10,880 | 67 / 0 / 11,057 |
| XAU 1 | 64 / 0 / 44,606 | 69 / 0 / 46,181 |
| XAU 5 | 64 / 0 / 28,977 | 69 / 0 / 30,134 |
| XAU 15 | 64 / 0 / 25,013 | 69 / 0 / 25,738 |
| XAU 30 | | 69 / 0 / 15,242 |
| XAU 60 | 64 / 0 / 8,088 | 69 / 0 / 8,383 |
| XAU 120 | | 69 / 0 / 8,026 |
| XAU 240 | 64 / 0 / 5,092 | 69 / 0 / 5,228 |
| total | 640 / 0 / 419,901 | 952 / 0 / 513,859 |

(Round 0 had no edge group; the edge cases were then run on XAU 5, XAU 60 and BTC 15 with A and B as delivered:
the two XAU weekend windows differed in `half1_pct` / `half2_pct`, every other edge case was equal.)

## The disagreement

### D1. `half1_pct` / `half2_pct` when the mid-window bar is the last bar (summary only; no trade affected)

SPEC_amvi section 12: the equity curve is "10,000, then E[0] .. E[n-2], then the final equity (after the 'end'
close and its cost) in place of E[n-1]"; `half1_pct` / `half2_pct` from `E[mid_j]`, "as hrd" (`hrd._kernel`:
`if mid_j == n - 1: eq_mid = eq_last` after the end close). B did that. A took `E[n-1]` BEFORE the end close.
The two differ only when `mid_j == n - 1` (no bar of the window closes after its mid-point) with a trade open at
the end: never on the pair windows. Hand trace (`$W/reconcile_amvi_trace.log`, part 1): XAU 5, window 2017-03-03
00:00 to 2017-03-05 12:00 UTC: every bar closes on the Friday, the mid-point is on the Saturday, `mid_j = n - 1`;
a long is open at the last close; A's `half1_pct` = E[n-1] before the 'end' fill (close - 1 tick, 0.04 %
commission), B's = after it: -0.1558 % / -0.1599 % (XAU 5, normal), the difference being exactly the end close's
slippage and commission. Not a Pine matter (the Pine has no halves); B follows the brief. A changed (3 lines at the
end of `_kernel`).

### Input-domain difference, not changed

A refuses a window that starts at row 0 of the data file or has a single bar (`ValueError`); B runs them (row
`w0 - 1` read as na). No such window is used anywhere (every data file starts in 2011 / 2012); the canonical
module (B) keeps B's behaviour.

## Shared readings checked against the Pine

The builds agreeing says nothing about a reading both took from the brief. The strategy section (L719-835) was
read line by line against SPEC_amvi sections 4-9 and the canonical kernel; no deviation was found. The points
that decide trades:

| Pine | brief / builds | checked |
|---|---|---|
| L779-783 `amviInv`, `longSig = trigger and (amviInv ? amviDirDn : amviDirUp) and inRange`, `goLong = longSig and strategy.position_size <= 0` | swap after the filter, real position test | `_decide`; the literal reference of `tests_amvi.py` T4 has its own transcription; T6 P2 / P5 |
| L797-805 `var float entryAtr`, `entryAtr := atrX` only when an order is placed | the order's ATR | T4's reference keeps the `var` and re-sends the exits every bar as the Pine does: equal to the kernel's per-trade ATR (the brief's C3 argument holds) |
| L808-809 `math.max(1, math.round(entryAtr * mult / syminfo.mintick))` | ticks per order, at least 1 | T4 (trail settings incl. activation 0) |
| L811-826 `hasBracket`, `ep = position_size > 0 ? position_avg_price : close` (long), the short block with `ep +/-` | fill bar from the signal close, then from the entry price | T4's reference re-sends both blocks every bar, including the reversal run where both fire (the old side with the NEW `entryAtr`): never acts, the old trade closes at the next open |
| L829-835 `close_all` on `ta.crossunder(avgAmvi, lowVolThreshold)` with `position_size != 0`; time stop `bar_index - strategy.opentrades.entry_bar_index(0) >= maxBars` | side-less closes at the next open; one close per run, 'vol' first | T4 |
| L744-770 crosses, `hot`, `cnt`, `val`, `avgAmvi`, `trigger` | na never crosses, `enCount` = non-na values | A and B computed them separately (A one pass, B with a cached count layer): equal on every case |
| L733-736 `request.security(..., calc_amvi()[noRepaint ? 1 : 0], lookahead = noRepaint ? on : off)` | A2: the last bar closed by the chart bar's open (`[1]` + lookahead on), `ltfRule` 'last' for the live reading of lower timeframes | the one reading that cannot be tested here; `runs_ltf_last` in the runner shows its weight |

Two statements of the brief were too broad (both builders noted them; the Pine wins, nothing to fix in the
modules): P8 (`noRepaint` off = on shifted one bar) holds only between contiguous chart bars, because a
timeframe's bar can close inside a data gap of the chart (T6 tests it on contiguous rows); and "impossible with
the default inputs" for `rev_close_same_run` holds for the defaults (0 in all 14 cells) but not for `maxBars` 5
alone (XAU 240: 1).

## The canonical module

`$W/amvi.py` = build B + the 'mag' path. B was taken because its kernel separates the decision (`_decide`,
used by the single-decision test P2) and the close decision, it can return the per-bar equity and position
(`full=True`), it has `prepare_injected` for hand-made kernel tests, layered and memory-capped caches as the
brief asks for the calibration, and a literal pure-Python reference (`amvi_b_ref.py`). A is equal trade for trade.

Path 'mag' (SWEEP_AH_SPEC.md section 2, SPEC_amvi 6.3): the open trade's bracket (stop loss, target, trailing
stop: this script has no other price order and no stop / limit entry) walks the 1-minute sub-bars of the chart
bar in time order (`sub_bars`: the rows of `data/<PAIR>_1.parquet` with `t_open` in `[t_open, t_close)` of the
chart bar, checked to rebuild every chart bar's OHLC); each sub-bar gets the open test and its own rule-4 path;
the trailing state carries over; the levels are those of the chart bar (the fill bar's `SL0` / `TP0` on all its
sub-bars, the re-anchored ones from the next chart bar). Market entries, reversals, the close_all orders and the
bar-close run stay on the chart bars. One function (`_bar_walk` over `_walk`) serves both paths. `R['xsub']`
gives the sub-bar of a bracket exit; the trade record keeps chart-bar times (SPEC 12). Chart "1": mag == tv.

## Hand traces (`$W/reconcile_amvi_trace.py`, log next to it)

1. D1 (above): 253 bars, the last closes Friday 2017-03-03 22:00, mid-point Saturday 06:00, `mid_j = 252 = n -
   1`; a short of 0.810581 oz from 1,232.172 is closed 'end' at 1,235.582 (the last close + 1 tick); E[n-1]
   = 9,984.4188 before that fill, 9,984.0101 after it: `half1_pct` -0.1599 % (B, the brief) against -0.1558 % (A
   as delivered).
2. 'mag' against 'tv' (BTC 60, default inputs, cost 'tv'): 2 of 303 trades exit elsewhere. Trade #47, a short
   filled at 94,151.99 on bar 111910 (signal close 94,113.00, ATR 1,259.285; fill-bar stop 96,001.93 / target
   90,335.14, then 96,040.92 / 90,374.13 from the entry price), runs 20 bars; bar 111930 (O 93,566 H 93,695 L
   89,157 C 89,179): 'tv' walks O-H-L-C ((high - open) 129 < (open - low) 4,409) and fills the target at its
   level, 90,374.13; 'mag' walks 54 minutes: 14:52 closes at 90,387, 14:53 opens at 90,363.00 below the target:
   filled at that open, 11.13 better.
3. The first XAU 60 trigger (bar 31917, SELL ZONE, close 1,160.599) with "Follow the filter" (short at 1,160.58
   = open 1,160.59 - 1 tick) and "Inverted" (long at 1,160.60): fill-bar stops 1,166.798 / 1,154.400 and targets
   1,148.202 / 1,172.996, both pairs centred on the signal close 1,160.599; re-anchored stops 1,166.778 /
   1,154.400, targets 1,148.182 / 1,172.996, centred on the raw open 1,160.589; a `2R - S` mirror of the normal
   stop about the inverted fill would be 1,154.420, the Pine's level is 1,154.400 (2 ticks).

## Tests, mutants

- `python3 -I tests_amvi.py` -> `$W/tests_amvi.log` (see amvi_notes.md section 11).
- `$W/amvi_s3_mut.sh` -> `$W/amvi_s3_mut.log`: 15 copies of `amvi.py` with one line changed, each run against
  T2-T7: 13 killed; the 2 survivors cannot change a trade (amvi_notes.md section 11).

## Runner

`python3 -I run_inv_amvi.py PAIR TF [TF ...]` -> `$W/out/inv_amvi_<PAIR>_<TF>.json` (logs
`$W/out/run_inv_amvi_<PAIR>_<TF>.log`), all 14 cells: `runs` (direction x filter x path x cost, 16 keys; filter
off = the unfused original, `filter_off_is`), `runs_ltf_last` (filter on, `ltfRule` 'last', 8 keys),
`fgf_off_literal` (the fused file with `fgfOn` false: 0 trades in every cell). Checks stored in every file: chart
"1": every 'mag' run equals its 'tv' run (true, both pairs); the sub-bars rebuild the chart bars (true, 14 cells).
Table: `python3 -I inv_tables_amvi.py [--ltf]` -> `$W/inv_tables_amvi.md`.
