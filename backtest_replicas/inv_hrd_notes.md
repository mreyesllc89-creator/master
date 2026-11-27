# HRD replica: the Update 1 option "Inverted direction" (hrdInv)

Brief: `INV_BT_SPEC.md`, strategy "hrd". Ground truth: the Pine at HEAD `d28ba97`,
`/home/user/master/HRD_Full_Divergence_Strategy_v1_03_FGF.pine`; what Update 1 changed in it:
`git -C /home/user/master diff 6c59b9f d28ba97 -- HRD_Full_Divergence_Strategy_v1_03_FGF.pine`.
Nothing was written inside `/home/user/master`. No other strategy's module was edited.

## Files

| file | what |
|---|---|
| `hrd.py` | the replica, with the new param `hrdInv` (alias `inv`), default False |
| `pre_inv_backup/hrd.py` | the replica as it was before this change (sha256 `a3f001ea...7bfc9b3`), kept for regression |
| `pre_inv_backup/baseline_sweep_ah_tests_hrd.log` | the existing hrd tests run on the module BEFORE the change (7 PASS) |
| `inv_tests_hrd.py` | R1-R4 (+ R5 reference, R6 speed, R7 public entry points, added by the sceptic review); log `inv_tests_hrd.log` (11 PASS, 0 FAIL) |
| `inv_existing_tests_hrd.py` | runs every existing `sweep_ah_tests.py` hrd test on the changed module in one process; log `inv_existing_tests_hrd.log` (12 PASS, 0 FAIL) |
| `inv_existing_verify_trail_hrd.log` | the existing independent verifier `verify_trail_hrd.py check` on the changed module (640 runs, 0 failed) |
| `inv_mutants_hrd.py`, `inv_mutants_hrd.sh` | 8 deliberately wrong versions of the option; the tests must catch each; log `inv_mutants_hrd.log`. They work in `inv_mut_hrd/` (links to the data and tests; its `hrd.py` is a scratch copy, not the replica) |
| `run_inv_hrd.py` | the runner; writes `out/inv_hrd_<PAIR>_<TF>.json` |
| `out/inv_hrd_BTC_60.json`, `out/inv_hrd_XAU_240.json` | the two cells run here |

## What changed in hrd.py

`diff pre_inv_backup/hrd.py hrd.py` is the whole change (49 lines in, 15 lines out): a docstring
paragraph, one default, one alias, one extra kernel argument, and in the kernel four values set
before the bar loop plus the gate, the blocked close and the head of the entry loop.

- `DEFAULTS['hrdInv'] = False`; `_ALIASES['inv'] = 'hrdInv'`. It is a broker-level param: it is
  not in `_PREP_KEYS`, so `simulate(P, {'hrdInv': True})` (or `{'inv': True}`) switches it on the
  arrays of one `prepare()`; `run(pair, tf, {'hrdInv': True})` works too. Signals, Reverse Trading
  and the filter permissions (`prepare`) do not depend on it.
- `_simulate(..., inv)`: one new last argument. Before the bar loop:
  `dir_ok_l / dir_ok_s` (Trade Direction for the order really placed) and `real_l / real_s` (the
  real side of the order a normal-frame LONG / SHORT entry places). In the loop: `hpos` (the
  Pine's `hrdPos`) replaces `pos` in the gate and in the blocked close; the blocked close and the
  entry carry the real side; the SL / TP formulas are chosen by the real side.
- Nothing else: `_walk` (the intrabar exit order), the time exit, the hybrid exit, sizing, costs,
  the fills, the 'mag' path, `summarize` / `summary_fast` / `trades_frame` are untouched. With the
  option off every expression evaluates to the previous one.

## The Update 1 diff, line by line

| Pine at HEAD (line) | replica |
|---|---|
| title `... [Update 1]`, the header text, the tooltips of `InpReverseTrading`, `InpTradeDirection`, `hrdBlkClose` | text only, nothing to replicate |
| `hrdInv = input.bool(false, "Inverted direction: ...")` (825) | param `hrdInv` (alias `inv`), default False |
| `float hrdPos = hrdInv ? -strategy.position_size : strategy.position_size` (1013) | `hpos = -pos if inv else pos` |
| `bool hrdDirOkL = hrdInv ? shortDirectionAllowed : longDirectionAllowed` (1014) | `dir_ok_l = short_allowed if inv else long_allowed` |
| `bool hrdDirOkS = hrdInv ? longDirectionAllowed : shortDirectionAllowed` (1015) | `dir_ok_s = long_allowed if inv else short_allowed` |
| `string hrdIdL = hrdInv ? "Short" : "Long"`, `hrdIdS = hrdInv ? "Long" : "Short"` (1016-1017) | `real_l = -1 if inv else 1`, `real_s = 1 if inv else -1`: an id names the side really placed ("Long" is always a buy), so the replica keeps the side |
| `hrdWantLong = longSignal and hrdDirOkL and hrdPos <= 0`, `hrdWantShort = shortSignal and hrdDirOkS and hrdPos >= 0` (1018-1019) | `wl = long_sig[k] and dir_ok_l and hpos <= 0`, `ws = short_sig[k] and dir_ok_s and hpos >= 0` |
| `hrdBlkLong = hrdWantLong and not fgfBuyOk`, `hrdBlkShort = ...` (1020-1021, unchanged) | `bl`, `bs` (unchanged): the gate stays in the normal frame |
| `if hrdBlkClose and hrdBlkLong and hrdPos < 0` -> `strategy.close(hrdIdS, ...)` (1027-1028) | `if blk_close and bl and hpos < 0:` close order for side `real_s` (inverted: the open long) |
| `if hrdBlkClose and hrdBlkShort and hrdPos > 0` -> `strategy.close(hrdIdL, ...)` (1029-1030) | `if blk_close and bs and hpos > 0:` close order for side `real_l` (inverted: the open short) |
| LONG block: `stopLossPriceLong = close * (hrdInv ? 1 + SL% : 1 - SL%)`, `takeProfitPriceLong = close * (hrdInv ? 1 - TP% : 1 + TP%)` (1041-1042) | block `blk = 1`, `side = real_l`; the bracket is chosen by `side`: a sell gets `est * (1.0 + sl_pct / 100.0)` and `est * (1.0 - tp_pct / 100.0)`, the same expressions |
| `strategy.entry(id = hrdIdL, direction = hrdInv ? strategy.short : strategy.long, qty = longQuantity, ...)` (1046) | entry order with `p_dir = side`; `qty` from the unchanged `calculatePositionSize` code (same stop distance, `strategy.equity` = the real account) |
| `strategy.exit(id = hrdInv ? "Short Exit" : "Long Exit", from_entry = hrdIdL, stop, limit, trail_points, trail_offset, ...)` (1049) | the entry order carries its `p_sl / p_tp / p_trp / p_tro` (unchanged mechanism); the trail ticks are the same numbers, and the broker trails the side really open |
| SHORT block (1056-1067), the same with the sides exchanged | block `blk = -1`, `side = real_s` |
| the two blocks keep their order (LONG block first) | `for blk in (1, -1)`: on a candle that sends both entries the inverted run sends the sell first, then the buy |
| time exit (986-992): unchanged, reads `strategy.position_size` | unchanged, reads `pos` |
| hybrid exit (1074-1106): unchanged, reads the real position, its average price, its own profit | unchanged, reads `pos`, `ppx` |
| FGD raw / blocked diagnostics (1116-1139): normal frame, unchanged | `n_wl / n_ws / n_bl / n_bs` and the per-bar `want_l / want_s / blk_l / blk_s` are counted from `wl / ws / bl / bs`: the SIGNAL's side |
| comments and ids ("Entry Short (inv)", "SL/TP Short (inv)", "filter blocked LONG signal, close long (inv)") | not stored by the replica (see "Not reproduced"); the test's Pine port carries them and checks that each names the side really traded |

## Interpretations

1. **Sides in the outputs.** `dir`, `long`, `short` are the REAL side of each trade. `raw_long`,
   `raw_short`, `blocked_long`, `blocked_short` (and `want_*`, `blk_*`) are the signal's side
   before the inversion, as the Pine's "FGD ..." values: in an inverted run a "raw long" is a LONG
   signal whose order is a sell.
2. **A candle with a LONG and a SHORT signal while flat** (Trade Direction Both, both allowed by
   the gate): both entries are sent and both fill at the next open in the order they were placed;
   the first is closed at once by the second (a trade of zero bars, P/L 0 before costs; cost
   'ours' charges its two fills). This is the base replica's reading of TradingView's broker and
   what the Pine header states ("Both entries are sent and the second one stays"). Normal: buy
   then sell, the SELL stays. Inverted: sell then buy, the BUY stays. It cannot be checked on
   TradingView from here.
3. **Sizing of an inverted reversal.** `calculatePositionSize` uses `strategy.equity`, the real
   account: cash plus the open P/L of the trade really open at the signal close. An inverted run
   and the normal run have different equity once their trades differ, so quantities differ even
   where the entries are on the same candles.
4. **hrdInv with Reverse Trading.** Both can be on: `reverse` swaps the signals in `prepare()`
   (before the gate), `hrdInv` flips the order in the kernel (after the gate).
5. **Trade Direction** is the Pine's `longDirectionAllowed` / `shortDirectionAllowed` for the
   orders really placed; the kernel swaps them for the normal-frame gate (`hrdDirOkL / S`).
6. **Chart "1"**: 'mag' equals 'tv' (each chart bar is its own sub-bar), with the option on too.
7. Everything the base replica already assumed stays as documented in `hrd_a_notes.md`,
   `reconcile_hrd.md`, `SPEC_AH.md`, `SWEEP_AH_SPEC.md` (fills at the next open in placement
   order, intrabar path rule, trailing state, Bar Magnifier on 1-minute data, no tolerance).

## Not reproduced

- The title, the tooltips, the entry / exit / close comments and the order ids as strings, the
  plots, labels, "x" marks and Data Window values: display only. The replica reports each trade's
  side and exit kind (`sl`, `tp`, `trail`, `reverse`, `blocked_close`, `time`, `hybrid`, `end`).
- Live behaviour (ticks inside a candle, `varip`): the replica is the history backtest, as before.
- There is no TradingView here: the replica reproduces the Pine as written; it has not been
  compared with a TradingView Strategy Tester run of the Update 1 file.

## Tests (`python3 -I inv_tests_hrd.py`, log `inv_tests_hrd.log`: 11 PASS, 0 FAIL, 2 min 2 s)

| test | what it shows | result |
|---|---|---|
| R1a | option off (absent, `hrdInv=False`, `inv=False`): every variant of `out/hrd_<PAIR>_<TF>.json`, 14 cells, and every saved trade list | 168 runs, 5208 saved fields, 140 trade lists (387 756 rows): all equal |
| R1b | option off: sample of `out/swah_hrd_<PAIR>_<TF>.parquet`, 14 files x 16 groups x (default row + 5 random settings), every summary column | 1344 rows (672 tv, 672 mag), 45 696 values: all equal |
| R1c | option off: bit for bit equal to `pre_inv_backup/hrd.py`, `run()` and every kernel output of `simulate(full=True)` | 80 random settings (38 mag), 10 347 trades: all equal |
| R2a | filter off: Inverted alone vs Reverse alone, and both on vs both off (header, INVERTED DIRECTION) | 280 run pairs over the 14 cells: 109 equal bit for bit; 171 differ, every difference inside an episode opened by a candle that sends both entries while flat (1008 episodes; 4690 trades inside, 976 242 trades outside all the same); with those candles' signals removed from the inputs all 280 pairs are equal bit for bit |
| R2b | filter on: the inverted run = the verified normal kernel on the mirrored normal frame (signals AND permissions swapped), i.e. the flip is after the gate; and Inverted is not the reversed-labels run | 280 run pairs, all equal bit for bit (400 881 inverted trades, 40 550 blocked closes); inverted differs from reversed labels in 140 of 140 settings |
| R2c | the header's statements read on the inverted trade lists, 14 cells, filter off and on: side vs signal and gate, fill candle and price, SL / TP mirrored, quantity rule, blocked close and reversal on the mirrored side, Trade Direction = real orders, and the inverted list stays the mirror of the normal one until an SL / TP / hybrid exit | 85 498 inverted trades, 2164 blocked closes, 5801 reversals: all hold |
| R3 | single decisions, 500 sampled bars x 288 cases: (i) option on from real position p = mirror of option off from -p (flags, time exit, closes, entries, SL / TP mirrored, quantity rule); (ii) time exit and hybrid exit measure the trade really open | (i) 139 264 decisions compared (44 672 from a position), 4736 skipped because one bracket had been hit on the way; (ii) 144 000 decisions, every kernel output equal; 1576 bars sending both entries: BUY stays inverted, SELL not |
| R4 | option on: 'mag' on chart "1" = 'tv' (BTC 1, XAU 1, filter off / on, 8 settings each); fake one-sub-bar table on BTC 60 / XAU 240 | 32 + 48 settings, all equal |
| R5 | option on: the kernel = a pure-Python port of the Pine at HEAD (lines 972-1106, Pine names, ids and comments), trade by trade; the 16 runs of the runner on BTC 60 and XAU 240, and 150 random settings (tv and mag) | 8396 + 11 033 trades, all equal; every id / comment names the side really traded |
| R6 | speed, BTC 1 (1.04 M bars), tv, per setting, best of 5 interleaved passes | pre-change 0.0164 s, changed with the option off 0.0171 s (x1.04), on 0.0163 s (x0.99); BTC 60 mag 0.0042 s off and on. The existing timing test (full grid of 1182 settings on BTC 1) took 24.9 s after the change (`inv_existing_tests_hrd.log`), 24.8 s in the log saved on Nov 18 before it (`sweep_ah_tests_hrd.log`) |
| R7 | (sceptic review) the option ON through every public entry point: `run(.., {'inv': True})` = `run(.., {'hrdInv': True})` = `prepare()` without it + `simulate(P, {'inv': True})` = `simulate(P, {'hrdInv': True})`, `summary_fast` = `run()`'s summary, another spelling refused; and the REAL side in the public DataFrame and summary (a `dir` -1 row comes from an allowed LONG signal, its P/L is a sell's, its stop above / target below; `short` = the LONG-signal entries; `raw_*` / `blocked_*` = the signal's side read on the real position) | 40 inverted runs (BTC 60 / 240, XAU 60 / 240 x filter off / on x 5 parameter sets), 7568 trades: all hold |

R2a in words. With the filter off the conditions for a real buy and a real sell are the same in
the inverted run and in the reversed-labels run; only the order of the two execution blocks
differs, which matters only when both fire, i.e. flat with both signals. The test cuts each pair
of runs at those candles: from such a candle until both runs are flat again the trades differ
(the BUY stays in the inverted run, the SELL in the other); everywhere else the trades are the
same, one to one (side, bars, prices, exit kind, SL, TP exactly; quantity and P/L per unit of
equity to 1e-9, because the two accounts differ after an episode).

The R3 mirror property does not hold for the hybrid exit, by design of the Pine: it measures the
profit of the trade really open, which is the opposite of the mirror trade's. R3 (i) therefore
runs with the hybrid exit off and R3 (ii) checks the hybrid and time exits as "same real trade,
same decision". The quantity is "the same rule on each account's equity": equal only when the
two equities are equal.

Sensitivity (`inv_mutants_hrd.log`): each mutant is `hrd.py` with one wrong reading of the
option; "caught by" lists the tests that FAIL on it (R2a, R2b, R2c, R3, R5 were run).

| mutant (one wrong reading of the option) | caught by |
|---|---|
| the gate reads the real position instead of `hrdPos` | R2a, R2b, R2c, R3, R5 |
| Trade Direction applied to the signal's side instead of the order really placed | R2a, R2b, R2c, R3, R5 |
| the blocked close closes the normal-frame id (a blocked LONG signal closes a short) | R2b, R2c, R3, R5 (R2a has no blocked signal: filter off) |
| SL / TP not mirrored (the sell keeps the stop below, the target above) | R2a, R2b, R2c, R3, R5 |
| the two execution blocks sent buy first instead of in the Pine's order | R2a, R2c, R3, R5 (R2b: the filter never allows both sides on one candle) |
| the flip applied before the gate (the inverted LONG signal asks the SELL ZONE) | R2b, R2c, R3, R5 (R2a: filter off) |
| the hybrid exit measures the mirror trade instead of the trade really open | R2a, R2b, R3, R5 |
| quantity from the mirror account's equity instead of the real equity | R2a, R2b, R2c, R3, R5 |
| control: the unmutated copy | none: 5 PASS |

Existing tests on the changed module:
- `sweep_ah_tests.py`, every hrd test (`inv_existing_tests_hrd.py`): 12 PASS, 0 FAIL. Three of
  them (R6, R7, R8) call the sweep with 3 workers; they were run with 1 worker here (process
  limit 2), so R6 (output independent of the worker count) compared two 1-worker runs and does
  not show that property this time. `sweep_hrd.py` itself was not changed.
- `verify_trail_hrd.py check` BTC60 and XAU240, seeds 1 and 2 (the second with `extra`):
  640 runs, 0 failed.

## Runner

`python3 -I run_inv_hrd.py PAIR TF [TF ...] [--trades]` writes `out/inv_hrd_<PAIR>_<TF>.json`:

- `runs["<direction>_<filter>_<path>_<cost>"]`, 16 runs: direction `normal` / `inverted`
  (hrdInv), filter `off` / `on`, path `tv` / `mag`, cost `script` (hrd cost 'tv': HRD's
  `strategy()` sets no commission, so none) / `ours` (hrd cost 'ours').
- `reference["rev_<filter>_<path>_<cost>"]`, 8 runs: the existing reversed-labels runs
  (Reverse Trading on, hrdInv off).
- every run: `trades, net_pct, pf, win_pct, max_dd_pct, max_dd_init_pct, h1r_pct, h2r_pct,
  h1_trades, h2_trades, long, short, exits{sl,tp,reverse,blocked_close,time,hybrid,end,trail},
  avg_bars_held, exposure, zero_length, costs, final_equity, half1_pct, half2_pct,
  net_closed_pct, end_trade_pnl_pct, avg_trade_pct, raw_long, raw_short, blocked_long,
  blocked_short`, plus `direction, labels, filter, path, cost, params`.
- `checks`: the 8 normal / reversed tv runs against the saved `out/hrd_<PAIR>_<TF>.json` (every
  common field; the runner stops with an error if one differs), `summary_fast` against the full
  summary, and on chart "1" mag == tv.
- Timing: BTC 60 1.1 s, XAU 240 0.6 s; BTC 1 about 6 s, XAU 1 about 2 s (tried with the output
  sent to a scratch directory; those files are not in `out/`).

### BTC 60 (17 518 bars, 2024-11-17 .. 2026-11-17), net % of the initial capital

| run | trades | net % | pf | win % | max DD % | h1r % | h2r % | long / short | exits sl/tp/rev/blk/time/hyb/end |
|---|---|---|---|---|---|---|---|---|---|
| normal, filter off, tv, script | 621 | +2.720 | 1.023 | 51.0 | 10.73 | +6.947 | -3.952 | 308 / 313 | 47/6/48/0/507/12/1 |
| normal, filter off, tv, ours | 621 | -9.343 | 0.919 | 49.3 | 16.79 | +0.691 | -9.965 | 308 / 313 | same |
| normal, filter off, mag, script | 621 | +2.717 | 1.023 | 51.0 | 10.73 | +6.944 | -3.952 | 308 / 313 | same |
| normal, filter off, mag, ours | 621 | -9.346 | 0.919 | 49.3 | 16.79 | +0.688 | -9.965 | 308 / 313 | same |
| normal, filter on, tv, script | 248 | +4.656 | 1.107 | 54.0 | 6.37 | +7.356 | -2.515 | 127 / 121 | 17/2/1/20/207/1/0 |
| normal, filter on, tv, ours | 248 | -0.437 | 0.990 | 50.8 | 9.43 | +4.821 | -5.016 | 127 / 121 | same |
| normal, filter on, mag, script | 248 | +4.653 | 1.107 | 54.0 | 6.37 | +7.353 | -2.515 | 127 / 121 | same |
| normal, filter on, mag, ours | 248 | -0.440 | 0.990 | 50.8 | 9.43 | +4.818 | -5.016 | 127 / 121 | same |
| inverted, filter off, tv, script | 624 | -4.838 | 0.957 | 48.4 | 11.69 | -8.269 | +3.740 | 316 / 308 | 58/6/50/0/492/17/1 |
| inverted, filter off, tv, ours | 624 | -16.066 | 0.857 | 45.2 | 17.79 | -13.673 | -2.772 | 316 / 308 | same |
| inverted, filter off, mag, script | 624 | -4.838 | 0.957 | 48.4 | 11.69 | -8.269 | +3.740 | 316 / 308 | same |
| inverted, filter off, mag, ours | 624 | -16.066 | 0.857 | 45.2 | 17.79 | -13.673 | -2.772 | 316 / 308 | same |
| inverted, filter on, tv, script | 248 | -3.524 | 0.920 | 46.0 | 9.07 | -6.930 | +3.660 | 121 / 127 | 17/2/2/21/205/1/0 |
| inverted, filter on, tv, ours | 248 | -8.222 | 0.820 | 42.7 | 10.81 | -9.131 | +1.001 | 121 / 127 | same |
| inverted, filter on, mag, script | 248 | -3.524 | 0.920 | 46.0 | 9.07 | -6.930 | +3.660 | 121 / 127 | same |
| inverted, filter on, mag, ours | 248 | -8.222 | 0.820 | 42.7 | 10.81 | -9.131 | +1.001 | 121 / 127 | same |
| reference: reversed labels, filter off, tv, script | 624 | -4.975 | 0.956 | 48.2 | 11.69 | -8.269 | +3.591 | 316 / 308 | 58/6/50/0/492/17/1 |
| reference: reversed labels, filter off, tv, ours | 624 | -16.187 | 0.856 | 45.0 | 17.90 | -13.673 | -2.912 | 316 / 308 | same |
| reference: reversed labels, filter on, tv, script | 299 | -8.102 | 0.876 | 49.5 | 15.10 | -4.477 | -3.794 | 155 / 144 | 43/3/7/20/222/3/1 |
| reference: reversed labels, filter on, tv, ours | 299 | -13.467 | 0.797 | 45.5 | 18.48 | -7.315 | -6.637 | 155 / 144 | same |

The four reversed-labels mag runs equal their tv runs on every field of the file.

### XAU 240 (2246 bars, 2017-01-02 .. 2018-06-19)

| run | trades | net % | pf | win % | max DD % | h1r % | h2r % | long / short | exits sl/tp/rev/blk/time/hyb/end |
|---|---|---|---|---|---|---|---|---|---|
| normal, filter off, tv, script | 141 | -3.150 | 0.836 | 43.3 | 7.38 | -1.284 | -1.891 | 73 / 68 | 0/0/21/0/112/8/0 |
| normal, filter off, tv, ours | 141 | -4.745 | 0.762 | 41.8 | 8.44 | -2.224 | -2.579 | 73 / 68 | same |
| normal, filter on, tv, script | 38 | -0.040 | 0.993 | 55.3 | 3.27 | +0.469 | -0.507 | 21 / 17 | 0/0/1/3/32/2/0 |
| normal, filter on, tv, ours | 38 | -0.482 | 0.915 | 52.6 | 3.44 | +0.231 | -0.711 | 21 / 17 | same |
| inverted, filter off, tv, script | 141 | +4.433 | 1.278 | 57.4 | 2.54 | +2.443 | +1.943 | 69 / 72 | 2/0/21/0/110/8/0 |
| inverted, filter off, tv, ours | 141 | +2.715 | 1.164 | 53.9 | 2.76 | +1.469 | +1.228 | 69 / 72 | same |
| inverted, filter on, tv, script | 38 | -0.635 | 0.895 | 44.7 | 2.25 | -0.329 | -0.307 | 17 / 21 | 1/0/1/4/32/0/0 |
| inverted, filter on, tv, ours | 38 | -1.075 | 0.828 | 44.7 | 2.43 | -0.565 | -0.512 | 17 / 21 | same |
| reference: reversed labels, filter off, tv, script | 141 | +5.455 | 1.352 | 58.2 | 2.54 | +2.443 | +2.939 | 69 / 72 | 2/0/21/0/110/8/0 |
| reference: reversed labels, filter off, tv, ours | 141 | +3.720 | 1.231 | 54.6 | 2.76 | +1.469 | +2.218 | 69 / 72 | same |
| reference: reversed labels, filter on, tv, script | 86 | +4.132 | 1.491 | 64.0 | 2.07 | +1.391 | +2.704 | 39 / 47 | 1/0/7/5/68/5/0 |
| reference: reversed labels, filter on, tv, ours | 86 | +3.082 | 1.352 | 58.1 | 2.13 | +0.763 | +2.302 | 39 / 47 | same |

On XAU 240 every mag run equals its tv run on every field of the file (all 12 pairs), so only tv is listed.

### Reading the two cells

- Filter off, inverted vs reversed labels: the same trades except one episode per cell, the
  header's exception. BTC 60: the candle closing 2026-09-17 00:00 UTC has a bullish and a bearish
  divergence while flat; inverted keeps the BUY (+684.64), reversed labels the SELL (-684.64):
  net -4.838 % vs -4.975 %. XAU 240: the candle closing 2018-02-01 19:00 UTC, the same; inverted
  keeps the BUY (-5088.90), reversed labels the SELL (+5088.90): net +4.433 % vs +5.455 %. One
  trade of 1 % risk moves the XAU 240 result by a full point, with 141 trades in the cell.
- Filter on, inverted is a different run from reversed labels (BTC 60: 248 trades, -3.524 %
  against 299 trades, -8.102 %): the inverted entry needs the zone of the signal's own side, the
  reversed one the zone of the opposite side.
- Inverted is not minus normal. The entries are the same candles while the two runs mirror each
  other, but the 2 % stop and 4 % target, the hybrid exit and the sizing on each account's equity
  are not symmetric. BTC 60 filter on: normal +4.656 %, inverted -3.524 %. XAU 240 filter off:
  normal -3.150 %, inverted +4.433 %.
- 'mag' and 'tv' give the same numbers in 20 of the 24 pairs of runs of these two cells. They differ
  only on the four normal BTC 60 runs (filter off / on x both costs), by 0.003 points of net %
  (e.g. +2.717 % against +2.720 %).
- These are two cells of 14 and one parameter set; they are not evidence for or against the
  option. The other cells are for the orchestrator to run with the same runner.

## Sceptic review (second pass, independent of the implementation)

Scope: the option in `hrd.py`, `inv_tests_hrd.py`, `run_inv_hrd.py`. `hrd.py` and `run_inv_hrd.py`
were NOT changed (sha256 `6dd2db90...05f195`, `ad76e639...78c6620`): no defect was found in them.
Changed: `inv_tests_hrd.py` (test R7 added, see below), `inv_tests_hrd.log` / `.time` (re-run, 11
PASS; the implementer's log is kept as `sceptic_hrd/inv_tests_hrd.log.implementer`), this file.
The review's own files are in `sceptic_hrd/` (that directory also holds older files of the
November 18 trailing-sweep review; the ones below are today's). Nothing was written in
`/home/user/master`.

| file (in `sceptic_hrd/`) | what |
|---|---|
| `ref_inv.py`, logs `ref_inv_json_<PAIR>.log`, `ref_inv_more_<PAIR>.log` | a second pure-Python reading of the Pine at HEAD, written in the REAL frame from the header text (a LONG signal is a sell order, wanted while flat or long, gated by the BUY ZONE, closing an open long when blocked; stop above / target below), with its own intrabar bracket walk and its own 1-minute table. It uses neither hrd's kernels nor `sweep_ah_tests` nor the R5 port |
| `mutants.py`, sandbox `mut/`, logs `mut_pass1.log`, `mut_pass2.log`, `ref_vs_mutants.log` | 18 wrong readings of the option, each written to the sandbox copy `mut/hrd.py` (never to `hrd.py`) |
| `off_check.py`, `off_check.log` | option off against the saved results, written apart from R1 |
| `runner_check.py`, `runner_check.log`, `run_all_scratch.py`, `out/` | checks of the runner's JSON; the runner run for all 14 cells into the scratch `sceptic_hrd/out/` (NOT into `out/`) |
| `sanity.py`, `notes_check.py` | normal against inverted trade lists; the tables of this file against the JSON |

1. **The Update 1 diff, line by line.** Every changed code line of the Pine has its counterpart:
   `hrdInv` (param, alias), `hrdPos` (`hpos`, read by the gate and by the blocked close),
   `hrdDirOkL / S` (`dir_ok_l / s`), `hrdIdL / S` (`real_l / real_s`: the side of the entry and the
   trade a close targets), the four SL / TP expressions (the same floating-point expressions,
   chosen by the real side), `strategy.entry` direction, `strategy.exit` (bracket and trail travel
   with the entry; trail ticks unchanged). Time exit, hybrid exit and the FGD counts are unchanged
   in both. The other changed lines are the title, tooltips and comments.
2. **Independent reference.** `ref_inv.py` equals the kernel trade by trade (side, signal / fill /
   exit candle, exit kind, exit order candle, prices, quantity, P/L, eq_before, SL, TP), and the
   kernel's FGD counts and final equity, on: all 14 cells x direction normal / inverted x filter
   off / on x path tv / mag x cost none / ours, default inputs (224 runs, 683 352 trades), and 12
   cells (charts 5 to 240) x 8 other input sets (Buy Only, Sell Only, blkClose off, SL 0.5 / TP 1,
   fixed quantity without SL / TP, SL 1 / no TP / 20 candles, hybrid off / 3 candles, SL 3 / TP 1.5
   with a fast hybrid exit and 2.5 % risk) x labels normal / reversed x option off / on x tv / mag
   x both costs (3072 runs, 2 623 948 trades, 1 311 960 of them in inverted runs): 0 differences.
   Its summary (26 values per run: trades, net, pf, win, max DD, fair halves and their counts,
   long / short, exit kinds, bars held, exposure, costs, FGD counts) equals the runner's JSON on
   all 14 cells (5824 values). It has no trailing stop: the trail with the option on rests on R2a,
   R2b and R5.
3. **Mutation test** (`mut_pass1.log`, `mut_pass2.log`). 18 mutants, each caught by at least one
   test. 17 of them by the property tests: the
   entry gated on the other side's permission; the gate not mirroring the position; the blocked
   close not mirroring the position; the bracket mirrored about the fill (2 x fill - level); the
   bracket at the % distances from the fill; the trade list reporting the signal's side; the trail
   activation and offset swapped; the normal trade's two levels kept with their roles exchanged;
   the FGD flags in the real frame; Trade Direction swapped for one block only; the option dropped
   when Reverse Trading is on; path mag ignored when inverted; only one order sent on a
   double-signal candle; the trail armed from the signal close; the size taken from the target
   distance; and, re-run, two of the implementer's (blocked close on the wrong id, the flip before
   the gate: same verdicts as in `inv_mutants_hrd.log`). The control (unmutated copy) passes.
   The 18th was caught only by accident: with the alias `inv` pointing at another param, no property
   test (R2 to R5) failed, because they all switch the option on as `simulate(P, {'hrdInv':
   True})`; only R1's `inv=False` runs tripped over it. **Test R7 was added** for that: it switches
   the option on through `run()` and `simulate()`, under both names, and reads the REAL side in the
   public DataFrame and summary; it fails on that mutant, on the wrong-side trade list, on the FGD
   flags in the real frame and on the option dropped under Reverse Trading.
   `ref_inv.py` on its own sees 15 of the 18: not the two trail mutants (it has no trailing stop)
   nor the alias one (it names the option `hrdInv` on the default inputs).
4. **Option off** (`off_check.log`): all 14 cells (7 per pair). 168 saved runs of
   `out/hrd_<PAIR>_<TF>.json` (5040 fields) and 140 saved trade lists (387 756 rows, every column);
   2016 rows of `out/swah_hrd_<PAIR>_<TF>.parquet`, 1008 on path tv and 1008 on path mag (per file
   16 groups x the default row + 8 random settings; 68 544 values): all equal. Of the saved runs a
   third name `hrdInv=False` and a third `inv=False`; half of the sweep rows name `hrdInv=False`.
5. **Runner** (`runner_check.log`). BTC 60 and XAU 240: every field of the 24 entries of each file
   recomputed with `hrd.run()` (816 fields per cell, exact; 12 random ones are printed); the
   runner run again gives the same file. Costs: every `script` entry has no cost (P/L = gross
   P/L); every `ours` trade pays XAU 0.30 x quantity, BTC quantity x (0.02 % x (entry + exit price)
   + 0.20), as the spec says (12 996 trades in the 48 entries, each also checked for gross P/L =
   side x quantity x (exit - entry)). The reference entries are the existing reversed-labels
   runs: the tv ones equal `out/hrd_<PAIR>_<TF>.json` `rev_off_tv / rev_off_ours / rev_on_tv /
   rev_on_ours` (every common field, costs, and the saved trade lists), tv and mag equal the
   default rows of `out/swah_hrd_<PAIR>_<TF>.parquet` (labels rev). The runner also runs on the
   other 12 cells (17 s for all 14, into the scratch directory): its 8 saved-run checks pass in
   every cell, chart "1" mag == tv.
6. **The two cells' numbers.** The 32 table rows above equal the JSON. Filter on, both cells: the
   normal and the inverted run take the same entries, every one on the other side (248 of 248,
   38 of 38), hence equal trade counts and the long / short split exchanged; 212 / 36 of them
   also leave on the same candle at the same price and then the P/L per unit is exactly the
   opposite; the others leave differently where the header says they can (BTC 60: 15 time ->
   stop, 13 stop -> time, 2 target -> stop, 2 stop -> target, ...). Filter off the two runs drift
   apart after such an exit (BTC 60: 619 mirrored entries, 2 only normal, 5 only inverted), each
   extra entry being a signal the other run could not take because its own trade was still open.
   Every inverted stop exit is at or beyond the stop, on the losing side of the signal close, and
   no earlier candle of the trade reaches its stop or target.
   Equal counts with the filter on are not a rule: in the scratch runs BTC 30 has 576 normal and
   575 inverted trades, BTC 240 has 48 and 47.
   With the option on, mag differs from tv only on BTC 30 and BTC 120 (filter off) among the 14
   cells at default inputs.

Not checked here, as before: TradingView itself (no Strategy Tester run of the Update 1 file).
